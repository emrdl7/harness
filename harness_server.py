#!/usr/bin/env python3
'''WebSocket 서버 — Ink UI와 통신하는 Python 백엔드'''
import asyncio
import json
import os
import sys
import threading

import websockets

import agent
import profile as prof
import context
import harness_core
import session as sess
from session.logger import read_recent
from session.analyzer import summarize_session, build_learn_prompt
from tools.improve import backup_sources, validate_python, read_sources, list_backups, restore_backup, HARNESS_DIR
import evolution
from tools.claude_cli import ask as claude_ask, is_available as claude_available
from session.compactor import needs_compaction, compact

PORT         = int(os.environ.get('HARNESS_PORT', '7891'))
BIND         = os.environ.get('HARNESS_BIND', '127.0.0.1')  # 외부 노출은 HARNESS_BIND=0.0.0.0 명시 필요
VALID_TOKENS = set(filter(None, os.environ.get('HARNESS_TOKENS', '').split(',')))

# Ollama는 동시 추론 불가 — 요청 1개씩 처리 + 대기열 가시화
_ollama_lock = asyncio.Semaphore(1)
_ollama_queue_count = 0


async def _enter_ollama_queue(ws) -> bool:
    '''큐 진입 시 카운터 증가. 앞에 대기자가 있으면 position을 알림. 대기했는지 반환.'''
    global _ollama_queue_count
    _ollama_queue_count += 1
    pos = _ollama_queue_count
    if pos > 1:
        await send(ws, type='queue', position=pos - 1)
        return True
    return False


def _leave_ollama_queue():
    global _ollama_queue_count
    if _ollama_queue_count > 0:
        _ollama_queue_count -= 1

# 원격 연결 중에는 idle_runner의 자가수정 차단 (파일 기반 신호)
_REMOTE_ACTIVE_PATH = os.path.expanduser('~/.harness/evolution/.remote_active')
_remote_count = 0
_remote_lock = asyncio.Lock()


async def _bump_remote_active(delta: int):
    global _remote_count
    async with _remote_lock:
        _remote_count += delta
        if _remote_count < 0:
            _remote_count = 0
        os.makedirs(os.path.dirname(_REMOTE_ACTIVE_PATH), exist_ok=True)
        if _remote_count > 0:
            with open(_REMOTE_ACTIVE_PATH, 'w') as f:
                f.write(str(_remote_count))
        elif os.path.exists(_REMOTE_ACTIVE_PATH):
            try:
                os.unlink(_REMOTE_ACTIVE_PATH)
            except OSError:
                pass


# ── 메시지 전송 헬퍼 ──────────────────────────────────────────────
async def send(ws, **kwargs):
    try:
        await ws.send(json.dumps(kwargs, ensure_ascii=False))
    except Exception:
        pass


# ── 세션 상태 (연결 단위) ─────────────────────────────────────────
class Session:
    def __init__(self):
        self.working_dir = os.environ.get('HARNESS_CWD') or os.getcwd()
        self.profile = prof.load(self.working_dir)
        # 원격 사용자는 무조건 fs 샌드박스 + 모든 write/bash 확인 필수
        self.profile['fs_sandbox'] = True
        self.profile['confirm_writes'] = True
        self.profile['confirm_bash'] = True
        self.messages: list = []
        self.undo_count: int = 0
        self._confirm_event: asyncio.Event | None = None
        self._confirm_result: bool = False
        self._confirm_bash_event: asyncio.Event | None = None
        self._confirm_bash_result: bool = False
        self.compact_count: int = 0


