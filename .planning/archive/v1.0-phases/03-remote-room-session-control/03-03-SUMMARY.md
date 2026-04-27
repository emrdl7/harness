---
phase: 03-remote-room-session-control
plan: "03"
subsystem: ui-ink-protocol-store-dispatch
tags: [pext-01, pext-02, pext-03, pext-05, rem-02, rem-03, rem-04, rem-05, diff-01, diff-03, tdd, client-side]
one_liner: "protocol.ts PEXT-01/02/05 타입 업데이트, store/room.ts wsState/reconnectAttempt/lastEventId 확장, store/messages.ts loadSnapshot action 추가, dispatch.ts from_self/agent_cancelled/event_id/loadSnapshot 처리 전부 구현"

dependency_graph:
  requires:
    - "03-01: PEXT-01~03 서버 구현 (from_self, old_content, event_id)"
    - "03-02: PEXT-04~05 서버 구현 (delta replay, cancel/agent_cancelled)"
  provides:
    - "PEXT-01: dispatch agent_start from_self 처리 → room.setActiveIsSelf"
    - "PEXT-02: ConfirmWriteMsg old_content 필드 + dispatch 전달"
    - "PEXT-05: AgentCancelledMsg 타입 + dispatch case"
    - "REM-03: loadSnapshot action + snapshotKey (Static key remount 트리거)"
    - "PEXT-03: dispatch event_id 추적 → setLastEventId"
    - "WSR-01~03: store/room.ts wsState/reconnectAttempt/lastEventId"
  affects:
    - ui-ink/src/protocol.ts
    - ui-ink/src/store/room.ts
    - ui-ink/src/store/messages.ts
    - ui-ink/src/ws/dispatch.ts

tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN 사이클 (Task 2)"
    - "unknown 캐스트 패턴으로 event_id 타입 안전 추출"
    - "role 화이트리스트 + content string 강제 변환 (T-03-03-01 threat 대응)"
    - "snapshotKey increment → Static key remount 트리거"

key_files:
  modified:
    - path: ui-ink/src/protocol.ts
      summary: "AgentStartMsg from_self?, ConfirmWriteMsg old_content?, AgentCancelledMsg 신규, RoomJoinedMsg shared/subscribers/busy 추가 (Pitfall H 수정)"
    - path: ui-ink/src/store/room.ts
      summary: "wsState/reconnectAttempt/lastEventId 필드 + setWsState/setReconnectAttempt/setLastEventId setter 추가"
    - path: ui-ink/src/store/messages.ts
      summary: "snapshotKey 필드 + loadSnapshot action 추가, appendUserMessage meta 파라미터 지원"
    - path: ui-ink/src/ws/dispatch.ts
      summary: "event_id 추적, agent_start from_self 처리, state_snapshot loadSnapshot 연결, agent_cancelled case, room_member 메시지 UI-SPEC 포맷, confirm_write oldContent 전달"
  created:
    - path: ui-ink/src/__tests__/store.messages.snapshot.test.ts
      summary: "loadSnapshot 3건 + dispatch 확장 4건 = 신규 테스트 7건 (TDD RED)"

decisions:
  - "event_id 추적을 dispatch() 시작부에 통합 — switch 외부에서 모든 메시지 타입에 공통 적용"
  - "unknown 이중 캐스트 패턴으로 event_id 타입 안전 추출 (tsc TS2352 회피)"
  - "room_joined case를 dispatch에서 members ?? []로 수정 — protocol.ts members optional과 연동"
  - "state/state_snapshot case를 분리 — state_snapshot만 loadSnapshot 호출"

metrics:
  duration: "약 15분 (2026-04-24)"
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 5
---

# Phase 03 Plan 03: Wave 2 클라이언트 기반 타입/스토어/디스패치 확장 Summary

protocol.ts PEXT-01/02/05 타입 업데이트, store/room.ts wsState/reconnectAttempt/lastEventId 확장, store/messages.ts loadSnapshot action 추가, dispatch.ts from_self/agent_cancelled/event_id/loadSnapshot 처리를 TDD 사이클로 구현하고 vitest 127건 green을 달성했습니다.

## 완료된 태스크

| Task | 이름 | 커밋 | 주요 파일 |
|------|------|------|-----------|
| 1 | protocol.ts 타입 업데이트 + store/room.ts wsState 확장 | `6095594` | protocol.ts, store/room.ts, ws/dispatch.ts (room_joined fix) |
| 2 RED | loadSnapshot + dispatch 확장 실패 테스트 | `054e4b0` | src/__tests__/store.messages.snapshot.test.ts |
| 2 GREEN | store/messages.ts loadSnapshot + dispatch.ts 확장 | `a6ff5a1` | store/messages.ts, ws/dispatch.ts |

## 구현 내용

### Task 1: protocol.ts + store/room.ts

**protocol.ts 수정 (4건):**
- `AgentStartMsg`에 `from_self?: boolean` 추가 (PEXT-01)
- `ConfirmWriteMsg`에 `old_content?: string` 추가 (PEXT-02)
- `AgentCancelledMsg` 인터페이스 신규 + `ServerMsg` union 포함 (PEXT-05)
- `RoomJoinedMsg`에 `shared: boolean`, `subscribers: number`, `busy: boolean` 추가, `members` optional로 교정 (Pitfall H 수정)

