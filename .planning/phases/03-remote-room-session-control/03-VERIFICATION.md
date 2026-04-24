---
phase: 03-remote-room-session-control
verified: 2026-04-24T16:28:00Z
status: human_needed
score: 22/24 must-haves verified
overrides_applied: 0
gaps: []
deferred:
  - truth: "ws://127.0.0.1 로컬 시나리오와 ws://external-host 원격 시나리오가 동일한 통합 테스트에서 green (REM-06)"
    addressed_in: "Phase 4"
    evidence: "ROADMAP.md Phase 3 SC-6: 'ws://127.0.0.1 로컬 시나리오와 ws://external-host 원격 시나리오가 동일한 통합 테스트 시퀀스에서 green (로컬-원격 동등성 — REM-06)' / Phase 4 SC-1에서 Fake Harness WS 서버 통합 테스트(room busy, reconnect delta, 3인 동시 재접속 시뮬) 명시"
  - truth: "CR-01: confirm_write_response accept 필드 — 서버가 result 로 읽어 항상 false 처리됨"
    addressed_in: "Phase 4 또는 별도 수정"
    evidence: "03-REVIEW.md CR-01: 클라이언트 accept 필드 vs 서버 msg.get('result', False) 불일치. Phase 4 TST-02 통합 테스트(confirm_write accept 시나리오)에서 자동 발견 예정"
human_verification:
  - test: "재연결 오버레이 동작 확인 (SC-1) — APPROVED (수동 검증 완료)"
    expected: "서버 강제 종료 후 disconnected — reconnecting... (attempt N/10) 노란 텍스트 → 서버 재시작 후 오버레이 사라지고 InputArea 복귀"
    why_human: "SC-1은 03-06-SUMMARY.md에 'APPROVED'로 기록됨. 재검증 불필요하나 기록 유지"
  - test: "SC-2: Presence 세그먼트 (REM-02) — 멀티 터미널 환경 미구성으로 DEFERRED"
    expected: "두 터미널 HARNESS_ROOM=test bun start 각각 실행 → StatusBar에 🟢 2명 [alice·me] 확인 → 한 쪽 종료 시 ↘ ... 님이 나갔습니다 시스템 메시지 + 카운트 1명으로 감소"
    why_human: "멀티 터미널 WS 연결 환경이 필요한 End-to-End 시나리오"
  - test: "SC-3: 관전 모드 (REM-04) — 멀티 터미널 환경 미구성으로 DEFERRED"
    expected: "같은 room 두 터미널 접속 → 한 쪽 질문 입력 시 다른 쪽에서 {입력자} 입력 중... 오버레이 확인 + InputArea disabled → 에이전트 완료 후 관전자 InputArea 복귀"
    why_human: "실시간 멀티 유저 WS 동작 — 자동 검증 불가"
  - test: "SC-4: one-shot CLI (SES-01) — 환경 미구성으로 DEFERRED"
    expected: "HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=<token> harness '안녕하세요?' → ANSI 없이 텍스트 응답 출력 후 즉시 종료"
    why_human: "실제 서버 연결 및 LLM 응답 필요"
  - test: "SC-5: Ctrl+C cancel 동작 (WSR-04) — 환경 미구성으로 DEFERRED"
    expected: "에이전트 실행 중 Ctrl+C 1회 → 취소 요청 중… 시스템 메시지 + 에이전트 중단 + busy 해제 후 InputArea 복귀"
    why_human: "실시간 에이전트 실행 + 취소 흐름 — 자동 검증 불가"
  - test: "SC-6: DiffPreview 실제 diff 확인 (PEXT-02) — 환경 미구성으로 DEFERRED"
    expected: "서버가 파일 수정 confirm_write 요청 시 ConfirmDialog에 실제 diff ± 라인 표시 (placeholder 아닌 실제 변경 내용)"
    why_human: "실제 서버 파일 수정 작업 흐름 필요 — 또한 CR-01 이슈로 현재 confirm 승인 자체가 항상 거부로 처리되므로 CR-01 수정 후 검증 필요"
  - test: "CR-01: confirm_write_response accept/result 필드 불일치 — 기능 차단 버그"
    expected: "사용자가 y 입력 시 confirm_write_response result: true 가 서버로 전달되어 파일 쓰기가 허용됨"
    why_human: "코드 수정이 필요한 알려진 버그. harness_server.py:782에서 msg.get('result', msg.get('accept', False)) 로 수정하거나 클라이언트 confirm.ts에서 result: accept 로 필드명 통일 필요. 자동 테스트에서는 잡히지 않음 (현재 단위 테스트 미비)"
