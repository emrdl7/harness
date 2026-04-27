---
phase: 03-remote-room-session-control
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - harness_server.py
  - tests/test_harness_server.py
  - ui-ink/src/__tests__/components.observer.test.tsx
  - ui-ink/src/__tests__/components.presence.test.tsx
  - ui-ink/src/__tests__/components.statusbar.test.tsx
  - ui-ink/src/__tests__/store.messages.snapshot.test.ts
  - ui-ink/src/__tests__/userColor.test.ts
  - ui-ink/src/__tests__/ws-backoff.test.ts
  - ui-ink/src/App.tsx
  - ui-ink/src/components/ConfirmDialog.tsx
  - ui-ink/src/components/DiffPreview.tsx
  - ui-ink/src/components/Message.tsx
  - ui-ink/src/components/MessageList.tsx
  - ui-ink/src/components/ObserverOverlay.tsx
  - ui-ink/src/components/PresenceSegment.tsx
  - ui-ink/src/components/ReconnectOverlay.tsx
  - ui-ink/src/components/StatusBar.test.tsx
  - ui-ink/src/components/StatusBar.tsx
  - ui-ink/src/index.tsx
  - ui-ink/src/one-shot.ts
  - ui-ink/src/protocol.ts
  - ui-ink/src/store/messages.ts
  - ui-ink/src/store/room.ts
  - ui-ink/src/utils/userColor.ts
  - ui-ink/src/ws/client.ts
  - ui-ink/src/ws/dispatch.ts
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-24
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Phase 3 Remote Room + Session Control 구현 전반을 검토했습니다. WS backoff/재연결, 멀티유저 Presence, confirm 격리, cancel, delta replay, one-shot CLI 등 주요 기능이 전반적으로 잘 설계되었으며 DQ2/DQ3 보안 가드도 올바르게 적용되었습니다.

단, 프로토콜 계층에서 Critical 급 필드명 불일치가 1건 발견되었습니다. confirm 승인/거부가 서버에 전달되지 않아 모든 confirm이 `false`(거부)로 처리됩니다. 그 외 Warning 수준의 서버-클라 타입 불일치, 중복 broadcast, `_handle_cplan_execute`의 cancel 플래그 미리셋 등 5건이 있습니다.

---

## Critical Issues

### CR-01: confirm 응답 필드명 불일치 — 항상 거부로 처리됨

**File:** `ui-ink/src/store/confirm.ts:61` / `harness_server.py:782`

**Issue:** 클라이언트가 `{type: 'confirm_write_response', accept: boolean}` 형태로 전송하지만, 서버는 `msg.get('result', False)`로 읽습니다. `accept` 키는 서버에서 읽히지 않으므로 기본값 `False`가 항상 사용됩니다. 즉, 사용자가 `y`를 눌러도 에이전트가 파일 쓰기/bash 실행을 거부당합니다.

`protocol.ts`의 `ConfirmWriteResponse`/`ConfirmBashResponse` 인터페이스도 `accept` 필드를 정의하고 있어, 서버·클라 양쪽이 서로 다른 필드명을 사용하는 상태입니다.

**Fix:**

서버(`harness_server.py` 라인 782, 789)를 수정하거나 클라이언트의 필드명을 통일해야 합니다. 서버를 기준으로 수정하는 경우:

```python
# harness_server.py:782
state._confirm_result = msg.get('result', msg.get('accept', False))

# harness_server.py:789
state._confirm_bash_result = msg.get('result', msg.get('accept', False))
```

또는 클라이언트를 서버 기준으로 통일하는 경우 (`protocol.ts` + `confirm.ts`):

```typescript
// protocol.ts
export interface ConfirmWriteResponse { type: 'confirm_write_response'; result: boolean }
export interface ConfirmBashResponse  { type: 'confirm_bash_response';  result: boolean }

// confirm.ts resolve() 내부
response = {type: 'confirm_write_response', result: accept}
response = {type: 'confirm_bash_response',  result: accept}
```

---

## Warnings

### WR-01: `state` 메시지에 `model`/`mode` 필수 필드가 서버에서 미전송

**File:** `harness_server.py:612` / `ui-ink/src/protocol.ts:38`

**Issue:** `protocol.ts`의 `StateMsg`는 `model: string`, `mode: string`을 필수 필드로 선언하고 있습니다. 그러나 `harness_server.py`의 `_state_payload()`는 이 두 필드를 전송하지 않습니다(`working_dir`, `turns`, `indexed`, `claude_available`, `compact_count`만 전송). `dispatch.ts`가 `msg.model`, `msg.mode`를 `status.setState()`에 넘길 때 `undefined`가 그대로 전달되어 상태가 오염됩니다.

**Fix:**

프로토콜 타입에서 두 필드를 optional로 완화하거나, dispatch에서 명시적으로 방어합니다:

```typescript
// protocol.ts
export interface StateMsg {
  type: 'state'
  working_dir: string
  turns: number
  model?: string   // 서버가 미전송 — optional로 완화
  mode?: string
  ctx_tokens?: number
}
```

```typescript
// dispatch.ts case 'state':
status.setState({
  working_dir: msg.working_dir,
  turns: msg.turns,
  ...(msg.model != null && {model: msg.model}),
  ...(msg.mode  != null && {mode:  msg.mode}),
  ctx_tokens: msg.ctx_tokens,
})
```

---

### WR-02: `/learn` 완료 시 `slash_result cmd='learn'` 중복 broadcast

**File:** `harness_server.py:574` / `harness_server.py:577`

**Issue:** `/improve`와 `/learn`을 처리하는 분기에서 `/learn` 경로일 때 `broadcast(room, type='slash_result', cmd='learn')`가 라인 574와 577에서 두 번 호출됩니다. 첫 번째는 `if name == '/improve': ... else:` 분기에서 발생하고, 두 번째는 분기 밖에서 무조건 실행됩니다. 클라이언트가 이 이벤트로 UI를 갱신하면 중복 처리가 일어납니다.

```python
# 현재 (잘못됨):
if name == '/improve':
    await broadcast(room, type='slash_result', cmd='improve', ...)
else:
    await broadcast(room, type='slash_result', cmd='learn')  # 574
if result.level in ('warn', 'error') and result.notice:
    await broadcast(room, type='info', text=result.notice)
await broadcast(room, type='slash_result', cmd='learn')  # 577 — 중복!
```

**Fix:**

```python
if name == '/improve':
    await broadcast(room, type='slash_result', cmd='improve',
                    backup=result.data.get('backup', ''),
                    validation=result.data.get('validation', []))
else:
    await broadcast(room, type='slash_result', cmd='learn')
if result.level in ('warn', 'error') and result.notice:
    await broadcast(room, type='info', text=result.notice)
# 577번 라인 삭제
```

---

### WR-03: `_handle_cplan_execute` finally에서 `_cancel_requested` 미리셋

**File:** `harness_server.py:735`

**Issue:** `_handle_cplan_execute`의 `finally` 블록은 `room.busy = False`와 `room.active_input_from = None`만 리셋하고 `room._cancel_requested = False`를 리셋하지 않습니다. cplan 실행 도중 cancel이 요청된 경우 `_cancel_requested`가 `True`인 채로 남아, 다음 에이전트 실행이 즉시 중단될 수 있습니다(`on_token` 콜백에서 체크). `_handle_input`의 `finally`는 올바르게 처리하고 있습니다(라인 721).

**Fix:**

```python
finally:
    room.busy = False
    room.active_input_from = None
    room._cancel_requested = False  # B2: 다음 실행을 위해 리셋 추가
```

---

### WR-04: `room_member_left` 서버 브로드캐스트에 `user` 필드 누락

**File:** `harness_server.py:902` / `ui-ink/src/protocol.ts:27` / `ui-ink/src/ws/dispatch.ts:92`

**Issue:** 서버가 `room_member_left` 이벤트를 broadcast할 때 `subscribers` 카운트만 보내고 `user` 필드를 포함하지 않습니다:

```python
await broadcast(room, type='room_member_left',
                subscribers=len(room.subscribers))
```

그러나 `protocol.ts`의 `RoomMemberLeftMsg`는 `user: string`을 필수 필드로 선언하고, `dispatch.ts`의 `case 'room_member_left':`는 `msg.user`로 `removeMember()`와 시스템 메시지에 사용합니다. `user`가 `undefined`이면 `removeMember(undefined)` 호출로 members 배열이 잘못 관리됩니다.

**Fix:**

서버에서 `user` 필드를 추가합니다. `room_member_left` 시점에는 이미 `room.subscribers.discard(ws)`가 완료됐으므로 `ws_token`을 finally 스코프에서 접근합니다:

```python
await broadcast(room, type='room_member_left',
                subscribers=len(room.subscribers),
                user=_token_hash(ws_token) if ws_token else '')
```

---

### WR-05: `index.tsx` argv 파싱에서 `skipIndices`의 offset이 상황에 따라 부정확

**File:** `ui-ink/src/index.tsx:54`

**Issue:** `skipIndices`에는 `process.argv` 전체 배열의 인덱스를 저장하지만 (`roomIdx`, `resumeIdx`는 `process.argv`의 인덱스), 57번 라인의 `find` 콜백에서는 `process.argv.slice(2)`의 `i`에 `+ 2`를 더해 비교합니다:

```typescript
const skipIndices = new Set<number>()
if (roomIdx > -1) { skipIndices.add(roomIdx); skipIndices.add(roomIdx + 1) }
// ...
const query = process.argv.slice(2).find(
  (a, i) => !a.startsWith('--') && !skipIndices.has(i + 2),  // i + 2 = 원본 argv 인덱스
)
```

