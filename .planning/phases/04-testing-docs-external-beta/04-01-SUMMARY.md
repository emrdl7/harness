---
phase: 04-testing-docs-external-beta
plan: "01"
subsystem: ui-ink/testing
tags: [integration-test, websocket, fake-ws-server, tst-02, cr-01, rem-06, wsr-03]
dependency_graph:
  requires:
    - 03-05-SUMMARY.md  # HarnessClient (jitter backoff, x-resume-from 헤더)
    - 03-03-SUMMARY.md  # store/room.ts (lastEventId, wsState), store/confirm.ts (resolve)
  provides:
    - integration.agent-turn.test.ts   # agent 턴 + one-shot 통합 테스트
    - integration.confirm-write.test.ts # CR-01 자동 발견 통합 테스트
    - integration.room.test.ts          # room busy + 3인 동시 재접속 통합 테스트
    - integration.reconnect.test.ts     # x-resume-from 헤더 + 로컬-원격 동등성 통합 테스트
  affects:
    - vitest suite (146건 → 153건 증가)
tech_stack:
  added:
    - ws (WebSocketServer — Fake WS 서버, 실제 TCP in-process)
  patterns:
    - port:0 OS 할당 랜덤 포트 Fake WS 서버
    - beforeAll/afterAll lifecycle + openSockets.terminate() 완전 종료
    - beforeEach 전 store 전체 초기화 (dispatch.test.ts 패턴)
key_files:
  created:
    - ui-ink/src/__tests__/integration.agent-turn.test.ts
    - ui-ink/src/__tests__/integration.confirm-write.test.ts
    - ui-ink/src/__tests__/integration.room.test.ts
    - ui-ink/src/__tests__/integration.reconnect.test.ts
  modified: []
decisions:
  - "Fake WS 서버를 vi.mock('ws') 대신 실제 TCP로 구현 (D-01 — reconnect delta, 3인 동시 접속 신뢰도)"
  - "afterAll에서 openSockets.terminate() 선실행 후 fakeServer.close() 호출 (T-04-01 타임아웃 방지)"
  - "CR-01 통합 테스트는 PASS가 정상 — 클라이언트가 accept 필드를 올바르게 전송함을 검증"
metrics:
  duration: "약 10분"
  completed_date: "2026-04-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 0
---

# Phase 4 Plan 01: Fake WS 서버 통합 테스트 (TST-02) Summary

Fake WS 서버(실제 TCP, port:0)로 agent 턴·CR-01 자동 발견·room busy·3인 동시 재접속·reconnect delta·로컬-원격 동등성 7건 통합 검증.

## Objectives

Phase 3 구현된 기능을 vi.mock() 없이 실제 TCP WS 통신으로 검증. 특히 CR-01 버그(confirm_write_response 필드명 불일치)를 통합 테스트가 자동으로 발견할 수 있도록 하고, 재연결·delta·3인 시나리오의 신뢰도를 실 TCP 기반으로 보장.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | agent 턴 + one-shot 통합 테스트 | e9d2164 | integration.agent-turn.test.ts |
| 2 | confirm_write CR-01 자동 발견 + room busy + 3인 동시 재접속 | 8028559 | integration.confirm-write.test.ts, integration.room.test.ts |
| 3 | reconnect delta (x-resume-from) 통합 테스트 | 0d279dc | integration.reconnect.test.ts |

## Test Results

- **기존:** 21개 파일, 146건 통과
- **최종:** 25개 파일, 153건 통과 (신규 7건 추가)
- **TypeScript:** tsc --noEmit 에러 0건

### 시나리오별 결과

| 시나리오 | 파일 | REQ-ID | 결과 |
|---------|------|--------|------|
| agent_start → busy=true, agent_end → busy=false | integration.agent-turn.test.ts | TST-02 | PASS |
| agent_end 후 클라이언트 close + busy=false | integration.agent-turn.test.ts | TST-02 (one-shot) | PASS |
| confirm_write accept → accept 필드 전송 (CR-01 클라 측 검증) | integration.confirm-write.test.ts | TST-02 | PASS |
| room_busy 수신 → useRoomStore.busy===true | integration.room.test.ts | TST-02 | PASS |
| 3개 HarnessClient 동시 접속 → 전원 connected | integration.room.test.ts | TST-02 | PASS |
| lastEventId=42 → x-resume-from: '42' 헤더 | integration.reconnect.test.ts | TST-02, REM-06 | PASS |
| 로컬-원격 동등성 (127.0.0.1 Fake 서버) | integration.reconnect.test.ts | TST-02, REM-06 | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] integration.reconnect.test.ts afterAll 타임아웃 수정**
- **Found during:** Task 3
- **Issue:** `fakeServer.close()`가 아직 열린 WebSocket 소켓이 있어 완료되지 않아 afterAll hook 10초 타임아웃 발생
- **Fix:** `openSockets: Set<WebSocket>`으로 모든 연결 소켓을 추적, afterAll에서 `ws.terminate()` 먼저 호출 후 `fakeServer.close()` 실행
- **Files modified:** `ui-ink/src/__tests__/integration.reconnect.test.ts`
- **Commit:** 0d279dc

**2. [Rule 1 - Bug] TypeScript 타입 에러 수정 (capturedServerWs null 단언)**
- **Found during:** Task 3 typecheck 실행 시
- **Issue:** `let capturedServerWs: WebSocket | null = null` 초기화 후 `as WebSocket` 단언 시 TS2352 에러
- **Fix:** `new Promise<WebSocket>((resolve) => ...)` 패턴으로 변경하여 타입 단언 불필요
- **Files modified:** `ui-ink/src/__tests__/integration.reconnect.test.ts`
- **Commit:** 0d279dc (동일 커밋)

## CR-01 이슈 문서화

`integration.confirm-write.test.ts`에서 CR-01 버그의 위치와 성격을 명확히 기록:
- **클라이언트 측 (confirm.ts:61):** `{type: 'confirm_write_response', accept: boolean}` — **올바름**
- **서버 측 (harness_server.py:782):** `result` 필드를 읽음 — **버그**
- **통합 테스트 결과:** PASS (클라이언트가 올바른 필드를 전송하므로)
- **수정 대상:** Phase 4 Plan 05에서 서버 측 `result → accept` 교정 예정

## Known Stubs

없음 — 통합 테스트 파일만 생성, UI 컴포넌트 없음.

## Threat Flags

없음 — Fake WS 서버는 localhost 한정, 실 토큰 미사용, T-04-01/02/03 모두 mitigate 처리됨.

## Self-Check: PASSED

- integration.agent-turn.test.ts: FOUND
- integration.confirm-write.test.ts: FOUND
- integration.room.test.ts: FOUND
- integration.reconnect.test.ts: FOUND
- e9d2164: FOUND (git log)
- 8028559: FOUND (git log)
- 0d279dc: FOUND (git log)
- vitest 153/153: PASSED
- tsc --noEmit: 에러 0건
