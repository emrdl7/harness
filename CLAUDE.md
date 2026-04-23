# harness — Claude 에이전트 지침

이 파일은 이 레포에서 동작하는 모든 Claude/Codex/Gemini 에이전트의 기본 컨텍스트다. 간결하게 유지하라 — 세부사항은 `.planning/` 을 참조한다.

## Project

**harness** — 로컬 Ollama(`qwen2.5-coder:32b`) 기반 Claude Code 풍 터미널 에이전트. 집 머신 = `harness_server.py` WS 서버 상시 구동 / 외부 원격 2인 = `bun run` 클라이언트.

**현재 milestone**: UI 층을 Python(prompt_toolkit+Rich) → **Node + Ink + Zustand + bun + TypeScript** 로 전면 재작성.

**Core Value**: ui-ink 가 harness 의 기본이자 유일한 UI. 로컬과 원격이 동일한 경험을 갖고, 그 경험은 Claude Code 수준이다.

## Planning Artifacts (모든 에이전트가 반드시 참조)

- `.planning/PROJECT.md` — milestone 정의 · Validated · Active · Out of Scope · Key Decisions · Constraints
- `.planning/ROADMAP.md` — 5 phase (Foundation / Core UX / Remote+Session / Testing+Beta / Legacy Deletion)
- `.planning/REQUIREMENTS.md` — 85개 v1 REQ-ID + Traceability 표
- `.planning/STATE.md` — 현재 phase · plan 위치 · next action
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS,SUMMARY}.md` — 연구 결과 (phase planning 시 참조)
- `.planning/codebase/{CONCERNS,ENHANCEMENTS}.md` — 기존 Python 백엔드 감사/개선 목록 (이번 milestone 은 UI 만)
- `.planning/BB-2-DESIGN.md` — 공유 Room · turn-taking · confirm 격리 설계 (WS 프로토콜 ground truth)

## 절대 금지 (이번 milestone)

- **Alternate screen** (`\x1b[?1049h`) 또는 **mouse tracking** (`\x1b[?1000h` 계열) 출력 — 터미널 scrollback 파괴
- **Python UI 병존 유지** — PROJECT.md Key Decision. `main.py` REPL / `cli/tui.py` / `cli/app.py` / `ui/index.js` 전부 Phase 5 에서 삭제 대상. 새 기능을 Python REPL 에 추가하지 말 것
- **Textual / curses / urwid** 같은 풀스크린 TUI 제안 — 영구 봉인 (`~/.claude/projects/-Users-johyeonchang-harness/memory/feedback_claude_code_ui.md` 참조)
- **Legacy 파일 유지하면서 새 파일 추가** — 사용자 명시: "기존 코드 유지해보니까 gsd나 다른 에이전트들이 헷깔리는 경우가 상당히 많음". 대체 구현은 old 삭제가 default
- `process.stdout.write` / `console.log` 직접 호출 (Ink 이중 렌더 붕괴)
- `child_process.spawn` 클라이언트 실행 (Ink 화면 박살)
- `<div>`/`<span>` JSX (Ink 에는 DOM 태그 없음)
- index 를 React key 로 사용 (`messages.map((m, i) => key={i})` 금지)
- 전체 store 객체 selector (`const s = useStore()` 금지 — `useShallow` 적용)

## 백엔드 경계

- **유지**: `agent.py` · `tools/` · `session/` · `evolution/` · `harness_core/` · `harness_server.py`
- **변경 허용 (이번 milestone)**: `harness_server.py` 및 `harness_core`/`session/` 에 WS 프로토콜 확장 5건(REQUIREMENTS PEXT-01..05) — 기존 이벤트 의미 변경 금지, 필드/메시지 추가 OK
- **삭제 (Phase 5)**: `main.py` REPL 경로 · `cli/intent.py` · `cli/render.py` · `cli/claude.py` · `cli/setup.py` · `cli/callbacks.py` · `cli/slash.py` · `cli/tui.py` · `cli/app.py` · `ui/index.js`

## 실행 / 테스트

- Python 백엔드: `.venv/bin/python harness_server.py` (Python 3.14 venv), pytest 현 199+건
- ui-ink: `cd ui-ink && bun install && bun start` (env: `HARNESS_URL=ws://127.0.0.1:7891`, `HARNESS_TOKEN`, `HARNESS_ROOM`)
- 회귀 기준: Python pytest 199건 유지 + ui-ink vitest green

## 커뮤니케이션 / 스타일

- **한국어 존댓말** (`-습니다/-입니다`) — 반말 금지
- **Git 커밋 메시지는 한국어, 명령형** (예: `fix:` 또는 기존 포맷 그대로)
- 코드 주석은 한국어
- 들여쓰기 2 spaces · single quote · 세미콜론 없음 (TypeScript 기본 규칙 따름)

## Workflow

GSD (`.planning/`) 워크플로우 사용. 주요 명령:

- `/gsd-progress` — 현 위치 / 다음 행동 확인
- `/gsd-plan-phase <N>` — phase 계획 수립
- `/gsd-execute-phase <N>` — phase 실행
- `/gsd-discuss-phase <N>` — phase 진입 전 context 수집

현재 다음 행동: **`/gsd-plan-phase 1`** (Phase 1: Foundation)

## 참고

에이전트는 작업 전 `.planning/STATE.md` 로 현 phase 를 먼저 확인하고, 관련 `.planning/phases/<N>-.../PLAN.md` (생기면) 를 읽은 뒤 코드를 수정한다. 85개 REQ-ID 중 어느 것을 건드리는지 커밋 메시지에 명시하면 Traceability 가 유지된다 (예: `feat(FND-03): WS 이벤트 이름 교정`).
