# BB-2: 원격 페어 프로그래밍 (공유 세션) — 설계 초안

**작성:** 2026-04-23 (BB-1 완료 직후)
**전제 조건:** BB-1 완료 (harness_core/ 모듈, 13/14 슬래시 양쪽 통합, SlashContext 4 콜백)

## 1. 목표

여러 WebSocket 클라이언트가 **하나의 세션 상태**(messages, working_dir, profile)를 실시간 공유. Cursor/Claude Code가 못 하는 영역으로, 집 머신 서버 + 외부 2명 시나리오에 정확히 부합.

### 사용 시나리오
- 사용자 A가 `harness --room team` 접속 → room 'team' 생성
- 사용자 B가 `harness --room team` 접속 → 같은 room 참가
- A가 입력하면 B도 토큰 스트리밍 관전 가능
- 모두 같은 messages/working_dir 본다

## 2. 핵심 구조 변경

### 2.1 현재 (BB-1 기준)
```
handler(ws) → _run_session(ws):
    state = Session()       # 매 연결마다 새 세션
    while message = ws.recv():
        handle_input(ws, state, message)
```

### 2.2 공유 세션 설계
```
handler(ws) → _run_session(ws):
    room_name = ws.request.headers.get('x-harness-room') or '_solo_' + uuid
    room = ROOMS.setdefault(room_name, Room())
    room.subscribers.add(ws)
    state = room.state       # Session 객체 공유
    try:
        while message = ws.recv():
            await handle_input(ws, room, message)
    finally:
        room.subscribers.discard(ws)
        if not room.subscribers:
            del ROOMS[room_name]
```

`Room`:
```python
@dataclass
class Room:
    state: Session                           # 기존 Session 재사용 (messages/working_dir/profile)
    subscribers: set[WebSocket]              # 현재 연결된 클라이언트
    input_lock: asyncio.Lock                 # turn-taking: 한 번에 한 입력만
    active_input_from: WebSocket | None      # 현재 입력 중인 사용자 식별
```

### 2.3 broadcast 헬퍼
기존 `send(ws, **kw)`를 방 단위로 확장:
```python
async def broadcast(room: Room, **kwargs):
    '''room의 모든 subscribers에 같은 메시지 송신. 끊긴 ws는 set에서 제거.'''
    dead = []
    for s in room.subscribers:
        try:
            await send(s, **kwargs)
        except Exception:
            dead.append(s)
    for s in dead:
        room.subscribers.discard(s)
```

run_agent의 on_token/on_tool이 `send(ws, ...)` 대신 `broadcast(room, ...)` 호출하도록 교체.

## 3. 설계 결정 필요 (사용자 입력 필요)

### DQ1. 방 이름 식별 방식
- **옵션 A**: WebSocket connection header `x-harness-room: team`
  - 장점: URL 깔끔, 단순. 클라이언트가 `harness --room team` 실행
  - 단점: Room 재접속 시 이전 상태 자동 재연결 안 됨
- **옵션 B**: 접속 후 `/join <name>` 슬래시로 전환
  - 장점: 런타임 방 이동 가능
  - 단점: 초기 solo session → room 이동 시 메시지 마이그레이션 이슈

**추천: A (header) + B (/join 둘 다 지원). 헤더 우선.**

### DQ2. Confirm 경쟁 (confirm_write/bash)
공유 방에서 write_file 호출 시 누가 승인?
- **옵션 A**: 첫 응답자 승리 (race)
- **옵션 B**: 모든 참여자가 승인해야 진행 (AND)
- **옵션 C**: "owner"(방 개설자)만 confirm 가능, 나머지는 관전만
- **옵션 D**: 에이전트 실행 주체(입력한 사용자)만 confirm

**추천: D (입력 주체 responsibility). `room.active_input_from` ws에만 confirm_* RPC 보냄.**

### DQ3. Turn-taking
한 사용자가 에이전트 실행 중 다른 사용자가 입력하면?
- **옵션 A**: 큐잉 (대기)
- **옵션 B**: 거부 + `room_busy` 알림
- **옵션 C**: 인터럽트 (현재 에이전트 중단)

