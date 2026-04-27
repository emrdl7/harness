# harness — Client-side Tool Execution milestone (v1.1)

## What This Is

harness 는 **Claude Code 셀프호스팅** 터미널 에이전트이다. 집 머신에 LLM 서버(`harness_server.py` + MLX/Ollama)를 상시 구동해두고, 각 사용자가 자기 PC 에서 ui-ink 클라이언트를 띄워 그 LLM 을 사용한다. 도구 실행(파일/쉘/git)은 **각 사용자 자기 PC** 에서 일어난다 — Claude Code 가 Anthropic 서버 파일을 만지지 않고 사용자 로컬 머신을 만지는 것과 동일한 모델.

이번 milestone(v1.1)은 v1.0 의 잘못된 "백엔드 공유" 모델 — 도구가 서버 측에서 도는 — 을 **Claude Code 셀프호스팅 모델** 로 정정한다. 도구 실행을 클라이언트 측으로 이전하고, 사용자 요구가 아니었던 BB-2 협업 인프라(Room/broadcast/presence)는 일괄 제거한다.

## Core Value

**"사용자가 자기 PC 에서 ui-ink 를 띄우면, 자기 PC 의 코드를 자기 PC 의 도구로 작업한다. LLM 만 집 머신을 통한다. Claude Code 와 동일한 사용자 경험."**

## Operating Model (확정)

- **1인 1세션** — 1 ws ↔ 1 session ↔ 1 working_dir (사용자 자기 PC)
- **LLM** = 서버 PC (집 머신 MLX/Ollama). 멀티 테넌트 (N 사용자 동시 접속, 컨텍스트 격리)
- **도구** (fs/shell/git/MCP) = 사용자 자기 PC. 서버는 RPC 로 위임
- **도구 (서버 측)** = `search_web`/`fetch_page`/`claude_cli`/`improve` — 외부망/API/자기수정 일관성
- **협업** = 사용자 요구 외. 외부 메신저(슬랙/디스코드) 책임. harness 안에 Room/broadcast/presence 없음

## Requirements

### Validated (이전 milestone v1.0 산출물 중 v1.1 에서 그대로 사용)

- ✓ Ollama/MLX 기반 agent 루프 (`agent.py`) — 툴 콜 · reflection · MAX_TOOL_RESULT_CHARS — existing
- ✓ ui-ink 코어 UX — 입력/스트리밍 렌더/슬래시 popup/confirm 다이얼로그/StatusBar/스크롤 — Phase 1~3 (v1.0)
- ✓ Tool 결과 렌더 (V1+V2) — BashBlock/GrepResultBlock/ListFilesBlock/ReadFileBlock/FileEditBlock/GitLogBlock/WebSearchBlock + R1~R5 자동 컬러링 (v1.0 종료 후)
- ✓ AR-01 tool registry · AR-02 60fps coalescer · AR-04 input queue · IX-01 `@` 파일 픽커 · RX-01 context auto-compact · RX-02 simple session — UI-RENDER-PLAN.md 참조
- ✓ 배포 하드닝 — `HARNESS_TOKENS` · `HARNESS_BIND=127.0.0.1` · shell classifier · fs sandbox · `run_python` confirm — existing
- ✓ MLX 백엔드 (`mlx_lm.server` qwen3.6 27B 4bit) — 서버 시작 시 자동 스폰 — 2026-04-26

### Active (v1.1 신규)

