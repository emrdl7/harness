---
phase: 03-remote-room-session-control
plan: "05"
subsystem: ui-ink/ws
tags:
  - websocket
  - reconnect
  - backoff
  - one-shot
  - session
dependency_graph:
  requires:
    - "03-03"  # store/room.ts wsState/reconnectAttempt/lastEventId 필드
    - "03-04"  # dispatch.ts event_id 처리
  provides:
    - HarnessClient jitter exponential backoff (WSR-01~03)
    - one-shot CLI 경량 클라이언트 (SES-01/03)
    - --resume/--room argv 파싱 (SES-02/03)
  affects:
    - ui-ink/src/ws/client.ts
    - ui-ink/src/one-shot.ts
    - ui-ink/src/index.tsx
tech_stack:
  added: []
  patterns:
    - jitter exponential backoff (base=1000ms, cap=30s, factor=0.5+rand*0.5)
    - Promise-based one-shot WS 클라이언트
    - async IIFE entrypoint (dynamic import 지원)
key_files:
  created:
    - ui-ink/src/one-shot.ts
    - ui-ink/src/__tests__/ws-backoff.test.ts
  modified:
    - ui-ink/src/ws/client.ts
    - ui-ink/src/index.tsx
decisions:
  - "vi.hoisted() + class 문법으로 vi.fn() new 키워드 한계 우회 — MockWS를 class로 선언"
  - "--resume 분기는 HARNESS_RESUME_SESSION env var를 통해 App.tsx에 전달 (Phase 4에서 ConnectOptions 확장)"
  - "index.tsx를 async IIFE로 래핑하여 동적 import(one-shot.ts) + await 지원"
metrics:
  duration: "약 25분"
  completed: "2026-04-24T07:04:23Z"
  tasks_completed: 2
  files_changed: 4
---

# Phase 03 Plan 05: WS Reconnect Backoff + one-shot CLI Summary

**One-liner:** jitter exponential backoff(WSR-01~03) + one-shot 경량 WS 클라이언트(SES-01/03) + --resume/--room argv 파싱(SES-02/03)으로 재연결·CLI 시나리오 완성

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 (RED) | ws-backoff 실패 테스트 6건 | b31af31 | `__tests__/ws-backoff.test.ts` |
| 1 (GREEN) | HarnessClient jitter backoff + resume_from 헤더 | 1823439 | `ws/client.ts`, `__tests__/ws-backoff.test.ts` |
| 2 | one-shot.ts 신규 + index.tsx argv 파싱 확장 | 19c50bf | `one-shot.ts`, `index.tsx` |

## What Was Built

### Task 1: HarnessClient jitter exponential backoff (WSR-01~03)

`ui-ink/src/ws/client.ts`에 다음을 구현했습니다:

- **`_scheduleReconnect()`**: `delay = min(1000 * 2^n * (0.5 + rand*0.5), 30000)` 공식. 10회 실패 시 `setWsState('failed')` 설정 후 재연결 중단
- **`_onConnectedStable()`**: open 이벤트 후 30초 타이머 → `backoff.attempts = 0` 리셋 (thundering herd 방지)
- **`_closed` 플래그**: 명시적 `close()` 호출 시 재연결 억제
- **`x-resume-from` 헤더**: `connect()` 시 `lastEventId != null`이면 WS 헤더에 포함 (WSR-03 delta replay)
- **`x-resume-session` 헤더**: `resumeSession` 옵션이 있으면 포함 (SES-02)
- **`ConnectOptions.resumeSession` 필드**: `--resume <id>` 세션 ID 전달용

### Task 2: one-shot.ts + index.tsx argv 파싱 (SES-01/02/03)

**`ui-ink/src/one-shot.ts` 신규:**
- Promise 기반 경량 WS 클라이언트
- `ready` → `input` 전송 → `token` stdout 출력 → `agent_end` → resolve 흐름
- 30초 타임아웃 + `error`/`close` 이벤트 reject 처리

**`ui-ink/src/index.tsx` stub 제거:**
- `[one-shot] {query}` stub 완전 제거
- `--resume <id>`, `--room <name>`, positional query 파싱
- async IIFE로 래핑하여 `await import('./one-shot.js')` 동적 import 지원
- `--resume` 분기: `HARNESS_RESUME_SESSION` env 설정 후 Ink REPL render로 진행

## Verification

```
tsc --noEmit       : 에러 0
vitest run         : 21 Test Files, 146 Tests — 모두 통과
```

acceptance criteria 체크:
- `_scheduleReconnect` 등장: 8건 (client.ts 내 정의 + 호출)
- `x-resume-from` 등장: 1건 (connect() 내)
- `[one-shot]` stub: 제거됨 (0건)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] vi.fn() 생성자 호환성 문제**
- **Found during:** Task 1 TDD RED→GREEN 전환
- **Issue:** `vi.fn(() => mockInstance)`는 `new` 키워드와 함께 사용 시 "is not a constructor" 오류 발생. vitest의 `vi.fn()`은 arrow function 기반이라 생성자 프로토콜이 없음
- **Fix:** `vi.hoisted()`를 사용하고, MockWS를 `class`로 선언하여 `new WebSocket()`과 동일한 동작 구현
- **Files modified:** `ui-ink/src/__tests__/ws-backoff.test.ts`
- **Commit:** 1823439

**2. [Rule 2 - Enhancement] Test 4 루프 경계 수정**
- **Found during:** Task 1 GREEN 단계
- **Issue:** `_scheduleReconnect`는 `attempts >= 10`이면 failed를 설정하므로, `attempts=10`이 된 후 다음 close 이벤트에서 failed 상태가 됨. 테스트가 10번 루프 + 마지막 1번 추가 close로 수정 필요
- **Fix:** 루프 10회 (각 close+runAllTimers) 후 별도 close 이벤트로 failed 확인
- **Files modified:** `ui-ink/src/__tests__/ws-backoff.test.ts`
- **Commit:** 1823439

## Known Stubs

- `--resume <id>` 분기에서 `HARNESS_RESUME_SESSION` env를 설정한 후 REPL render로 진행하지만, `App.tsx`의 `HarnessClient` 생성 시 해당 env를 `resumeSession` 옵션으로 전달하는 코드가 아직 없습니다. Phase 4 (Wave 4) `App.tsx` 작업에서 `ConnectOptions.resumeSession` 연결 예정.

## Threat Surface Scan

이 플랜의 `<threat_model>`에 명시된 5건 외 추가 threat surface 없음:
- `one-shot.ts`의 `process.stdout.write`는 ANSI injection 가능하나 서버가 plain text token을 전송하므로 위험도 낮음 (T-03-05-03 accept)

## Self-Check: PASSED

| Item | Result |
|------|--------|
| `ui-ink/src/ws/client.ts` 존재 | FOUND |
| `ui-ink/src/one-shot.ts` 존재 | FOUND |
| `ui-ink/src/__tests__/ws-backoff.test.ts` 존재 | FOUND |
| commit b31af31 (TDD RED) | FOUND |
| commit 1823439 (GREEN) | FOUND |
| commit 19c50bf (Task 2) | FOUND |
| tsc --noEmit 에러 | 0 |
| vitest 테스트 | 146/146 통과 |
