# harness — Ink UI 재작성 milestone

## What This Is

harness 는 로컬 Ollama(`qwen2.5-coder:32b` 등) 기반의 Claude Code 풍 터미널 에이전트이다. 집 머신에 `harness_server.py` 를 상시 구동해두고, 로컬 사용자 + 외부 원격 2인이 각자 장비에서 접속해 하나의 백엔드를 공유한다. 이번 milestone 은 **UI 층을 Python(prompt_toolkit + Rich)에서 Node + Ink + Zustand + bun + TypeScript 로 전면 재작성** 해 로컬·원격이 동일한 ui-ink 클라이언트를 쓰도록 통일한다.

## Core Value

**"ui-ink 가 harness 의 기본이자 유일한 UI. 로컬과 원격이 동일한 경험을 갖고, 그 경험은 Claude Code 수준이다."**

이 한 문장이 우선순위 판단 기준이다. 백엔드 기능 추가·진화 엔진 개선 등이 이 목표와 충돌하면 뒤로 미룬다. 반대로 UI 요구가 백엔드 프로토콜 변경을 요구하면 같은 milestone 에서 처리한다.

## Requirements

### Validated

<!-- 기존 코드로 이미 동작하고 신뢰 가능한 기능. 이번 milestone 에서 건드리지 않거나 인터페이스만 맞춘다. -->

- ✓ Ollama 기반 agent 루프 (`agent.py`) — 툴 콜 · reflection · MAX_TOOL_RESULT_CHARS — existing
- ✓ 툴 레이어 (`tools/fs.py · shell.py · git.py · web.py · claude_cli.py` 외) — 샌드박스 + shell 인젝션 방어 포함 — existing
- ✓ 세션 저장/복원 (`session/store.py · compactor.py · logger.py · analyzer.py`) — existing
- ✓ 진화 엔진 (`evolution/*`) — idle_runner · proposer · executor · scorer · tracker. 원격 활성 시 skip, git 커밋 강제 — existing
- ✓ `harness_core/` (13/14 슬래시 명령 · SlashContext · dispatch) — BB-1 — existing
- ✓ `harness_server.py` WS 서버 — 다중 방(Room) · turn-taking · confirm 격리 · state snapshot · `/who` — BB-1, BB-2 — existing
- ✓ 배포 하드닝 — `HARNESS_TOKENS` · `HARNESS_BIND=127.0.0.1` 기본 · shell classifier · fs sandbox · `run_python` confirm 강제 — existing
- ✓ `ui-ink/` 에 모든 핵심 UX 구현 — 입력 · 슬래시 · confirm 다이얼로그 · tool 결과 렌더 · status bar · 스크롤 · 리모트 룸 · one-shot/resume — Phase 1~3
- ✓ 멀티라인 입력 (Enter=제출 / Shift+Enter=개행) + 슬래시 자동완성 popup — Phase 2
- ✓ `confirm_write` · `confirm_bash` 전용 다이얼로그 (diff Panel · 코드 미리보기 · y/n) — Phase 2
- ✓ Tool 결과 렌더 (diff hunks · 코드 펜스 Syntax highlight · Write 요약) — Phase 2
- ✓ Status bar 세그먼트 — path · model · turn · mode · ctx · room presence — Phase 2
- ✓ 스크롤 지원 — PgUp/PgDn, 마우스 휠, scrollback 유지 (alternate screen 금지) — Phase 2
- ✓ 리모트 룸 UX — 멤버 목록, busy 표시, 입력 주체 시각화, 새 join 시 snapshot 로드 — Phase 3
- ✓ One-shot (`harness "질문"`) 과 resume (`harness --resume <id>`) 모드 — Phase 3
- ✓ 원격 2인도 ui-ink 를 공식 클라이언트로 사용 (`bun run` 또는 배포 번들) — `ui/index.js` 완전 대체 — Phase 3
- ✓ WS 프로토콜 명세 문서화 + 확장 5건 (PEXT-01~05) — Phase 3~4
- ✓ **Legacy UI 삭제** — `main.py` REPL 경로 · `cli/tui.py` · `cli/app.py` · `ui/index.js` — Phase 5
- ✓ ui-ink 자체 테스트 스캐폴드 (vitest 163건) — REPL 피처 동등 + 회귀 가드 — Phase 4

