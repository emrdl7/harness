# Phase 3: Remote Room + Session Control — Research

**Researched:** 2026-04-24
**Domain:** harness_server.py WS 프로토콜 확장 (PEXT-01~05) · HarnessClient.ts 재연결 backoff (WSR-01~04) · Ink UI 관전 모드 / Presence (REM-01~06) · Session one-shot/resume (SES-01~04) · Differentiators (DIFF-01~05)
**Confidence:** HIGH (harness_server.py 전수 분석 + 현재 ui-ink Phase 2 코드 직접 확인 + BB-2-DESIGN.md + session/store.py 분석 + 234개 Python pytest 코드 직접 확인)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REM-01 | `x-harness-room` 헤더로 방 지정 (`--room <name>` 또는 `HARNESS_ROOM` env var) | 서버 이미 구현됨. 클라이언트 HarnessClient.ts 이미 헤더 주입 구현됨 [VERIFIED] |
| REM-02 | Presence 렌더 — `room_joined`·`room_member_joined`·`room_member_left`·`room_busy`·`state_snapshot` 처리. StatusBar `🟢 2명 [alice·me]` | dispatch.ts에 이미 `room_joined`/`room_member_joined`/`room_member_left` 케이스 있음. PresenceSegment 컴포넌트 신규 구현 필요 |
| REM-03 | Join 시 `state_snapshot`으로 과거 turn 히스토리 일괄 로드 (`<Static>` key remount 패턴) | 서버는 이미 `state_snapshot` 전송. 클라이언트 dispatch에 `state_snapshot` 케이스 있으나 메시지 히스토리 리스트 로드 미구현 |
| REM-04 | `room.activeIsSelf` 플래그로 관전 모드 판정. 관전자 `<InputArea>` disabled + "A is typing" 오버레이 | room.ts에 `activeIsSelf` 필드 있음. `ObserverOverlay` 컴포넌트 신규. `agent_start`에 `from_self` 필드 필요 (PEXT-01) |
| REM-05 | Join/Leave 시 system 메시지 1줄을 `<Static>` 히스토리에 append | dispatch.ts에 이미 `appendSystemMessage` 연결됨. 텍스트 포맷 개선 필요 (03-UI-SPEC.md 기준) |
| REM-06 | 로컬 ↔ 원격 동등성 — 통합 테스트로 보증 | fake WS server로 ws://127.0.0.1 / ws://external-host 동일 시나리오 green |
| SES-01 | One-shot — `harness "질문"` → REPL 없이 answer 출력 후 exit. non-TTY 시 ANSI off | index.tsx에 one-shot 분기 이미 있음 (FND-12 stub). Phase 3에서 실제 WS 연결 + answer stdout 출력으로 확장 필요 |
| SES-02 | Resume — `harness --resume <id>` → 저장 세션 로드 후 REPL | session/store.py의 `load(filename)` API 확인됨. CLI argv 파싱 + WS 연결 시 `resume_from_session` 헤더 추가 필요 |
| SES-03 | `--room <name> "질문"` 조합 — 방 one-shot | SES-01 + REM-01 조합. HarnessClient에 room 헤더 이미 지원됨 |
| SES-04 | Terminal resize → `useStdout().stdout.on('resize')` → RND-04 clear 루틴 수행 | Phase 2 App.tsx에 이미 구현됨 (RND-04). Phase 3에서 변경 없음 |
| WSR-01 | jitter exponential backoff — `delay = base * 2^n * (0.5 + Math.random()*0.5)`, max 10회, 30초 cap, 안정 30초 후 attempts 리셋 | HarnessClient.ts에 stub 주석 있음. Phase 3에서 확장 구현 필요 |
| WSR-02 | 재연결 중 `disconnected — reconnecting...` 오버레이 + InputArea disabled + 로컬 입력 버퍼링 | ReconnectOverlay 컴포넌트 신규. store/room.ts에 `wsState` 필드 추가 필요 |
| WSR-03 | 안정 재연결 후 `resume_from: <last_event_id>` 헤더로 delta 재요청 | PEXT-03/04 서버 ring buffer 구현 + 클라이언트 `resume_from` WS 헤더 송신 필요 |
| WSR-04 | Ctrl+C 첫 번째가 `cancel` 메시지를 WS로 송신 → 현재 agent turn만 중단 | App.tsx에서 이미 `{type: 'input', text: '/cancel'}` 전송 중 (임시). `{type: 'cancel'}` 타입으로 교정 + 서버 PEXT-05 구현 |
| PEXT-01 | `agent_start` 이벤트에 `from_self: bool` 필드 추가 | harness_server.py의 `broadcast(room, type='agent_start')` 호출 확장 필요 |
| PEXT-02 | `confirm_write` 이벤트에 `old_content?: string` optional 필드 추가 | harness_server.py의 `confirm_write(path, content)` — content 파라미터 이미 있음. send 호출에 포함만 하면 됨 |
| PEXT-03 | 서버에 monotonic `event_id` 부여 + Room당 60초 이벤트 ring buffer | Room 클래스에 `event_counter: int`와 `event_buffer: deque[dict]` 추가 필요 |
| PEXT-04 | 클라 → 서버 `resume_from: <event_id>` 헤더 파싱 + 해당 id 이후 이벤트 재송신 | `_run_session()`에서 WS handshake 시점에 `ws.request.headers.get('x-resume-from')` 파싱 |
| PEXT-05 | 클라 → 서버 `cancel` 메시지 타입 신설 + agent asyncio task 안전 중단 | `_dispatch_loop`에 `cancel` 케이스 추가. `input_tasks` set에서 현재 실행 task cancel |
| DIFF-01 | 공유 관전 모드 — 관전자가 에이전트 토큰 스트리밍 라이브 시청 | REM-04 + RND-01 조합물. 서버는 이미 broadcast로 모두에게 전송. 클라이언트 관전자 상태 렌더가 핵심 |
| DIFF-02 | 메시지 author 표기 — 각 user 메시지에 `[alice]` prefix 자동 부착 | Message.tsx에 room 존재 시 author prefix 렌더 추가 필요. `agent_start.from_self` 로 입력자 식별 |
| DIFF-03 | Confirm 관전 뷰 — 입력 주체 아닌 관전자에게는 read-only 모달 | Phase 2 ConfirmDialog에서 CNF-04 조건 이미 있음. 관전자용 UI 텍스트 교체 필요 |
| DIFF-04 | 사용자 색 해시 — 토큰 기반 deterministic 색 생성 | 03-UI-SPEC.md에 알고리즘 확정됨. `userColor(token)` 순수함수 구현 필요 |
| DIFF-05 | `--room <name> "질문"` one-shot room 공유 | SES-03과 동일 항목 |
</phase_requirements>

---

## Summary

Phase 3은 Phase 2에서 완성된 로컬 UX 위에 "공유 · 재연결 · 세션 진입 모드"를 계층적으로 얹는 단계다. 작업은 두 계층으로 명확히 분리된다: (1) **서버 레이어** — `harness_server.py`에 PEXT-01~05 총 5건의 WS 프로토콜 확장. (2) **클라이언트 레이어** — `ui-ink/src/`에 Presence UI · 재연결 backoff · 관전자 오버레이 · one-shot/resume 경로 완성.