# ── 에이전트 실행 (스레드 → asyncio 브릿지) ──────────────────────
async def run_agent(ws, state: Session, user_input: str, plan_mode: bool = False):
    loop = asyncio.get_event_loop()

    def on_token(token: str):
        asyncio.run_coroutine_threadsafe(
            send(ws, type='token', text=token), loop
        )

    def on_tool(name: str, args: dict, result):
        if result is None:
            asyncio.run_coroutine_threadsafe(
                send(ws, type='tool_start', name=name, args=args), loop
            )
        else:
            asyncio.run_coroutine_threadsafe(
                send(ws, type='tool_end', name=name, result=result), loop
            )

    def confirm_write(path: str, content: str | None = None) -> bool:
        event = asyncio.Event()
        state._confirm_event = event
        state._confirm_result = False
        asyncio.run_coroutine_threadsafe(
            send(ws, type='confirm_write', path=path), loop
        )
        # 최대 60초 대기 (스레드에서 asyncio Event를 기다리는 우회)
        future = asyncio.run_coroutine_threadsafe(
            asyncio.wait_for(event.wait(), timeout=60), loop
        )
        try:
            future.result(timeout=61)
        except Exception:
            pass
        return state._confirm_result

    def confirm_bash(command: str) -> bool:
        event = asyncio.Event()
        state._confirm_bash_event = event
        state._confirm_bash_result = False
        asyncio.run_coroutine_threadsafe(
            send(ws, type='confirm_bash', command=command), loop
        )
        future = asyncio.run_coroutine_threadsafe(
            asyncio.wait_for(event.wait(), timeout=60), loop
        )
        try:
            future.result(timeout=61)
        except Exception:
            pass
        return state._confirm_bash_result

    snippets = context.search(user_input, state.working_dir) if context.is_indexed(state.working_dir) else ''

    # 세션이 너무 길면 요약 압축
    if needs_compaction(state.messages):
        await send(ws, type='info', text='세션 압축 중...')
        new_msgs, dropped = await asyncio.get_event_loop().run_in_executor(
            None, compact, state.messages
        )
        state.messages = new_msgs
        state.compact_count += 1
        await send(ws, type='info', text=f'압축 완료 (메시지 {dropped}개 요약)')

    await send(ws, type='agent_start')

    def _run():
        try:
            _, state.messages = agent.run(
                user_input,
                session_messages=state.messages,
                working_dir=state.working_dir,
                profile=state.profile,
                context_snippets=snippets if isinstance(snippets, str) else '',
                plan_mode=plan_mode,
                on_token=on_token,
                on_tool=on_tool,
                confirm_write=confirm_write if state.profile.get('confirm_writes', True) else None,
                confirm_bash=confirm_bash if state.profile.get('confirm_bash', True) else None,
                hooks=state.profile.get('hooks', {}),
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, type='error', text=str(e)), loop
            )

    was_queued = await _enter_ollama_queue(ws)
    try:
        async with _ollama_lock:
            if was_queued:
                await send(ws, type='queue_ready')
            await asyncio.get_event_loop().run_in_executor(None, _run)
    finally:
        _leave_ollama_queue()
    await send(ws, type='agent_end')


# ── Claude CLI 실행 ───────────────────────────────────────────────
async def run_claude(ws, state: Session, query: str, add_to_session: bool = False):
    if not claude_available():
        await send(ws, type='error', text='claude CLI를 찾을 수 없습니다')
        return

    loop = asyncio.get_event_loop()
    collected = []

    await send(ws, type='claude_start')

    def _run():
        def _tok(line):
            collected.append(line)
            asyncio.run_coroutine_threadsafe(
                send(ws, type='claude_token', text=line), loop
            )
        try:
            claude_ask(query, on_token=_tok)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                send(ws, type='error', text=str(e)), loop
            )

    await asyncio.get_event_loop().run_in_executor(None, _run)

    if add_to_session and collected:
        response = ''.join(collected).strip()
        state.messages.append({'role': 'user', 'content': f'[Claude에게 질문]\n{query}'})
        state.messages.append({'role': 'assistant', 'content': f'[Claude 답변]\n{response}'})

    await send(ws, type='claude_end')


def _to_core_state(state: 'Session') -> harness_core.SlashState:
    '''Session → SlashState (코어 입력 형식).'''
    return harness_core.SlashState(
        messages=state.messages,
        working_dir=state.working_dir,
        profile=state.profile,
        undo_count=state.undo_count,
    )


def _apply_core_result(state: 'Session', result: harness_core.SlashResult) -> None:
    '''SlashResult → Session in-place 갱신.'''
    state.messages = result.state.messages
    state.working_dir = result.state.working_dir
    state.profile = result.state.profile
    state.undo_count = result.state.undo_count


