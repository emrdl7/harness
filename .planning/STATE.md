---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: client-side-tool-execution
status: Phase 01 완료 (RPC 골격 + read_file PoC). Phase 02 대기.
last_updated: "2026-04-28"
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 20
---

# harness — v1.1 Client-side Tool Execution Milestone State

**Last updated:** 2026-04-27

---

## Project Reference

**Milestone def:** `.planning/PROJECT.md` (v1.1)
**Design ground truth:** `.planning/CLIENT-TOOLS-DESIGN.md`
**Roadmap:** `.planning/ROADMAP.md` — 5 phase
**Requirements:** `.planning/REQUIREMENTS.md` — RPC-01~06, BBR-01, SES-01, MCP-01, DOC-01

**Core Value:** "사용자가 자기 PC 에서 ui-ink 를 띄우면, 자기 PC 코드를 자기 PC 도구로 작업한다. LLM 만 집 머신을 통한다. Claude Code 와 동일한 사용자 경험."

---

## Current Position

Phase: 01 (rpc-skeleton) — EXECUTING
Plan: 3 of 3
**Phase 1 — rpc-skeleton** (RPC 골격 + read_file PoC)

- **Phase dir:** `.planning/phases/01-rpc-skeleton/`
- **Status:** Executing Phase 01 — Plan 01 + Plan 02 완료
- **Progress:** [███████░░░] 67%
- **Next action:**
  1. Plan 03 (vitest read_file 5케이스 + Python deletion + 수동 검증) 실행

---

## Phases (v1.1)

| # | Slug | Status | CONTEXT | PLAN |
|---|------|--------|---------|------|
| 1 | rpc-skeleton | In progress (2/3) | ✓ | ✓ |
| 2 | fs-tools | Not started | — | — |
| 3 | shell-git | Not started | — | — |
| 4 | bb2-deletion-session | Not started | — | — |
| 5 | mcp-cleanup | Not started | — | — |

---

## Key Decisions (from PROJECT.md)

- 운영 모델 = Claude Code 셀프호스팅 (1인 1세션) — 사용자 발화 2026-04-27
- 도구 위치: fs/shell/git/MCP = 클라, web/claude_cli/improve = 서버
- BB-2 코드 전체 deletion (Phase 4) — 사용자 발화 *"같은 방에서 만날 필요 자체가 없다. 메신저 좋다"*
- RPC = WS 위임 (별도 transport 아님). call_id correlation + asyncio.Future
- Python 측 도구 deletion = phase 별 즉시 (CLAUDE.md "legacy 삭제 default")
- RX-02 세션 = 클라 단독 `./.harness/sessions/` (Phase 4 에서 이전)

---

## Session Continuity

### Last session summary (2026-04-27)

- Plan 01-02 실행 완료 — Python 백엔드 (harness_server.py + agent.py) 에 RPC 위임 골격 추가
- harness_server.py: ws._pending_calls + run_agent.rpc_call 클로저 + _dispatch_loop tool_result case + finally cleanup
- agent.py: CLIENT_SIDE_TOOLS = {'read_file'} + run() 의 rpc_call 인자 + line 564 직전 분기 + file_path alias 정규화
- 신규 pytest 7건 (test_rpc_bridge 3 + test_agent_client_side_dispatch 4) — 전체 234 green (227 baseline + 7), 회귀 0
- Deviation 1건: alias 정규화 dict spread 패턴 버그 자동 수정 (`{**args, ...args.pop()}` → `dict(args)` 카피 후 pop+assign)

### Decisions

- RPC bridge: confirm_write 패턴 응용 (D-09) — Event 대신 asyncio.Future 로 결과값 운반. asyncio.shield 로 외부 cancel 보호
- ws._pending_calls (D-05): Room 단위 X, ws scope dict[str, asyncio.Future]. BB-2 deletion 후에도 변경 0
- alias 정규화 (D-16): dict(args) 카피 후 pop+assign — {**args, ...args.pop()} 패턴이 양쪽 키 잔존 버그 발생하므로 회피

### Next session should

1. `/gsd-execute-phase 1` 의 Plan 03 실행 — vitest read_file 5케이스 + tools/fs.py:read_file deletion + 수동 검증
2. Phase 1 의 D-19 수동 검증 — 외부 PC ui-ink → `read_file` → 외부 PC 파일이 LLM 컨텍스트에 들어가는지 확인

---

## v1.0 (closed 2026-04-24)

archive: `.planning/milestones/v1.0-ROADMAP.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`, `.planning/archive/v1.0-phases/`
delivered: ui-ink UI 재작성, 85 REQ-ID, pytest 224건+vitest 163건 green
v1.1 정정 항목: 협업 모델 ("백엔드 공유" → "모델 공유"), BB-2 deletion 확정

---

*State file maintained across phases and sessions.*

**Planned Phase:** 01 (rpc-skeleton) — 3 plans — 2026-04-27T13:05:43.533Z