### Active

(없음 — milestone 완료)

### Out of Scope

<!-- 이번 milestone 에서 의도적으로 제외. 이유가 반드시 따라붙는다. -->

- Textual · curses · urwid 등 Python 풀스크린 TUI — **Claude Code 급 UX 를 Python 으로 재현 불가** 가 2026-04-23 세션 전반에서 검증됨. 영구 봉인.
- Python UI 층 유지/병존 — **에이전트가 old/new 혼동하는 사고가 반복** 되어 사용자가 명시적으로 "legacy 유지 금지" 요청.
- Electron / 웹 UI / 브라우저 클라이언트 — 터미널 네이티브 UX 가 목표이므로 이번 milestone 밖.
- 바이너리 배포 · 자동 업데이트 · Homebrew 탭 — 외부 사용자 2인은 `git clone` 전제, 배포 편의성은 다음 milestone 후보.
- 백엔드 언어 교체 (Python → TS 등) — UI 만 Ink, 백엔드는 Python 유지. 한 번에 하나씩.
- 진화 엔진 대규모 개편 — 필요시 소규모 수정은 허용하되 프로젝트 목표 아님.
- Claude API 직접 호출 — `tools/claude_cli.py`(Claude CLI `--print` 위임) 이 이미 충분.

## Context

**기술 환경**
- Python 3.14 venv (프리릴리스) · Ollama 로컬 · websockets 16 · Rich · prompt_toolkit (Python REPL 은 이번 milestone 에서 삭제 예정)
- 신규: bun · TypeScript · React (via Ink) · Zustand · Yoga layout · chalk · open source Ink ecosystem
- 집 머신 = 상시 서버 / 외부 2인 = `bun run` 클라이언트 + `HARNESS_TOKENS` 토큰 + `HARNESS_URL` WS 주소 + `HARNESS_ROOM` 룸 이름

**누적 결정 (이전 세션들)**
- BB-1 (harness_core) 완료 — 슬래시 명령 13/14 가 main 과 server 양쪽에서 동일 로직 공유
- BB-2 (공유 룸) 완료 — 여러 WS 가 한 `Room` 을 공유, turn-taking, confirm 격리, state snapshot, `/who`
- 배포 하드닝 체크리스트 전부 체크 완료 — 서버 거부/바인딩/샌드박스/shell 분류/자가수정 git commit
- `main.py` 분할(§3.1) 완료 — 1666 → 515 줄. `cli/intent · render · claude · setup · callbacks · slash` 로 모듈화. **이번 milestone 에서 `main.py` 자체가 삭제 대상이므로 위 모듈들의 운명도 함께 결정 필요.**
- Ink 방향 전환(2026-04-23) — Python prompt_toolkit Application + patch_stdout 시도가 Claude Code UX 재현에 실패 (prompt_toolkit renderer 가 wrap 추적 불가) → 스택 교체 결론

**알려진 배경 이슈 (CONCERNS 잔여)**
- §1.10 `run_command` shell-quoting Edge — sticky-deny 로 부분 완화. Ink 재작성과 독립이므로 이번 milestone 에선 건드리지 않음.
- §1.12 spinner vs Live — Python REPL 버그. **legacy 삭제와 함께 자동 소멸.**
- §3 Architecture 잔여 7건 — 대부분 Python REPL 관련 리팩터. **legacy 삭제로 자동 처리되는 항목 검토 필요.**
- CONCERNS · ENHANCEMENTS 전체는 `.planning/codebase/` 에 보존됨. 참조만 하고 이번 milestone 에 끌어오진 않음.

## Constraints