# ── 슬래시 명령어 처리 ────────────────────────────────────────────
async def handle_slash(ws, state: Session, cmd: str):
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0]

    if name == '/clear':
        # 상태 변경은 harness_core에 위임. UI 호환 메시지는 그대로 유지.
        result = harness_core.dispatch(cmd, _to_core_state(state))
        _apply_core_result(state, result)
        await send(ws, type='slash_result', cmd='clear')

    elif name == '/undo':
        before = len(state.messages)
        result = harness_core.dispatch(cmd, _to_core_state(state))
        _apply_core_result(state, result)
        await send(ws, type='slash_result', cmd='undo', ok=len(state.messages) < before)

    elif name == '/plan':
        query = parts[1] if len(parts) > 1 else ''
        if query:
            await run_agent(ws, state, query, plan_mode=True)
        else:
            await send(ws, type='error', text='사용법: /plan <작업>')

    elif name == '/cplan':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            await send(ws, type='error', text='사용법: /cplan <작업>')
            return
        if not claude_available():
            await send(ws, type='error', text='claude CLI를 찾을 수 없습니다')
            return
        from main import CPLAN_PROMPT_TMPL
        prompt = CPLAN_PROMPT_TMPL.format(task=query, working_dir=state.working_dir)
        await run_claude(ws, state, prompt)
        await send(ws, type='cplan_confirm', task=query)  # UI에서 실행 여부 물어봄

    elif name == '/index':
        await send(ws, type='info', text='인덱싱 중...')
        loop = asyncio.get_event_loop()

        def _run_dispatch():
            return harness_core.dispatch(cmd, _to_core_state(state))

        result = await loop.run_in_executor(None, _run_dispatch)
        await send(ws, type='slash_result', cmd='index',
                   indexed=result.data.get('indexed', 0),
                   skipped=result.data.get('skipped', 0))

    elif name == '/cd':
        if len(parts) < 2:
            await send(ws, type='error', text='사용법: /cd <경로>')
        else:
            result = harness_core.dispatch(cmd, _to_core_state(state))
            if result.level == 'error':
                await send(ws, type='error', text=result.notice)
            else:
                _apply_core_result(state, result)
                await send(ws, type='slash_result', cmd='cd', working_dir=state.working_dir)

    elif name == '/save':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        _apply_core_result(state, result)
        await send(ws, type='slash_result', cmd='save', filename=result.data['filename'])

    elif name == '/resume':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        if result.level == 'ok':
            _apply_core_result(state, result)
            await send(ws, type='slash_result', cmd='resume', turns=result.data['turns'])
        else:
            await send(ws, type='slash_result', cmd='resume', turns=0, ok=False)

    elif name == '/sessions':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        await send(ws, type='slash_result', cmd='sessions',
                   sessions=result.data.get('sessions', [])[:10])

    elif name == '/files':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        await send(ws, type='slash_result', cmd='files',
                   tree=result.data.get('tree', {}))

    elif name == '/init':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        if result.level == 'ok':
            path = os.path.join(state.working_dir, '.harness.toml')
            await send(ws, type='slash_result', cmd='init', path=path)
        else:
            # 이미 존재 시 warn — UI는 error 메시지로 매핑
            await send(ws, type='error', text=result.notice)

    elif name == '/improve':
        await send(ws, type='info', text='백업 생성 중...')
        backup_path = backup_sources()
        await send(ws, type='info', text=f'백업: {backup_path}')
        logs = read_recent(days=7)
        sources = read_sources()
        improve_input = f'실패 로그:\n{logs}\n\n소스:\n{sources[:12000]}\n\n개선하세요.'
        improve_session = [{'role': 'system', 'content': '하네스 자기 개선 전문가. 수정 후 py_compile 검증.'}]

        loop = asyncio.get_event_loop()

        def on_tool(name, args, result):
            pass

        async def _run_improve():
            await asyncio.get_event_loop().run_in_executor(None, lambda: agent.run(
                improve_input,
                session_messages=improve_session,
                working_dir=HARNESS_DIR,
                profile=state.profile,
                on_token=lambda t: None,
                on_tool=on_tool,
                confirm_write=None,
            ))

        await _run_improve()
        await send(ws, type='slash_result', cmd='improve')

    elif name == '/learn':
        if state.messages:
            summary = summarize_session(state.messages)
            learn_prompt = build_learn_prompt(
                summary, state.profile.get('global_doc', ''),
                state.profile.get('project_doc', ''), state.working_dir
            )
            learn_session = [{'role': 'system', 'content': '하네스 자기학습. HARNESS.md만 갱신.'}]
            await asyncio.get_event_loop().run_in_executor(None, lambda: agent.run(
                learn_prompt, session_messages=learn_session,
                working_dir=state.working_dir, profile={},
                on_token=lambda t: None, on_tool=lambda *a: None, confirm_write=None,
            ))
        await send(ws, type='slash_result', cmd='learn')

    elif name == '/help':
        await send(ws, type='slash_result', cmd='help')

    elif name in ('/quit', '/exit', '/q'):
        await send(ws, type='quit')

    else:
        await send(ws, type='error', text=f'알 수 없는 명령어: {name}')

    # 매 슬래시 명령 후 상태 동기화
    await send_state(ws, state)