**store/room.ts 확장 (WSR-01~03):**
- `wsState: 'connected' | 'reconnecting' | 'failed'` 필드 + `setWsState` setter
- `reconnectAttempt: number` 필드 + `setReconnectAttempt` setter
- `lastEventId: number | null` 필드 + `setLastEventId` setter

**dispatch.ts room_joined 수정 (Rule 3 - 블로킹):**
- `msg.members ?? []` 처리 추가 (members optional 타입 에러 즉시 수정)

### Task 2: store/messages.ts + dispatch.ts (TDD)

**store/messages.ts 확장:**
- `snapshotKey: number` 필드 — Static key remount 트리거 (REM-03)
- `loadSnapshot(rawMessages)` action — 악성 데이터 방어 포함 (T-03-03-01):
  - `typeof m === 'object' && m !== null` 필터
  - `role` 화이트리스트 `['user','assistant','tool','system']`
  - `content` string 강제 변환 (`JSON.stringify` fallback)
  - `snapshotKey + 1` increment → Static key remount 트리거
- `appendUserMessage` meta 파라미터 지원 추가 (DIFF-02)

**dispatch.ts 확장 (7건):**
- `event_id` 추적: dispatch() 시작부에서 모든 이벤트에 적용 (PEXT-03)
- `agent_start`: `room.setActiveIsSelf(msg.from_self ?? true)` — 구버전 호환 (PEXT-01)
- `state_snapshot`: `messages.loadSnapshot(msg.messages)` 연결 (REM-03)
- `agent_cancelled` case 신규: `agentEnd + setBusy(false) + setActiveIsSelf(true) + 시스템 메시지` (PEXT-05)
- `room_member_joined/left`: UI-SPEC 포맷 `↗/↘` 교정 (REM-05)
- `confirm_write`: `oldContent: msg.old_content` 전달 (PEXT-02)
- `state/state_snapshot` case 분리 — state_snapshot만 loadSnapshot 호출

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - 블로킹] room_joined members?? [] 처리 — Task 1 범위에서 즉시 수정**
- **Found during:** Task 1 tsc 검증
- **Issue:** `RoomJoinedMsg.members`를 optional로 변경하자 `dispatch.ts:65`에서 `string[] | undefined` 타입 에러 발생
- **Fix:** `room.setRoom(msg.room, msg.members ?? [])` 처리 추가
- **Files modified:** `ui-ink/src/ws/dispatch.ts`
- **Commit:** `6095594` (Task 1 커밋에 포함)

**2. [Rule 1 - Bug] event_id TS2352 캐스팅 에러**
- **Found during:** Task 2 GREEN 단계 tsc 검증
- **Issue:** `(msg as {event_id: number})` 캐스트가 `SlashResultMsg` 등 non-overlapping 타입과 충돌
- **Fix:** `const rawMsg = msg as unknown as {event_id?: unknown}` 이중 캐스트 패턴으로 교체
- **Files modified:** `ui-ink/src/ws/dispatch.ts`
- **Commit:** `a6ff5a1` (Task 2 GREEN 커밋에 포함)

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (Task 2) | `054e4b0` | test(03-03): loadSnapshot + dispatch 확장 실패 테스트 추가 |
| GREEN (Task 2) | `a6ff5a1` | feat(03-03): store/messages.ts loadSnapshot + dispatch.ts 확장 |

RED/GREEN 게이트 커밋 순서 확인됨. Task 1은 tdd="true" 없음 (일반 auto task).

## 검증 결과

```
tsc --noEmit: 에러 0
vitest: 127 passed (기존 120 + 신규 7)
  - store.messages.snapshot.test.ts: 7/7 passed

grep 'AgentCancelledMsg' protocol.ts: 2건 (정의 + union)
grep 'snapshotKey' store/messages.ts: 3건 (interface + 초기값 + loadSnapshot 내부)
grep 'setLastEventId' dispatch.ts: 1건 (dispatch 시작부)
grep 'wsState' store/room.ts: 4건 (주석 + interface + 초기값 + setter)
grep 'lastEventId' store/room.ts: 4건 (주석 + interface + 초기값 + setter)
```

## Known Stubs

없음 — 모든 구현이 실제 동작합니다. Wave 3~4 컴포넌트들이 이 플랜의 store 계약과 dispatch를 참조할 수 있습니다.

## Threat Surface Scan

플랜의 threat_model 항목(T-03-03-01~03)이 모두 처리됐습니다:
- T-03-03-01 (Tampering): loadSnapshot에서 object 필터 + role 화이트리스트 + content string 강제 변환 완료
- T-03-03-02 (Info Disclosure): accept — event_id는 클라이언트가 resume_from으로 재사용하는 공개 값
- T-03-03-03 (Tampering): accept — from_self는 서버가 per-subscriber로 주입, 클라이언트 위조 불가

새로 추가된 네트워크 엔드포인트 없음. 기존 타입/store/dispatch 확장만 수행했습니다.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| ui-ink/src/protocol.ts 존재 | FOUND |
| ui-ink/src/store/room.ts 존재 | FOUND |
| ui-ink/src/store/messages.ts 존재 | FOUND |
| ui-ink/src/ws/dispatch.ts 존재 | FOUND |
| ui-ink/src/__tests__/store.messages.snapshot.test.ts 존재 | FOUND |
| commit 6095594 (Task 1) | FOUND |
| commit 054e4b0 (RED Task 2) | FOUND |
| commit a6ff5a1 (GREEN Task 2) | FOUND |
| tsc --noEmit 에러 0 | PASSED |
| vitest 127건 green | PASSED |