- **Tech stack**: UI = Node 20+ · bun · TypeScript · Ink(React) · Zustand. 백엔드는 Python 3.14 유지. 두 스택이 섞이지 않도록 디렉토리 경계 명확.
- **Compatibility**: `harness_server.py` WS 프로토콜은 **기존 이벤트 타입을 깨지 않고 확장** (신규 필드 추가 OK, 기존 필드 의미 변경 금지). 서버 버전과 ui-ink 버전이 일정 기간 호환 유지.
- **Deployment**: 외부 2인이 `git clone + bun install + bun start` 로 실행 가능해야 함. 패키지 매니저 전제 = **bun** (npm/pnpm 혼재 금지).
- **Security**: 토큰 = `HARNESS_TOKENS` 환경변수. ui-ink 는 토큰을 파일에 저장하지 않음 (env var 또는 대화형 입력). `HARNESS_BIND` 외부 노출은 명시적 opt-in 유지.
- **Dependency discipline**: Ink 생태계에서 small, well-maintained 패키지 선호. `ink-select-input`, `ink-text-input`, `ink-spinner` 등 공식 wrapper 우선. 자체 작성은 명확한 이유가 있을 때만.
- **Terminal UX 원칙**: alternate screen 사용 금지. 터미널 scrollback 유지 (사용자가 Cmd+C 로 과거 출력 복사 가능). 이건 Claude Code 와 동일한 핵심 UX.
- **Testing**: Python 백엔드 pytest 회귀 0. Ink 는 bun test 또는 vitest + ink-testing-library. Ink 쪽 테스트 부재 = 블로커로 승격.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| UI 스택 = Node + Ink + Zustand + bun + TS | Claude Code 본체와 동일 스택. Python(prompt_toolkit/Rich)로 재현 불가 검증됨. | ✓ Validated — Phase 1~5 완료 |
| Legacy Python UI 전부 삭제 (`main.py` REPL · `cli/tui.py` · `cli/app.py` · `ui/index.js`) | 사용자 명시: "기존 코드 유지해보니까 gsd나 다른 에이전트들이 헷깔리는 경우가 상당히 많음". 새 구현이 old 를 대체할 때 old 를 남기지 않는다. | ✓ Validated — Phase 5 완료 |
| ui-ink 가 로컬 + 원격 공통 UI | "외부 원격 클라이언트 또한 동일 ui로 사용해야 함" 사용자 결정. 유지 비용 절반. | ✓ Validated — Phase 1~5 완료 |
| WS 프로토콜 확장은 같은 milestone 에서 자유롭게 | UI 요구에 맞춰 한 번에 정리. 이후 drift 최소화. | ✓ Validated — Phase 5 완료 |
| `harness_server.py` = 유일한 백엔드 경계 | CLI/원격 이분이 없어짐. server 하나만 유지하면 됨. | ✓ Validated — Phase 5 완료 |
| Python 백엔드(agent/tools/session/evolution/core) 유지 | UI 만 교체. 한 번에 하나씩. 백엔드 교체는 별도 milestone 후보. | ✓ Validated — Phase 5 완료 |

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

## Milestone Closure

**Milestone:** v1.0 — ui-ink UI 재작성
**Completed:** 2026-04-24
**Phases:** 5/5 완료

### 달성 요약

- ui-ink 가 harness 의 기본이자 유일한 UI 로 확정 (Core Value 달성)
- 로컬 + 원격 2인 = 3 클라이언트가 동일한 ui-ink 클라이언트 사용
- Python prompt_toolkit UI 전수 삭제 — 에이전트 혼동 원인 제거
- 85/85 v1 REQ-ID 전부 구현 완료
- WS 프로토콜 확장 5건(PEXT-01~05) stable
- Python pytest 224건 + ui-ink vitest 163건 전 케이스 green

### 다음 milestone 후보

- 바이너리 배포 (bun build --compile 단일 실행파일)
- 백엔드 언어 교체 검토 (별도 milestone)
- 진화 엔진 개편 (별도 milestone)

---
*Last updated: 2026-04-24 — milestone v1.0 완료*
