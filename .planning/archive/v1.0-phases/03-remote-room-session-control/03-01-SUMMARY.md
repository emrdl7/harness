---
phase: 03-remote-room-session-control
plan: "01"
subsystem: backend-ws-protocol
tags: [pext, websocket, event-id, ring-buffer, agent-start, confirm-write]
one_liner: "Room에 monotonic event_id + ring buffer 추가(PEXT-03), agent_start per-subscriber from_self 분기(PEXT-01), confirm_write old_content 필드 추가(PEXT-02)"

dependency_graph:
  requires: []
  provides:
    - "PEXT-01: _broadcast_agent_start() — per-subscriber from_self 플래그"
    - "PEXT-02: confirm_write old_content 필드 — 파일 diff 기반 UX"
    - "PEXT-03: broadcast() event_id 자동 부여 + ring buffer — delta replay 기반"
  affects:
    - harness_server.py

tech_stack:
  added:
    - "collections.deque (maxlen=10000) — ring buffer"
    - "time.monotonic() — TTL 기반 cleanup"
  patterns:
    - "TDD RED/GREEN 사이클 2회"
    - "per-subscriber broadcast 패턴 (ws.send() 직접 호출)"

key_files:
  modified:
    - path: harness_server.py
      summary: "Room 데이터클래스 확장, broadcast() 개선, 신규 헬퍼 2개 추가, run_agent() 호출 교체, confirm_write 콜백 수정"
    - path: tests/test_harness_server.py
      summary: "TestEventBuffer 4건, TestAgentStartFromSelf 3건, TestConfirmWriteOldContent 2건 추가. test_payload_is_valid_json assertSubset 패턴으로 변경"

decisions:
  - "_broadcast_agent_start()에서 send() 헬퍼 대신 ws.send() 직접 호출 — send() 헬퍼가 예외를 삼키므로 dead ws 감지 불가"
  - "event_counter는 broadcast() 경유 이벤트만 카운트 — _broadcast_agent_start()는 per-subscriber라 공통 payload 불가, 별도 counter 없음"
  - "TTL cleanup: 매 broadcast() 호출 시 eager cleanup (별도 타이머 없음, 3인 스케일에서 충분)"

metrics:
  duration: "약 3분 (2026-04-24 15:26~15:29)"
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 03 Plan 01: 서버 WS 프로토콜 확장 1차 (PEXT-01~03) Summary

Room에 monotonic event_id + ring buffer(PEXT-03), agent_start per-subscriber from_self 분기(PEXT-01), confirm_write old_content 필드(PEXT-02)를 TDD 사이클로 구현했습니다.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | PEXT-03 TestEventBuffer 실패 테스트 | 326c1af | tests/test_harness_server.py |
| 1 (GREEN) | PEXT-03 Room event_counter + ring buffer + broadcast() | f0b179d | harness_server.py |
| 2 (RED) | PEXT-01/02 TestAgentStartFromSelf + TestConfirmWriteOldContent 실패 테스트 | 993945a | tests/test_harness_server.py |
| 2 (GREEN) | PEXT-01 _broadcast_agent_start + PEXT-02 confirm_write old_content | 3aadd89 | harness_server.py |

## Verification Results

```
grep -n 'event_counter' harness_server.py  → Room 클래스(line 181) + broadcast()(lines 94-97) 2곳
grep -n '_broadcast_agent_start' harness_server.py  → 함수 정의(line 126) + run_agent() 호출(line 286) 2곳
grep -n 'old_content' harness_server.py  → _read_existing_file 독스트링(line 116) + send() 호출(line 243) 2곳
pytest 전체: 243 passed (기존 234건 + 신규 9건)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _broadcast_agent_start() dead ws 감지 실패**
- **Found during:** Task 2 GREEN 단계 (test_dead_ws_removed 실패)
- **Issue:** 플랜 초안에서 `await send(s, ...)` 사용을 제안했으나, `send()` 헬퍼가 내부에서 모든 예외를 `except Exception: pass`로 삼키기 때문에 dead ws가 감지되지 않았습니다.
- **Fix:** `ws.send(json.dumps(payload))` 직접 호출로 변경 — `broadcast()` 함수와 동일한 패턴 적용
- **Files modified:** harness_server.py (line 133~137)
- **Commit:** 3aadd89 (GREEN 커밋에 포함)

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (Task 1) | 326c1af | test(03-01): PEXT-03 TestEventBuffer 실패 테스트 |
| GREEN (Task 1) | f0b179d | feat(03-01): PEXT-03 구현 |
| RED (Task 2) | 993945a | test(03-01): PEXT-01/02 실패 테스트 |
| GREEN (Task 2) | 3aadd89 | feat(03-01): PEXT-01/02 구현 |

모든 RED/GREEN 게이트 커밋이 순서대로 존재합니다.

## Known Stubs

없음 — 모든 구현이 실제 동작합니다.

## Threat Flags

플랜의 threat_model 항목(T-03-01-01~04)이 모두 구현에 반영됐습니다:
- T-03-01-01 (DoS): `deque(maxlen=10000)` + 60초 TTL cleanup 완료
- T-03-01-02 (Tampering): `s is requester_ws` identity 비교 완료
- T-03-01-03 (Info Disclosure): accept — 인증된 클라이언트 전용
- T-03-01-04 (DoS): accept — Python int arbitrary precision

새로 추가된 네트워크 엔드포인트 없음. 기존 WS 핸들러에 필드 추가만 수행했습니다.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| harness_server.py 존재 | FOUND |
| tests/test_harness_server.py 존재 | FOUND |
| 03-01-SUMMARY.md 존재 | FOUND |
| commit 326c1af (RED Task 1) | FOUND |
| commit f0b179d (GREEN Task 1) | FOUND |
| commit 993945a (RED Task 2) | FOUND |
| commit 3aadd89 (GREEN Task 2) | FOUND |
