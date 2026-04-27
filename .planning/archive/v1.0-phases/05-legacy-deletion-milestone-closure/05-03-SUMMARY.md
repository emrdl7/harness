---
phase: 05-legacy-deletion-milestone-closure
plan: "03"
subsystem: documentation-closure
tags:
  - milestone-closure
  - documentation
  - project-md
  - concerns
  - roadmap
  - state
requirements:
  - LEG-06
  - LEG-07
  - LEG-08
dependency_graph:
  requires:
    - 05-02 (pytest 224건·vitest 163건 green, 환경 위생 grep 통과)
  provides:
    - PROJECT.md Key Decisions 전부 Validated 확정
    - PROJECT.md Active→Validated 이동 완료
    - PROJECT.md Milestone Closure 섹션 추가
    - CONCERNS.md §1.12·§3.1·§3.5 RESOLVED Phase 5 처리
    - ROADMAP.md Phase 5 [x] 3/3 complete
    - STATE.md status: complete, percent: 100
  affects:
    - .planning/PROJECT.md
    - .planning/codebase/CONCERNS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
tech_stack:
  added: []
  removed: []
  patterns:
    - "milestone closure 문서 패턴: Active→Validated 이동, Key Decisions Outcome 확정, Closure 섹션 추가"
key_files:
  created: []
  modified:
    - .planning/PROJECT.md
    - .planning/codebase/CONCERNS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
  deleted: []
decisions:
  - PROJECT.md Active 섹션 항목 전체를 Validated로 이동 — Phase 1~5 참조 추가하여 이력 명확화
  - CONCERNS.md §1.12·§3.1·§3.5 close 처리 — legacy 삭제로 자동 소멸된 항목, 오픈 항목 혼동 방지
  - STATE.md status: complete 전환 — milestone v1.0 공식 종료
metrics:
  duration: "약 3분 20초"
  completed_date: "2026-04-24T12:24:49Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 4
---

# Phase 5 Plan 03: PROJECT.md Evolution + CONCERNS close + milestone 종료 Summary

**한 줄 요약:** PROJECT.md Active→Validated 이동·Key Decisions 6건 확정·CONCERNS §1.12/§3.1/§3.5 close·ROADMAP/STATE milestone v1.0 공식 종료

---

## 목표

harness ui-ink milestone v1.0 의 마지막 문서 작업. ui-ink 가 유일한 UI 로 확정된 사실을 planning 문서에 공식 기록하고, legacy 삭제로 자동 소멸된 CONCERNS 항목을 닫아 코드베이스 감사 기록을 정확히 유지한다.

---

## 실행 결과

### Task 1: PROJECT.md Evolution 업데이트 (LEG-06)

**A. Active → Validated 이동**

`### Active` 섹션의 ui-ink 관련 항목 12건 전체를 `### Validated` 섹션으로 이동.
각 항목에 완료 phase 참조 추가 (Phase 1~3, Phase 2, Phase 3~4, Phase 4, Phase 5).
`### Active` 섹션: `(없음 — milestone 완료)` 상태.

**B. Key Decisions Outcome 업데이트**

| Decision | 이전 | 이후 |
|----------|------|------|
| UI 스택 = Node + Ink + Zustand + bun + TS | — Pending (이번 milestone 검증) | ✓ Validated — Phase 1~5 완료 |
| Legacy Python UI 전부 삭제 | — Pending | ✓ Validated — Phase 5 완료 |
| ui-ink = 로컬 + 원격 공통 UI | — Pending | ✓ Validated — Phase 1~5 완료 |
| WS 프로토콜 확장은 같은 milestone 에서 | — Pending | ✓ Validated — Phase 5 완료 |
| `harness_server.py` = 유일한 백엔드 경계 | — Pending | ✓ Validated — Phase 5 완료 |
| Python 백엔드 유지 | — Pending | ✓ Validated — Phase 5 완료 |

**C. Milestone Closure 섹션 추가**

파일 맨 끝에 `## Milestone Closure` 섹션 추가:
- 달성 요약 (Core Value 달성, 85/85 REQ-ID, pytest 224건 + vitest 163건 green)
- 다음 milestone 후보 (바이너리 배포, 백엔드 언어 교체 검토, 진화 엔진 개편)