# ── 상태 전송 ─────────────────────────────────────────────────────
async def send_state(ws, state: Session):
    turns = len([m for m in state.messages if m['role'] == 'user'])
    await send(
        ws,
        type='state',
        working_dir=state.working_dir,
        turns=turns,
        indexed=context.is_indexed(state.working_dir),
        claude_available=claude_available(),
        compact_count=state.compact_count,
    )


# ── 파일 트리 빌드 ────────────────────────────────────────────────
# ── 메인 핸들러 ───────────────────────────────────────────────────
async def handler(ws):
    # 토큰 인증 (websockets 14+: ws.request_headers → ws.request.headers)
    if VALID_TOKENS:
        token = ws.request.headers.get('x-harness-token', '')
        if token not in VALID_TOKENS:
            await ws.close(4401, 'Unauthorized')
            return

    await _bump_remote_active(1)
    try:
        await _run_session(ws)
    finally:
        await _bump_remote_active(-1)


async def _run_session(ws):
    state = Session()

    # 초기 상태 전송
    await send_state(ws, state)
    await send(ws, type='ready')

    # 자동 인덱싱
    if state.profile.get('auto_index') and not context.is_indexed(state.working_dir):
        py_count = sum(1 for _, _, fs in os.walk(state.working_dir) for f in fs if f.endswith('.py'))
        if py_count > 3:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: context.index_directory(state.working_dir))
            await send(ws, type='info', text=f'인덱싱 완료 {result["indexed"]}개 청크')
            await send_state(ws, state)

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            t = msg.get('type')

            if t == 'input':
                text = msg.get('text', '').strip()
                if not text:
                    continue
                if text.startswith('/'):
                    await handle_slash(ws, state, text)
                elif text.startswith('@claude '):
                    await run_claude(ws, state, text[8:].strip(), add_to_session=True)
                else:
                    await run_agent(ws, state, text)
                    await send_state(ws, state)

            elif t == 'confirm_write_response':
                state._confirm_result = msg.get('result', False)
                if state._confirm_event:
                    state._confirm_event.set()

            elif t == 'confirm_bash_response':
                state._confirm_bash_result = msg.get('result', False)
                if state._confirm_bash_event:
                    state._confirm_bash_event.set()

            elif t == 'cplan_execute':
                task = msg.get('task', '')
                if task:
                    execute_prompt = (
                        f'위에서 Claude가 작성한 플랜을 그대로 실행해줘.\n'
                        f'각 단계를 순서대로 처리하고 도구를 사용해.\n\n작업: {task}'
                    )
                    await run_agent(ws, state, execute_prompt)
                    await send_state(ws, state)

            elif t == 'ping':
                await send(ws, type='pong')

    except websockets.exceptions.ConnectionClosed:
        pass


# ── 진입점 ────────────────────────────────────────────────────────
async def main():
    import logging
    logging.getLogger('websockets').setLevel(logging.CRITICAL)

    if not VALID_TOKENS:
        print('ERROR: HARNESS_TOKENS 환경변수가 비어있습니다.', file=sys.stderr)
        print('  안전한 토큰 생성: export HARNESS_TOKENS=$(openssl rand -hex 32)', file=sys.stderr)
        print('  여러 토큰은 쉼표로 구분: HARNESS_TOKENS=token1,token2', file=sys.stderr)
        print('  인증 없는 서버 기동을 거부합니다.', file=sys.stderr)
        sys.exit(1)

    # 스타트업 시 이전 실행의 잔재 파일 정리
    if os.path.exists(_REMOTE_ACTIVE_PATH):
        try:
            os.unlink(_REMOTE_ACTIVE_PATH)
        except OSError:
            pass

    print(f'harness server  ws://{BIND}:{PORT}  (토큰 인증 {len(VALID_TOKENS)}개)', flush=True)
    async with websockets.serve(handler, BIND, PORT):
        await asyncio.Future()  # 영원히 실행


if __name__ == '__main__':
    asyncio.run(main())