- RPC-01 — WS 프로토콜에 `tool_request` / `tool_result` 추가, 서버 측 `room.pending_calls`(또는 `session.pending_calls`) 도입
- RPC-02 — `agent.py` 의 도구 dispatch 분기 — 클라 위임 도구 vs 서버 도구. 첫 PoC = `read_file`
- RPC-03 — ui-ink 측 `tools/registry.ts` + `tools/fs.ts shell.ts git.ts` (Bun child_process 기반)
- RPC-04 — Confirm 플로우 클라 측 통합 — 다이얼로그 → 사용자 응답 → 클라 도구 실행 (BB-2 broadcast 없음)
- RPC-05 — pytest fs/shell/git 케이스를 vitest 동등 변환 (~70건 추정)
- RPC-06 — `tools/fs.py` `tools/shell.py` `tools/git.py` 삭제 + pytest 삭제 (CLAUDE.md "legacy 삭제 default")
- BBR-01 — BB-2 코드 일괄 deletion: `harness_server.py` Room/broadcast/active_input_from/snapshot/who, ui-ink `PresenceSegment`/`ReconnectOverlay`/`ObserverOverlay`/`store/room.ts`, `protocol.ts` room_*, `--room`/`HARNESS_ROOM` env, 관련 pytest/vitest, `BB-2-DESIGN.md` archive
- SES-01 — RX-02 세션 위치 = 서버 측 → 클라 측 `./.harness/sessions/` 로 이전
- MCP-01 — `tools/mcp.py` → ui-ink 측 (sidecar 또는 직접). `~/.harness/mcp.json` 정의 위치 = 클라 측
- DOC-01 — PROTOCOL.md 갱신 (RPC 추가, room_* 제거), CLIENT_SETUP.md 갱신 (--room 제거, 1인 1세션 명시)

### Out of Scope

- **협업 기능** (Room/broadcast/presence/공동 컨텍스트) — 사용자가 명시: *"같은 방에서 만날 필요 자체가 없다. 메신저 좋다"* (2026-04-27). 협업이 필요하면 외부 메신저 사용
- **PTY 기반 shell** — `run_command` 는 simple spawn 시작. PTY 는 v1.2+ 후보
- **Anthropic API 직접 호출** — `tools/claude_cli.py` (Claude CLI `--print` 위임) 유지
- **바이너리 배포 / 자동 업데이트 / Homebrew 탭** — 외부 사용자는 `git clone + bun install + bun start` 전제
- **백엔드 언어 교체** (Python → TS 등) — 클라 측 도구만 TS, 서버 측 agent/세션/web/improve 은 Python 유지
- **진화 엔진 대규모 개편** — 별도 milestone

## Context

**기술 환경**
- Python 3.14 venv + websockets 16 + asyncio · MLX/Ollama (집 머신 LLM)
- ui-ink: bun + TypeScript + React (Ink) + Zustand · Bun child_process (도구 실행)
- 1 사용자 = 1 ws = 1 session = 1 working_dir (자기 PC). 서버는 N session 동시 보유

**누적 결정 (이전 milestones)**
- v1.0 (2026-04-22 → 2026-04-24) — UI 층 Python → ui-ink 재작성. **단, 협업 모델을 "백엔드 공유" 로 잘못 옮긴 결과 도구가 서버 측에서 동작 → v1.1 에서 정정**
- BB-1 (harness_core) — 슬래시 명령 코어 분리. 1인 1세션 모델에서도 그대로 사용 가능
- BB-2 (Room) — **v1.1 에서 폐기 확정** (사용자 요구 아니었음, 메신저로 대체)
- MLX 마이그레이션 — Ollama → mlx_lm.server. 서버 시작 시 자동 스폰

**알려진 배경 이슈**
- v1.0 PROJECT.md 의 "하나의 백엔드 공유" 표현이 사용자 의도("LLM 만 공유, 도구는 각자 PC")와 어긋났던 것이 v1.1 milestone 의 트리거
- `.planning/CLIENT-TOOLS-DESIGN.md` — 본 milestone 의 ground truth design doc

## Constraints

