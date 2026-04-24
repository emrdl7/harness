#!/usr/bin/env python3
'''WebSocket 서버 — Ink UI와 통신하는 Python 백엔드'''
import asyncio
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

import websockets
from websockets.exceptions import ConnectionClosed

import agent
import profile as prof
import context
import harness_core
import session as sess
import session.store as session_store
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


async def broadcast(room: 'Room', **kwargs):
    '''룸의 모든 subscribers에 같은 메시지를 송신.

    송신 중 깨진 ws는 dead 리스트에 모았다가 마지막에 일괄 discard
    (set 변경 중 순회 회피). subscribers가 비어도 안전.

    PEXT-03: 매 호출마다 event_id를 monotonic하게 부여하고 ring buffer에 기록.
    60초 초과 항목은 eager cleanup.
    '''
    # PEXT-03: event_id 부여 + ring buffer 기록
    room.event_counter += 1
    kwargs['event_id'] = room.event_counter
    now = time.monotonic()
    room.event_buffer.append((room.event_counter, now, dict(kwargs)))
    # TTL 60초 초과 항목 eager cleanup
    while room.event_buffer and (now - room.event_buffer[0][1]) > 60:
        room.event_buffer.popleft()

    if not room.subscribers:
        return
    payload = json.dumps(kwargs, ensure_ascii=False)
    dead = []
    for s in list(room.subscribers):
        try:
            await s.send(payload)
        except Exception:
            dead.append(s)
    for s in dead:
        room.subscribers.discard(s)


def _token_hash(token: str) -> str:
    '''토큰의 SHA-256 앞 8자 hex — Presence 식별자 (개인정보 노출 없음).

    B4: room_member_joined 에서 user 필드로 사용.
    SHA-256 preimage는 실용적으로 역산 불가 — 토큰 원문 미노출.
    '''
    return hashlib.sha256(token.encode()).hexdigest()[:8]


def _read_existing_file(path: str) -> str | None:
    '''PEXT-02: confirm_write 의 old_content 제공용 파일 읽기 헬퍼.
    파일이 없거나 읽기 실패 시 None 반환 — 신규 파일 쓰기 시 diff 없음.
    '''
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None


async def _broadcast_agent_start(room: 'Room', requester_ws) -> None:
    '''PEXT-01: agent_start 는 per-subscriber — from_self 플래그가 구독자마다 다름.
    broadcast() 와 동일한 dead 처리 패턴 사용.
    참고: event_id 부여는 broadcast() 경유가 아니므로 별도 counter 증가 없음
         (agent_start 는 from_self 로 인해 공통 payload 가 불가능).
    '''
    dead = []
    for s in list(room.subscribers):
        try:
            # send() 헬퍼는 예외를 삼키므로 dead 감지를 위해 직접 ws.send() 호출
            payload = json.dumps(
                {'type': 'agent_start', 'from_self': (s is requester_ws)},
                ensure_ascii=False,
            )
            await s.send(payload)
        except Exception:
            dead.append(s)
    for s in dead:
        room.subscribers.discard(s)


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


