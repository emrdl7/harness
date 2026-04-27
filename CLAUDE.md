# harness — Claude 에이전트 지침

이 파일은 이 레포에서 동작하는 모든 Claude/Codex/Gemini 에이전트의 기본 컨텍스트다. 간결하게 유지하라 — 세부사항은 `.planning/` 을 참조한다.

## Project

**harness** — **Claude Code 셀프호스팅** 터미널 에이전트. 집 머신에 LLM 서버(`harness_server.py` + MLX/Ollama)를 상시 구동하고, 각 사용자가 자기 PC 에서 ui-ink 클라이언트로 그 LLM 을 사용한다. **도구 실행(파일/쉘/git)은 사용자 자기 PC** 에서 일어난다 — Claude Code 가 Anthropic 서버 파일을 만지지 않듯이.

**현재 milestone**: v1.1 — Client-side Tool Execution (도구 실행을 서버 → 클라 RPC 로 이전 + BB-2 협업 인프라 deletion).

**Core Value**: 사용자가 자기 PC 에서 ui-ink 를 띄우면, 자기 PC 코드를 자기 PC 도구로 작업한다. LLM 만 집 머신을 통한다. Claude Code 와 동일한 사용자 경험.

## Operating Model (확정)

- **1인 1세션** — 1 ws ↔ 1 session ↔ 1 working_dir (사용자 자기 PC)
- **LLM** = 서버 PC (집 머신 MLX/Ollama). 멀티 테넌트 (N 사용자 동시, 컨텍스트 격리)
- **도구 — 클라 측**: fs/shell/git/MCP — 사용자 자기 PC
- **도구 — 서버 측**: search_web/fetch_page/claude_cli/improve — 외부망/API/자기수정
- **협업** = 사용자 요구 외. 외부 메신저 책임. harness 안에 Room/broadcast/presence 없음

## Planning Artifacts (모든 에이전트가 반드시 참조)

- `.planning/PROJECT.md` — v1.1 milestone 정의 · Validated · Active · Out of Scope · Key Decisions
- `.planning/CLIENT-TOOLS-DESIGN.md` — v1.1 design ground truth (도구 분류 표 · RPC 프로토콜 · phase 분해)
- `.planning/MILESTONES.md` — milestone 히스토리 (v1.0 closure + v1.1 active)
- `.planning/STATE.md` — 현재 phase · plan 위치 · next action
- `.planning/UI-RENDER-PLAN.md` — UI 렌더 V1+V2 잔여 작업 (별 트랙)

## 절대 금지 (v1.1 milestone)

- **Room / broadcast / active_input_from / presence / observer / snapshot / `/who`** 관련 코드 추가 금지 — BB-2 는 v1.1 에서 deletion 확정
- **`HARNESS_ROOM` / `--room` CLI 인자** 추가 금지 — 1인 1세션 모델
- **서버 측 fs/shell/git 도구 새로 추가 금지** — fs/shell/git 은 클라 측 (`ui-ink/src/tools/`)
- **`tool_end` broadcast 의 새 필드** 추가는 단일 사용자 가정 — `actor`/`broadcast` 같은 멀티유저 필드 금지
- **Raw alternate screen escape** (`\x1b[?1049h`) 직접 stdout — Ink `alternateScreen: true` 옵션 경유로만
- **Legacy 파일 유지하면서 새 파일 추가** — 사용자 명시: "기존 코드 유지해보니까 gsd나 다른 에이전트들이 헷깔리는 경우가 상당히 많음". 대체 구현은 old 삭제가 default
- `process.stdout.write` / `console.log` 직접 호출 (Ink 이중 렌더 붕괴)
- `<div>`/`<span>` JSX (Ink 에는 DOM 태그 없음)
- index 를 React key 로 사용 (`messages.map((m, i) => key={i})` 금지)
- 전체 store 객체 selector (`const s = useStore()` 금지 — `useShallow` 적용)

## 백엔드 경계 (v1.1 갱신)

- **유지 (서버)**: `agent.py` · `tools/web.py` · `tools/claude_cli.py` · `tools/improve.py` · `session/` · `evolution/` · `harness_core/` · `harness_server.py` (RPC 추가, Room 제거)
- **클라로 이전 (deletion 대상)**: `tools/fs.py` · `tools/shell.py` · `tools/git.py` · `tools/mcp.py`
- **deletion (BB-2)**: `harness_server.py` 의 Room/broadcast/active_input_from/snapshot/who 핸들러 · `BB-2-DESIGN.md` archive
- **신규 (클라)**: `ui-ink/src/tools/{registry,fs,shell,git,mcp}.ts`
- **신규 (서버)**: `harness_server.py` 에 `pending_calls` 딕셔너리 + `tool_request`/`tool_result` 핸들러

## 실행 / 테스트

- Python 백엔드: `.venv/bin/python harness_server.py` (Python 3.14 venv) + MLX 자동 스폰
- ui-ink: `cd ui-ink && bun install && bun start` (env: `HARNESS_URL=ws://...`, `HARNESS_TOKEN`)
- 회귀 기준: Python pytest (fs/shell/git 삭제 후 잔여) + ui-ink vitest green

## 커뮤니케이션 / 스타일

- **한국어 존댓말** (`-습니다/-입니다`) — 반말 금지
- **Git 커밋 메시지는 한국어, 명령형**
- 코드 주석은 한국어
- 들여쓰기 2 spaces · single quote · 세미콜론 없음 (TypeScript 기본 규칙)

## Workflow

GSD (`.planning/`) 워크플로우 사용. v1.1 시작 — phase 미정.

- `/gsd-progress` — 현 위치 / 다음 행동 확인
- `/gsd-discuss-phase <N>` — phase 진입 전 context 수집
- `/gsd-plan-phase <N>` — phase 계획 수립
- `/gsd-execute-phase <N>` — phase 실행

**현재 다음 행동**: v1.1 ROADMAP/REQUIREMENTS 작성 후 Phase 1 (RPC 골격 + read_file PoC) discussion. `.planning/CLIENT-TOOLS-DESIGN.md` 의 6장 phase 분해를 따른다.

## 참고

작업 전 `.planning/STATE.md` 로 현 phase 확인 → `.planning/CLIENT-TOOLS-DESIGN.md` 로 design ground truth 확인 → 관련 `.planning/phases/<N>-.../PLAN.md` (생기면) 확인. 커밋 메시지에 RPC-NN / BBR-NN / SES-NN / MCP-NN 등 REQ-ID 명시 (PROJECT.md Active 참조).
