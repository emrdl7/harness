# PROTOCOL — harness WebSocket 프로토콜 명세

**버전:** v1 (Phase 3 확장 완료)
**대상:** AI 에이전트(Claude, Codex 등) 및 서드파티 클라이언트 구현자

모든 메시지는 JSON UTF-8. 서버: `harness_server.py`. 클라이언트 레퍼런스: `ui-ink/src/`.

---

## 연결

```
ws://host:7891
```

### 연결 헤더

| 헤더 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `x-harness-token` | 필수 | string | 인증 토큰 |
| `x-harness-room` | 선택 | string | 공유 Room 이름. 미포함 시 단독 세션 |
| `x-resume-from` | 선택 | string(integer) | PEXT-04: 마지막 수신 `event_id`. delta replay 요청 |
| `x-resume-session` | 선택 | string | SES-02: 재개할 세션 ID |

---

## ServerMsg — 서버 → 클라이언트

모든 서버 메시지에 `event_id: number` 필드가 자동 부여됩니다 (PEXT-03).

### 스트리밍

```typescript
interface TokenMsg        { type: 'token';        event_id: number; text: string }
interface ClaudeTokenMsg  { type: 'claude_token'; event_id: number; text: string }
```

- `token`: harness 에이전트가 생성한 텍스트 토큰 (스트리밍 중)
- `claude_token`: Claude API가 직접 반환한 토큰

### 에이전트 라이프사이클

```typescript
interface AgentStartMsg     { type: 'agent_start';     event_id: number; from_self?: boolean }  // PEXT-01
interface AgentEndMsg       { type: 'agent_end';       event_id: number }
interface AgentCancelledMsg { type: 'agent_cancelled'; event_id: number }                         // PEXT-05
interface ClaudeStartMsg    { type: 'claude_start';    event_id: number }
interface ClaudeEndMsg      { type: 'claude_end';      event_id: number }
```

- `agent_start.from_self`: true = 본인 입력으로 시작된 턴, false = 다른 Room 멤버 입력 (PEXT-01 관전 모드 판정)
- `agent_cancelled`: PEXT-05 cancel 메시지 처리 후 에이전트 asyncio task 중단 완료 알림

### 툴 호출

```typescript
interface ToolStartMsg { type: 'tool_start'; event_id: number; name: string; args: Record<string, unknown> }
interface ToolEndMsg   { type: 'tool_end';   event_id: number; name: string; result: string }
```

### 상태

```typescript
interface ErrorMsg { type: 'error'; event_id: number; text: string }  // .text 사용, .message 아님
interface InfoMsg  { type: 'info';  event_id: number; text: string }
interface ReadyMsg { type: 'ready'; event_id: number; room: string }
interface QuitMsg  { type: 'quit';  event_id: number }
interface PongMsg  { type: 'pong';  event_id: number }
```

```typescript
interface StateMsg {
  type: 'state'
  event_id: number
  working_dir: string
  model: string
  mode: string
  turns: number
  ctx_tokens?: number
}

interface StateSnapshotMsg {
  type: 'state_snapshot'
  event_id: number
  working_dir: string
  model: string
  mode: string
  turns: number
  ctx_tokens?: number
  messages?: unknown[]  // 과거 메시지 히스토리 (Room join 시 전송)
}
```

### Room

```typescript
interface RoomJoinedMsg {
  type: 'room_joined'
  event_id: number
  room: string
  shared: boolean
  subscribers: number
  busy: boolean
  members?: string[]  // 현재 접속 중인 멤버 토큰 해시 목록
}

interface RoomMemberJoinedMsg { type: 'room_member_joined'; event_id: number; user: string }
interface RoomMemberLeftMsg   { type: 'room_member_left';   event_id: number; user: string }
interface RoomBusyMsg         { type: 'room_busy';          event_id: number }
```

### 확인 다이얼로그

