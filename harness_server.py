#!/usr/bin/env python3
'''WebSocket 서버 — Ink UI와 통신하는 Python 백엔드'''
import asyncio
import json
import os
import sys
import threading
import uuid
from dataclasses import dataclass, field

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


# ── 세션 상태 (룸 단위) ──────────────────────────────────────────
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


# ── 공유 룸 (BB-2 Phase 1) ───────────────────────────────────────
# 같은 room_name으로 접속한 WS들이 하나의 Session을 공유한다.
# 헤더가 없는 솔로 모드는 매 연결마다 고유 UUID 룸을 받아 격리된다.
@dataclass
class Room:
    name: str
    state: Session
    subscribers: set = field(default_factory=set)        # 현재 연결된 ws
    input_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active_input_from: object = None                      # 현재 입력 중인 ws (Phase 2~4에서 사용)


ROOMS: dict[str, Room] = {}


def _get_or_create_room(name: str) -> Room:
    '''같은 name이면 같은 Room 반환 (Session 공유). 없으면 새로 생성.'''
    room = ROOMS.get(name)
    if room is None:
        room = Room(name=name, state=Session())
        ROOMS[name] = room
    return room


def _maybe_drop_room(room: Room) -> None:
    '''subscribers가 비면 ROOMS에서 제거 (메모리 누수 방지).'''
    if not room.subscribers and ROOMS.get(room.name) is room:
        del ROOMS[room.name]