가장 중요한 발견은 **서버의 Room/broadcast 구조가 BB-2 Phase 1~3을 이미 구현 완료**했다는 것이다 [VERIFIED: harness_server.py 전수 분석]. `room_joined`, `room_member_joined`, `room_member_left`, `state_snapshot` 이벤트를 서버가 이미 전송한다. `confirm_write(path, content)` 함수에 `content` 파라미터도 이미 존재하지만 `send(ws, type='confirm_write', path=path)`에서 `content`를 생략하고 있다(PEXT-02는 이 추가만 하면 됨).

클라이언트 측에서는 `dispatch.ts`에 room 이벤트 케이스들이 이미 있으나, `state_snapshot`의 히스토리 메시지 로드, `PresenceSegment` 컴포넌트, 재연결 backoff, 관전자 오버레이가 미구현 상태다. `HarnessClient.ts`에는 재연결 로직을 위한 stub 주석이 있다.

**Primary recommendation:** 서버 PEXT 구현을 Wave 1에서 먼저 완료하여 프로토콜을 고정하고, Wave 2에서 클라이언트 Presence + 관전 UI를 얹고, Wave 3에서 재연결 backoff + delta replay + one-shot/resume를 완성한다. 234개 Python pytest가 Room/broadcast 단위 테스트를 이미 상당 부분 커버하므로, PEXT 변경이 기존 테스트를 파괴할 위험은 낮다(필드 추가만, 의미 변경 없음).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PEXT-01 `agent_start.from_self` | 백엔드 (harness_server.py) | — | broadcast 호출 시점에서 per-subscriber 구분이 필요. 서버 레이어에서만 가능 |
| PEXT-02 `confirm_write.old_content` | 백엔드 (harness_server.py) | — | `confirm_write()` 콜백 안에서 파일 내용 읽어 포함. 서버 레이어 |
| PEXT-03 event_id + ring buffer | 백엔드 (harness_server.py) Room 클래스 | — | Room 단위 상태이므로 Room 클래스에 직접 추가 |
| PEXT-04 resume_from 파싱 | 백엔드 (harness_server.py) `_run_session()` | — | WS handshake 시점 헤더 파싱은 핸들러 진입부에서 처리 |
| PEXT-05 cancel 처리 | 백엔드 (harness_server.py) `_dispatch_loop` | — | asyncio task cancel은 이벤트 루프에서 처리. `input_tasks` set 접근 |
| 재연결 backoff (WSR-01) | Ink 클라이언트 (HarnessClient.ts) | store/room.ts wsState | WS 생명주기는 클라이언트 레이어 |
| 재연결 오버레이 (WSR-02) | Ink 컴포넌트 (ReconnectOverlay.tsx) | store/room.ts | wsState 구독하여 조건부 렌더 |
| delta replay 요청 (WSR-03) | Ink 클라이언트 (HarnessClient.ts) | 백엔드 PEXT-03/04 | 클라이언트가 `resume_from` 헤더로 요청, 서버가 ring buffer에서 응답 |
| Presence UI (REM-02) | Ink 컴포넌트 (PresenceSegment.tsx) | store/room.ts | StatusBar 서브컴포넌트 패턴 (CtxMeter와 동일) |
| state_snapshot 히스토리 로드 (REM-03) | ws/dispatch.ts | store/messages.ts | WS 이벤트 → store action 패턴 |
| 관전자 오버레이 (REM-04) | Ink 컴포넌트 (ObserverOverlay.tsx) | store/room.ts `activeIsSelf` | App.tsx 치환 우선순위 조건부 렌더 |
| 사용자 색 해시 (DIFF-04) | 순수 함수 유틸리티 (userColor.ts) | theme.ts | store 불필요, 모든 컴포넌트에서 import하여 사용 |
| one-shot/resume (SES-01/02) | index.tsx + HarnessClient.ts | session/store.py | 진입점에서 분기. 서버는 기존 `state_snapshot` 이벤트 활용 |
| author prefix (DIFF-02) | Ink 컴포넌트 (Message.tsx 수정) | store/room.ts roomName | roomName 존재 시 prefix 조건부 렌더 |

---

## Standard Stack

### 기존 설치 완료 — Phase 3에서 신규 설치 없음

| Library | Version | Purpose | 확인 |
|---------|---------|---------|------|
| `ink@7` | ^7.0.1 | TUI 렌더러 | Phase 1 설치됨 [VERIFIED] |
| `zustand@5` | ^5.0.12 | 상태 관리 | Phase 1 설치됨 [VERIFIED] |
| `ws@8` | ^8.x | WebSocket 클라이언트 | Phase 1 설치됨 [VERIFIED] |
| `@inkjs/ui@2` | ^2.0.0 | Spinner 등 | Phase 1 설치됨 [VERIFIED] |
| `ink-spinner@5` | ^5.0.0 | Phase 2 사용 중 | [VERIFIED] |

**Phase 3 신규 npm 패키지 없음** — 03-UI-SPEC.md §Registry Safety에서 명시됨 [CITED: 03-UI-SPEC.md].

### Python 백엔드 의존성 — 표준 라이브러리만 사용

| 모듈 | 목적 | 확인 |
|------|------|------|
| `asyncio` | task cancel, Semaphore, Queue | 이미 사용 중 [VERIFIED] |
| `collections.deque` | PEXT-03 ring buffer | 표준 라이브러리 [VERIFIED] |
| `time.monotonic()` | PEXT-03 60초 TTL 만료 판정 | 표준 라이브러리 [VERIFIED] |

---

## Architecture Patterns

### System Architecture Diagram