```typescript
interface ConfirmWriteMsg {
  type: 'confirm_write'
  event_id: number
  path: string
  old_content?: string  // PEXT-02: 기존 파일 내용 (diff 미리보기용)
}

interface ConfirmBashMsg  { type: 'confirm_bash';  event_id: number; command: string }
interface CplanConfirmMsg { type: 'cplan_confirm'; event_id: number; task: string }
```

### 기타

```typescript
interface SlashResultMsg { type: 'slash_result'; event_id: number; cmd: string; [key: string]: unknown }
interface QueueMsg       { type: 'queue';         event_id: number; position: number }
interface QueueReadyMsg  { type: 'queue_ready';   event_id: number }
```

---

## ClientMsg — 클라이언트 → 서버

### 입력

```typescript
interface InputMsg { type: 'input'; text: string }
```

### 확인 응답

```typescript
interface ConfirmWriteResponse { type: 'confirm_write_response'; accept: boolean }
interface ConfirmBashResponse  { type: 'confirm_bash_response';  accept: boolean }
```

> **주의 — CR-01 버그:** 서버(`harness_server.py:782`)는 `result` 필드를 읽지만
> 클라이언트는 `accept` 필드를 전송합니다. 현재 confirm 승인이 항상 거부로 처리됩니다.
> Known Bugs 섹션 참조.

### 슬래시 명령

```typescript
interface SlashMsg { type: 'slash'; name: string; args?: string }
```

### 제어

```typescript
interface PingMsg   { type: 'ping' }
interface CancelMsg { type: 'cancel' }  // PEXT-05: 실행 중 에이전트 취소 요청
```

---

## 연결 흐름

### 기본 REPL 흐름

```
클라  →  서버: WebSocket 연결 (x-harness-token 헤더)
서버  →  클라: ready
클라  →  서버: {type:'input', text:'질문'}
서버  →  클라: agent_start (from_self: true)
서버  →  클라: token × N (스트리밍)
서버  →  클라: agent_end
```

### Room 흐름 (PEXT-01~04)

```
클라  →  서버: WebSocket 연결 (x-harness-room: 'team')
서버  →  클라: state_snapshot (히스토리 + 현재 상태)
서버  →  클라: room_joined {subscribers: 2, members: [...]}
(다른 클라가 입력 시)
서버  →  클라: agent_start (from_self: false)  ← 관전자 판정
서버  →  클라: token × N
서버  →  클라: agent_end
```

### 재연결 (PEXT-04)

```
클라  →  서버: WebSocket 연결 (x-resume-from: '42')
서버  →  클라: event_id 43부터 delta replay
```

---

## PEXT 확장 목록 (Phase 3)

| 코드 | 설명 |
|------|------|
| PEXT-01 | `agent_start.from_self?: boolean` — 관전 모드 판정 |
| PEXT-02 | `confirm_write.old_content?: string` — diff 미리보기 |
| PEXT-03 | 모든 서버 메시지에 monotonic `event_id` + Room당 60초 ring buffer |
| PEXT-04 | `x-resume-from` 헤더 파싱 + ring buffer delta replay |
| PEXT-05 | `cancel` ClientMsg + asyncio task 안전 중단 + `agent_cancelled` 응답 |

---

## Known Bugs

### CR-01: confirm_write_response 필드명 불일치

**심각도:** 차단 (confirm 기능 전체 무력화)

**현상:** 사용자가 y 키를 눌러도 에이전트가 파일 쓰기/bash 실행을 항상 거부함.

**원인:**
- 클라이언트 `confirm.ts:61`: `{type: 'confirm_write_response', accept: boolean}` 전송
- 서버 `harness_server.py:782`: `msg.get('result', False)` — `accept` 키 무시

**수정 방법 (서버):**
```python
# harness_server.py:782, 789
state._confirm_result = msg.get('result', msg.get('accept', False))
state._confirm_bash_result = msg.get('result', msg.get('accept', False))
```

또는 클라이언트에서 `result: accept` 로 필드명 통일.
