---
phase: 03-remote-room-session-control
plan: 02
subsystem: harness_server (WS 프로토콜 확장 2차)
tags: [pext-04, pext-05, ses-02, b2, b3, b4, delta-replay, cancel, tdd]
dependency_graph:
  requires: [03-01]
  provides: [PEXT-04, PEXT-05, SES-02, B2, B3, B4]
  affects: [harness_server.py, tests/test_harness_server.py]
tech_stack:
  added: []
  patterns:
    - asyncio done callback으로 미실행 task 정리 (_spawn_input_task)
    - SHA-256 앞 8자 token hash (Presence 식별자)
    - ring buffer delta replay (event_id > resume_from 필터)
key_files:
  created: []
  modified:
    - harness_server.py
    - tests/test_harness_server.py
decisions:
  - _spawn_input_task done callback 패턴으로 task 미실행 시 room 상태 정리
  - asyncio 시작 전 cancel 시 코루틴 미실행 → finally 미동작 엣지케이스 대응
metrics:
  duration: ~40분 (한도 리셋 포함)
  completed: 2026-04-24
---

# Phase 3 Plan 02: PEXT-04/05 + SES-02 + B2~B4 WS 프로토콜 확장 2차 Summary

**한 줄 요약:** x-resume-from delta replay, cancel/agent_cancelled 경로, x-resume-session 세션 로드, SHA-256 token_hash Presence 식별자를 harness_server.py에 구현하고 TDD로 17건 검증 완료.

## 완료된 태스크

| Task | 이름 | 커밋 | 주요 파일 |
|------|------|------|-----------|
| 1 RED | TestDeltaReplay 실패 테스트 추가 | `eeba035` | tests/test_harness_server.py |
| 1 GREEN | PEXT-04/SES-02/B3/B4 구현 | `677c644` | harness_server.py |
| 2 RED | TestCancelTask 실패 테스트 추가 | `d6a2ed9` | tests/test_harness_server.py |
| 2 GREEN | PEXT-05/B2 cancel 처리 구현 | `5d510ee` | harness_server.py, tests/test_harness_server.py |

## 구현 내용

### Task 1: PEXT-04 + SES-02 + B3 + B4

**`_run_session()` 헤더 파싱 확장:**
- `x-resume-from` 헤더 파싱: `isdigit() + < 2**31` 검증으로 주입 방지 (T-03-02-01)
- `x-resume-session` 헤더 파싱: 세션 파일명으로 사용 (SES-02/B3)
- ring buffer delta 재송신: `event_id > resume_from` 필터로 누락 이벤트 재전송 (PEXT-04)
- `sess.load()` 호출로 세션 복구, FileNotFoundError 시 error 이벤트 전송

**헬퍼 함수 추가:**
- `_token_hash(token)`: SHA-256 앞 8자 hex — 토큰 원문 미노출 Presence 식별자 (B4)
- `room_member_joined` broadcast에 `user=_token_hash(ws_token)` 필드 추가

**TestDeltaReplay 10건:**
- 헤더 없음, resume_from 필터, 전체 재송신, 비정수 무시, 오버플로우 무시
- SES-02 세션 로드, 파일 없음 오류, token_hash 8자, room_member_joined user 필드, members 필드

### Task 2: PEXT-05 + B2

**`_dispatch_loop()` cancel 케이스:**
- `elif t == 'cancel':` 추가
- `ws is not room.active_input_from` 가드 — 관전자 취소 방지 (T-03-02-02)
- `room._cancel_requested = True` — executor 스레드 조기 종료 플래그
- `task.done()` 체크 후 `task.cancel()` — 안전한 DoS 방어 (T-03-02-03)
- `broadcast(room, type='agent_cancelled')` 전송

**`_handle_input()` 정리 강화:**
- `except asyncio.CancelledError: pass` 추가 (정상 취소 경로)
- `finally`에 `room._cancel_requested = False` 리셋 (B2)

**`_spawn_input_task()` done callback 패턴 (핵심 버그 수정):**
- asyncio에서 task가 첫 `await` 이전에 cancel되면 코루틴이 미실행되어 `finally` 미동작
- `_on_done` callback에서 `t.cancelled()` 감지 시 `room.busy/active_input_from/_cancel_requested` 강제 정리

**TestCancelTask 7건:**
- active_input_from 취소, 비active 무시, agent_cancelled broadcast, _cancel_requested 플래그
- busy 정리, done task safe, finally 리셋

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] task 미실행 시 room 상태 미정리**
- **Found during:** Task 2 GREEN
- **Issue:** `task.cancel()` 호출 시 첫 `await` 이전이면 코루틴이 실행되지 않아 `_handle_input` finally가 동작하지 않음. `room.busy = True`인 채로 유지됨
- **Fix:** `_spawn_input_task`에 `_on_done` done callback 추가. `t.cancelled()` 시 room 상태 강제 정리
- **Files modified:** `harness_server.py` (_spawn_input_task)
- **Commit:** `5d510ee`

**2. [Rule 1 - Bug] test_cancelled_error_clears_busy 테스트 직접 create_task 사용**
- **Found during:** Task 2 GREEN 검증 중
- **Issue:** 테스트가 `asyncio.create_task`를 직접 사용해 `_spawn_input_task`의 done callback이 적용되지 않음
- **Fix:** 테스트를 `srv._spawn_input_task`를 경유하도록 수정 (실제 코드 경로와 일치)
- **Files modified:** `tests/test_harness_server.py`
- **Commit:** `5d510ee`

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (Task 1) | `eeba035` | test(03-02): TestDeltaReplay 실패 테스트 추가 |
| GREEN (Task 1) | `677c644` | feat(03-02): PEXT-04/SES-02/B3/B4 구현 |
| RED (Task 2) | `d6a2ed9` | test(03-02): TestCancelTask 실패 테스트 추가 |
| GREEN (Task 2) | `5d510ee` | feat(03-02): PEXT-05/B2 cancel 처리 구현 |

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| (해당 없음) | - | 기존 threat_model의 T-03-02-01~06 모두 mitigate/accept 처리됨 |

WS 헤더 파싱, cancel 권한 가드, session 파일 경로 처리 모두 계획된 범위 내 구현.

## 검증 결과

```
TestDeltaReplay: 10 passed
TestCancelTask: 7 passed
전체 pytest: 260 passed (기존 243건 + 신규 17건)
```

## Self-Check: PASSED

- `harness_server.py` 존재 확인: FOUND
- `tests/test_harness_server.py` 존재 확인: FOUND
- 커밋 `eeba035` 존재 확인: FOUND
- 커밋 `677c644` 존재 확인: FOUND
- 커밋 `d6a2ed9` 존재 확인: FOUND
- 커밋 `5d510ee` 존재 확인: FOUND
- 전체 pytest 260건 green: PASSED
