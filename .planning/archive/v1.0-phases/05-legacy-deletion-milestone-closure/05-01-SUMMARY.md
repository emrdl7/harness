---
phase: 05-legacy-deletion-milestone-closure
plan: "01"
subsystem: legacy-deletion
tags:
  - legacy
  - cleanup
  - cli
  - python-ui
requirements:
  - LEG-01
  - LEG-02
  - LEG-03
dependency_graph:
  requires: []
  provides:
    - cli/ 모듈 전체 삭제 완료
    - ui/index.js 삭제 완료
    - main.py REPL 경로 삭제 완료
    - prompt_toolkit 잔재 0건
  affects:
    - harness_server.py (유일한 백엔드 진입점으로 확정)
    - ui-ink/ (유일한 UI 클라이언트로 확정)
tech_stack:
  removed:
    - prompt_toolkit (Python 기반 REPL UI 라이브러리)
    - 구형 ui/index.js (Node.js WS 클라이언트)
  patterns: []
key_files:
  deleted:
    - cli/__init__.py
    - cli/app.py
    - cli/callbacks.py
    - cli/claude.py
    - cli/intent.py
    - cli/render.py
    - cli/setup.py
    - cli/slash.py
    - cli/tui.py
    - ui/index.js
    - ui/package.json
    - ui/package-lock.json
    - main.py
    - tests/test_handle_slash.py
    - tests/test_main_intent.py
  modified: []
decisions:
  - main.py 완전 삭제 선택 (옵션 A) — harness_server.py 가 독립 진입점이므로 shim 불필요. from main import 의존 파일이 cli.* 기반 UI 테스트 2건뿐이었으며 재배선 불가능하여 함께 삭제
  - test_handle_slash.py, test_main_intent.py 삭제 — cli.slash / cli.intent 심볼 테스트는 해당 모듈 삭제로 재배선 불가능; ui-ink vitest 로 커버리지 대체 예정
metrics:
  duration: "약 10분"
  completed_date: "2026-04-24T12:15:01Z"
  tasks_completed: 3
  tasks_total: 3
  files_deleted: 15
---

# Phase 5 Plan 01: Legacy Python UI 삭제 Summary

**한 줄 요약:** cli/ 9개 모듈 + ui/index.js + main.py 553줄 완전 삭제 — prompt_toolkit 잔재 0건, ui-ink 가 유일한 UI로 코드베이스 수준에서 확정

---

## 목표

Legacy Python UI 파일 전수 삭제 — `cli/` REPL 모듈 9종 + `ui/index.js` + `main.py` REPL 오케스트레이터를 제거하여 `ui-ink`가 유일한 UI임을 코드베이스 수준에서 확정.

---

## 실행 결과

### Task 1: cli/ legacy 모듈 삭제 (커밋 `279a52f`)

| 파일 | 결과 |
|------|------|
| cli/__init__.py | 삭제 |
| cli/app.py | 삭제 |
| cli/callbacks.py | 삭제 |
| cli/claude.py | 삭제 |
| cli/intent.py | 삭제 |
| cli/render.py | 삭제 |
| cli/setup.py | 삭제 |
| cli/slash.py | 삭제 |
| cli/tui.py | 삭제 |

- cli/ 디렉터리 자체 완전 제거
- `python -c "import cli"` → ModuleNotFoundError 확인

### Task 2: ui/ 구형 JS 클라이언트 삭제 (커밋 `b7130f8`)

| 파일 | 결과 |
|------|------|
| ui/index.js | 삭제 |
| ui/package.json | 삭제 |
| ui/package-lock.json | 삭제 |
| ui/node_modules/ | rm -rf 정리 |

- ui/ 디렉터리 자체 완전 제거
- ui-ink/ 디렉터리는 정상 유지

### Task 3: main.py 완전 삭제 (커밋 `0d8c636`)

**판단:** `grep -rn "from main import|import main"` 결과 → `tests/test_main_intent.py`, `tests/test_handle_slash.py` 2건 존재. 두 파일 모두 삭제된 `cli.intent` / `cli.slash` 심볼에 의존하며 `harness_core` 기반 재배선 불가능하므로 함께 삭제.

**적용:** 옵션 A (완전 삭제) — harness_server.py 가 독립 진입점으로 충분.

| 파일 | 결과 |
|------|------|
| main.py (553줄) | 삭제 |
| tests/test_main_intent.py | 삭제 |
| tests/test_handle_slash.py | 삭제 |

---

## 검증 결과

```
PASS: cli 임포트 실패 (ModuleNotFoundError)
PASS: ui/index.js 없음
PASS: prompt_toolkit 잔재 0건
PASS: harness_server.py 존재
PASS: agent.py 존재
PASS: main.py 삭제됨
PASS: harness_core/ 존재
PASS: tools/ 존재
PASS: session/ 존재
PASS: evolution/ 존재
PASS: ui-ink/ 존재
```

---

## Deviations from Plan

### Auto-removed Files (Rule 2 — 정확성)

**1. [Rule 2 - Missing] tests/test_handle_slash.py, tests/test_main_intent.py 삭제**

- **Found during:** Task 3
- **Issue:** main.py 삭제 전 `from main import` 의존 파일 확인 결과 테스트 2건 존재. 두 파일 모두 삭제된 cli.slash / cli.intent 기반 UI 로직 테스트로, harness_core 기반 재배선 불가능.
- **Fix:** 플랜 지침("main.py 의존 테스트가 존재하면 삭제가 아닌 재배선 우선")을 따르되, cli.* 모듈이 이미 삭제된 상황에서 재배선 대상 심볼 자체가 존재하지 않으므로 삭제 처리.
- **Files deleted:** tests/test_handle_slash.py, tests/test_main_intent.py
- **Commit:** 0d8c636

---

## Known Stubs

없음 — 이번 플랜은 삭제 작업만 수행.

---

## Threat Flags

없음 — 파일 삭제만 수행, 신규 네트워크 엔드포인트/인증 경로/스키마 변경 없음.

---

## Self-Check: PASSED

### 삭제 파일 확인

```
PASS: cli/ 디렉터리 없음
PASS: ui/index.js 없음
PASS: main.py 없음
PASS: tests/test_handle_slash.py 없음
PASS: tests/test_main_intent.py 없음
```

### 유지 파일 확인

```
PASS: harness_server.py 존재
PASS: agent.py 존재
PASS: harness_core/ 존재
PASS: tools/ 존재
PASS: session/ 존재
PASS: evolution/ 존재
PASS: ui-ink/ 존재
```

### 커밋 확인

```
PASS: 279a52f — feat(LEG-01,LEG-02): cli/ legacy Python UI 모듈 전체 삭제
PASS: b7130f8 — feat(LEG-03): ui/ 구형 JS 클라이언트 전체 삭제
PASS: 0d8c636 — feat(LEG-01): main.py REPL 오케스트레이터 완전 삭제
```
