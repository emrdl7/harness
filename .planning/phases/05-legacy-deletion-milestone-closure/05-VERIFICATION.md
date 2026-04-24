---
phase: 05-legacy-deletion-milestone-closure
verified: 2026-04-24T12:35:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
gaps:
  - truth: "REQUIREMENTS.md LEG-01~08 체크박스 및 Traceability 표 미업데이트"
    status: resolved
    resolved_at: "2026-04-24"
    resolution: "docs(05): REQUIREMENTS.md LEG-01~08 체크박스 [x] 처리 + Traceability Completed 처리 (commit 5839867)"
---

# Phase 5: Legacy Deletion + Milestone Closure 검증 보고서

**Phase Goal:** Python UI 잔재 전수 삭제 · PROJECT.md Evolution 업데이트 · milestone 종료 처리 — ui-ink 가 유일한 UI 임을 코드베이스 수준에서 확정한다.
**Verified:** 2026-04-24T12:35:00Z
**Status:** gaps_found
**Re-verification:** No — 초기 검증

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | cli/ 디렉터리 내 REPL 관련 Python 모듈 전부 삭제 | ✓ VERIFIED | `ls cli/ 2>/dev/null` → DELETED. git 커밋 279a52f (cli/ 9개 모듈 전체 삭제) 존재 확인. |
| 2 | ui/index.js (구형 JS 클라이언트) 삭제 | ✓ VERIFIED | `test ! -f ui/index.js` → DELETED. git 커밋 b7130f8 확인. ui/ 디렉터리에는 git-untracked node_modules 잔재만 남아있음 (정상). |
| 3 | main.py 완전 삭제 | ✓ VERIFIED | `ls main.py 2>/dev/null` → DELETED. git 커밋 0d8c636 확인. |
| 4 | prompt_toolkit import가 harness 소스 어디에도 남지 않음 | ✓ VERIFIED | `grep -rn "prompt_toolkit" . --include="*.py" --exclude-dir=".venv"` → COUNT: 0. |
| 5 | Python pytest 전 케이스 green | ✓ VERIFIED | 실시간 실행: `224 passed in 0.71s`. 0 failed. |
| 6 | ui-ink vitest 전 케이스 green | ✓ VERIFIED | 실시간 실행: `163 passed (25 files), 0 failed, 1.79s`. |
| 7 | PROJECT.md Key Decisions Outcome 전부 Validated | ✓ VERIFIED | `grep -c "Pending" .planning/PROJECT.md` → 0. 6건 전부 `✓ Validated` 확인. |
| 8 | PROJECT.md Milestone Closure 섹션 추가 | ✓ VERIFIED | `## Milestone Closure` 섹션 존재. Active 섹션 `(없음 — milestone 완료)` 상태. |
| 9 | CONCERNS.md §1.12·§3.1·§3.5 RESOLVED Phase 5 처리 | ✓ VERIFIED | 3건 모두 `✅ RESOLVED Phase 5` 텍스트 포함 확인. |
| 10 | REQUIREMENTS.md LEG-01~08 체크박스 및 Traceability 표 업데이트 | ✗ FAILED | LEG-01~08 체크박스가 `[ ]`로 남아있음. Traceability 표 Status가 `Pending`으로 남아있음. FND-01~16은 `[x]`로 업데이트되어 있어 이 차이가 의도되지 않은 누락임을 시사함. |

**Score:** 9/10 truths verified

---

### ROADMAP Success Criteria 검증

Phase 5 ROADMAP.md Success Criteria (5건) 전수 검증:

| SC | 내용 | Status | Evidence |
|----|------|--------|---------|
| SC-1 | ui/index.js·main.py·cli/*.py 삭제, session/·evolution/·tools/·harness_core/·harness_server.py 유지 | ✓ VERIFIED | 삭제 대상 전부 삭제됨. 유지 대상 전부 존재 확인. |
| SC-2 | prompt_toolkit grep 빈 결과·import cli 의도적 실패·harness_server.py+ui-ink 유일 실행 경로 | ✓ VERIFIED | prompt_toolkit 0건, ModuleNotFoundError 확인, harness_server.py + ui-ink/ 존재. |
| SC-3 | main.py 완전 삭제 또는 thin shim | ✓ VERIFIED | 완전 삭제 (옵션 A 적용). |
| SC-4 | 최종 회귀 green: pytest 199건+ + vitest 전 테스트 | ✓ VERIFIED | pytest 224 passed / vitest 163 passed, 모두 0 failed. |
| SC-5 | PROJECT.md Evolution 업데이트 + CONCERNS §1.12·§3 close | ✓ VERIFIED | Active→Validated 이동, Key Decisions 확정, Milestone Closure 추가, §1.12·§3.1·§3.5 RESOLVED. |

---

### Required Artifacts

| Artifact | 기대 상태 | Status | Details |
|----------|-----------|--------|---------|
| `cli/` | 삭제 | ✓ DELETED | 디렉터리 완전 제거. `__pycache__` 잔재도 rm -rf 정리됨 (05-02에서 수정). |
| `ui/index.js` | 삭제 | ✓ DELETED | `test ! -f ui/index.js` → exit 0 확인. |
| `main.py` | 삭제 또는 thin shim | ✓ DELETED | 완전 삭제됨. |
| `harness_server.py` | 유지 + 직접 import | ✓ WIRED | 존재 확인, `import harness_core` 직접 사용. |
| `ui-ink/` | 유일 UI 클라이언트 | ✓ EXISTS | 정상 존재, vitest 163건 green. |
| `.planning/PROJECT.md` | Validated + Closure 섹션 | ✓ COMPLETE | Key Decisions 6건 Validated, Milestone Closure 섹션, Active 비어있음. |
| `.planning/ROADMAP.md` | Phase 5 [x] + 3/3 complete | ✓ COMPLETE | `[x]` 확인, Progress Tracking `3/3 | Complete | 2026-04-24`. |
| `.planning/STATE.md` | status: complete, percent: 100 | ✓ COMPLETE | 실시간 확인: `status: complete`, `percent: 100`. |
| `.planning/codebase/CONCERNS.md` | §1.12·§3.1·§3.5 RESOLVED | ✓ COMPLETE | 3건 모두 `✅ RESOLVED Phase 5` 포함. |
| `.planning/REQUIREMENTS.md` | LEG-01~08 [x] + Traceability 업데이트 | ✗ INCOMPLETE | LEG-01~08 체크박스 `[ ]` 미업데이트, Traceability Status `Pending` 미업데이트. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `harness_server.py` | `harness_core/` | `import harness_core` | ✓ WIRED | `harness_server.py:20`에서 `import harness_core` 직접 확인. main.py 경유 없음. |
| Python 진입점 | `harness_server.py` | 직접 실행 | ✓ WIRED | `main.py` 삭제되어 `harness_server.py`가 유일 진입점으로 확정. |
| `ui-ink/` | WS 서버 | `HarnessClient` | ✓ WIRED | ui-ink만 클라이언트 역할. ui/index.js 삭제됨. |

---

### Data-Flow Trace (Level 4)

Phase 5는 삭제·문서 업데이트 작업이므로 동적 데이터를 렌더링하는 신규 컴포넌트가 없습니다. Level 4 데이터 흐름 추적은 적용 대상 아님 (SKIPPED — 삭제·문서 phase).

---

### Behavioral Spot-Checks

| 동작 | 결과 | Status |
|------|------|--------|
| `python -c "import cli"` → ModuleNotFoundError | `No module named 'cli'` (exit 1) | ✓ PASS |
| `test ! -f ui/index.js` | exit 0 (파일 없음) | ✓ PASS |
| `grep -rn "prompt_toolkit" . --include="*.py" --exclude-dir=.venv` | 0건 | ✓ PASS |
| `pytest tests/ -q` | 224 passed, 0 failed | ✓ PASS |
| `bun run test` (ui-ink) | 163 passed (25 files), 0 failed | ✓ PASS |
| `harness_server.py` 존재 확인 | 존재 | ✓ PASS |
| `ui-ink/` 존재 확인 | 존재 | ✓ PASS |
| escape guard grep | 0건 | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | 설명 | Status | Evidence |
|-------------|------------|------|--------|---------|
| LEG-01 | 05-01 | `ui/index.js` 삭제 | ✓ SATISFIED | 삭제 확인 (git b7130f8) |
| LEG-02 | 05-01 | `main.py` + cli/*.py 삭제 | ✓ SATISFIED | 삭제 확인 (git 279a52f, 0d8c636) |
| LEG-03 | 05-01 | `cli/tui.py`·`cli/app.py` 제거 | ✓ SATISFIED | cli/ 전체 삭제로 포함 |
| LEG-04 | 05-02 | `main.py` thin shim 또는 삭제 | ✓ SATISFIED | 완전 삭제 (옵션 A) |
| LEG-05 | 05-02 | CONCERNS.md §1.12·§3 close | ✓ SATISFIED | §1.12·§3.1·§3.5 RESOLVED 확인 |
| LEG-06 | 05-03 | PROJECT.md Active→Validated + Key Decisions | ✓ SATISFIED | Pending 0건, Validated 확인 |
| LEG-07 | 05-03 | pytest 199+ green + vitest green + prompt_toolkit 0건 | ✓ SATISFIED | pytest 224 / vitest 163 / prompt_toolkit 0건 |
| LEG-08 | 05-03 | PROJECT.md milestone closure 섹션 추가 | ✓ SATISFIED | `## Milestone Closure` 섹션 존재 |

**중요 불일치:** REQUIREMENTS.md Traceability 표의 LEG-01~08 Status 열이 `Pending`으로 남아있고 체크박스도 `[ ]`입니다. 코드베이스 관점에서는 모두 달성되었으나 REQUIREMENTS.md 문서 자체가 최종 상태를 반영하지 못하고 있습니다.

---

### Anti-Patterns Found

| 파일 | 패턴 | 심각도 | 영향 |
|------|------|--------|------|
| `.planning/REQUIREMENTS.md` | LEG-01~08 체크박스 `[ ]` 미업데이트 | ⚠️ Warning | milestone 완료 상태를 추적 문서가 반영 못함. 에이전트·개발자 혼동 가능. |
| `.planning/REQUIREMENTS.md` | Traceability 표 LEG-01~08 Status `Pending` | ⚠️ Warning | 동일 원인. 05-03-PLAN이 PROJECT.md·ROADMAP·STATE를 업데이트했으나 REQUIREMENTS.md는 포함되지 않음. |
| `ui/` 디렉터리 | `node_modules/` 잔재 (git-tracked) | ℹ️ Info | git ls-files에서 `ui/node_modules/*` 파일들이 추적됨. 구형 ui/package.json·package-lock.json은 삭제됐으나 node_modules는 이미 커밋된 상태. 기능 영향 없음. |

---

### Human Verification Required

Phase 5는 삭제·문서 작업 phase이며, 코드베이스 검증으로 모든 핵심 must-have를 확인할 수 있었습니다. 다음 1건은 판단이 필요합니다:

#### 1. ui/ node_modules git-tracked 상태 수용 여부

**Test:** `git ls-files ui/node_modules/ | wc -l` 실행 후 결과 확인
**Expected:** 이 파일들이 git history에서 제거되어야 하는지 판단 필요
**Why human:** git history에서 node_modules를 제거하면 rebase가 필요하거나 의도적으로 남겨둔 것일 수 있음. 기능에는 영향 없으나 리포 정리 관점에서 결정 필요.

---

### Gaps Summary

**갭 1건: REQUIREMENTS.md LEG-01~08 미업데이트**

Phase 5의 모든 코드베이스·기능 목표는 달성되었습니다:
- cli/, main.py, ui/index.js 전부 삭제 완료
- prompt_toolkit 잔재 0건
- pytest 224건 / vitest 163건 green
- PROJECT.md, ROADMAP.md, STATE.md, CONCERNS.md 전부 milestone 완료 상태로 업데이트

그러나 `.planning/REQUIREMENTS.md`의 LEG-01~08 체크박스가 `[ ]`로 남아있고 Traceability 표의 Status도 `Pending`으로 남아있습니다. 05-03-PLAN이 PROJECT.md·ROADMAP.md·STATE.md를 업데이트했으나 REQUIREMENTS.md는 명시적으로 포함되지 않았습니다. FND-01~16은 이미 `[x]`로 업데이트되어 있는 점에서 이 누락은 의도되지 않은 것으로 판단됩니다.

**수정 범위:** `.planning/REQUIREMENTS.md`에서
1. `- [ ] **LEG-01~08**` → `- [x] **LEG-01~08**` 로 변경 (8건)
2. Traceability 표 LEG-01~08 행의 Status `Pending` → `Completed`, Plan 열 `TBD` → `05-01`, `05-02`, `05-03` 으로 채움

이는 순수 문서 업데이트로, 재테스트나 코드 변경이 필요하지 않습니다.

---

_Verified: 2026-04-24T12:35:00Z_
_Verifier: Claude (gsd-verifier)_