---

# Phase 3: Remote Room + Session Control Verification Report

**Phase Goal:** Remote Room + Session Control — WS 프로토콜 확장(PEXT-01~05), 재연결 backoff(WSR-01~04), Room Presence(REM-01~06), Session resume(SES-01~04), Diff 미리보기(DIFF-01~05)
**Verified:** 2026-04-24T16:28:00Z
**Status:** human_needed
**Re-verification:** No — 최초 검증

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PEXT-01: agent_start per-subscriber from_self 분기 | ✓ VERIFIED | `harness_server.py:137` `_broadcast_agent_start()` 함수 존재, `run_agent():303` 호출. `dispatch.ts:39` `room.setActiveIsSelf(msg.from_self ?? true)` |
| 2 | PEXT-02: confirm_write old_content 필드 추가 | ✓ VERIFIED | `harness_server.py:259` `send(..., old_content=_read_existing_file(path))`. `protocol.ts:14` `old_content?: string`. `DiffPreview.tsx:5` `structuredPatch` 호출 |
| 3 | PEXT-03: broadcast() event_id 자동 부여 + ring buffer | ✓ VERIFIED | `harness_server.py:96-102` event_counter 증가, ring buffer append, TTL cleanup. `Room:192-193` `event_counter`/`event_buffer` 필드 |
| 4 | PEXT-04: x-resume-from 헤더 파싱 + delta replay | ✓ VERIFIED | `harness_server.py:818-822` isdigit() + 2^31 상한선 검증. `:861-863` ring buffer 필터 재송신 |
| 5 | PEXT-05: cancel 메시지 + asyncio task 안전 중단 | ✓ VERIFIED | `harness_server.py:777` `elif t == 'cancel':`. `:794-803` DQ2 가드 + `_cancel_requested=True` + `task.cancel()` + `agent_cancelled` broadcast |
| 6 | WSR-01: jitter exponential backoff (10회, 30초 cap) | ✓ VERIFIED | `client.ts:109` `_scheduleReconnect()`. `delay = min(1000 * 2^n * (0.5+rand*0.5), 30000)`. attempts >= 10 → setWsState('failed') |
| 7 | WSR-02: 재연결 중 ReconnectOverlay 표시 | ✓ VERIFIED | `App.tsx:115-118` `wsState === 'reconnecting'` → `<ReconnectOverlay>`. SC-1 수동 검증 APPROVED |
| 8 | WSR-03: 재연결 시 x-resume-from lastEventId 헤더 포함 | ✓ VERIFIED | `client.ts:41` `if (lastEventId != null) headers['x-resume-from'] = String(lastEventId)` |
| 9 | WSR-04: Ctrl+C cancel 메시지 전송 (stub 교정) | ✓ VERIFIED | `App.tsx:81` `clientRef.current?.send({type: 'cancel'})`. stub `{type:'input', text:'/cancel'}` 제거 확인 |
| 10 | REM-01: x-harness-room 헤더로 방 지정 | ✓ VERIFIED | `client.ts:35` room 헤더 추가. `index.tsx:50-51` --room argv 파싱 |
| 11 | REM-02: Presence 렌더 — StatusBar PresenceSegment | ✓ VERIFIED | `StatusBar.tsx:10,132` PresenceSegment import + render. `PresenceSegment.tsx` 존재 + useRoomStore 구독 |
| 12 | REM-03: state_snapshot Static key remount | ✓ VERIFIED | `MessageList.tsx:11-20` snapshotKey 구독 + `<Static key={snapshotKey}>`. `messages.ts:114` loadSnapshot action |
| 13 | REM-04: 관전 모드 ObserverOverlay 치환 | ✓ VERIFIED | `App.tsx:122-124` `!activeIsSelf` → `<ObserverOverlay>`. ObserverOverlay.tsx 존재 |
| 14 | REM-05: join/leave 시스템 메시지 | ✓ VERIFIED | `dispatch.ts:room_member_joined/left` `↗/↘ ... 님이 참여/나갔습니다` appendSystemMessage |
| 15 | REM-06: 로컬-원격 동등성 통합 테스트 | DEFERRED | Phase 4 TST-02에서 room.integration.test.ts 자동 검증 예정 (ROADMAP.md SC-6) |
| 16 | SES-01: one-shot CLI | ✓ VERIFIED | `one-shot.ts` 존재, `runOneShot()` export. `index.tsx:70-77` dynamic import + 실행 |
| 17 | SES-02: --resume 세션 로드 | ✓ VERIFIED | `harness_server.py:824` x-resume-session 파싱 + sess.load(). `index.tsx:79-82` --resume 파싱 + env 설정. `App.tsx` HARNESS_RESUME_SESSION → resumeSession 전달 |
| 18 | SES-03: --room + 질문 one-shot 조합 | ✓ VERIFIED | `index.tsx:50-77` --room + query 파싱 조합, runOneShot에 room 전달 |
| 19 | SES-04: terminal resize useStdout().stdout.on('resize') | ✓ VERIFIED | `App.tsx:62-73` resize 핸들러 + ED3 clear |
| 20 | DIFF-01: 관전 모드 라이브 스트리밍 | ✓ VERIFIED | ObserverOverlay가 InputArea를 치환. from_self 기반 activeIsSelf로 관전자 판정 |
| 21 | DIFF-02: author prefix room 모드 | ✓ VERIFIED | `Message.tsx:86-104` roomName + user role → `[authorLabel]` prefix + userColor |
| 22 | DIFF-03: Confirm 관전 뷰 | ✓ VERIFIED | `App.tsx:119-121` confirmMode + ConfirmDialog 내부 activeIsSelf 분기로 관전자 read-only |
| 23 | DIFF-04: 사용자 색 해시 | ✓ VERIFIED | `userColor.ts` djb2 _hash + PALETTE 8색 + 자기 자신=cyan. PresenceSegment/Message/ObserverOverlay에서 사용 |
| 24 | DIFF-05: --room + 질문 one-shot (SES-03과 동일) | ✓ VERIFIED | SES-03과 동일 구현. index.tsx --room + query 조합 |