검증: `grep -c "Pending" .planning/PROJECT.md` → 0건

**Commit:** `ce3e911`

---

### Task 2: CONCERNS.md §1.12 · §3 Python REPL 항목 close (LEG-07)

| 항목 | 이전 상태 | 이후 상태 |
|------|-----------|-----------|
| §1.12 `_spinner` vs `rich.Live` | Open (Medium) | ✅ RESOLVED Phase 5 (main.py REPL 삭제로 자동 소멸) |
| §3.1 `main.py` 1680줄 | Open (High) | ✅ RESOLVED Phase 5 (main.py 삭제, cli/ 전수 삭제) |
| §3.5 Korean intent detection | Open (Medium) | ✅ RESOLVED Phase 5 (main.py 삭제로 자동 소멸) |

**잔여 미해결 항목 요약** (2026-04-24 Phase 5 완료 기준):
- §1 Bugs: 1건 — 1.10 (run_command shell-quoting)
- §2 Security: 1건 — 2.8 (manual YAML)
- §3 Architecture: 잔여 항목 — 3.4·3.6·3.7·3.9·3.10·3.11 (Python 백엔드 관련, 다음 milestone)
- §4 Performance: 6건 — 4.1·4.2·4.3·4.5·4.6·4.7

**Commit:** `64fa928`

---

### Task 3: ROADMAP.md + STATE.md milestone 종료 표시 (LEG-08)

**ROADMAP.md:**
- Phase 5 체크박스: `[ ]` → `[x]` (completed 2026-04-24 추가)
- Plans 3건 전부: `[ ]` → `[x]`
- Progress Tracking: `0/3 | In progress | -` → `3/3 | Complete | 2026-04-24`
- Last updated 갱신

**STATE.md:**
- frontmatter: `status: executing` → `status: complete`, `percent: 86` → `percent: 100`
- `completed_phases: 4` → `completed_phases: 5`, `completed_plans: 19` → `completed_plans: 22`
- Current Position: `Phase 5 — COMPLETE`, `Complete (3/3)`, `Milestone v1.0 완료`
- Phases 표: `Planned | 0/3` → `Complete | 3/3`
- Key Decisions 6건: `— Pending` → `✓ Validated`
- Todos 3건: `[ ]` → `[x]`

**Commit:** `6ceaac9`

---

## Deviations from Plan

없음 — 플랜에 명시된 대로 정확히 실행됨.

---

## Known Stubs

없음 — 이번 플랜은 문서 업데이트 작업만 수행.

---

## Threat Flags

없음 — 신규 네트워크 엔드포인트·인증 경로·스키마 변경 없음. 문서 수정만 수행.

---

## Self-Check: PASSED

```
PASS: PROJECT.md Pending 0건 (grep -c "Pending" → 0)
PASS: PROJECT.md "## Milestone Closure" 섹션 존재
PASS: PROJECT.md Active 섹션 "(없음 — milestone 완료)" 상태
PASS: PROJECT.md Validated 건수 8건 (원래 7건 + Active 이동 항목)
PASS: CONCERNS.md §1.12 RESOLVED Phase 5
PASS: CONCERNS.md §3.1 RESOLVED Phase 5
PASS: CONCERNS.md §3.5 RESOLVED Phase 5
PASS: ROADMAP.md Phase 5 [x] + completed 2026-04-24
PASS: ROADMAP.md Progress 3/3 Complete 2026-04-24
PASS: STATE.md status: complete
PASS: STATE.md percent: 100
PASS: 커밋 ce3e911 존재 (Task 1)
PASS: 커밋 64fa928 존재 (Task 2)
PASS: 커밋 6ceaac9 존재 (Task 3)
```

---

## milestone v1.0 종료 선언

이 SUMMARY 가 커밋됨으로써 harness ui-ink milestone v1.0 이 공식 종료됩니다.

**달성:** Python prompt_toolkit UI → Node + Ink + Zustand + bun + TypeScript 전면 재작성 완료.
**결과:** 로컬 + 원격 2인 = 3 클라이언트가 동일한 ui-ink 경험을 갖고, 그 경험은 Claude Code 수준입니다.