이 로직 자체는 올바르지만, `process.argv[0]`=`node`, `process.argv[1]`=스크립트 경로 가정에 의존합니다. `bun run` 환경에서 `process.argv`의 구조가 다를 경우(예: wrapper 삽입) query가 잘못 필터링될 수 있습니다. 또한 `--room my-room "actual query"` 형태에서 `my-room`이 `--` 접두가 없으므로 query로 잘못 파싱될 수 있습니다(`skipIndices`는 `roomIdx+1`을 제외하지만 `roomIdx`는 `--room` 자체의 인덱스).

**Fix:**

`skipIndices.has(roomIdx + 1)`이 `--room` 다음 값의 argv 인덱스를 올바르게 제외하고 있으므로 현재 로직은 의도대로 동작합니다. 다만 명확성을 위해 변수명을 `argvSkipIndices`로 변경하거나, `slice(2)` 이후 인덱스를 직접 다루도록 리팩토링을 권장합니다:

```typescript
const argvSlice = process.argv.slice(2)
const skipSliceIndices = new Set<number>()
if (roomIdx > -1) {
  skipSliceIndices.add(roomIdx - 2)
  skipSliceIndices.add(roomIdx - 1)
}
if (resumeIdx > -1) {
  skipSliceIndices.add(resumeIdx - 2)
  skipSliceIndices.add(resumeIdx - 1)
}
const query = argvSlice.find(
  (a, i) => !a.startsWith('--') && !skipSliceIndices.has(i),
)
```

---

## Info

### IN-01: `PresenceSegment`에서 전체 토큰을 UI에 표시

**File:** `ui-ink/src/components/PresenceSegment.tsx:29`

**Issue:** `members` 배열에 저장된 값은 서버가 보내는 `_token_hash(ws_token)[:8]` 해시값이지만, 본인 판별 시 `m === process.env['HARNESS_TOKEN']`으로 비교합니다. 토큰이 짧거나 해시값과 우연히 일치하는 경우는 낮지만, 실제 비교 대상이 전체 토큰이 아닌 해시 앞 8자여야 하므로 `userColor`와 동일하게 해시 비교를 사용해야 일관성이 유지됩니다. 현재는 본인 판별이 항상 `false`가 되어 'me' 레이블이 표시되지 않습니다.

**Fix:**

```typescript
// PresenceSegment.tsx
import {hashToken} from '../utils/userColor.js'  // 또는 _token_hash 클라이언트 사이드 포트

const myHash = hashToken(process.env['HARNESS_TOKEN'] ?? '')
// ...
<Text color={userColor(m)} bold>{m === myHash ? 'me' : m}</Text>
```

---

### IN-02: `StatusBar.tsx`에서 `getState()` 직접 호출로 `ctxPct` 계산

**File:** `ui-ink/src/components/StatusBar.tsx:68`

**Issue:** 레이아웃 예산 계산을 위해 `useStatusStore.getState().ctxTokens`를 구독 없이 직접 읽습니다. 이는 렌더 시점의 스냅샷이므로 `ctxTokens`가 변경되어도 `StatusBar` 본체가 재렌더되지 않는 한 `ctxPct` 레이아웃 계산이 stale해집니다. `CtxMeter`의 렌더 결과와 레이아웃 계산에 사용된 `ctxPct`가 불일치할 수 있습니다(예: 세그먼트가 표시되어야 할 때 드롭될 수 있음). 코드 주석도 이를 "구독 없음"으로 명시하고 있으나, 버그 가능성이 있습니다.

**Fix:**

`ctxTokens`를 `StatusBar`의 `useShallow` 구독에 포함하거나, 레이아웃 계산에서 `ctxPct`가 있을 때 고정 길이(예: 8자)를 사용합니다:

```typescript
// 레이아웃 계산 전용 고정 추정치 사용
const ctxSegLen = ctxPct !== undefined ? 8 : 0  // 'ctx 100%' = 8자
```

---

### IN-03: `one-shot.ts`에서 `agent_cancelled` 이벤트 미처리

**File:** `ui-ink/src/one-shot.ts:77`

**Issue:** `one-shot.ts`의 switch 문에 `agent_cancelled` 케이스가 없습니다. one-shot 모드에서 cancel이 발생하면(서버에서 `agent_cancelled` 전송) `default:` 로 떨어져 무시되고, `agent_end`도 수신되지 않으면 30초 타임아웃 후 에러로 종료됩니다.

**Fix:**

```typescript
case 'agent_cancelled':
  if (!resolved) {
    resolved = true
    clearTimeout(timeout)
    process.stdout.write('\n')
    ws.close()
    reject(new Error('[harness] 에이전트 실행이 취소되었습니다'))
  }
  break
```

---

_Reviewed: 2026-04-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