```
┌─── Phase 3 데이터 흐름 ──────────────────────────────────────────────────┐
│                                                                         │
│  [클라이언트 A] ─── WS 연결 ──→ harness_server.py                       │
│  [클라이언트 B] ─── WS 연결 ──→ handler()                               │
│  [클라이언트 C] ─── WS 연결 ──┘   │                                     │
│                                    ↓                                    │
│                              _run_session()                             │
│                                    │                                    │
│                              ┌─────┴──────┐                            │
│                              │ Room 룩업   │ ← ROOMS[name]              │
│                              │ + event_id  │ ← PEXT-03 monotonic counter│
│                              │ + ring_buf  │ ← 60초 deque               │
│                              └─────┬──────┘                            │
│                                    │                                    │
│               ┌──────────────────-─┴────────────────────┐              │
│               │    _dispatch_loop() — 메시지 처리         │              │
│               │                                          │              │
│               │  input → _spawn_input_task()             │              │
│               │           └→ _handle_input()             │              │
│               │               ├→ run_agent()             │              │
│               │               │   ├→ broadcast(agent_start, from_self) │
│               │               │   │   └ per-subscriber send (PEXT-01)  │
│               │               │   ├→ broadcast(token/tool_*)           │
│               │               │   ├→ send(ws, confirm_write, old_content) │
│               │               │   │   (PEXT-02)                        │
│               │               │   └→ broadcast(agent_end)              │
│               │               │                                        │
│               │  cancel ──────┼→ task.cancel() on input_tasks (PEXT-05)│
│               │                                                          │
│               └──────────────────────────────────────────────────────-─┘
│                                    │                                    │
│                 resume_from 헤더 파싱 (PEXT-04)                         │
│                 └→ ring_buffer에서 event_id 이후 이벤트 재송신           │
│                                                                         │
│  ─── 클라이언트 레이어 ──────────────────────────────────────────────── │
│                                                                         │
│  WS close → HarnessClient.ts                                           │
│              ├→ wsState = 'reconnecting' → store/room.ts               │
│              ├→ jitter exponential backoff 타이머                       │
│              ├→ 재연결 성공 시 resume_from: <last_event_id> 헤더 전송   │
│              └→ wsState = 'connected'                                  │
│                                                                         │
│  dispatch(agent_start, from_self) → room.ts                            │
│  ├→ activeIsSelf = from_self                                            │
│  ├→ activeInputFrom = username (from token)                             │
│  └→ App.tsx 치환 우선순위 재평가:                                        │
│       reconnecting  → <ReconnectOverlay>                                │
│       !activeIsSelf → <ObserverOverlay>                                 │
│       confirmMode   → <ConfirmDialog> or <ConfirmObserverView>          │
│       otherwise     → <InputArea>                                       │
│                                                                         │
│  dispatch(state_snapshot, messages=[...]) → messages.ts                │
│  └→ Static key remount (completedMessages 전체 교체 + Static 키 변경)  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (Phase 3 변경사항만)

```
ui-ink/src/
├── index.tsx               ← one-shot/resume 실제 구현 (SES-01, SES-02, SES-03)
├── protocol.ts             ← AgentStartMsg에 from_self 필드, ConfirmWriteMsg에 old_content 필드 추가
├── ws/
│   ├── client.ts           ← jitter backoff reconnect + resume_from 헤더 (WSR-01, WSR-03)
│   └── dispatch.ts         ← agent_start from_self 처리, state_snapshot 히스토리 로드
├── store/
│   └── room.ts             ← wsState, reconnectAttempt, lastEventId, activeInputFrom 확장
├── components/
│   ├── PresenceSegment.tsx  ← 신규 (REM-02, DIFF-04)
│   ├── ReconnectOverlay.tsx ← 신규 (WSR-02)
│   ├── ObserverOverlay.tsx  ← 신규 (REM-04, DIFF-01)
│   ├── SystemMessage.tsx    ← 신규 또는 Message.tsx 통합 (REM-05)
│   ├── App.tsx              ← 치환 우선순위 확장 + wsState 구독
│   ├── StatusBar.tsx        ← PresenceSegment 연결 (REM-02)
│   ├── Message.tsx          ← author prefix 추가 (DIFF-02)
│   └── DiffPreview.tsx      ← old_content 기반 실제 diff 활성화 (CNF-01 완성)
└── utils/
    └── userColor.ts         ← 신규 순수함수 (DIFF-04)

harness_server.py (Python 백엔드 변경사항)
├── Room 클래스: event_counter, event_buffer(deque) 필드 추가 (PEXT-03)
├── broadcast(): event_id 자동 부여 + ring buffer append (PEXT-03)
├── _record_event(): ring buffer TTL 관리 헬퍼
├── run_agent(): agent_start broadcast를 per-subscriber로 교체 (PEXT-01)
├── run_agent(): confirm_write send에 old_content 포함 (PEXT-02)
├── _run_session(): resume_from 헤더 파싱 + delta 재송신 (PEXT-04)
└── _dispatch_loop(): cancel 케이스 추가 + input_tasks cancel (PEXT-05)
```

---

## Pattern 1: PEXT-01 — `agent_start.from_self: bool`

**문제:** `broadcast(room, type='agent_start')`는 모든 구독자에게 동일한 메시지를 보낸다. 클라이언트가 자신이 입력한 에이전트 실행인지(입력자) vs 타인이 입력한 것인지(관전자)를 구분할 수 없다.

**서버 구현 위치:** `harness_server.py`의 `run_agent()` 함수. Line 236의 `broadcast(room, type='agent_start')` 한 줄을 per-subscriber 루프로 교체.

```python
# harness_server.py — run_agent() 안 (PEXT-01)
# 기존: await broadcast(room, type='agent_start')
# 변경: per-subscriber로 from_self 구분
async def _broadcast_agent_start(room: 'Room', requester_ws):
    '''agent_start는 per-subscriber — from_self 플래그가 달라야 함.'''
    dead = []
    for s in list(room.subscribers):
        try:
            await send(s, type='agent_start', from_self=(s is requester_ws))
        except Exception:
            dead.append(s)
    for s in dead:
        room.subscribers.discard(s)
```

**클라이언트 처리:** `dispatch.ts`의 `agent_start` 케이스에서 `msg.from_self`를 `room.setActiveIsSelf(msg.from_self ?? true)`로 처리.

**프로토콜 타입 업데이트:**
```typescript
// protocol.ts
export interface AgentStartMsg { type: 'agent_start'; from_self?: boolean }
```

**테스트 영향:** `test_harness_server.py`의 `TestBroadcast` 클래스가 broadcast를 테스트하지만, `_broadcast_agent_start`는 별도 함수이므로 기존 테스트는 영향 없음. 새 단위 테스트 추가 필요.

---

## Pattern 2: PEXT-02 — `confirm_write.old_content?: string`

**현재 서버 코드 [VERIFIED: harness_server.py line 188-203]:**
```python
def confirm_write(path: str, content: str | None = None) -> bool:
    ...
    asyncio.run_coroutine_threadsafe(
        send(ws, type='confirm_write', path=path), loop  # ← content 미포함!
    )
```

`content` 파라미터가 이미 있지만 `send()` 호출에서 누락되어 있다. 추가 로직 없음:

```python
# 변경
asyncio.run_coroutine_threadsafe(
    send(ws, type='confirm_write', path=path,
         old_content=_read_existing_file(path)), loop
)
```

`_read_existing_file(path)` 헬퍼:
```python
def _read_existing_file(path: str) -> str | None:
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None
```

**클라이언트 처리:** `DiffPreview.tsx`에서 `old_content`가 있으면 `structuredPatch(old_content, new_content)`로 실제 diff 렌더 (Phase 2의 placeholder를 교체).

**프로토콜 타입 업데이트:**
```typescript
export interface ConfirmWriteMsg { type: 'confirm_write'; path: string; old_content?: string }
```

**테스트 영향:** 기존 `confirm_write` 이벤트 테스트는 `path` 필드만 체크 — optional 필드 추가는 기존 테스트 파괴 없음.

---

## Pattern 3: PEXT-03 — monotonic event_id + 60초 ring buffer

**구현 위치:** `Room` 클래스에 직접 추가. 별도 모듈 불필요 (3인 스케일에 과잉).

```python
# harness_server.py — Room 클래스 확장
import time
from collections import deque

@dataclass
class Room:
    name: str
    state: Session
    subscribers: set = field(default_factory=set)
    busy: bool = False
    active_input_from: object = None
    input_tasks: set = field(default_factory=set)
    # PEXT-03 추가
    event_counter: int = field(default=0)
    event_buffer: deque = field(default_factory=deque)  # (event_id, timestamp, payload_dict)