# ── 공유 룸 (BB-2 Phase 1+2.5) ───────────────────────────────────
# 같은 room_name으로 접속한 WS들이 하나의 Session을 공유한다.
# 헤더가 없는 솔로 모드는 매 연결마다 고유 UUID 룸을 받아 격리된다.
@dataclass
class Room:
    name: str
    state: Session
    subscribers: set = field(default_factory=set)        # 현재 연결된 ws
    # busy: 단일 스레드 asyncio라 await 없는 체크-set은 race-free.
    # _dispatch_loop 진입 시 set, _handle_input의 finally에서 clear.
    busy: bool = False
    active_input_from: object = None                      # 현재 입력 중인 ws (DQ2 confirm 격리)
    # 진행 중인 _handle_input task의 강한 참조 유지 (asyncio.create_task GC 회피).
    # done 콜백으로 자동 discard.
    input_tasks: set = field(default_factory=set)
    # PEXT-03: monotonic event_id + 60초 ring buffer (maxlen=10000 으로 메모리 고갈 방지)
    event_counter: int = field(default=0)
    event_buffer: deque = field(default_factory=lambda: deque(maxlen=10000))
    # PEXT-05 (B2): executor 스레드 조기 종료 플래그 — cancel 수신 시 True, finally에서 False 리셋
    _cancel_requested: bool = field(default=False)


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
async def run_agent(ws, room: 'Room', user_input: str, plan_mode: bool = False,
                    context_snippets: str = '',
                    system_override: str | None = None,
                    working_dir_override: str | None = None,
                    ephemeral_profile: dict | None = None):
    '''ephemeral 모드 지원:
    - system_override: None이 아니면 새 세션([{role:system,content:override}])으로 실행
    - working_dir_override: HARNESS_DIR 등 다른 디렉토리에서 실행 (/improve용)
    - ephemeral_profile: 기본은 state.profile 그대로 사용
    state.messages는 ephemeral일 때 갱신하지 않음.

    출력은 룸 전체에 broadcast (관전자도 토큰/툴 결과 봐야 함).
    confirm_*은 ws에만 송신 (DQ2: 입력 주체만 승인).
    queue 알림은 개인 ws (룸 단위 큐 아님).
    '''
    state = room.state
    loop = asyncio.get_event_loop()

    def on_token(token: str):
        # B2: _cancel_requested 플래그 체크 — executor 스레드 조기 종료
        # GIL로 bool 읽기는 안전. return으로 스트리밍 중단 (이미 broadcast된 토큰은 취소 불가)
        if room._cancel_requested:
            return
        asyncio.run_coroutine_threadsafe(
            broadcast(room, type='token', text=token), loop
        )

    def on_tool(name: str, args: dict, result):
        if result is None:
            asyncio.run_coroutine_threadsafe(
                broadcast(room, type='tool_start', name=name, args=args), loop
            )
        else:
            asyncio.run_coroutine_threadsafe(
                broadcast(room, type='tool_end', name=name, result=result), loop
            )

    def confirm_write(path: str, content: str | None = None) -> bool:
        event = asyncio.Event()
        state._confirm_event = event
        state._confirm_result = False
        asyncio.run_coroutine_threadsafe(
            send(ws, type='confirm_write', path=path,
                 old_content=_read_existing_file(path)), loop  # PEXT-02
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
        await broadcast(room, type='info', text='세션 압축 중...')
        new_msgs, dropped = await asyncio.get_event_loop().run_in_executor(
            None, compact, state.messages
        )
        state.messages = new_msgs
        state.compact_count += 1
        await broadcast(room, type='info', text=f'압축 완료 (메시지 {dropped}개 요약)')

    await _broadcast_agent_start(room, ws)  # PEXT-01: per-subscriber from_self 분기

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
                broadcast(room, type='error', text=str(e)), loop
            )

    was_queued = await _enter_ollama_queue(ws)
    try:
        async with _ollama_lock:
            if was_queued:
                await send(ws, type='queue_ready')
            await asyncio.get_event_loop().run_in_executor(None, _run)
    finally:
        _leave_ollama_queue()
    await broadcast(room, type='agent_end')


