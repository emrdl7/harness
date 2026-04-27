# harness — Roadmap

## Milestones

- ✅ **v1.0 ui-ink UI 재작성** — Phases 1–5 (shipped 2026-04-24) · [archive](milestones/v1.0-ROADMAP.md)
- 🔄 **v1.1 Client-side Tool Execution** — Phases 1–5 (started 2026-04-27)

## v1.1 Phases (active)

> Source of truth: `.planning/CLIENT-TOOLS-DESIGN.md` 6장.
> 운영 모델 = Claude Code 셀프호스팅 1인 1세션. 도구 실행을 클라 측으로 RPC 위임 + BB-2 협업 인프라 deletion.

### Phase 1 — rpc-skeleton (RPC 골격 + read_file PoC)
- dir: `.planning/phases/01-rpc-skeleton/`
- 목표: WS RPC 패턴 검증. 외부 PC 클라가 자기 PC `read_file` 결과 받는 것 수동 검증
- 변경: `protocol.ts` `tool_request`/`tool_result` 타입 · `harness_server.py` `pending_calls` + dispatch · `agent.py` `CLIENT_SIDE_TOOLS = {'read_file'}` 분기 · `ui-ink/src/tools/{registry,fs}.ts` 의 `read_file` · `ws/dispatch.ts` `tool_request` 핸들러
- 삭제: `tools/fs.py:read_file` + 관련 pytest
- REQ: RPC-01, RPC-02, RPC-03 (read_file 부분), RPC-05 (read_file)
- **Plans:** 3 plans (Wave 1/2/3 직렬)
  - [ ] 01-01-PLAN.md — TS 측: protocol.ts RPC 메시지 + tools/{fs,registry}.ts + dispatch.ts + App.tsx 배선 (RPC-01, RPC-03)
  - [ ] 01-02-PLAN.md — Python 측: harness_server.py pending_calls + rpc_call + tool_result dispatch + agent.py CLIENT_SIDE_TOOLS 분기 (RPC-01, RPC-02)
  - [ ] 01-03-PLAN.md — vitest 5케이스 + Python read_file deletion + 외부 PC 수동 검증 (RPC-03, RPC-05)

### Phase 2 — fs-tools (fs 도구 전체 클라 이전)
- dir: `.planning/phases/02-fs-tools/`
- 목표: write/edit/list/grep 까지 클라. confirm 클라 측 통합
- 변경: `tools/fs.ts` 전체 + confirm 다이얼로그 → 클라 측 실행 (broadcast 없음)
- 삭제: `tools/fs.py` 전체 + pytest fs 케이스 (~30건)
- vitest: fs 동등 회귀 ~30건
- REQ: RPC-03 (fs 전체), RPC-04, RPC-05 (fs)

### Phase 3 — shell-git (shell + git 클라 이전)
- dir: `.planning/phases/03-shell-git/`
- 목표: 사용자 PC 쉘 / 사용자 repo git 작업
- 변경: `tools/shell.ts` (Bun child_process spawn, simple — PTY v1.2+) + `tools/git.ts` + 위험 명령 분류 클라 측 재구현
- 삭제: `tools/shell.py` `tools/git.py` + pytest 케이스 (~25건)
- vitest: shell/git ~25건
- REQ: RPC-03 (shell/git), RPC-05 (shell/git), RPC-06

### Phase 4 — bb2-deletion-session (BB-2 deletion + RX-02 세션 클라 이전)
- dir: `.planning/phases/04-bb2-deletion-session/`
- 목표: 협업 인프라 일괄 제거. 1인 1세션 단순 구조 확정
- 삭제 (server): `Room` dataclass · `ROOMS` · `_get_or_create_room` · `_maybe_drop_room` · `broadcast` · `broadcast_state` · `active_input_from` · `room_joined`/`room_busy`/`room_member_*`/`state_snapshot` · `/who` 슬래시
- 삭제 (client): `PresenceSegment` `ReconnectOverlay` `ObserverOverlay` `store/room.ts` `protocol.ts` room_* 타입 · `--room` CLI · `HARNESS_ROOM` env
- 삭제 (test): pytest Room 관련 ~30건 + vitest room 관련
- archive: `.planning/BB-2-DESIGN.md` → `.planning/archive/`
- 변경: RX-02 세션 위치 = 클라 `./.harness/sessions/`
- REQ: BBR-01, SES-01

### Phase 5 — mcp-cleanup (MCP 클라 이전 + 문서 갱신)
- dir: `.planning/phases/05-mcp-cleanup/`
- 목표: MCP 가 사용자 IDE/DB 와 붙는 정상 동작
- 변경: `tools/mcp.py` → ui-ink 측 (sidecar 또는 직접). `~/.harness/mcp.json` 정의 위치 = 클라
- 변경: PROTOCOL.md / CLIENT_SETUP.md / RELEASE_NOTES.md 갱신 (RPC, --room 제거, 1인 1세션)
- 정리: `tools/__init__.py` import · `agent.py` dispatch 단순화
- 회귀: pytest 잔여 (web/claude_cli/improve/hooks) green + vitest 전체 green
- REQ: MCP-01, DOC-01

## v1.0 (archived)

<details>
<summary>✅ v1.0 ui-ink UI 재작성 (Phases 1–5) — SHIPPED 2026-04-24</summary>

- [x] Phase 1: Foundation (3/3 plans) — completed 2026-04-23
- [x] Phase 2: Core UX (5/5 plans) — completed 2026-04-24
- [x] Phase 3: Remote Room + Session Control (6/6 plans) — completed 2026-04-24
- [x] Phase 4: Testing + Docs + External Beta (5/5 plans) — completed 2026-04-24
- [x] Phase 5: Legacy Deletion + Milestone Closure (3/3 plans) — completed 2026-04-24

archive: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md), [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md)

</details>

## Progress (v1.1)

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. RPC 골격 + read_file PoC | 0/3 | Not started | — |
| 2. fs 도구 전체 클라 이전 | 0/? | Not started | — |
| 3. shell + git 클라 이전 | 0/? | Not started | — |
| 4. BB-2 deletion + RX-02 세션 이전 | 0/? | Not started | — |
| 5. MCP 클라 이전 + cleanup | 0/? | Not started | — |

---

*Last updated: 2026-04-27 — v1.1 phase breakdown*