```

`broadcast()` 함수 확장:
```python
async def broadcast(room: 'Room', **kwargs):
    # event_id 부여 + ring buffer 기록
    room.event_counter += 1
    event_id = room.event_counter
    kwargs['event_id'] = event_id
    now = time.monotonic()
    room.event_buffer.append((event_id, now, dict(kwargs)))
    # TTL 60초 초과 항목 정리
    while room.event_buffer and (now - room.event_buffer[0][1]) > 60:
        room.event_buffer.popleft()

    # 기존 broadcast 로직
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
```

**테스트 영향:** `TestBroadcast` 클래스의 테스트들이 broadcast를 호출하므로, `event_id` 필드가 페이로드에 추가되어도 기존 테스트의 `'"type": "token"'` 체크는 `in` 연산이라 영향 없음. `test_payload_is_valid_json`은 exact equality 체크라 `event_id` 추가 시 실패 가능 → 해당 테스트 업데이트 필요.

---

## Pattern 4: PEXT-04 — `resume_from` 헤더 파싱 + delta 재송신

**구현 위치:** `_run_session(ws)` 진입부 — WS handshake 이후 즉시.

```python
async def _run_session(ws):
    # 기존 코드
    room_header = (ws.request.headers.get('x-harness-room', '') or '').strip()
    room_name = room_header if room_header else f'_solo_{uuid.uuid4().hex}'
    room = _get_or_create_room(room_name)
    room.subscribers.add(ws)

    # PEXT-04: resume_from 헤더 파싱
    resume_from_str = (ws.request.headers.get('x-resume-from', '') or '').strip()
    resume_from = int(resume_from_str) if resume_from_str.isdigit() else None

    try:
        await send_state(ws, room.state)
        await send(ws, type='ready', room=room_name)
        await send(ws, type='room_joined', ...)

        # PEXT-04: delta 재송신 — ring buffer에서 resume_from 이후 이벤트
        if resume_from is not None:
            for (eid, ts, payload) in room.event_buffer:
                if eid > resume_from:
                    await send(ws, **payload)

        # state_snapshot 전송 ...
```

**클라이언트 헤더 전송 위치:** `HarnessClient.ts`의 reconnect 시 `connect()` 호출에서:
```typescript
const lastEventId = useRoomStore.getState().lastEventId
if (lastEventId != null) {
  headers['x-resume-from'] = String(lastEventId)
}
```

---

## Pattern 5: PEXT-05 — `cancel` 메시지 + asyncio task 안전 중단

**현재 상태 [VERIFIED: App.tsx line 72]:** `clientRef.current?.send({type: 'input', text: '/cancel'})` — 잘못된 임시 구현. `cancel` ClientMsg 타입이 `protocol.ts`에 이미 있으나 서버가 `cancel` 타입을 처리하지 않음.

**서버 구현 위치:** `_dispatch_loop()`에 케이스 추가:
```python
elif t == 'cancel':
    # DQ3: 입력 주체(active_input_from)만 취소 가능
    if ws is not room.active_input_from:
        continue
    # 현재 실행 중인 input task 안전 중단
    for task in list(room.input_tasks):
        task.cancel()
    # busy/active_input_from은 task의 finally에서 자동 정리됨 (기존 패턴 유지)
    await broadcast(room, type='agent_cancelled')
```

**`_handle_input()` 수정 — CancelledError 처리:**
```python
async def _handle_input(ws, room: 'Room', text: str):
    try:
        if text.startswith('/'):
            await handle_slash(ws, room, text)
        ...
    except asyncio.CancelledError:
        # 정상 취소 경로 — busy/active_input_from은 finally에서 정리
        pass
    except Exception as e:
        await broadcast(room, type='error', text=f'입력 처리 오류: {e}')
    finally:
        room.busy = False
        room.active_input_from = None
```

**클라이언트 수정:** `App.tsx`의 `{type: 'input', text: '/cancel'}` → `{type: 'cancel'}` 교정. `dispatch.ts`에 `agent_cancelled` 이벤트 케이스 추가.

**기존 `turn_end`와의 차이:** `agent_end`는 에이전트가 정상 완료 시 서버가 자동 전송. `cancel`은 클라이언트가 요청하는 능동적 중단이며, 응답으로 `agent_cancelled` 이벤트를 신설하여 UI가 "취소됨" 상태를 명확히 표시. `agent_end`와 동일하게 `busy=False`로 전환.

**테스트 영향:** `TestDispatchLoop.test_ping_returns_pong` 등 기존 dispatch 테스트는 `cancel` 케이스 추가에 영향 없음. 별도 `test_cancel_stops_task` 테스트 추가 필요.

---

## Pattern 6: WSR-01 — jitter exponential backoff

**구현 위치:** `HarnessClient.ts` 확장 (별도 `reconnect.ts` 모듈로 분리 가능하나 3인 스케일에서 불필요).

```typescript
// HarnessClient.ts 확장
interface BackoffState {
  attempts: number
  stableTimer: ReturnType<typeof setTimeout> | null
}

private backoff: BackoffState = {attempts: 0, stableTimer: null}

private _scheduleReconnect(): void {
  const {attempts} = this.backoff
  if (attempts >= 10) {
    useRoomStore.getState().setWsState('failed')
    return
  }
  // WSR-01 공식: delay = base * 2^n * (0.5 + Math.random() * 0.5)
  const base = 1000  // 1초
  const cap = 30_000  // 30초
  const delay = Math.min(base * Math.pow(2, attempts) * (0.5 + Math.random() * 0.5), cap)
  this.backoff.attempts++
  useRoomStore.getState().setReconnectAttempt(this.backoff.attempts)
  useRoomStore.getState().setWsState('reconnecting')

  setTimeout(() => this.connect(), delay)
}

// 안정 30초 후 attempts 리셋
private _onConnectedStable(): void {
  this.backoff.stableTimer = setTimeout(() => {
    this.backoff.attempts = 0
  }, 30_000)
}

// ws.on('close') 핸들러 교체
this.ws.on('close', () => {
  useStatusStore.getState().setConnected(false)
  this._clearPing()
  if (this.backoff.stableTimer) clearTimeout(this.backoff.stableTimer)
  this._scheduleReconnect()
})
```

---

## Pattern 7: WSR-03 — delta replay

**데이터 흐름:**
1. WS close 이벤트 시 `useRoomStore.getState().lastEventId` 저장
2. reconnect 시 `HarnessClient.connect()`에서 `x-resume-from: <lastEventId>` 헤더 포함
3. 서버 `_run_session()`에서 ring buffer의 `event_id > resume_from` 이벤트를 순서대로 `send(ws, ...)`
4. 클라이언트 `dispatch()` 함수가 수신된 이벤트를 정상 처리

**store/room.ts 확장:**
```typescript
interface RoomState {
  // 기존 필드 ...
  wsState: 'connected' | 'reconnecting' | 'failed'
  reconnectAttempt: number
  lastEventId: number | null
  // 신규 actions
  setWsState: (s: RoomState['wsState']) => void
  setReconnectAttempt: (n: number) => void
  setLastEventId: (id: number) => void
}
```

**dispatch.ts에서 event_id 추적:**
```typescript
// 모든 ServerMsg에 event_id? 필드 추가 (optional — 서버가 부여)
// dispatch() 함수 시작부에:
if ('event_id' in msg && typeof msg.event_id === 'number') {
  useRoomStore.getState().setLastEventId(msg.event_id)
}
```

---

## Pattern 8: REM-03 — state_snapshot 히스토리 로드

**현재 dispatch.ts 상태 [VERIFIED]:**
```typescript
case 'state_snapshot':
  status.setState({...})  // 상태만 업데이트, messages 로드 안 됨
  break
