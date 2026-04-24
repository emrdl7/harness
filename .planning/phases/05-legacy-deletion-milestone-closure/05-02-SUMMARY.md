---
phase: 05-legacy-deletion-milestone-closure
plan: "02"
subsystem: regression-validation
tags:
  - legacy
  - verification
  - pytest
  - vitest
  - hygiene
requirements:
  - LEG-04
  - LEG-05
dependency_graph:
  requires:
    - 05-01 (cli/ · main.py · ui/index.js 삭제)
  provides:
    - pytest 224건 green 확인
    - vitest 163건 green 확인
    - 환경 위생 grep 5종 전부 통과
    - cli/__pycache__ 잔재 완전 제거
  affects:
    - harness_server.py (유일한 백엔드 진입점 최종 확정)
    - ui-ink/ (유일한 UI 클라이언트 최종 확정)
tech_stack:
  added: []
  removed: []
  patterns:
    - "pytest 회귀 기준: 224 passed, 0 failed"
    - "vitest 회귀 기준: 163 passed (25 files), 0 failed"
key_files:
  created: []
  modified: []
  deleted:
    - cli/ (디렉터리 전체 — __pycache__ 잔재 포함)
decisions:
  - cli/__pycache__ 디렉터리 삭제 (Rule 1 자동 수정) — .py 삭제 후 __pycache__ 잔재로 import cli 가 여전히 성공하는 버그 수정; rm -rf cli/ 로 완전 제거
metrics:
  duration: "약 5분"
  completed_date: "2026-04-24T12:19:27Z"
  tasks_completed: 3
  tasks_total: 3
  files_deleted: 1
---

# Phase 5 Plan 02: Legacy 삭제 최종 회귀 검증 Summary

**한 줄 요약:** pytest 224건·vitest 163건 green + 환경 위생 grep 5종 전부 통과 — cli/__pycache__ 잔재 수정 포함

---

## 목표

05-01의 Legacy 삭제 이후 최종 회귀 검증 게이트를 통과한다. Python pytest, ui-ink vitest, 환경 위생 grep 5종(prompt_toolkit · import cli · ui/index.js · server entry · escape guard)을 모두 확인한다.

---

## 실행 결과

### Task 1: Python pytest 회귀 라운드

```
224 passed in 0.83s
```

- 실패 0건
- `from cli import` / `from main import` 의존 테스트는 05-01에서 이미 삭제됨
- 나머지 224건 전부 green

### Task 2: ui-ink vitest 회귀 라운드

```
Test Files  25 passed (25)
     Tests  163 passed (163)
  Duration  1.88s
```

- 실패 0건 (Phase 4 기준 163건 유지)
- tsc --noEmit: 오류 0건

### Task 3: 환경 위생 grep — 5종 결과 전문

```
=== 1. prompt_toolkit grep ===
(결과 없음 — 0건)
EXIT:0

=== 2. import cli ===
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import cli
    ^^^^^^^^^^
ModuleNotFoundError: No module named 'cli'
EXIT:1  ← 의도적 실패 (모듈 없음 확인)

=== 3. ui/index.js ===
DELETED

=== 4. server entry ===
harness_server.py: OK
ui-ink/: OK

=== 5. escape guard (alternate screen / mouse tracking) ===
(결과 없음 — 0건)
EXIT:0
```

**판정:** 5종 전부 통과.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] cli/__pycache__ 잔재로 인한 import cli 성공 버그 수정**

- **Found during:** Task 3
- **Issue:** 05-01에서 `cli/` 디렉터리의 `.py` 파일들은 git으로 삭제됐지만, `cli/__pycache__/` 디렉터리(`.pyc` 파일 9개)가 git-untracked 상태로 남아있어 `python -c "import cli"`가 성공하고 있었음. 환경 위생 grep 수행 중 발견.
- **Fix:** `rm -rf cli/` — `__pycache__` 포함 디렉터리 완전 제거
- **Files deleted:** `cli/__pycache__/__init__.cpython-314.pyc` 외 8개 `.pyc` 파일, `cli/` 디렉터리
- **Commit:** 해당 파일들은 git에서 추적되지 않으므로 별도 커밋 없음 (워킹 트리 정리)

---

## Known Stubs

없음 — 이번 플랜은 검증 작업만 수행.

---

## Threat Flags

없음 — 파일 삭제 및 검증만 수행, 신규 네트워크 엔드포인트/인증 경로/스키마 변경 없음.

---

## Self-Check: PASSED

### 검증 결과 확인

```
PASS: pytest 224 passed, 0 failed
PASS: vitest 163 passed, 0 failed
PASS: tsc --noEmit 오류 0건
PASS: prompt_toolkit grep 0건
PASS: import cli → ModuleNotFoundError
PASS: ui/index.js 없음
PASS: harness_server.py 존재
PASS: ui-ink/ 존재
PASS: escape guard grep 0건
PASS: cli/ 디렉터리 완전 제거
```