- **Tech stack**: 서버 = Python 3.14 (도구 일부만 잔존, fs/shell/git 은 클라). 클라 = bun + TS + Ink + Zustand
- **Compatibility**: WS 프로토콜은 RPC 추가 + room_* 제거. 기존 클라이언트 호환 안 됨 = `harness_server.py` ↔ ui-ink 동시 갱신
- **Deployment**: 사용자 = `git clone + bun install + bun start`. 서버 운영자 = `git clone + .venv + python harness_server.py`. 둘이 별도 PC 가능
- **Security**: `HARNESS_TOKENS` 멀티유저 인증 유지. `HARNESS_BIND` 외부 노출은 명시적 opt-in. 도구 실행이 클라 측이라 서버는 더 이상 사용자 fs 와 직접 접촉 안 함
- **Confirm**: 클라 측 자체 다이얼로그. 서버는 "이 도구 호출 허용?" 메타도 안 묻고 그냥 tool_request 보냄. 클라가 자기 사용자에게만 묻고 결정
- **RPC 신뢰성**: 타임아웃 30s 기본, run_command 별도. 클라 disconnect 시 pending tool calls 일괄 cancel
- **Testing**: Python pytest 회귀 0 (fs/shell/git deletion 분 제외). ui-ink vitest 회귀 0 + RPC-* 신규 케이스 추가

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 운영 모델 = Claude Code 셀프호스팅 (1인 1세션) | 사용자 발화 *"Claude Code 가 어디 Anthropic 서버 파일 수정하냐"* (2026-04-27). v1.0 의 "백엔드 공유" 는 잘못된 의역 | v1.1 진행 중 |
| 도구 실행 위치 = 클라 (fs/shell/git/MCP) + 서버 (web/claude_cli/improve) | LLM 한테 자기 PC 코드 작업시키는 게 목적. 외부망/자기수정만 서버 측 일관성 | v1.1 진행 중 |
| BB-2 코드 전체 deletion | 사용자 발화 *"같은 방에서 만날 필요 자체가 없다. 메신저 좋다"* (2026-04-27). 사용자 요구 아니었음 | v1.1 진행 중 |
| RPC = WS 위임 (별도 transport 아님) | 기존 WS 채널 재사용. call_id correlation + asyncio.Future | v1.1 진행 중 |
| Python 측 도구 deletion 시점 = 즉시 (phase 별) | CLAUDE.md "legacy 삭제 default". dual-stack 유지 비용 > 일시 회귀 위험 | v1.1 진행 중 |
| RX-02 세션 = 클라 측 단독 | 서버는 사용자 PC fs 모름. session 메타도 사용자 PC 에 둠 | v1.1 진행 중 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

## Previous Milestone Closure — v1.0 (ui-ink UI 재작성)

**Milestone:** v1.0 — ui-ink UI 재작성
**Completed:** 2026-04-24
**Phases:** 5/5 완료

### 달성

- ui-ink 가 harness 의 기본이자 유일한 UI (UI 층 Python → bun+TS+Ink 전면 재작성)
- 85/85 v1 REQ-ID 구현
- WS 프로토콜 확장 5건 (PEXT-01~05)
- Python pytest 224건 + ui-ink vitest 163건 green
- Python prompt_toolkit UI 5,440줄 deletion

### v1.1 에서 정정/폐기되는 항목

- **"하나의 백엔드 공유" 협업 모델** — 사용자 의도 *"Claude Code 처럼"* 의 잘못된 의역. v1.1 에서 1인 1세션 + LLM 만 공유로 정정
- **BB-2 (Room/broadcast/presence/active_input_from/snapshot/who)** — 사용자 요구 아니었음 (*"되네?" 하면서 지켜본 것뿐, 같은 방에서 만날 필요 자체가 없다*). v1.1 에서 일괄 deletion
- **PROTOCOL.md room_\* 메시지** — RPC 신설 + room_* 제거로 갱신

### 그대로 유지

- ui-ink 코어 UX 컴포넌트 (Message/Input/Slash/Confirm/StatusBar/Scrollback)
- AR-01 tool registry, V1 의 R1~R5/T1~T6 시각화 (BB-2 와 독립)
- harness_core 슬래시 명령 13/14 (1인 세션에서도 동등 동작)
- MLX 백엔드 마이그레이션
- 배포 하드닝 체크리스트

---
*Last updated: 2026-04-27 — v1.1 milestone 시작*