```

**Phase 3 확장:**
```typescript
case 'state_snapshot':
  status.setState({working_dir: msg.working_dir, ...})
  // 과거 turn 히스토리 로드
  if (msg.messages && Array.isArray(msg.messages)) {
    messages.loadSnapshot(msg.messages)
  }
  break
```

**`Static` key remount 패턴 — store/messages.ts:**
```typescript
loadSnapshot: (rawMessages: unknown[]) => set((s) => ({
  // snapshotKey 변경 시 <Static key={snapshotKey}> 강제 remount
  snapshotKey: s.snapshotKey + 1,
  completedMessages: _parseSnapshotMessages(rawMessages),
  activeMessage: null,
})),
```

**MessageList.tsx에서:**
```tsx
const snapshotKey = useMessagesStore(s => s.snapshotKey)
// ...
<Static key={snapshotKey} items={completedMessages}>
  {(msg) => <Message key={msg.id} message={msg} />}
</Static>
```

---

## Pattern 9: SES-01 — one-shot 완성

**현재 index.tsx 상태 [VERIFIED: lines 44-54]:**
```typescript
if (!isInteractive) {
  const query = process.argv[2]
  if (query) {
    process.stdout.write(`[one-shot] ${query}\n`)  // ← stub
  }
  process.exit(0)
}
```

**Phase 3 구현:**
```typescript
if (!isInteractive) {
  const query = process.argv[2]
  const roomFlag = process.argv.indexOf('--room')
  const roomName = roomFlag > -1 ? process.argv[roomFlag + 1] : process.env['HARNESS_ROOM']

  if (query) {
    const url = process.env['HARNESS_URL']
    const token = process.env['HARNESS_TOKEN']
    if (!url || !token) {
      process.stderr.write('[harness] HARNESS_URL / HARNESS_TOKEN 필요\n')
      process.exit(1)
    }
    // one-shot: WS 연결 → input 전송 → agent_end 수신 → stdout → exit
    const {runOneShot} = await import('./one-shot.js')
    await runOneShot({url, token, room: roomName, query, ansi: false})
    process.exit(0)
  }
}
```

**`one-shot.ts` 신규 파일** — `HarnessClient`를 경량 버전으로 사용:
- WS 연결
- `ready` 이벤트 후 `{type: 'input', text: query}` 전송
- `token` 이벤트로 stdout에 누적 (ANSI 없이)
- `agent_end` 이벤트에서 process.exit(0)
- 30초 타임아웃

---

## Pattern 10: SES-02 — resume

**session/store.py API [VERIFIED]:**
```python
# session/store.py의 load(filename) — 이미 구현됨
def load(filename: str) -> dict:
    path = os.path.join(SESSION_DIR, filename)
    with open(path, encoding='utf-8') as f:
        return json.load(f)
# 반환 형식: {'working_dir': str, 'messages': list}
```

**구현 방법:** `harness --resume <id>` CLI 인자 파싱 후 WS 연결 시 `x-resume-session: <id>` 헤더 추가 → 서버에서 해당 세션을 Room.state에 로드.

서버 `_run_session()` 확장:
```python
resume_session_id = (ws.request.headers.get('x-resume-session', '') or '').strip()
if resume_session_id and not room.subscribers - {ws}:
    # 첫 번째 접속자만 세션 로드 (기존 subscribers가 있으면 유지)
    try:
        data = sess.load(resume_session_id)
        room.state.messages = data['messages']
        room.state.working_dir = data['working_dir']
    except FileNotFoundError:
        await send(ws, type='error', text=f'세션 없음: {resume_session_id}')
```

**클라이언트:** index.tsx에서 `--resume <id>` 파싱 → ConnectOptions에 `resumeSession` 추가 → HarnessClient가 헤더로 전달.

---

## Pattern 11: PresenceSegment 컴포넌트

```tsx
// components/PresenceSegment.tsx
// 03-UI-SPEC.md §Presence 세그먼트 규격 그대로
import {Text} from 'ink'
import {useRoomStore} from '../store/room.js'
import {useShallow} from 'zustand/react/shallow'
import {userColor} from '../utils/userColor.js'

export const PresenceSegment: React.FC = () => {
  const {roomName, members} = useRoomStore(useShallow(s => ({
    roomName: s.roomName,
    members: s.members,
  })))
  if (!roomName) return null  // solo 모드: 세그먼트 미표시

  const count = members.length
  return (
    <Text>
      {'🟢 '}<Text color='green'>{count}명</Text>
      {' ['}
      {members.map((m, i) => (
        <React.Fragment key={m}>
          {i > 0 && <Text color='gray'>·</Text>}
          <Text color={userColor(m)} bold>{m}</Text>
        </React.Fragment>
      ))}
      {']'}
    </Text>
  )
}
```

**`userColor.ts` 순수함수:**
```typescript
// utils/userColor.ts — 03-UI-SPEC.md §사용자 색 해시 규격
const PALETTE = ['cyan', 'green', 'yellow', 'magenta', 'blue', 'red', 'white', 'greenBright']

function _hash(token: string): number {
  return token.split('').reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) & 0xffff, 0)
}

export function userColor(token: string): string {
  // 자기 자신은 항상 cyan (기존 user 역할 색과 통일)
  const myToken = process.env['HARNESS_TOKEN'] ?? ''
  if (token === myToken || token === 'me') return 'cyan'
  return PALETTE[_hash(token) % PALETTE.length]
}
```

---

## Pattern 12: App.tsx 치환 우선순위 확장

```tsx
// App.tsx — Phase 3 치환 우선순위 (03-UI-SPEC.md §치환 우선순위)
const wsState = useRoomStore(s => s.wsState)
const reconnectAttempt = useRoomStore(s => s.reconnectAttempt)
const activeIsSelf = useRoomStore(s => s.activeIsSelf)
const activeInputFrom = useRoomStore(s => s.activeInputFrom)

// 입력 영역 결정 로직
let inputArea: React.ReactNode
if (wsState === 'reconnecting') {
  inputArea = <ReconnectOverlay attempt={reconnectAttempt} />
} else if (wsState === 'failed') {
  inputArea = <ReconnectOverlay failed />
} else if (confirmMode !== 'none' && activeIsSelf) {
  inputArea = <ConfirmDialog />
} else if (confirmMode !== 'none' && !activeIsSelf) {
  inputArea = <ConfirmObserverView activeInputFrom={activeInputFrom} />
} else if (!activeIsSelf) {
  inputArea = <ObserverOverlay username={activeInputFrom} />
} else {
  inputArea = <InputArea onSubmit={handleSubmit} disabled={busy} />
}
```

---

## Pattern 13: dispatch.ts `room_joined` 수정

**현재 [VERIFIED: dispatch.ts line 64-66]:**
```typescript
case 'room_joined':
  room.setRoom(msg.room, msg.members)  // members: string[]
  break
```

**서버 실제 전송 [VERIFIED: harness_server.py line 727-731]:**
```python
await send(ws, type='room_joined',
           room=room_name,
           shared=is_shared,
           subscribers=len(room.subscribers),
           busy=room.busy)