# ── Claude CLI 실행 ───────────────────────────────────────────────
async def run_claude(ws, room: 'Room', query: str, add_to_session: bool = False):
    '''Claude CLI 호출. 출력은 룸 전체 broadcast (관전자도 답변 봐야).
    입력 자체는 ws에서 왔지만 룸 컨텍스트라 모두 공유.'''
    state = room.state
    if not claude_available():
        await broadcast(room, type='error', text='claude CLI를 찾을 수 없습니다')
        return

    loop = asyncio.get_event_loop()
    collected = []

    await broadcast(room, type='claude_start')

    def _run():
        def _tok(line):
            collected.append(line)
            asyncio.run_coroutine_threadsafe(
                broadcast(room, type='claude_token', text=line), loop
            )
        try:
            claude_ask(query, on_token=_tok)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                broadcast(room, type='error', text=str(e)), loop
            )

    await asyncio.get_event_loop().run_in_executor(None, _run)

    if add_to_session and collected:
        response = ''.join(collected).strip()
        state.messages.append({'role': 'user', 'content': f'[Claude에게 질문]\n{query}'})
        state.messages.append({'role': 'assistant', 'content': f'[Claude 답변]\n{response}'})

    await broadcast(room, type='claude_end')


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
async def handle_slash(ws, room: 'Room', cmd: str):
    '''슬래시 처리 — 상태 변경은 룸 전체 broadcast.

    - slash_result/info/error/agent 출력: broadcast
    - help 표시·quit 신호: 입력자 ws만 (개인적 응답)
    '''
    state = room.state
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0]

    if name == '/clear':
        # 상태 변경은 harness_core에 위임. UI 호환 메시지는 그대로 유지.
        result = harness_core.dispatch(cmd, _to_core_state(state))
        _apply_core_result(state, result)
        await broadcast(room, type='slash_result', cmd='clear')

    elif name == '/undo':
        before = len(state.messages)
        result = harness_core.dispatch(cmd, _to_core_state(state))
        _apply_core_result(state, result)
        await broadcast(room, type='slash_result', cmd='undo', ok=len(state.messages) < before)

    elif name == '/plan':
        # harness_core.slash_plan에 위임. async run_agent를 sync wrapper로 감싸
        # executor 스레드에서 dispatch 실행 (이벤트 루프 deadlock 회피).
        loop = asyncio.get_event_loop()

        def _sync_run_agent(user_input, *, plan_mode=False, context_snippets=''):
            fut = asyncio.run_coroutine_threadsafe(
                run_agent(ws, room, user_input, plan_mode=plan_mode,
                          context_snippets=context_snippets),
                loop,
            )
            fut.result()  # 완료까지 블로킹 (이 콜백은 이미 executor 스레드)

        ctx = harness_core.SlashContext(run_agent=_sync_run_agent)
        result = await loop.run_in_executor(
            None,
            lambda: harness_core.dispatch(cmd, _to_core_state(state), ctx),
        )
        if result.level in ('warn', 'error'):
            # "사용법: /plan <작업 내용>" 같은 안내
            await broadcast(room, type='error', text=result.notice)

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
                    broadcast(room, type='claude_token', text=line), loop,
                )

            try:
                claude_ask(prompt, on_token=_on_tok)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    broadcast(room, type='error', text=str(e)), loop,
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
            # cplan_confirm은 입력자에게만 — 승인 권한은 입력 주체(DQ2)
            await send(ws, type='cplan_confirm', task=result.data.get('task', ''))
        elif result.level in ('warn', 'error'):
            await broadcast(room, type='error', text=result.notice)

    elif name == '/index':
        await broadcast(room, type='info', text='인덱싱 중...')
        loop = asyncio.get_event_loop()

        def _run_dispatch():
            return harness_core.dispatch(cmd, _to_core_state(state))

        result = await loop.run_in_executor(None, _run_dispatch)
        await broadcast(room, type='slash_result', cmd='index',
                        indexed=result.data.get('indexed', 0),
                        skipped=result.data.get('skipped', 0))

    elif name == '/cd':
        if len(parts) < 2:
            await send(ws, type='error', text='사용법: /cd <경로>')
        else:
            result = harness_core.dispatch(cmd, _to_core_state(state))
            if result.level == 'error':
                await broadcast(room, type='error', text=result.notice)
            else:
                _apply_core_result(state, result)
                await broadcast(room, type='slash_result', cmd='cd', working_dir=state.working_dir)

    elif name == '/save':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        _apply_core_result(state, result)
        await broadcast(room, type='slash_result', cmd='save', filename=result.data['filename'])

    elif name == '/resume':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        if result.level == 'ok':
            _apply_core_result(state, result)
            await broadcast(room, type='slash_result', cmd='resume', turns=result.data['turns'])
        else:
            await broadcast(room, type='slash_result', cmd='resume', turns=0, ok=False)

    elif name == '/sessions':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        # 세션 목록 조회는 입력자에게만 — 룸 동기화 대상 아님
        await send(ws, type='slash_result', cmd='sessions',
                   sessions=result.data.get('sessions', [])[:10])

    elif name == '/files':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        # 파일 트리는 룸 working_dir이라 모두에게 의미 있음
        await broadcast(room, type='slash_result', cmd='files',
                        tree=result.data.get('tree', {}))

    elif name == '/init':
        result = harness_core.dispatch(cmd, _to_core_state(state))
        if result.level == 'ok':
            path = os.path.join(state.working_dir, '.harness.toml')
            await broadcast(room, type='slash_result', cmd='init', path=path)
        else:
            # 이미 존재 시 warn — UI는 error 메시지로 매핑
            await broadcast(room, type='error', text=result.notice)

    elif name in ('/improve', '/learn'):
        # harness_core 위임: slash_improve / slash_learn이 ephemeral 세션으로 agent 실행.
        # sync wrapper가 run_agent를 system_override/wd_override 모드로 호출.
        loop = asyncio.get_event_loop()

        def _sync_ephemeral(user_input, *, system_prompt, working_dir, profile):
            fut = asyncio.run_coroutine_threadsafe(
                run_agent(ws, room, user_input,
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
            await broadcast(room, type='slash_result', cmd='improve',
                            backup=result.data.get('backup', ''),
                            validation=result.data.get('validation', []))
        else:
            await broadcast(room, type='slash_result', cmd='learn')
        if result.level in ('warn', 'error') and result.notice:
            await broadcast(room, type='info', text=result.notice)
        await broadcast(room, type='slash_result', cmd='learn')

    elif name == '/help':
        # 도움말은 개인 요청 — 입력자에게만
        await send(ws, type='slash_result', cmd='help')

    elif name == '/who':
        # 룸 subscribers 조회 — 카운트 + busy + active 마커.
        # core 등록 X (server-only): subscribers는 server-side에만 존재.
        # 식별자는 익명(active 여부만 표시) — IP 노출 회피.
        members = [
            {'self': s is ws, 'active': s is room.active_input_from}
            for s in room.subscribers
        ]
        await send(ws, type='slash_result', cmd='who',
                   room=room.name,
                   shared=not room.name.startswith('_solo_'),
                   busy=room.busy,
                   members=members,
                   count=len(members))

    elif name in ('/quit', '/exit', '/q'):
        # 본인 종료 신호 — 다른 subscriber를 쫓아내지 않음
        await send(ws, type='quit')

    else:
        await send(ws, type='error', text=f'알 수 없는 명령어: {name}')

    # 매 슬래시 후 룸 전체 상태 동기화
    await broadcast_state(room)


# ── 상태 전송 ─────────────────────────────────────────────────────
def _state_payload(state: Session) -> dict:
    turns = len([m for m in state.messages if m['role'] == 'user'])
    model = os.environ.get('HARNESS_MODEL', 'qwen3-coder:30b')
    return dict(
        type='state',
        working_dir=state.working_dir,
        model=model,
        turns=turns,
        indexed=context.is_indexed(state.working_dir),
        claude_available=claude_available(),
        compact_count=state.compact_count,
    )


async def send_state(ws, state: Session):
    '''개인 ws에 state 송신 — 룸 join 직후처럼 본인에게만 보낼 때 사용.'''
    await send(ws, **_state_payload(state))


async def broadcast_state(room: 'Room'):
    '''룸 전체에 state 송신 — 슬래시/agent 후 모두 동기화.'''
    await broadcast(room, **_state_payload(room.state))


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


async def _reader_loop(ws, queue: asyncio.Queue):
    '''ws에서 raw를 받아 JSON 디코드 후 queue에 put. 종료 시 None 신호.

    dispatch_loop가 input 처리에 막혀도 confirm_*_response 같은 후속 메시지를
    계속 큐잉할 수 있게 하는 핵심 — Phase 2.5 deadlock 회피.
    '''
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await queue.put(msg)
    except ConnectionClosed:
        pass
    finally:
        await queue.put(None)


def _spawn_input_task(room: 'Room', coro):
    '''_handle_input task 생성 + room.input_tasks 강한 참조 유지.

    asyncio.create_task만으로는 GC될 위험 — 명시적으로 set에 저장하고
    done 콜백으로 자동 discard.

    PEXT-05 (B2): task가 시작 전에 cancel()되면 코루틴이 한 번도 실행되지 않아
    _handle_input finally 블록이 실행되지 않는다. done callback에서 cancelled
    상태를 감지해 busy/active_input_from/_cancel_requested를 안전하게 정리.
    '''
    task = asyncio.create_task(coro)
    room.input_tasks.add(task)

    def _on_done(t):
        # set에서 제거
        room.input_tasks.discard(t)
        # task가 start 전에 cancel된 경우 코루틴 finally가 실행되지 않으므로
        # 여기서 busy/active_input_from/_cancel_requested를 강제 정리
        if t.cancelled():
            room.busy = False
            room.active_input_from = None
            room._cancel_requested = False

    task.add_done_callback(_on_done)
    return task


async def _handle_input(ws, room: 'Room', text: str):
    '''스폰된 input 처리 — busy/active_input_from clear는 finally에서만.

    busy/active_input_from의 set은 _dispatch_loop에서 atomic하게 끝낸 후
    이 함수를 spawn한다 (race 회피).
    '''
    try:
        if text.startswith('/'):
            await handle_slash(ws, room, text)
        elif text.startswith('@claude '):
            await run_claude(ws, room, text[8:].strip(), add_to_session=True)
        else:
            await run_agent(ws, room, text)
            await broadcast_state(room)
    except asyncio.CancelledError:
        # PEXT-05: 정상 취소 경로 — busy/active_input_from/cancel_flag는 finally에서 정리
        pass
    except Exception as e:
        await broadcast(room, type='error', text=f'입력 처리 오류: {e}')
    finally:
        room.busy = False
        room.active_input_from = None
        room._cancel_requested = False  # B2: 다음 실행을 위해 리셋


async def _handle_cplan_execute(ws, room: 'Room', task: str):
    '''cplan 승인 후 실행 — _handle_input과 동일한 busy 사이클을 따른다.'''
    try:
        execute_prompt = (
            f'위에서 Claude가 작성한 플랜을 그대로 실행해줘.\n'
            f'각 단계를 순서대로 처리하고 도구를 사용해.\n\n작업: {task}'
        )
        await run_agent(ws, room, execute_prompt)
        await broadcast_state(room)
    except Exception as e:
        await broadcast(room, type='error', text=f'cplan 실행 오류: {e}')
    finally:
        room.busy = False
        room.active_input_from = None


async def _dispatch_loop(ws, room: 'Room', queue: asyncio.Queue):
    '''queue에서 메시지 받아 dispatch. input/cplan_execute는 spawn해서
    dispatch_loop가 confirm_*_response 같은 후속 메시지를 즉시 처리할 수 있도록.

    busy 체크/set/spawn은 await 없는 동기 블록이라 race-free
    (단일 스레드 asyncio + 다른 코루틴 양보 시점 없음).
    '''
    state = room.state
    while True:
        msg = await queue.get()
        if msg is None:
            return
        t = msg.get('type')

        if t == 'input':
            text = msg.get('text', '').strip()
            if not text:
                continue
            if room.busy:
                # DQ3: 동시 입력 거부 + 룸 전체에 알림
                await broadcast(room, type='room_busy')
                continue
            room.busy = True
            room.active_input_from = ws
            _spawn_input_task(room, _handle_input(ws, room, text))

        elif t == 'cplan_execute':
            task_text = msg.get('task', '')
            if not task_text:
                continue
            if room.busy:
                await broadcast(room, type='room_busy')
                continue
            room.busy = True
            room.active_input_from = ws
            _spawn_input_task(room, _handle_cplan_execute(ws, room, task_text))

        elif t == 'confirm_write_response':
            # DQ2: 입력 주체(active_input_from) ws만 confirm 가능.
            # 다른 ws의 응답은 무시 — 같은 룸의 관전자가 위조해도 차단.
            if ws is not room.active_input_from:
                continue
            state._confirm_result = msg.get('accept', msg.get('result', False))
            if state._confirm_event:
                state._confirm_event.set()

        elif t == 'confirm_bash_response':
            if ws is not room.active_input_from:
                continue
            state._confirm_bash_result = msg.get('accept', msg.get('result', False))
            if state._confirm_bash_event:
                state._confirm_bash_event.set()

        elif t == 'cancel':
            # PEXT-05: 입력 주체(active_input_from)만 취소 가능 — confirm_write_response와 동일한 DQ2 가드 (T-03-02-02)
            if ws is not room.active_input_from:
                continue
            # B2: executor 스레드 조기 종료를 위한 플래그 설정
            room._cancel_requested = True
            # input_tasks에서 살아있는 task를 cancel (done() 체크로 안전 처리 — T-03-02-03)
            for task in list(room.input_tasks):
                if not task.done():
                    task.cancel()
            await broadcast(room, type='agent_cancelled')

        elif t == 'ping':
            await send(ws, type='pong')


async def _run_session(ws):
    # 룸 식별: 헤더 있으면 공유 룸, 없으면 연결 단위 솔로 룸 (UUID).
    # 솔로 모드는 매 연결마다 고유 이름이라 회귀 없음.
    room_header = (ws.request.headers.get('x-harness-room', '') or '').strip()
    room_name = room_header if room_header else f'_solo_{uuid.uuid4().hex}'
    is_shared = bool(room_header)  # 솔로 룸은 _solo_ 접두로 구분

    # PEXT-04: x-resume-from 헤더 파싱 (재연결 시 delta replay 요청)
    # isdigit() — 부동소수/음수/빈 문자열 거부. 2^31 상한선 — 대형 정수 거부 (T-03-02-01)
    resume_from_raw = (ws.request.headers.get('x-resume-from', '') or '').strip()
    if resume_from_raw.isdigit() and int(resume_from_raw) < 2 ** 31:
        resume_from: int | None = int(resume_from_raw)
    else:
        resume_from = None

    # SES-02 (B3): x-resume-session 헤더 파싱 — 세션 파일명
    resume_session_id = (ws.request.headers.get('x-resume-session', '') or '').strip()

    room = _get_or_create_room(room_name)
    room.subscribers.add(ws)
    state = room.state  # 같은 룸의 모든 ws가 같은 Session 공유

    # B4: 이 ws의 토큰을 저장해두어 room_member_joined에서 user 필드 계산에 사용
    ws_token = (ws.request.headers.get('x-harness-token', '') or '').strip()

    try:
        # 초기 상태 전송 (room은 신규 필드 — 모르는 UI는 무시함)
        await send_state(ws, state)
        await send(ws, type='ready', room=room_name)

        # Phase 3-A: 룸 메타 + 과거 컨텍스트 snapshot (DQ4) — 새 join에게만
        # Pitfall H 수정: members 필드 추가 (현재는 빈 리스트 — room_member_joined로 점진 추가)
        await send(ws, type='room_joined',
                   room=room_name,
                   shared=is_shared,
                   subscribers=len(room.subscribers),
                   busy=room.busy,
                   members=[])

        # SES-02 (B3): 세션 resume — 첫 번째 접속자만 세션 로드
        if resume_session_id and not (room.subscribers - {ws}):
            try:
                data = session_store.load(resume_session_id)
                state.messages = data.get('messages', [])
                if 'working_dir' in data:
                    state.working_dir = data['working_dir']
            except FileNotFoundError:
                await send(ws, type='error', text=f'세션 없음: {resume_session_id}')
            except Exception as e:
                await send(ws, type='error', text=f'세션 로드 오류: {e}')

        # PEXT-04: delta 재송신 — ring buffer에서 resume_from 이후 이벤트 순서대로 전송
        if resume_from is not None:
            for (eid, _ts, payload_dict) in list(room.event_buffer):
                if eid > resume_from:
                    await send(ws, **payload_dict)

        if state.messages:
            await send(ws, type='state_snapshot',
                       turns=len([m for m in state.messages if m['role'] == 'user']),
                       messages=state.messages)
        # 기존 멤버에게 새 사람 합류 알림 (자기 자신도 받지만 UI가 자체 식별)
        # B4: user=_token_hash(ws_token) 필드 추가 — 토큰 원문 미노출
        if is_shared and len(room.subscribers) > 1:
            await broadcast(room, type='room_member_joined',
                            subscribers=len(room.subscribers),
                            user=_token_hash(ws_token) if ws_token else '')

        # 자동 인덱싱 — 룸의 working_dir 기준. 두 번째 join은 is_indexed=True로 자연 스킵.
        if state.profile.get('auto_index') and not context.is_indexed(state.working_dir):
            py_count = sum(1 for _, _, fs in os.walk(state.working_dir) for f in fs if f.endswith('.py'))
            if py_count > 3:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: context.index_directory(state.working_dir))
                await send(ws, type='info', text=f'인덱싱 완료 {result["indexed"]}개 청크')
                await send_state(ws, state)

        # reader/dispatch 분리 (Phase 2.5):
        # reader가 별도 코루틴이라 dispatch가 input 처리에 막혀도 큐는 계속 채워짐.
        # → confirm_*_response가 즉시 dispatch에 도달해 데드락 회피.
        queue: asyncio.Queue = asyncio.Queue()
        reader_task = asyncio.create_task(_reader_loop(ws, queue))
        try:
            await _dispatch_loop(ws, room, queue)
        finally:
            reader_task.cancel()
            # 진행 중인 input task는 자연 종료를 기대.
            # 끊긴 ws에 대한 broadcast는 dead 정리 로직이 자동 처리.
    finally:
        room.subscribers.discard(ws)
        # Phase 3-A: 다른 멤버에게 이탈 알림 (룸이 비어 정리되기 전에 한 번)
        if is_shared and room.subscribers:
            try:
                await broadcast(room, type='room_member_left',
                                subscribers=len(room.subscribers))
            except Exception:
                pass
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