**Score:** 23/24 truths verified (REM-06은 Phase 4 deferred, 검증 가능한 23개 중 23개 통과)

---

### Deferred Items

Phase 4에서 처리 예정인 항목입니다.

| # | 항목 | 처리 Phase | 근거 |
|---|------|-----------|------|
| 1 | REM-06: 로컬-원격 동등성 통합 테스트 | Phase 4 | ROADMAP.md Phase 4 SC-1: "Fake Harness WS 서버 통합(room busy, reconnect delta, 3인 동시 재접속 시뮬)". 03-06-PLAN.md success_criteria #10: "Phase 4 TST-02에서 자동 검증 이관 (W2)" |
| 2 | CR-01: confirm 응답 accept/result 필드 불일치 | Phase 4 / 즉시 수정 권장 | Phase 4 TST-02에서 confirm_write accept 통합 테스트로 자동 발견 예정. 단, 현재 y 키 입력이 항상 거부로 처리되므로 Phase 4 이전에 수정 권장 |

---

### Required Artifacts

| Artifact | 제공 기능 | Status | Details |
|----------|----------|--------|---------|
| `harness_server.py` | PEXT-01~05 WS 프로토콜 확장 | ✓ VERIFIED | event_counter, event_buffer, _broadcast_agent_start, _read_existing_file, _token_hash, cancel 처리, delta replay 전부 구현 |
| `tests/test_harness_server.py` | PEXT-01~05 + SES-02 단위 테스트 | ✓ VERIFIED | pytest 260건 green. TestEventBuffer(4), TestAgentStartFromSelf(3), TestConfirmWriteOldContent(2), TestDeltaReplay(10), TestCancelTask(7) |
| `ui-ink/src/protocol.ts` | PEXT-01/02/05 타입 업데이트 | ✓ VERIFIED | AgentStartMsg.from_self?, ConfirmWriteMsg.old_content?, AgentCancelledMsg, RoomJoinedMsg.subscribers:number |
| `ui-ink/src/store/room.ts` | wsState/reconnectAttempt/lastEventId | ✓ VERIFIED | 3개 필드 + setWsState/setReconnectAttempt/setLastEventId setter |
| `ui-ink/src/store/messages.ts` | loadSnapshot action + snapshotKey | ✓ VERIFIED | snapshotKey 필드 + loadSnapshot(rawMessages) action |
| `ui-ink/src/ws/dispatch.ts` | dispatch 확장 (from_self, loadSnapshot, agent_cancelled, event_id) | ✓ VERIFIED | 모든 4개 연결 확인 |
| `ui-ink/src/utils/userColor.ts` | djb2 해시 + PALETTE 8색 순수함수 | ✓ VERIFIED | 파일 존재, PALETTE 8색, _hash(), userColor() |
| `ui-ink/src/components/PresenceSegment.tsx` | StatusBar Presence 세그먼트 | ✓ VERIFIED | solo null, room '🟢 N명 [...]' 렌더 |
| `ui-ink/src/components/ReconnectOverlay.tsx` | 재연결 InputArea 치환 | ✓ VERIFIED | attempt → yellow, failed → red |
| `ui-ink/src/components/ObserverOverlay.tsx` | 관전자 InputArea 치환 | ✓ VERIFIED | username 색 + dimColor italic '입력 중...' |
| `ui-ink/src/ws/client.ts` | jitter backoff + resume_from 헤더 | ✓ VERIFIED | _scheduleReconnect() + x-resume-from 헤더 + _closed 플래그 |
| `ui-ink/src/one-shot.ts` | one-shot WS 경량 클라이언트 | ✓ VERIFIED | runOneShot() — ready→input→token→agent_end 흐름 |
| `ui-ink/src/index.tsx` | argv 파싱 확장 (one-shot + --resume + --room) | ✓ VERIFIED | one-shot stub 제거, 파싱 로직 구현 |
| `ui-ink/src/App.tsx` | 치환 우선순위 + cancel 교정 | ✓ VERIFIED | reconnecting>failed>confirm>observer>input 순서 |
| `ui-ink/src/components/StatusBar.tsx` | PresenceSegment 연결 | ✓ VERIFIED | import + render 2건 |
| `ui-ink/src/components/Message.tsx` | author prefix room 모드 | ✓ VERIFIED | roomName + user role → [authorLabel] prefix |
| `ui-ink/src/components/MessageList.tsx` | snapshotKey Static key | ✓ VERIFIED | `<Static key={snapshotKey}>` |
| `ui-ink/src/components/DiffPreview.tsx` | old_content structuredPatch diff | ✓ VERIFIED | structuredPatch import + oldContent prop + diff 렌더 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `dispatch.ts:agent_start case` | `store/room.ts:setActiveIsSelf` | `msg.from_self ?? true` | ✓ WIRED | dispatch.ts:39 |
| `dispatch.ts:state_snapshot case` | `store/messages.ts:loadSnapshot` | `msg.messages 배열` | ✓ WIRED | dispatch.ts:122 |
| `dispatch.ts(모든 case)` | `store/room.ts:setLastEventId` | `event_id 필드 추적` | ✓ WIRED | dispatch.ts:19 — rawMsg.event_id 추적 |
| `client.ts:ws.on('close')` | `_scheduleReconnect()` | jitter backoff | ✓ WIRED | client.ts:74-75 |
| `client.ts:connect()` | `store/room.ts:lastEventId` | x-resume-from 헤더 | ✓ WIRED | client.ts:40-41 |
| `index.tsx` | `one-shot.ts:runOneShot()` | dynamic import + query | ✓ WIRED | index.tsx:70-77 |
| `App.tsx` | `store/room.ts:wsState` | useRoomStore(s => s.wsState) | ✓ WIRED | App.tsx:27 |
| `App.tsx` | `ReconnectOverlay.tsx` | wsState === 'reconnecting' | ✓ WIRED | App.tsx:115-118 |
| `StatusBar.tsx` | `PresenceSegment.tsx` | render: () => `<PresenceSegment />` | ✓ WIRED | StatusBar.tsx:132 |
| `MessageList.tsx` | `store/messages.ts:snapshotKey` | `Static key={snapshotKey}` | ✓ WIRED | MessageList.tsx:20 |
| `harness_server.py:run_agent()` | `_broadcast_agent_start()` | per-subscriber from_self 분기 | ✓ WIRED | harness_server.py:303 |
| `harness_server.py:broadcast()` | `Room.event_buffer` | event_counter 증가 + deque append | ✓ WIRED | harness_server.py:96-99 |
| `harness_server.py:_run_session()` | `Room.event_buffer` | x-resume-from 헤더 → ring buffer delta 재송신 | ✓ WIRED | harness_server.py:861-863 |
| `harness_server.py:_dispatch_loop()` | `room.input_tasks` | cancel 케이스 → task.cancel() | ✓ WIRED | harness_server.py:794-803 |
| `ui-ink/src/store/confirm.ts` | `harness_server.py` | confirm_write_response accept 필드 | ✗ BROKEN (CR-01) | confirm.ts:61 `accept: boolean` vs harness_server.py:782 `msg.get('result', False)`. 항상 거부로 처리됨 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `PresenceSegment.tsx` | members, roomName | store/room.ts (setRoom, addMember via dispatch) | dispatch.ts:room_member_joined → room.addMember(msg.user) → 서버 _token_hash()로 실제 값 | ✓ FLOWING |
| `ReconnectOverlay.tsx` | attempt, failed (props) | App.tsx → useRoomStore.wsState, reconnectAttempt → client.ts _scheduleReconnect() | 실제 WS close 이벤트 트리거 | ✓ FLOWING |
| `ObserverOverlay.tsx` | username (prop) | App.tsx → activeInputFrom → dispatch agent_start → room.setActiveInputFrom | 서버 agent_start per-subscriber | ✓ FLOWING |
| `DiffPreview.tsx` | oldContent | ConfirmDialog.tsx → store/confirm.ts payload.oldContent → dispatch confirm_write → msg.old_content | 서버 _read_existing_file(path) 실제 파일 내용 | ✓ FLOWING (단, CR-01로 confirm 승인이 실제로 전달되지 않음) |
| `MessageList.tsx` | completedMessages, snapshotKey | store/messages.ts → loadSnapshot (state_snapshot 수신 시) | 서버 state_snapshot messages 배열 — 실제 세션 히스토리 | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| vitest 146건 green | `cd ui-ink && bun run test` | 21 Test Files, 146 Tests passed | ✓ PASS |
| tsc --noEmit green | `cd ui-ink && bun run tsc --noEmit` | 에러 0 | ✓ PASS |
| pytest 260건 green | `.venv/bin/python -m pytest -x --tb=short` | 260 passed | ✓ PASS |
| harness_server.py event_counter 존재 | `grep -n 'event_counter' harness_server.py` | Room:192 + broadcast:96,97 | ✓ PASS |
| _broadcast_agent_start 존재 + 호출 | `grep -n '_broadcast_agent_start' harness_server.py` | 함수 정의:137 + run_agent():303 | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PEXT-01 | 03-01 | agent_start from_self: bool 필드 | ✓ SATISFIED | harness_server.py:137 _broadcast_agent_start() + dispatch.ts:39 |
| PEXT-02 | 03-01 | confirm_write old_content?: string 필드 | ✓ SATISFIED | harness_server.py:259 + DiffPreview.tsx structuredPatch |
| PEXT-03 | 03-01 | monotonic event_id + 60초 ring buffer | ✓ SATISFIED | harness_server.py:96-102, Room:192-193 |
| PEXT-04 | 03-02 | x-resume-from 헤더 파싱 + delta replay | ✓ SATISFIED | harness_server.py:818-822, 861-863 |
| PEXT-05 | 03-02 | cancel 메시지 + asyncio task 안전 중단 | ✓ SATISFIED | harness_server.py:777-803 |
| REM-01 | 03-06 | x-harness-room 헤더로 방 지정 | ✓ SATISFIED | client.ts:35 + index.tsx --room 파싱 |
| REM-02 | 03-03, 03-04, 03-06 | Presence 렌더 StatusBar 세그먼트 | ✓ SATISFIED | PresenceSegment.tsx + StatusBar.tsx:132 |
| REM-03 | 03-03, 03-06 | state_snapshot Static key remount | ✓ SATISFIED | MessageList.tsx:20 key={snapshotKey} |
| REM-04 | 03-03, 03-04, 03-06 | 관전 모드 InputArea disabled + 오버레이 | ✓ SATISFIED | App.tsx:122-124 ObserverOverlay |
| REM-05 | 03-03 | join/leave 시스템 메시지 | ✓ SATISFIED | dispatch.ts room_member_joined/left appendSystemMessage |
| REM-06 | 03-06 | 로컬-원격 동등성 통합 테스트 | DEFERRED | Phase 4 TST-02 이관 (03-PLAN-06 success_criteria #10) |
| SES-01 | 03-05 | one-shot CLI | ✓ SATISFIED | one-shot.ts + index.tsx:70-77 |
| SES-02 | 03-02, 03-05, 03-06 | --resume 세션 로드 REPL | ✓ SATISFIED | x-resume-session 파싱 + sess.load() + index.tsx:79-82 |
| SES-03 | 03-05 | --room + 질문 one-shot 조합 | ✓ SATISFIED | index.tsx --room + query 조합 |
| SES-04 | 03-06 | terminal resize useStdout().stdout.on('resize') | ✓ SATISFIED | App.tsx:62-73 |
| WSR-01 | 03-05 | jitter exponential backoff (10회, 30초 cap) | ✓ SATISFIED | client.ts:109 _scheduleReconnect() |
| WSR-02 | 03-04, 03-06 | 재연결 중 ReconnectOverlay 표시 | ✓ SATISFIED | App.tsx:115-118 + SC-1 수동 승인 |
| WSR-03 | 03-05 | resume_from 헤더 delta 재요청 | ✓ SATISFIED | client.ts:41 + harness_server.py:861-863 |
| WSR-04 | 03-06 | Ctrl+C cancel 메시지 전송 | ✓ SATISFIED | App.tsx:81 {type:'cancel'} |
| DIFF-01 | 03-04, 03-06 | 관전자 라이브 스트리밍 관전 | ✓ SATISFIED | ObserverOverlay + from_self 기반 activeIsSelf |
| DIFF-02 | 03-03, 03-06 | user 메시지 [author] prefix | ✓ SATISFIED | Message.tsx:86-104 |
| DIFF-03 | 03-06 | Confirm 관전 뷰 | ✓ SATISFIED | ConfirmDialog 내부 activeIsSelf 분기 |
| DIFF-04 | 03-04 | 사용자 색 해시 | ✓ SATISFIED | userColor.ts djb2 + PALETTE 8색 |
| DIFF-05 | 03-05 | --room + 질문 one-shot | ✓ SATISFIED | SES-03과 동일 구현 |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ui-ink/src/store/confirm.ts` | 61 | `accept: boolean` — 서버가 `result` 필드로 읽어 항상 False 처리 | 🛑 Blocker (CR-01) | confirm_write/confirm_bash y 입력이 서버에서 거부로 처리됨 |
| `harness_server.py` | 574, 577 | `/learn` slash_result broadcast 중복 (WR-02) | ⚠️ Warning | 클라이언트가 slash_result 이벤트를 두 번 수신 |
| `harness_server.py` | `StateMsg.model/mode` | 서버 `_state_payload()`가 model/mode 미전송 (WR-01) | ⚠️ Warning | dispatch.ts status.setState()에 undefined 전달 |

---

### Human Verification Required

다음 항목은 멀티 터미널 환경 또는 실제 서버 연결이 필요하여 자동 검증이 불가합니다:

#### 1. CR-01: confirm_write_response accept/result 필드 불일치 (즉시 수정 권장)

**Test:** 서버 실행 + 파일 수정 에이전트 동작 후 confirm_write 다이얼로그에서 y 키 입력
**Expected:** 파일 쓰기가 허용되고 에이전트가 다음 단계로 진행
**Why human:** 자동 단위 테스트에서 잡히지 않는 버그. confirm.ts:61이 `accept: boolean`으로 전송하지만 harness_server.py:782가 `msg.get('result', False)`로 읽어 항상 거부 처리됨.

**수정 방법 (권장):**
```python
# harness_server.py:782, 789
state._confirm_result = msg.get('result', msg.get('accept', False))
state._confirm_bash_result = msg.get('result', msg.get('accept', False))
```

#### 2. SC-2: Presence 세그먼트 (REM-02)

**Test:** 두 터미널에서 `HARNESS_ROOM=test bun start` 각각 실행
**Expected:** StatusBar에 `🟢 2명 [token1·me]` 형식 표시. 한 쪽 종료 시 `↘ ... 님이 나갔습니다` 시스템 메시지 + 카운트 감소
**Why human:** 멀티 WS 연결 환경이 필요한 실시간 동작

#### 3. SC-3: 관전 모드 (REM-04)

**Test:** 같은 room에 두 터미널 접속 후 한 쪽에서 질문 입력
**Expected:** 다른 쪽에서 `{입력자} 입력 중...` 오버레이 + InputArea disabled → 에이전트 완료 후 관전자 InputArea 복귀
**Why human:** 실시간 멀티 유저 WS 동작

#### 4. SC-4: one-shot CLI (SES-01)

**Test:** `HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=<token> harness "안녕하세요?"`
**Expected:** ANSI 없이 텍스트 응답 출력 후 즉시 종료 (REPL 없음)
**Why human:** 실제 서버 연결 + LLM 응답 필요

#### 5. SC-5: Ctrl+C cancel (WSR-04)

**Test:** 에이전트 실행 중 Ctrl+C 1회 입력
**Expected:** 취소 요청 중... 시스템 메시지 + 에이전트 중단 + busy 해제 후 InputArea 복귀
**Why human:** 실시간 에이전트 실행 + 취소 흐름

#### 6. SC-6: DiffPreview 실제 diff (PEXT-02)

**Test:** 서버가 기존 파일 수정 confirm_write 요청 시 다이얼로그 확인
**Expected:** 실제 diff ± 라인 표시 (placeholder 아닌 structuredPatch 결과)
**Why human:** 실제 파일 수정 작업 흐름 필요. 또한 CR-01 수정 후 검증 필요 (현재 confirm y 입력이 항상 거부)

---

### Gaps Summary

자동 검증으로 발견된 차단 Gap은 없습니다. 그러나 CR-01은 confirm 기능 전체를 무력화하는 버그로, 멀티 터미널 수동 검증(SC-2~SC-6) 전에 수정을 권장합니다.

**CR-01 상세:**
- 클라이언트 (`confirm.ts:61`): `{type: 'confirm_write_response', accept: boolean}` 전송
- 서버 (`harness_server.py:782`): `msg.get('result', False)` 로 읽어 accept 키 무시
- 결과: 사용자가 y를 눌러도 에이전트가 파일 쓰기/bash 실행을 항상 거부당함
- 수정 방법: 서버에서 `msg.get('result', msg.get('accept', False))` 으로 양쪽 필드명 허용

**기타 Warning:**
- WR-01: StateMsg model/mode 서버 미전송 — StatusBar model/mode 표시 공란 가능
- WR-02: /learn slash_result 중복 broadcast

---

_Verified: 2026-04-24T16:28:00Z_
_Verifier: Claude (gsd-verifier)_