# ── 에이전트 실행 (스레드 → asyncio 브릿지) ──────────────────────
async def run_agent(ws, state: Session, user_input: str, plan_mode: bool = False,
                    context_snippets: str = '',
                    system_override: str | None = None,
                    working_dir_override: str | None = None,
                    ephemeral_profile: dict | None = None):
    '''ephemeral 모드 지원:
    - system_override: None이 아니면 새 세션([{role:system,content:override}])으로 실행
    - working_dir_override: HARNESS_DIR 등 다른 디렉토리에서 실행 (/improve용)
    - ephemeral_profile: 기본은 state.profile 그대로 사용
    state.messages는 ephemeral일 때 갱신하지 않음.'''
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

    # 외부 주입값 우선, 없으면 자체 계산
    snippets = context_snippets or (
        context.search(user_input, state.working_dir) if context.is_indexed(state.working_dir) else ''
    )

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

    # ephemeral 모드: 별도 임시 세션 + 선택적 working_dir 오버라이드
    is_ephemeral = system_override is not None
    if is_ephemeral:
        ephemeral_session = [{'role': 'system', 'content': system_override}]
    run_wd = working_dir_override or state.working_dir
    run_profile = ephemeral_profile or state.profile

    def _run():
        try:
            if is_ephemeral:
                agent.run(
                    user_input,
                    session_messages=ephemeral_session,
                    working_dir=run_wd,
                    profile=run_profile,
                    on_token=on_token,
                    on_tool=on_tool,
                    confirm_write=confirm_write if run_profile.get('confirm_writes', True) else None,
                    confirm_bash=confirm_bash if run_profile.get('confirm_bash', True) else None,
                    hooks=run_profile.get('hooks', {}),
                )
            else:
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
        # harness_core.slash_plan에 위임. async run_agent를 sync wrapper로 감싸
        # executor 스레드에서 dispatch 실행 (이벤트 루프 deadlock 회피).
        loop = asyncio.get_event_loop()

        def _sync_run_agent(user_input, *, plan_mode=False, context_snippets=''):
            fut = asyncio.run_coroutine_threadsafe(
                run_agent(ws, state, user_input, plan_mode=plan_mode,
                          context_snippets=context_snippets),
                loop,
            )
            fut.result()  # 완료까지 블로킹 (이 콜백은 이미 executor 스레드)

        ctx = harness_core.SlashContext(run_agent=_sync_run_agent)
        result = await loop.run_in_executor(
            None,
            lambda: harness_core.dispatch(cmd, _to_core_state(state), ctx),
        )
        if result.level == 'warn':
            # "사용법: /plan <작업 내용>" 같은 안내
            await send(ws, type='error', text=result.notice)
        elif result.level == 'error':
            await send(ws, type='error', text=result.notice)

    elif name == '/cplan':
        # Phase 1만 harness_core에 위임 — slash_cplan이 confirm_execute=None이면
        # 플랜 작성 + state.messages 기록까지만 수행. 실행 여부는 UI가 cplan_confirm
        # 응답 후 별도 /plan 라운드로 처리 (기존 UX 유지).
        loop = asyncio.get_event_loop()

        def _sync_ask_claude(prompt: str) -> str:
            collected: list[str] = []

            def _on_tok(line: str):
                collected.append(line)
                asyncio.run_coroutine_threadsafe(
                    send(ws, type='claude_token', text=line), loop,
                )

            try:
                claude_ask(prompt, on_token=_on_tok)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    send(ws, type='error', text=str(e)), loop,
                )
                return ''
            return ''.join(collected).strip()

        ctx = harness_core.SlashContext(ask_claude=_sync_ask_claude)
        result = await loop.run_in_executor(
            None,
            lambda: harness_core.dispatch(cmd, _to_core_state(state), ctx),
        )
        _apply_core_result(state, result)
        if result.level == 'ok' and 'plan_text' in result.data:
            await send(ws, type='cplan_confirm', task=result.data.get('task', ''))
        elif result.level in ('warn', 'error'):
            await send(ws, type='error', text=result.notice)

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

    elif name in ('/improve', '/learn'):
        # harness_core 위임: slash_improve / slash_learn이 ephemeral 세션으로 agent 실행.
        # sync wrapper가 run_agent를 system_override/wd_override 모드로 호출.
        loop = asyncio.get_event_loop()

        def _sync_ephemeral(user_input, *, system_prompt, working_dir, profile):
            fut = asyncio.run_coroutine_threadsafe(
                run_agent(ws, state, user_input,
                          system_override=system_prompt,
                          working_dir_override=working_dir,
                          ephemeral_profile=profile),
                loop,
            )
            fut.result()

        ctx = harness_core.SlashContext(run_agent_ephemeral=_sync_ephemeral)
        result = await loop.run_in_executor(
            None,
            lambda: harness_core.dispatch(cmd, _to_core_state(state), ctx),
        )
        if name == '/improve':
            await send(ws, type='slash_result', cmd='improve',
                       backup=result.data.get('backup', ''),
                       validation=result.data.get('validation', []))
        else:
            await send(ws, type='slash_result', cmd='learn')
        if result.level in ('warn', 'error') and result.notice:
            await send(ws, type='info', text=result.notice)
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
    # CONCERNS.md §2.3 대응: `token not in VALID_TOKENS` → timing 누설.
    # hmac.compare_digest로 상수시간 비교.
    if VALID_TOKENS:
        import hmac
        token = ws.request.headers.get('x-harness-token', '') or ''
        ok = any(hmac.compare_digest(token, v) for v in VALID_TOKENS)
        if not ok:
            await ws.close(4401, 'Unauthorized')
            return

    await _bump_remote_active(1)
    try:
        await _run_session(ws)
    finally:
        await _bump_remote_active(-1)


async def _run_session(ws):
    # 룸 식별: 헤더 있으면 공유 룸, 없으면 연결 단위 솔로 룸 (UUID).
    # 솔로 모드는 매 연결마다 고유 이름이라 회귀 없음.
    room_header = (ws.request.headers.get('x-harness-room', '') or '').strip()
    room_name = room_header if room_header else f'_solo_{uuid.uuid4().hex}'
    room = _get_or_create_room(room_name)
    room.subscribers.add(ws)
    state = room.state  # 같은 룸의 모든 ws가 같은 Session 공유

    try:
        # 초기 상태 전송 (room은 신규 필드 — 모르는 UI는 무시함)
        await send_state(ws, state)
        await send(ws, type='ready', room=room_name)

        # 자동 인덱싱 — 룸의 working_dir 기준. 두 번째 join은 is_indexed=True로 자연 스킵.
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
    finally:
        room.subscribers.discard(ws)
        _maybe_drop_room(room)


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
