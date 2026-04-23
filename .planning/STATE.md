# harness — ui-ink Milestone State

**Last updated:** 2026-04-23

---

## Project Reference

**See:** `.planning/PROJECT.md` (milestone 정의 · Validated · Active · Out of Scope · Key Decisions · Constraints)
**Core Value:** "ui-ink 가 harness 의 기본이자 유일한 UI. 로컬과 원격이 동일한 경험을 갖고, 그 경험은 Claude Code 수준이다."
**Current focus:** Phase 1 (Foundation — Upgrade · Protocol Fix · Hardening · Smoke)

---

## Current Position

- **Phase:** 1 — Foundation
- **Plan:** (not yet planned)
- **Status:** Not started
- **Progress:** `[░░░░░░░░░░] 0% (0/5 phases complete)`
- **Next action:** `/gsd-discuss-phase 1` (discuss mode) 또는 `/gsd-plan-phase 1` (직행)

---

## Phases

| # | Name | Status | Plans |
|---|------|--------|-------|
| 1 | Foundation | Not started | 0/0 |
| 2 | Core UX | Not started | 0/0 |
| 3 | Remote Room + Session Control | Not started | 0/0 |
| 4 | Testing + Docs + External Beta | Not started | 0/0 |
| 5 | Legacy Deletion + Milestone Closure | Not started | 0/0 |

---

## Performance Metrics

- **Requirements:** 85 v1 REQ-ID · 100% phase 매핑 완료
- **Phases:** 5 (coarse granularity)
- **Mode:** YOLO · Parallelization enabled
- **Workflow toggles:** research ✓ · plan_check ✓ · verifier ✓ · ui_phase ✓ · ui_safety_gate ✓ · code_review ✓ · discuss_mode ✓

---

## Accumulated Context

### Key Decisions (from PROJECT.md)

- UI 스택 = Node + Ink + Zustand + bun + TypeScript (Python 재현 불가 검증됨) — Pending
- Legacy Python UI 전부 삭제 (Phase 5) — Pending
- ui-ink = 로컬 + 원격 공통 UI — Pending
- WS 프로토콜 확장은 같은 milestone 에서 자유롭게 (Phase 3 집결) — Pending
- `harness_server.py` = 유일한 백엔드 경계 — Pending
- Python 백엔드 유지 (UI 만 교체) — Pending

### Background Issues (CONCERNS 잔여, 이번 milestone 범위)

- §1.12 spinner vs Live (Python REPL) — **Phase 5 legacy 삭제와 함께 자동 소멸**
- §3 Architecture 잔여 7건 중 Python REPL 관련 — **Phase 5 에서 close 처리**
- §1.10 `run_command` shell-quoting — Ink 재작성과 독립, 이번 milestone 제외

### Todos

(none — roadmap 단계 완료, plan 단계 진입 대기)

### Blockers

(none)

---

## Session Continuity

### Last session summary

- `/gsd-new-project` 실행 → PROJECT.md · REQUIREMENTS.md · research/{STACK, FEATURES, ARCHITECTURE, PITFALLS, SUMMARY}.md · ROADMAP.md · STATE.md 생성 완료.
- 85개 v1 REQ-ID 를 5 phase 로 매핑 완료 (Phase 1: 16 · Phase 2: 28 · Phase 3: 24 · Phase 4: 9 · Phase 5: 8).
- 누적 결정: BB-1/BB-2 완료 · `main.py` 분할 완료 (1666 → 515) — 이번 milestone 에서 `main.py` 자체가 삭제 대상.

### Next session should

1. Phase 1 discuss 또는 plan 진입.
2. `/gsd-discuss-phase 1` 으로 의존성 bump · 프로토콜 정합성 · 하드닝 3 개 작업군의 상호 의존성/병렬 가능성 논의.
3. 또는 `/gsd-plan-phase 1` 으로 바로 plan 수립.

---

*State file maintained across phases and sessions.*