**추천: B (거부) + 진행 상황 알림 broadcast. 큐잉은 복잡도 높음.**

### DQ4. 새 참여자 join 시 과거 대화 어떻게 보여줄지
- **옵션 A**: `state.messages` 전체를 초기 snapshot으로 송신
- **옵션 B**: "N턴 진행 중인 방에 합류했습니다" 안내만
- **옵션 C**: user input만 표시, tool 결과는 미송신 (요약본)

**추천: A (전체 snapshot). context가 핵심.**

### DQ5. 인증 / 권한 레벨
- 모두 같은 `HARNESS_TOKENS`면 같은 방 가능
- 방별 추가 인증? (복잡)
- **추천: 기존 토큰 모델 유지. 방은 이름만으로 식별.**

## 4. 점진 구현 단계 (예상 3-4 세션)

### Phase 1 — Room 구조 도입 (1 세션)
- `Room` 클래스 + `ROOMS: dict[str, Room]` 추가
- `_run_session(ws)` 수정:
  - 헤더 `x-harness-room` 파싱 (없으면 solo=UUID)
  - Room 조회/생성 + subscribers 관리
- 기존 `Session`은 `Room.state`가 소유. 단일 연결이어도 구조 동일.
- 이 단계까지는 사용자 경험 변화 없음 (내부 refactor만).

### Phase 2 — Broadcast 교체 (1 세션)
- `send()` 호출 중 agent 출력 경로만 `broadcast(room, ...)`로 교체
- on_token / on_tool / agent_start / agent_end / claude_token 등
- turn-taking: `room.input_lock`으로 보호, 시도 시 `room_busy` 응답

### Phase 3 — UX + 인터페이스 (1 세션)
- Snapshot 송신: 새 join 시 `room_joined` + `state_snapshot` 이벤트
- `/who` 슬래시 추가 → subscribers 목록
- `ui/index.js` 수정: `--room <name>` CLI 인자 → 헤더 주입 + busy 상태 UI

### Phase 4 — 안정화 (0.5-1 세션)
- 끊긴 ws 감지(ping/pong)
- confirm_* 주체 격리 (DQ2 옵션 D 엄격 적용)
- 에러/재접속 복구 시나리오 테스트

## 5. 위험 요소

### 동기화 버그
- `room.state.messages`가 가변 리스트. 동시 읽기/쓰기 — 단일 `input_lock`으로 직렬화되므로 실제 race는 없음. 다만 디버깅 어려움.
- 완화: `_apply_core_result` 경로를 항상 input_lock 안에서만 호출.

### 메모리 누수
- Room 참여자가 모두 나가도 `ROOMS[name]` 잔존할 경우 누수.
- 완화: finally 블록에서 `if not room.subscribers: del ROOMS[name]`.

### ws 생명주기 불일치
- broadcast 도중 일부 ws 끊김 → 예외 처리로 조용히 제거.

### Claude CLI 공유
- `ask_claude` / `run_claude`는 stdout 스트리밍. 동시 호출 불가 → claude_lock 필요. `_ollama_lock`과 유사 패턴.

## 6. 백업 기초 (이미 준비된 것)

- `harness_server.py`의 `_remote_active` 카운터 + `queue/queue_ready` 이벤트 → 큐잉 UI 재사용 가능
- `_ollama_lock`(Semaphore(1)) → `input_lock` 선례
- BB-1 6차에서 확립한 `run_in_executor` + `run_coroutine_threadsafe` sync wrapper 패턴 → broadcast에도 활용

## 7. 다음 세션 킥오프 체크리스트

1. **DQ1-DQ5 결정을 먼저 확인** — 설계가 바뀌면 구현 전부 재작성.
2. Phase 1부터 시작. `Room` 클래스 + 테스트.
3. 기존 단일 연결 동작이 깨지지 않는지 회귀 확인 — solo 모드 유지.
4. harness_core 재사용 — `slash_plan` 등 핸들러는 변경 없이 동작해야.
