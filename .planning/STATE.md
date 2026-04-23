# harness — ui-ink Milestone State

**Last updated:** 2026-04-24

---

## Project Reference

**See:** `.planning/PROJECT.md` (milestone 정의 · Validated · Active · Out of Scope · Key Decisions · Constraints)
**Core Value:** "ui-ink 가 harness 의 기본이자 유일한 UI. 로컬과 원격이 동일한 경험을 갖고, 그 경험은 Claude Code 수준이다."
**Current focus:** Phase 1 (Foundation — Upgrade · Protocol Fix · Hardening · Smoke)

---

## Current Position

- **Phase:** 1 — Foundation
- **Plan:** 3 plans (Wave 1: A+B 완료 / Wave 2: C 실행 중)
- **Status:** Wave 2 실행 중
- **Progress:** `[░░░░░░░░░░] 0% (0/5 phases complete)`
- **Next action:** Wave 2 Plan C 완료 후 verify

---

## Phases

| # | Name | Status | Plans |
|---|------|--------|-------|
| 1 | Foundation | Ready to execute | 3/3 |
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

- `/gsd-plan-phase 1` 실행 → Phase 1 플랜 3개 생성 완료. 검증 통과 (0 blocker, 0 warning).
- Plan A (Wave 1): 의존성 bump (ink@7/react@19.2/zustand@5), tsconfig, ESLint, CI 가드 — FND-01,02,09,10,11
- Plan B (Wave 1, 병렬): WS 프로토콜 교정, protocol.ts, ws/ 모듈, store 5 슬라이스 — FND-03..08
- Plan C (Wave 2): 하드닝, vitest 4종, end-to-end 스모크 — FND-12..16
- 이전: `/gsd-new-project` 실행 · 85 REQ-ID · ROADMAP 5 phase · BB-1/BB-2 완료.

### Next session should

1. `/gsd-execute-phase 1` — Wave 1 (Plan A + Plan B 병렬) → Wave 2 (Plan C) 순서로 실행.
2. Phase 1 exit criteria 확인: `bun start` smoke · `tsc --noEmit` green · vitest green · alternate screen 가드.

---

*State file maintained across phases and sessions.*