```

`members: string[]`를 전송하지 않는다 — 불일치! `protocol.ts`의 `RoomJoinedMsg`와 서버 실제 전송이 다름. Phase 3에서 서버가 `members` 필드(토큰 식별자 배열)를 추가 전송하거나, 클라이언트가 `subscribers: number`를 카운트로만 사용하도록 수정 필요. 개인 정보(토큰) 노출 없이 익명 카운트만 표시하는 방향이 바람직 [ASSUMED: 03-UI-SPEC.md는 `[alice·me]` 표시를 요구하므로 식별자 전송 필요].

**결정 필요 (Claude 판단):** 멤버 식별자를 토큰 그대로 보낼지, 해시된 별명으로 보낼지. 현재 `/who` 슬래시 명령은 `{'self': bool, 'active': bool}` 익명으로만 보여줌.

**권장:** `room_member_joined`에 `token_hash` 필드 추가 (SHA-256 앞 8자) → 클라이언트에서 색 해시 계산에 사용. 토큰 원문은 노출하지 않음.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WS 재연결 타이머 | `while loop + sleep` | `setTimeout` + backoff state | Event loop 블로킹 회피. bun/Node 표준 패턴 |
| Ring buffer TTL 정리 | 별도 스케줄러 | `time.monotonic()` + broadcast 호출 시 eager cleanup | 3인 스케일에서 별도 태스크 불필요 |
| 사용자 색 배정 | 랜덤 color + localStorage | deterministic hash (03-UI-SPEC.md 공식) | 재접속 시에도 동일 색 보장 |
| Diff 렌더 | 직접 문자 비교 | 기존 `diff@9 structuredPatch` (Phase 2 설치됨) | 이미 DiffPreview.tsx에 구현됨, old_content만 추가하면 됨 |
| WS 헤더 파싱 | 커스텀 파싱 | `ws.request.headers.get()` (websockets 14+ API) | 이미 token 헤더에 동일 패턴 사용 중 |
| asyncio task cancel | `global flag` + polling | `task.cancel()` + `CancelledError` | asyncio 공식 취소 경로 |

---

## Common Pitfalls

### Pitfall A: broadcast에 event_id 추가 시 기존 테스트 파괴 (PEXT-03)
**What goes wrong:** `test_payload_is_valid_json`이 `exact equality`로 페이로드를 비교 — `event_id` 필드 추가 시 실패.
**How to avoid:** 해당 테스트를 `assertsubset` 패턴으로 변경 (기존 필드가 포함되는지만 체크).
**Warning signs:** `pytest test_harness_server.py::TestBroadcast::test_payload_is_valid_json FAILED`.

### Pitfall B: `agent_start.from_self`가 없을 때 관전자가 입력자로 오인 (PEXT-01)
**What goes wrong:** `from_self` 필드가 없는 구 서버와 연결 시 클라이언트가 `undefined ?? true`로 항상 입력자로 판단.
**How to avoid:** `dispatch.ts`에서 `msg.from_self ?? true` — 구버전 호환 유지. 단, `from_self`가 없는 `agent_start`에서 관전자 UI가 안 나옴을 문서화.
**Warning signs:** 3인 접속 시 모두 InputArea가 활성 상태.

### Pitfall C: ring buffer deque에 event_id=0 기준 처리 오류 (PEXT-03/04)
**What goes wrong:** `resume_from=0`이면 ring buffer의 모든 이벤트를 재송신해야 하는데, `event_id > 0` 조건이 항상 true라 첫 연결 시 불필요한 재송신 발생.
**How to avoid:** `resume_from`이 `None`(헤더 없음)일 때만 delta skip. `resume_from=0`은 "처음부터 재송신" 의미로 사용.

### Pitfall D: cancel task.cancel()이 이미 완료된 task에 호출 (PEXT-05)
**What goes wrong:** `input_tasks`에 이미 done인 task가 남아있으면 `task.cancel()`이 `False`를 반환하며 아무 일도 안 일어남. 정상 동작이지만 취소 실패처럼 보임.
**How to avoid:** `asyncio.Task.done()` 체크 후 cancel 호출. `_spawn_input_task`의 done 콜백이 자동으로 set에서 제거하므로 실제로는 드문 케이스.

### Pitfall E: Static key remount 시 completedMessages 전체 Ink 재렌더 (REM-03)
**What goes wrong:** `<Static key={snapshotKey}>`의 key 변경 시 새 항목만 렌더하는 `<Static>` 특성과 충돌 — key 변경이 전체 unmount/remount를 유발해 대용량 히스토리(100+ 메시지) 시 느림.
**How to avoid:** `state_snapshot` 히스토리는 한 번만 로드 (join 직후). 이후 신규 메시지는 기존 `agentEnd` 패턴으로만 추가. snapshotKey 변경은 `/clear` slash + join 시에만.

### Pitfall F: thundering herd — 서버 재시작 시 3클라이언트 동시 재연결
**What goes wrong:** 모두 동시에 재연결 시도 → 서버에 동시 부하. WSR-01 jitter 공식이 `Math.random()*0.5` 범위를 추가하는 이유.
**How to avoid:** WSR-01 공식의 jitter 계수(`0.5 + Math.random()*0.5`)가 50% 범위 spread를 보장. base=1초, 3클라이언트면 재연결이 0.5~1초 범위에 분산됨.

### Pitfall G: one-shot에서 ANSI escape가 파이프에 출력 (SES-01)
**What goes wrong:** `non-TTY` 환경에서 `harness "질문" | grep 내용` 시 ANSI 색상 코드가 파이프에 포함.
**How to avoid:** `one-shot.ts`에서 `process.stdout.isTTY` 체크. TTY가 아니면 ANSI strip. `cli-highlight`의 `{ignoreIllegals: true}` 사용 안 하고 plain text 출력.

### Pitfall H: `room_joined` 서버 실제 페이로드와 protocol.ts 불일치
**What goes wrong:** 서버는 `subscribers: number`를 전송하지만 `protocol.ts`는 `members: string[]`를 기대. 현재 `room.setRoom(msg.room, msg.members)`에서 `msg.members`가 `undefined`.
**How to avoid:** Phase 3 Wave 1에서 프로토콜 타입과 서버 전송 페이로드를 일치시키는 작업 필수. 서버에 `members: string[]` 추가 또는 클라이언트에서 `msg.subscribers: number`로 카운트만 처리.

---

## Runtime State Inventory

> Phase 3는 새 기능 추가이며 rename/refactor가 없으므로 대부분 항목은 해당 없음.
> 단, PEXT-03 ring buffer는 서버 재시작 시 초기화되는 in-memory 상태임.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `session/store.py` — `~/.harness/sessions/` 디렉토리에 JSON 파일 (SES-02 resume 대상) | 코드 변경만. 기존 포맷 호환 유지 |
| Live service config | `ROOMS: dict[str, Room]` — 서버 in-memory. 서버 재시작 시 초기화됨 | 클라이언트 재연결 + delta replay (WSR-03) 로 커버 |
| OS-registered state | 없음 | None — 해당 없음 |
| Secrets/env vars | `HARNESS_TOKENS`, `HARNESS_TOKEN`, `HARNESS_URL`, `HARNESS_ROOM` — 코드 변경 없음 | None |
| Build artifacts | `ui-ink/` TypeScript 빌드 — Phase 3 컴포넌트 추가 시 자동 재빌드 | `bun run build` 또는 `bun start` |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python .venv | 백엔드 서버 | ✓ | Python 3.14 | — |
| bun | ui-ink 실행 | ✓ | (설치됨) | — |
| `asyncio` (Python stdlib) | PEXT-03/05 | ✓ | 내장 | — |
| `collections.deque` (stdlib) | PEXT-03 ring buffer | ✓ | 내장 | — |
| `ws@8` (npm) | HarnessClient.ts | ✓ | Phase 1 설치됨 | — |
| `time.monotonic()` (stdlib) | PEXT-03 TTL | ✓ | 내장 | — |
| `session/store.py` | SES-02 resume | ✓ | 현재 구현됨 | — |
| `diff@9` | PEXT-02 DiffPreview | ✓ | Phase 1 설치됨 | DiffPreview placeholder |

**외부 의존성 없음** — 모든 필요 도구가 설치되어 있음.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | vitest@4.1.5 + ink-testing-library@4.0.0 (클라이언트) / pytest (서버) |
| Config file | `ui-ink/vitest.config.ts` (존재 확인됨 [VERIFIED]) |
| Quick run command (클라이언트) | `cd ui-ink && bun run test` |
| Full suite command (클라이언트) | `cd ui-ink && bun run test --reporter=verbose` |
| Quick run command (서버) | `.venv/bin/python -m pytest tests/test_harness_server.py -x` |
| Full suite command (서버) | `.venv/bin/python -m pytest` |

**현재 기준선:** vitest 120/120 green [VERIFIED: 2026-04-24 Phase 2 완료] · pytest 234개 수집 (199건 기준 — 추가 테스트 포함됨).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PEXT-01 | `agent_start`에 `from_self` 필드 포함 | unit | `pytest tests/test_harness_server.py::TestAgentStartFromSelf -x` | ❌ Wave 1 |
| PEXT-02 | `confirm_write`에 `old_content` 포함 | unit | `pytest tests/test_harness_server.py::TestConfirmWriteOldContent -x` | ❌ Wave 1 |
| PEXT-03 | broadcast 시 event_id 부여 + ring buffer TTL | unit | `pytest tests/test_harness_server.py::TestEventBuffer -x` | ❌ Wave 1 |
| PEXT-04 | resume_from 헤더로 delta 재송신 | integration | `pytest tests/test_harness_server.py::TestDeltaReplay -x` | ❌ Wave 3 |
| PEXT-05 | cancel 메시지로 input task 중단 | unit | `pytest tests/test_harness_server.py::TestCancelTask -x` | ❌ Wave 2 |
| WSR-01 | backoff delay 공식 검증 | unit | `vitest run ws-backoff.test.ts` | ❌ Wave 2 |
| WSR-03 | delta replay — 중간 이벤트 0 유실 | integration | `vitest run reconnect.integration.test.ts` | ❌ Wave 3 |
| REM-03 | state_snapshot 히스토리 로드 | unit | `vitest run store.messages.test.ts` | ✅ (업데이트 필요) |
| REM-04 | activeIsSelf=false 시 ObserverOverlay 렌더 | component | `vitest run components.observer.test.tsx` | ❌ Wave 2 |
| SES-01 | one-shot: query → answer stdout → exit | smoke | `echo 'x' | harness "테스트"` | 수동 검증 |
| REM-06 | 로컬-원격 동등성 | integration | `vitest run room.integration.test.ts` | ❌ Wave 3 |

### Wave 0 Gaps

- [ ] `tests/test_harness_server.py` — PEXT-01~05 단위 테스트 추가 (Wave 1에서 기존 파일에 append)
- [ ] `ui-ink/src/__tests__/ws-backoff.test.ts` — backoff 공식 단위 테스트
- [ ] `ui-ink/src/__tests__/components.observer.test.tsx` — ObserverOverlay 렌더 테스트
- [ ] `ui-ink/src/__tests__/room.integration.test.ts` — Fake WS Server 기반 room 시나리오

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | 예 | 기존 `HARNESS_TOKENS` + hmac.compare_digest. PEXT-05 cancel은 `active_input_from` 가드로 권한 확인 |
| V3 Session Management | 부분 | SES-02 resume — session 파일 권한 0o600 이미 적용됨 |
| V4 Access Control | 예 | CNF-04: confirm 응답은 active_input_from만 허용 (server line 694). cancel은 동일 패턴 적용 |
| V5 Input Validation | 예 | `resume_from` 헤더 파싱 시 `isdigit()` 체크 필수 (정수 주입 방지) |
| V6 Cryptography | 아니오 | — |

### Known Threat Patterns for Phase 3 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 관전자가 confirm_write_response 위조 | Tampering | 기존 `ws is not room.active_input_from` 가드 [VERIFIED: line 694] |
| 관전자가 cancel 메시지 전송 | Tampering | PEXT-05에서 동일 `ws is not room.active_input_from` 가드 추가 |
| `resume_from` 헤더에 대형 정수 주입 | Tampering | `isdigit()` + 합리적 상한선 체크 (`< 2**31`) |
| ring buffer 메모리 고갈 (60초 내 대량 이벤트) | DoS | `event_buffer`에 최대 크기 제한 추가 (예: maxlen=10000) |
| one-shot에서 ANSI injection | Tampering | `process.stdout.isTTY` 체크 후 non-TTY 시 ANSI strip |
| session 파일 path traversal | Tampering | `os.path.basename(filename)` 정규화 후 `SESSION_DIR` 내 경로만 허용 |

---

## 10가지 핵심 연구 질문 답변

### Q1. PEXT-01: per-subscriber `from_self` 구현 위치
**답변:** `run_agent()` 내 `broadcast(room, type='agent_start')` 호출을 전용 `_broadcast_agent_start(room, requester_ws)` 함수로 교체. `broadcast()` 함수 자체는 공통 함수이므로 수정하지 않음. [VERIFIED: harness_server.py line 236]

### Q2. PEXT-03: room 클래스 vs 별도 모듈
**답변:** `Room` 클래스에 직접 추가. `event_counter: int = 0`, `event_buffer: deque = field(default_factory=deque)`. 3인 스케일에 별도 모듈 과잉. broadcast() 함수에서 eager TTL cleanup.

### Q3. PEXT-04: `resume_from` 헤더 파싱 위치
**답변:** `_run_session(ws)` 함수 진입부 — `room_header` 파싱과 동일한 위치. `ws.request.headers.get('x-resume-from', '')`.

### Q4. PEXT-05: `cancel` 과 기존 `turn_end` 차이
**답변:** `agent_end`는 정상 완료 시 서버 자동 전송. `cancel`은 클라이언트 요청 능동 중단. 응답 이벤트 `agent_cancelled`를 신설하여 UI가 구분. `busy=False` + `active_input_from=None` 정리는 동일(finally 블록에서 처리).

### Q5. WSR-01: HarnessClient.ts 확장 vs 별도 reconnect.ts
**답변:** HarnessClient.ts 내 `BackoffState` 인터페이스로 통합. 3인 스케일에서 별도 모듈 불필요. 나중에 필요 시 추출 가능.

### Q6. WSR-03: 서버 ring buffer → 클라이언트 delta 전달 흐름
**답변:** 위 Pattern 4 참조. `x-resume-from` WS 연결 헤더 → `_run_session()` 파싱 → ring buffer event_id 이후 순서대로 `send(ws, ...)`. [분석: harness_server.py _run_session()]

### Q7. SES-01: index.tsx 현재 one-shot 구현 상태
**답변:** stub 수준 [VERIFIED: index.tsx lines 44-54]. `process.stdout.write('[one-shot] ${query}\n')` 후 exit. Phase 3에서 실제 WS 연결 + answer stdout 출력으로 교체 필요.

### Q8. SES-02: 세션 저장 포맷
**답변:** `~/.harness/sessions/YYYYMMDD_HHMMSS_<dir_hash>.json` — `{working_dir: str, messages: list}`. [VERIFIED: session/store.py]

### Q9. REM-03: `state_snapshot` 메시지 서버 전송 현황
**답변:** 서버에서 이미 전송 중 [VERIFIED: harness_server.py lines 733-735]. `messages: list`를 포함하나 `dispatch.ts`에서 `status.setState`만 처리하고 메시지 히스토리 로드 미구현. Phase 3에서 `messages.loadSnapshot()` 액션 추가 + Static key remount 패턴 적용.

### Q10. Python pytest 199건 유지 — PEXT 변경 위험
**답변:** 실제 수집 기준 234개. 영향 위험이 있는 테스트는 `test_payload_is_valid_json` (exact equality 체크, PEXT-03 event_id 추가로 실패 가능). 나머지 Room/broadcast 테스트는 `in` 연산 체크라 영향 없음. `test_dataclass_defaults`는 Room 클래스 필드 추가 시 새 필드 기본값 체크 필요. 총 영향 테스트: 추정 2~3건 (업데이트 필요, 삭제 없음).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `room_joined` 이벤트에 `members: string[]` 필드를 서버가 추가할 수 있음 (현재 없음) | Pattern 13, REM-02 | 없으면 Presence UI에서 사용자 이름 표시 불가. 익명 카운트만 표시하는 fallback 필요 |
| A2 | bun 환경에서 WS 연결 헤더(`x-resume-from`)가 정상 전달됨 | WSR-03, PEXT-04 | `ws` 라이브러리가 커스텀 헤더를 지원함. Phase 1에서 `x-harness-room` 동일 패턴 사용 확인됨 [VERIFIED] |
| A3 | asyncio task.cancel()이 agent.run() 스레드를 즉시 중단함 | PEXT-05 | `agent.run()`은 executor 스레드에서 실행 중. asyncio task cancel은 `await` 지점에서만 작동. `run_in_executor`로 스폰된 스레드는 cancel으로 즉시 중단 안 됨 — threading.Event나 플래그 기반 중단 필요 가능성 있음 |
| A4 | one-shot 경로에서 `harness_server.py` WS 서버가 실행 중이어야 함 | SES-01 | 서버 없으면 one-shot 연결 실패. 에러 메시지 + non-zero exit 처리 필요 |

**A3에 대한 추가 분석:** `asyncio.create_task`로 생성된 task가 `await run_in_executor(None, _run)`을 실행 중일 때 `task.cancel()`을 호출하면 `CancelledError`가 `await` 지점에서 발생한다. 그러나 `_run` 함수 자체(executor 스레드)는 계속 실행된다 — `agent.run()`이 Python 스레드를 블로킹하는 동안에는. **실용적 해결책:** `Room`에 `_cancel_flag: threading.Event` 추가 → `agent.run()`의 `on_token` 콜백에서 플래그 확인 후 조기 종료. 또는 `task.cancel()` 후 `broadcast(room, type='agent_cancelled')`만 즉시 전송하고, 실제 task는 다음 I/O에서 자연 종료되도록 허용.

---

## Open Questions

1. **멤버 식별자 공개 범위 (REM-02)**
   - 현재: 서버가 `subscribers: number` (카운트)만 전송
   - 필요: 03-UI-SPEC.md는 `[alice·me]` 표시 요구
   - 옵션 A: 토큰의 SHA-256 앞 8자를 `token_hash`로 전송 (익명성 유지)
   - 옵션 B: 클라이언트가 입력 시 임의 별명을 `HARNESS_NAME` env var로 등록
   - Recommendation: A (token_hash) — 서버 코드 최소 변경

2. **cancel task 실제 중단 경로 (PEXT-05 A3)**
   - asyncio task cancel이 executor 스레드를 즉시 중단하지 않음
   - Recommendation: `Room`에 `_cancel_requested: bool` 플래그 추가. `on_token` 콜백에서 플래그 체크 후 `raise InterruptedError`. 서버 단에서 이를 통해 에이전트 실행 조기 종료.

3. **one-shot 응답 완성 판정 기준 (SES-01)**
   - `agent_end` 이벤트로 판정? 아니면 응답 텍스트 완결 판정?
   - Recommendation: `agent_end` 이벤트 수신 후 exit — 가장 단순하고 신뢰성 있음.

---

## Sources

### Primary (HIGH confidence)

- `/Users/johyeonchang/harness/harness_server.py` — 전수 분석 (Room 클래스, broadcast, _run_session, _dispatch_loop, confirm_write 등)
- `/Users/johyeonchang/harness/ui-ink/src/` — Phase 2 완성 코드 전수 확인 (App.tsx, protocol.ts, store/room.ts, ws/client.ts, ws/dispatch.ts, index.tsx)
- `/Users/johyeonchang/harness/session/store.py` — SES-02 resume용 session API 확인
- `/Users/johyeonchang/harness/tests/test_harness_server.py` — 기존 pytest 커버리지 확인 (TestBroadcast, TestRoom, TestDispatchLoop)
- `/Users/johyeonchang/harness/.planning/BB-2-DESIGN.md` — WS 프로토콜 설계 ground truth
- `/Users/johyeonchang/harness/.planning/phases/03-remote-room-session-control/03-UI-SPEC.md` — Phase 3 UI 설계 계약 (색상·타이포그래피·컴포넌트·치환 우선순위 전수 명세)
- `/Users/johyeonchang/harness/.planning/REQUIREMENTS.md` — Phase 3 REQ-ID 전수 (REM/SES/WSR/PEXT/DIFF)
- `/Users/johyeonchang/harness/.planning/ROADMAP.md` — Phase 3 목표 및 Success Criteria 6건

### Secondary (MEDIUM confidence)

- `.planning/phases/02-core-ux/02-CONTEXT.md` — Phase 2 결정 사항 (D-07 cancel stub 등)
- `.planning/phases/02-core-ux/02-RESEARCH.md` — Phase 2 연구 결과 (Static/active 패턴, store 구조)
- Python asyncio task cancel 동작 — [ASSUMED: asyncio 공식 동작에 기반, executor 스레드 즉시 중단 안 됨은 Python asyncio docs의 알려진 특성]

### Tertiary (LOW confidence)

- 멤버 식별자 `token_hash` 방식 — Open Question. 구현 시 결정 필요.

---

## Metadata

**Confidence breakdown:**
- 서버 PEXT 패턴: HIGH — harness_server.py 코드 직접 분석 + 기존 테스트 커버리지 확인
- 클라이언트 WSR/REM 패턴: HIGH — Phase 2 코드 + 03-UI-SPEC.md 직접 참조
- PEXT-05 cancel 즉시 중단: LOW → A3 ASSUMED 태깅. executor 스레드 즉시 중단 여부 검증 필요
- 멤버 식별자 방식: LOW → 설계 결정 필요

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30일 — 라이브러리 버전 변동 없으면 유효)
