# Project Research Summary

**Project:** harness — Ink UI 재작성 milestone
**Domain:** Node + Ink + Zustand + bun + TypeScript 기반 Claude Code 급 터미널 에이전트 UI. 로컬 1 + 외부 원격 2 = 3 사용자 공유 Room. 집 머신 Python WS 서버 (harness_server.py) 유지.
**Researched:** 2026-04-23
**Confidence:** HIGH (Stack · Features · Architecture · Pitfalls 4개 리서치가 Context7/공식 repo/내부 코드 교차검증)

---

## Executive Summary

harness 의 Python prompt_toolkit+Rich REPL 은 Claude Code 급 UX 재현이 구조적으로 불가능하다는 결론(PROJECT.md Evolution) 위에서, 이번 milestone 은 **UI 층을 전면 Ink 로 교체**한다. 4개 리서치가 교차 확인한 단일 결론은 "스켈레톤(`ui-ink/`, commit `5d275e3`)이 방향은 맞지만 **ink@5 / react@18 / zustand@4 버전 전부 구세대** + **WS 프로토콜 네이밍이 서버와 전부 어긋나서 현재 스켈레톤은 아무것도 동작하지 않는다**" 는 것이다. Ink 7 / React 19.2 / Zustand 5 로 올리고, `on_token`/`on_tool` 허구의 이벤트 이름을 실제 서버가 쏘는 `token`/`tool_start`/`tool_end` 로 교정하는 두 작업이 물리적 전제조건이다.

추천 접근은 **세로 절단(vertical slice) Phase 구조** — 각 phase 끝에 end-to-end 동작하는 상태를 유지하며, "인프라 먼저 전부 만들고 마지막에 연결" 패턴을 금지한다. 기술적 핵심 결정 3 가지는 (1) 완결 메시지 = `<Static>` / 스트리밍 중 = 일반 트리 분리로 Ink 의 full-tree redraw 특성을 우회, (2) WS 레이어를 React 밖 순수 TS 모듈로 격리하고 `useStore.getState()` 만 호출하는 discriminated union 디스패처 패턴, (3) 멀티라인 입력 · bracketed paste · IME 를 `ink-text-input` 이 아닌 **자체 `<MultilineInput>`** 으로 구현(2026 년 현재 프로덕션급 멀티라인 Ink 입력 패키지가 npm 에 부재).

주요 리스크는 세 축 — (a) Ink 생태계 고유 함정 (alternate screen · raw mode · resize · Static 오용) 이 Python REPL 에서 겪던 동형 버그를 그대로 재생산 가능, (b) WS 재연결 · 상태 복구가 3인 동시 reconnect thundering · 재연결 구간 이벤트 유실을 유발해 서버 프로토콜 확장이 필수(monotonic event id + `resume_from` + room ring buffer), (c) 사용자 3인 전원이 기존 Python REPL 기대치에 적응되어 있어 `Ctrl+R` history search / `/save` 포맷 / macOS IME 동작 등의 미시 UX 괴리가 신뢰 손실로 직결. 이 리스크들은 **Phase 1 하드닝(lint 가드·TTY 가드·프로토콜 정합성 복구) 과 milestone 최종 단계에서 legacy 삭제 전 외부 2인 beta 검증** 두 지점에 집중적으로 대응한다.

---

## Key Findings

### Recommended Stack

ui-ink 스켈레톤은 방향이 맞으나 **모든 core 의존성이 구세대**라 bump 가 Phase 1 의 물리적 전제. Ink 생태계에서 공식 wrapper 우선 채택, 없는 기능(멀티라인 입력)만 자체 구현. bun 은 전제(PROJECT.md), Node 22 는 fallback. 상세는 `.planning/research/STACK.md`.

**Core technologies (반드시 pin):**
- **Node.js ≥ 22.0.0 · bun ≥ 1.2.19** — Ink 7 peer, bun 은 사용자 setup 표준.
- **TypeScript ^6.0.3** — React 19 타입 완전 대응, `tsc --noEmit` 만 사용.
- **React ^19.2.5** — Ink 7 peer `>=19.2.0` 강제.
- **Ink ^7.0.1** — `usePaste` · `useWindowSize` 등 TUI 품질 핵심 훅 v7 에서 신설. Ink 5 이하는 이번 milestone 의 멀티라인 · resize 요구 충족 불가.
- **Zustand ^5.0.12** — 단일 스토어 + 5 슬라이스, React 바깥에서 `useStore.getState()` 호출하는 WS 레이어 패턴이 Jotai/Valtio 대비 가장 자연스러움.
- **ws ^8.20.0** — 커스텀 헤더(`x-harness-token`, `x-harness-room`) 네이티브 지원. bun native WebSocket 은 헤더 처리 이슈(bun#5951, #6686) 때문에 회피.

**Supporting (Phase 1 필수):**
- `@inkjs/ui ^2.0.0` (ConfirmInput · StatusMessage · Badge · Spinner · TextInput) — ink@7 peer 실전 검증은 Phase 1 스모크 필수.
- `ink-spinner ^5.0.0` · `ink-select-input ^6.2.0` · `ink-link ^5.0.0`.
- `diff ^9.0.0` (jsdiff) · `cli-highlight ^2.1.11` (Phase 3 · Diff/Syntax).
- `vitest ^4.1.5` + `ink-testing-library ^4.0.0` — bun test 는 snapshot UX 가 덜 성숙.

**Stack 절대 금지:**
- `ink-text-input@6` 유지 (싱글라인 전용, Enter=제출/Shift+Enter=개행 충족 불가) → 자체 `<MultilineInput>`.
- `ink@5` 유지 / `react@18` 유지 / `zustand@4` 유지 — ink@7 설치 거부되거나 usePaste 없어짐.
- `ink-markdown` · `ink-table` · `ink-scrollbar` · `ink-big-text` (전부 2~4년 정체 · ink@7 미검증).
- `diff2html` / `react-diff-view` (DOM 기반, 터미널 부적합).
- `oclif` · `pkg` · `bun build --compile` — 이번 milestone 사용자 규모 3명에 과잉.
- **Alternate screen 관련 모든 escape** (`\x1b[?1049h`, `\x1b[?1000h` 등) — PROJECT.md Constraint.

### Expected Features

FEATURES.md 가 31개 table stakes(TS-*) + 8개 differentiator(D-*) + 14개 anti-feature(AF-*)를 제시. **v1 = TS 전 항목**(하나라도 빠지면 기존 사용자가 "다운그레이드" 로 인식), **v1.1 = D-1,4,5,7,8**, **v1.2+ = D-2,3,6**. 상세는 `.planning/research/FEATURES.md`.

**Must have (table stakes — v1, 총 31개 TS-*):**
- **Input**: 멀티라인(Enter 제출 / Shift+Enter·Ctrl+J 개행) · continuation prefix · 슬래시 popup(필터·arg hint·Tab 보완) · ↑↓ 히스토리 · bracketed paste(Ink 7 `usePaste`) · Tab 자동완성(경로/세션명) · Ctrl+C 턴 취소 · POSIX 편집 단축키(Ctrl+A/E/K/W).
- **Output**: `<Static>` + 라이브 슬롯 분리 스트리밍 · syntax highlight(cli-highlight/Shiki) · unified diff 렌더 · tool 결과 요약 1줄 · spinner · ctx/토큰 meter · 터미널 네이티브 scrollback(alt-screen 금지) · 테마 감지.
- **Confirm**: `confirm_write` 다이얼로그(diff 패널 · y/n/a/s) · `confirm_bash`(위험도 라벨) · 동일 턴 반복 억제(sticky-deny) · 입력 주체만 confirm 가능(BB-2 DQ2-D).
- **Session/Control**: `harness "질문"` one-shot · `--resume <id>` · `--room <name>` · resize 안정(Ink 7 `useWindowSize`) · Ctrl+D 종료.
- **Remote Room**: 멤버 presence · 입력 주체 시각화(`[alice is typing]`) · busy/queued · join 시 state_snapshot 재현 · 연결 상태/자동 재연결 · 로컬-원격 동등성(테스트 보증).
- **Status Bar**: `path · model · mode · turn · ctx% · room[members]` · 좁은 폭 graceful 축약.

**Should have (v1.1 — 같은 milestone 여유분):**
- **D-1 공유 관전 모드** — 관전자는 에이전트 스트리밍 라이브 시청. TS-O1 + broadcast 조합물이라 거의 공짜. Cursor/Claude Code 에 없는 본질적 차별점.
- **D-4 메시지 author 표기**(`[alice]` prefix) — 3인 방 로그 해석 필수.
- **D-5 Confirm 관전 뷰**(read-only) — 감사·신뢰 요소.
- **D-7 사용자 색 해시** · **D-8 `--room <name> "질문"` one-shot 방 공유**.

**Defer (v1.2+ 또는 다음 milestone):**
- D-2 `/pass` 명시 핸드오프 — 서버 active_input_from 이관 API 신설 필요.
- D-3 `/nod` · `/stop` · 관전 채팅 — 새 메시지 타입 · UX 라운드 필요.
- D-6 Join 시 최근 활동 하이라이트 — UX 튜닝 후.

**절대 하지 말 것 (Anti-features + Pitfall 위험 패턴 통합):**

이 목록은 FEATURES.md AF-1..14 와 PITFALLS.md 상위 위험 패턴을 단일 리스트로 병합. roadmap 작성 시 phase 검증 체크리스트로 직접 사용.

| # | 금지 | 이유 |
|---|------|------|
| 1 | Alternate screen / 풀스크린 TUI (`\x1b[?1049h`) | AF-1 + Pitfall 1 — scrollback 상실, Cmd+C 복사 불가, PROJECT.md Constraint |
| 2 | 마우스 트래킹(`\x1b[?1000h` 계열) | AF-2 — 터미널 기본 텍스트 선택 파손, tmux scrollback 붕괴 (claude-code #38810) |
| 3 | 로컬 전용 기능 분기 | AF-4 — PROJECT.md Core Value "로컬·원격 동일" 직접 위배 |
| 4 | Electron / 웹뷰 / GUI 창 | AF-5 |
| 5 | Python UI 병존 (textual · prompt_toolkit Application 잔존) | AF-7 — MEMORY.md 사용자 명시 금지 |
| 6 | 자체 스크롤 뷰포트 (앱 내부 up/down) | AF-9 — 터미널 scrollback 사용 |
| 7 | CRDT 실시간 공동 편집 | AF-10 — 3인 스케일 과잉, turn-taking + `/pass` 로 충분 |
| 8 | 로그인/프로필/아바타 시스템 | AF-11 — 토큰=사용자, 색 해시로 대체 |
| 9 | 서버측 원격 관리 UI (권한 매트릭스 · admin console) | AF-8 — env var `HARNESS_TOKENS` 수준에서 멈춤 |
| 10 | 알림 센터 / 히스토리 검색 UI | AF-12 — 쉘의 `grep`/`less`/`jq` 사용 |
| 11 | LLM 실시간 자동완성 | AF-13 — 관전자에 prediction broadcast 되는 사고 |
| 12 | 테마 에디터 / 플러그인 마켓 | AF-14 — 파일 편집 + `/theme` 로 충분 |
| 13 | `process.stdout.write` / `console.log` 직접 호출 | Pitfall 5 — Ink 이중 렌더 붕괴. ESLint 차단 |
| 14 | `child_process.spawn` 클라이언트 실행 | Pitfall 13 — Ink 화면 박살, bun#27766. 서버만 사용 |
| 15 | `React.FC` children implicit + `<div>` JSX | Pitfall 15 — TS strict + Ink 에 DOM 태그 금지 |
| 16 | 인덱스 key (`messages.map((m, i) => <Box key={i}>)`) | Pitfall 14 — `/undo` 후 메시지 오염 |
| 17 | `ink-text-input` 유지 | Pitfall 7 · Stack — 싱글라인, bracketed paste submit 사고 |
| 18 | spinner/진행 메시지를 `<Static>` 에 push | Pitfall 20 — scrollback 에 spinner 프레임 수백줄 오염 (Python `c45e29f`/`c27111a` 버그 동형) |
| 19 | 전체 store 객체 selector (`const s = useStore()`) | Pitfall 8 — 타이핑마다 리스트 리렌더 |
| 20 | WS handler 에서 React state 직접 참조 | Pitfall 9 — stale closure, room switch 시 엉뚱한 slot 에 append |
| 21 | 바이너리 배포 / 자동 업데이트 / Homebrew | PROJECT.md Out of Scope — 다음 milestone 후보 |
| 22 | 백엔드 언어 교체 (Python → TS) | PROJECT.md Out of Scope — 이번 milestone 은 UI 만 |

### Architecture Approach

ARCHITECTURE.md 가 제시한 단일 권장안은 **Zustand 단일 스토어 + 5 슬라이스(`messages / input / status / room / confirm`)** + **WS 레이어 완전 격리(순수 TS 모듈, discriminated union dispatch)** + **세로 절단 Phase 빌드** 의 세 축. 현 스켈레톤의 본질적 버그 4 건(프로토콜 이름 불일치 `on_token`/`on_tool` vs `token`/`tool_start`/`tool_end` · `error.message` vs `error.text` · 매 토큰 `appendMessage` 누적 · 단일 store 파일)을 Phase 1 에서 먼저 복구하지 않으면 Phase 2+ 는 전부 허공 위 레이어링이 된다. 상세는 `.planning/research/ARCHITECTURE.md`.

**Major components:**

1. **`src/protocol.ts`** — ServerMsg · ClientMsg discriminated union. 실제 `harness_server.py` broadcast 타입 23+종을 전수 매핑. 컴파일 시 exhaustive switch 로 미처리 이벤트 탐지.
2. **`src/ws/` (client.ts · dispatch.ts · parse.ts)** — `HarnessClient` 클래스 (connect · send · reconnect with jitter backoff · heartbeat) + `dispatch(msg, store)` (ServerMsg → store action 매핑).
3. **`src/store/` (messages · input · status · room · confirm · index)** — 5 슬라이스 Zustand. `messages` 는 "in-place 마지막 메시지 업데이트" 패턴 (매 토큰 push 금지). `confirm` 은 WS 인스턴스 주입받아 `resolve(accept)` 에서 응답 전송.
4. **`src/App.tsx` + components/** — `<MessageList>`(완결=`<Static>` / 스트리밍=active slot) · `<Message>` · `<ToolCard>` · `<InputArea>` (`<MultilineInput>` + 조건부 `<SlashPopup>`) · `<StatusBar>` · `<ConfirmDialog>` (모달 아닌 **InputArea 치환 패턴** — Ink 에 z-index 없음).

**구조적 결정 (Phase 1 고정):**
- 모달은 `confirm.mode === 'none' ? <InputArea/> : <ConfirmDialog/>` 조건부 치환. `ink-overlay` 같은 `measureElement` 해킹 회피.
- 메시지 스트리밍 in-place 업데이트: `agentStart` → 빈 assistant 메시지 push + `streaming: true`, `appendToken` → 마지막 메시지 `content +=` (새 배열/객체 참조), `agentEnd` → `streaming: false` + `<Static>` 으로 이동.
- WS 는 `useRef` 또는 module 싱글톤 (현 스켈레톤의 `useState<WebSocket>` 제거 — 전체 App 리렌더 유발).
- Immer middleware 미도입 (TS slice 타입 이슈 zustand#1796, 스트리밍 hot path 오버헤드).

### Critical Pitfalls

PITFALLS.md 가 20 건 식별, Phase-Mapping 표 제공. 아래는 roadmap 구조에 직접 영향을 주는 상위 5 건과 그 Phase 배치.

1. **Alternate screen 오활성 + Raw mode 미복원 + TTY 없는 환경 crash (Pitfall 1·3·19)** — **Phase 1 하드닝 첫 PR**. `index.tsx` 에 TTY 가드 + one-shot 분기, `uncaughtException`/`unhandledRejection`/`SIGHUP` 에서 `stty sane` 등가 cleanup, `render()` 옵션 `patchConsole: false` 고정, `grep '\x1b\[?1049\|?1000' src/` CI 가드, `trap 'stty sane' EXIT` 쉘 안전망.
2. **Ink 재렌더가 매 토큰마다 전체 messages 트리 훑기 + Static 오용 (Pitfall 4·6·20)** — **Phase 2 초기 아키텍처 결정**. 완결 메시지는 `<Static>`, 스트리밍 중 active slot 은 일반 트리. spinner 는 절대 `<Static>` 에 넣지 않음. store 에 `activeTokens` / `activeMessage` 분리, 히스토리 컴포넌트는 별도 selector 로 구독해 타이핑·토큰 중 재렌더 제외. Python `Rich.Live` + `_Spinner` 동형 버그 재현 방지.
3. **Terminal resize 시 stale line 잔존 (Pitfall 2)** — **Phase 2 렌더 구간**. `useStdout().stdout.on('resize', ...)` 에서 `\x1b[2J\x1b[3J\x1b[H` 강제 clear (Python `5ba9e6f` commit 의 ED3 경험 계승). 한국어/emoji 폭 경계 케이스 vitest 스냅샷 회귀.
4. **WS 재연결 thundering herd + 재연결 구간 메시지 유실 (Pitfall 10·11)** — **Phase 3 서버 프로토콜 확장**. 3 클라(로컬+원격 2)가 동시 reconnect → jitter backoff(`delay = base * 2^n * (0.5 + Math.random()*0.5)`). 서버에 monotonic `event_id` + room 당 60초 ring buffer + 클라 `resume_from: <id>` 헤더. snapshot 만으로는 spinner 영원히 회전 / 답변 잘림 발생.
5. **Bracketed paste 미처리로 붙여넣기마다 submit (Pitfall 7)** — **Phase 2 입력 구간**. Ink 7 `usePaste` + 자체 `<MultilineInput>`. `\x1b[?2004h` 활성화 / exit 시 `\x1b[?2004l` 복원. 500줄 paste 수동 테스트 필수.

추가 주의(Phase 매핑 테이블 PITFALLS §마지막 섹션 참조):
- **Pitfall 16 Python 유저 기대 괴리** — macOS IME 한국어 조합 완성 시점, `Ctrl+R` history search, `/save` 포맷, `~/.harness/history.txt` persist. 릴리스 노트 "이전과 달라진 점" 섹션 필수. **Phase 5 외부 2인 beta 에서 검증.**
- **Pitfall 18 외부 사용자 `bun install` 실패** — `ws` 의 `bufferutil`/`utf-8-validate` 네이티브 빌드 이슈, `bun install --frozen-lockfile` 표준화, `engines.bun` pin. Phase 5 fresh VM clean install.

---

## Implications for Roadmap

### Phase 제안 통합 (Coarse Granularity — 3~5 Phase)

4 리서처의 Phase 제안이 입도가 달랐다:

- **STACK** : "Phase 1 초반 smoke 로 `@inkjs/ui`/`ink-select-input` 의 ink@7 peer 실전 검증, 의존성 전체 bump" (1 단계)
- **FEATURES**: A(Input) → B(Output) → C(Confirm) → D(Remote) → E(Session/One-shot) 5 단계
- **ARCHITECTURE**: P1(Smoke) → P2(Tool/StatusBar) → P3(Confirm) → P4(Input/Slash) → P5(Diff/Syntax) → P6(Scroll) → P7(Room) → P8(OneShot) → P9(Legacy 삭제) 9 단계
- **PITFALLS**: Phase 1(스켈레톤 하드닝) → 2(렌더) → 3(입력) → 4(WS) → 5(Tool) → 6(One-shot) → 7(배포/beta) 7 단계

세 리서처가 모두 Phase 1 에 몰아넣은 세 종류의 작업 — **STACK 의 "의존성 upgrade + smoke"** · **ARCHITECTURE 의 "프로토콜 정합성 복구(on_token→token)"** · **PITFALLS 의 "스켈레톤 하드닝(alt-screen 금지·TTY 가드·raw mode 복원·lint)"** — 은 **전부 동일한 Phase 1 에 결합된다**. 세 작업 모두 "다른 모든 것의 전제" 이며 서로 독립적으로 진행 가능하나 Phase 2 시작 전에 완결되어야 하고, 분리하면 "업그레이드했더니 프로토콜 때문에 아무것도 안 움직임" / "프로토콜 고쳤더니 구버전 Ink 에서 API 없음" / "둘 다 됐는데 crash 시 터미널 망가짐" 같은 dead end 가 난다.

PROJECT.md Constraint 가 granularity=coarse(3~5 phase) 를 요구하므로, 아래 **5 phase 통합안** 을 roadmap 초안으로 권장:

---

### Phase 1: Foundation — Upgrade · Protocol Fix · Hardening · Smoke

**Rationale:** 세 리서처가 모두 이 단계로 몰아넣은 3 종 작업을 단일 phase 로 묶는다. 독립적으로 처리해도 Phase 2 시작 전 완결이 물리적 전제이므로 쪼갤 이유가 없다. 끝에는 "`bun start` → 연결 → 입력 → 토큰 스트림 → `agent_end`" end-to-end 스모크가 통과한다. vertical slice 원칙.

**Delivers:**
- 의존성 bump: `ink@5→7 / react@18→19.2 / zustand@4→5 / @types/react@18→19.2`, `ink-text-input` 제거, `@inkjs/ui`·`ink-spinner`·`ink-select-input`·`ink-link`·`diff`·`cli-highlight` 추가, `vitest`+`ink-testing-library` dev 추가.
- tsconfig 신규 (`"jsx": "react-jsx"` · `"moduleResolution": "bundler"` · strict · `lib: ["ES2022"]` DOM 제외) + ESLint 가드(`process.stdout.write`/`console.log`/`<div>`/`spawn` 금지).
- **프로토콜 정합성 복구** — `src/protocol.ts` 신규 (23+ ServerMsg discriminated union), `src/ws/` 재구조화 (client · dispatch · parse 분리, `HarnessClient` 클래스), `on_token`→`token` / `on_tool`→`tool_start`+`tool_end` / `error.message`→`error.text` 전수 교정.
- **스토어 분할** — `src/store/` 5 슬라이스(`messages`/`input`/`status`/`room`/`confirm`). `appendToken` in-place 패턴으로 "매 토큰 push" 버그 제거. 각 메시지에 `crypto.randomUUID()` id 부여(Pitfall 14 방지).
- **하드닝 첫 PR** — `index.tsx` TTY 가드 + one-shot 분기, `uncaughtException`/`unhandledRejection`/`SIGHUP` cleanup (`setRawMode(false)` + 커서 복원 + `stdin.pause()`), `render(<App/>, {patchConsole: false})` 옵션 고정, `<ErrorBoundary>` 루트, `trap 'stty sane' EXIT` 쉘 진입 스크립트.
- **`@inkjs/ui`·`ink-select-input` 의 ink@7 실전 호환 스모크** — peer 는 `>=5` 선언뿐이라 Phase 1 초반에 확인, 깨지면 개별 대체(자체 ConfirmInput).
- Phase 1 단위 테스트: `parseServerMsg` / store reducers / `dispatch` exhaustive switch / TTY 가드.

**Addresses:** TS-S1(one-shot 기본 경로는 여기서 분기만 생성) · 프로토콜 명세 문서화 기반
**Avoids:** Pitfall 1(alt-screen) · 3(raw mode) · 5(stdout direct) · 14(index key) · 15(TS strict+JSX) · 19(non-TTY crash)
**Stack 결정 확정:** Ink 7 · React 19.2 · Zustand 5 · ws 8 · TypeScript 6 · vitest 4

**Exit criteria:**
- `"hello"` → assistant 토큰 렌더 완료, 기존 `ui/index.js` 와 동등 smoke.
- `tsc --noEmit` green · ESLint green · vitest 단위 테스트 green.
- `echo 'x' | harness` → crash 아닌 one-shot 경로로 빠짐.
- `kill -9 <pid>` 후 터미널 에코/라인편집 정상.
- `grep '\x1b\[?1049' src/` 빈 결과.

### Phase 2: Rendering + Tools + Status + Confirm + Input (Core UX)

**Rationale:** FEATURES 의 TS-I* + TS-O* + TS-C* + TS-B* 를 단일 phase 로 묶는다. ARCHITECTURE 의 P2/P3/P4/P5/P6 을 통합. 이 기능들은 모두 "Phase 1 스모크 + <Static>/active slot 아키텍처 결정 + 입력 주체 컨셉" 의 같은 아키텍처 기반을 공유하며, 기능 간 의존성이 tight 해서 쪼개면 반쪽 UX 로 끝나는 phase 가 생긴다 (예: tool 결과는 있는데 diff 는 없고 confirm 도 없는 상태).

**Delivers:**
- **스트리밍 렌더**: `<Static>` + active slot 분리, `useShallow` selector, 타이핑 중 리스트 리렌더 0회. Yoga full-redraw 우회.
- **`<MultilineInput>` 자체 구현**: Enter 제출 / Shift+Enter · Ctrl+J 개행 / ↑↓ 히스토리 / `~/.harness/history.txt` persist(Python 포맷 유지, Pitfall 16 마이그레이션) / POSIX 편집 단축키(Ctrl+A/E/K/W/U).
- **Ink 7 `usePaste` 적용** + `\x1b[?2004h`/`\x1b[?2004l` bracketed paste 마커 관리, 500줄 paste 검증.
- **`<SlashPopup>`**: `ink-select-input` 기반, 슬래시 카탈로그 `src/slash-catalog.ts` (`harness_core` 의 13개 명령 메타 재사용), `slash_result` 이벤트 cmd 별 렌더(files tree · sessions 목록 · who).
- **`<ToolCard>` + TOOL_META**: `tool_start` pending → `tool_end` 요약 1줄(`read 120 lines (of 340)` · `+42 −5, 3.1 KB` · `exit 0, 1.2s`).
- **`<StatusBar>`**: 세그먼트 `path · model · mode · turn · ctx% · room[members]` + 좁은 폭 우선순위 기반 drop.
- **Syntax highlight + Diff 렌더**: `cli-highlight` 로 코드 펜스, `diff@9 structuredPatch` 로 unified diff hunks + ± 색 + 라인 번호.
- **Confirm 다이얼로그**: `confirm_write`(경로 + DiffPreview + y/n/d 키) · `confirm_bash`(커맨드 + 위험도 라벨 + y/n) · `cplan_confirm`. InputArea 치환 패턴. 동일 턴 반복 억제(sticky-deny 서버 로직 재사용). 로컬 60초 타임아웃(UX 용, 서버 timeout 과 독립).
- **resize 안정**: `useStdout().stdout.on('resize')` + `\x1b[2J\x1b[3J\x1b[H` (Python ED3 경험), wide char/emoji 스냅샷 회귀.
- **Ctrl+C 2단계**: 첫 번째 = turn abort (`ws.close` 아닌 `cancel` 메시지 — **서버 프로토콜 확장 필요**), 두 번째(2초 내) = exit.
- **테마 기본**: `COLORFGBG`/`TERM_PROGRAM` 감지 + `/theme` 수동.

**Addresses:** TS-I1..I8 · TS-O1..O8 · TS-C1..C4 · TS-B1..B2 · TS-S4(resize)
**Avoids:** Pitfall 2(resize) · 4(full-tree redraw) · 6(Static 오용) · 7(bracketed paste) · 8(selector) · 20(scrollback spinner)
**Architecture 결정 구체화:** `<Static>` 계약 문서화, 모달=조건부 치환, WS ref 전환(useState 제거)

**Exit criteria:**
- 500 토큰 연속 스트리밍 시 CPU 50% 미만 · flicker 0 · scrollback 에 spinner 잔재 0.
- 터미널 폭 200↔40 반복 resize 시 stale line 0 (한국어·emoji 포함).
- `/undo` · `/clear` 후 화면/데이터 일치.
- write_file 요청 → diff 패널 → y 수락 → 서버 진행 → tool 완료 렌더.
- 500줄 paste → 중간 submit 0회, 전체 보존.

### Phase 3: Remote Room + Session Control (Multi-user + Reconnect)

**Rationale:** FEATURES 의 TS-R*/TS-S* + ARCHITECTURE 의 P7/P8 을 묶는다. Phase 2 의 메시지 렌더 · confirm 격리 · InputArea 위에 "공유 + 재연결 + 세션 진입 모드" 를 얹는 단계. 여기서 **서버 WS 프로토콜 확장이 집중적으로 발생** — 이 phase 가 끝나면 프로토콜이 stable.

**Delivers:**
- **Room 슬라이스 완성**: `room_joined` / `room_member_joined` / `room_member_left` / `room_busy` / `state_snapshot` 처리, `room.activeIsSelf` 플래그 도입, 관전자 시 `<InputArea>` disabled + "A 가 입력 중" 표시.
- **Presence 렌더**: StatusBar 의 `🟢 2명 [alice·me]` 세그먼트, join/leave 시 system 메시지 1줄.
- **state_snapshot 히스토리 일괄 로드**: `<Static>` remount 패턴, 새 join 시 과거 turn 복원.
- **WS 재연결** (jitter exponential backoff · max 10회 · 30초 cap · 연결 안정 30초 후 attempts 리셋), 재연결 중 `disconnected — reconnecting...` + 입력 비활성화 + 로컬 입력 버퍼링.
- **One-shot** (`harness "질문"`): Phase 1 분기 위에 실제 구현. argv 프롬프트 → WS `input` → token stdout → `agent_end` 시 `useApp().exit()`. TTY 아닐 때 ANSI off.
- **Resume** (`harness --resume <id>`): `input: '/resume <id>'` 송신 후 REPL 전환.
- **`--room <name>`**: `x-harness-room` 헤더, D-8 `--room "질문"` 원격 one-shot.
- **D-1 공유 관전 · D-4 author 표기 · D-5 Confirm 관전 뷰 · D-7 사용자 색 해시**: Phase 2 조합물이므로 같이 완성.

**서버 WS 프로토콜 확장 (이 phase 에서 전부 처리 — 아래 "서버 확장 요구 단일 리스트" 참조):**
1. `agent_start` 에 `from_self: bool` 필드 (ARCHITECTURE §4.2)
2. `confirm_write` 에 `old_content` 필드 (ARCHITECTURE §Phase 5 — Phase 2 에서 처리될 수도 있으나 Phase 3 에 집결 가능)
3. 클라이언트 → 서버 `resume_from: <event_id>` 헤더 (PITFALLS §11)
4. 서버에 monotonic `event_id` + room 당 60초 이벤트 ring buffer (PITFALLS §11)
5. 클라 → 서버 `cancel` 메시지 (Phase 2 Ctrl+C 턴 취소용 — 물리적으로 여기 몰릴 수 있음)

**Addresses:** TS-R1..R6 · TS-S1..S5 · D-1, D-4, D-5, D-7, D-8
**Avoids:** Pitfall 9(stale closure) · 10(thundering herd) · 11(재연결 유실) · 17(slow 네트워크)
**Stack:** `ws@8` 커스텀 헤더 · Ink `useApp().exit()`
**Architecture:** `HarnessClient` 클래스 완성(reconnect + heartbeat + backpressure 측정점)

**Exit criteria:**
- 로컬 + 원격 2 = 3 클라가 같은 room 에 접속 → 한쪽 입력 시 다른 둘이 관전 렌더.
- 서버 kill → restart 시 3 클라 전원 자연 재연결 + `resume_from` delta 수신으로 중간 이벤트 0 유실.
- `bun start "What is 2+2?"` → 답만 출력 후 exit.
- `harness --resume <id>` 로 저장 세션 로드 후 REPL.
- 관전자 시 input box disabled + "A is typing" 오버레이.

### Phase 4: Testing · Docs · CLIENT_SETUP Hardening · External Beta

**Rationale:** Phase 1~3 에서 기능은 전부 완결. 이 phase 는 **"legacy 삭제 전에 반드시 통과해야 할 품질 게이트"** — 바로 삭제로 가지 않는다. 외부 2인 beta 가 여기 들어간다. PITFALLS.md 의 "Looks Done But Isn't" 체크리스트 17 항목이 이 phase 의 verification.

**Delivers:**
- **통합 테스트 수립**: Fake Harness WS 서버 + `HarnessClient` + store + `ink-testing-library`. 시나리오 — agent 턴 1개 · confirm_write accept · room busy · reconnect delta · one-shot · 3인 동시 재접속 시뮬.
- **회귀 스냅샷**: 500 토큰 스트리밍 · 한국어/emoji wrap · resize 200↔40 · `/undo`+새 메시지 · Static 오염.
- **CI matrix**: bun + Node 22 양쪽 green. `tsc --noEmit` + ESLint 가드 + Python pytest 199건.
- **Looks-Done-But-Isn't 체크리스트 17건 수동 검증** (PITFALLS.md 마지막 체크리스트 그대로 복제).
- **CLIENT_SETUP.md 재작성**: `git clone + bun install --frozen-lockfile + bun start` 표준화, `HARNESS_URL` / `HARNESS_TOKEN` / `HARNESS_ROOM` env var 문서, troubleshooting(native dep · bun 버전 mismatch · macOS IME).
- **WS 프로토콜 명세 (PROTOCOL.md)**: Phase 1~3 의 23+ 이벤트 + 확장 5건을 공식 문서화. PROJECT.md Constraint "기존 이벤트 의미 변경 금지, 확장 OK" 기준.
- **외부 2인 beta 라운드**: fresh VM `git clone → bun install → bun start` 10분 이내, Pitfall 16 마이그레이션 검증(Ctrl+R 등가 · macOS IME · history persist · `/save` 포맷), 피드백 수집 후 blocker 수정.
- **릴리스 노트 "이전과 달라진 점"** 섹션 작성.

**Addresses:** TS-R6 동등성 보증(테스트로) · Pitfall 16 마이그레이션 · Pitfall 18 배포
**Avoids:** Pitfall 12(bun↔ws 호환) · 16(Python 유저 괴리) · 17(slow 네트워크) · 18(bun install 실패)

**Exit criteria:**
- vitest + ink-testing-library 통합 테스트 green (목표 커버리지 hot path 80%+).
- 외부 2인 beta 에서 blocker 0. "다운그레이드" 피드백 0.
- PROTOCOL.md · CLIENT_SETUP.md merged.
- 3 클라 동시 재접속 수동 테스트 통과.
- Looks-Done-But-Isn't 체크리스트 17건 전원 ✓.

### Phase 5: Legacy Deletion + Milestone Closure

**Rationale:** Phase 4 beta 에서 greenlight 받은 후에만 진입. 사용자 명시 요청("기존 코드 유지해보니까 gsd나 다른 에이전트들이 헷깔리는 경우가 상당히 많음") 이행 + PROJECT.md Key Decision "Legacy Python UI 전부 삭제" 실행. 이 phase 를 Phase 4 앞으로 당기면 "beta 에서 regression 발견 → legacy 롤백 불가" 의 돌이킬 수 없는 상태가 된다.

**Delivers:**
- `ui/index.js` 삭제
- `main.py` REPL 경로 + `cli/` 모듈(intent/render/claude/setup/callbacks/slash 전부) 삭제. 단 `session/` · `evolution/` · `tools/` · `harness_core/` · `harness_server.py` 는 유지 (PROJECT.md Validated).
- `cli/tui.py` · `cli/app.py` 잔재 확인 후 제거.
- `main.py` 가 남아야 한다면 `harness_server.py` 서버 엔트리만 래핑하는 thin shim 으로.
- `.planning/codebase/CONCERNS.md` §1.12 (spinner vs Live) · §3 Architecture 잔여 중 Python REPL 관련 항목 close 처리.
- PROJECT.md Evolution 섹션 업데이트 (Active → Validated 이동, Key Decisions Outcome 확정).
- 최종 회귀 라운드 + Python pytest 199 + ui-ink vitest green 최종 확인.

**Addresses:** PROJECT.md Active 의 "Legacy UI 삭제" 전 항목 완결
**Avoids:** AF-7(Python UI 병존 재발) — 사용자 명시 금지

**Exit criteria:**
- `grep -rn "prompt_toolkit" .` 빈 결과.
- `python -c "import cli"` 실패(의도적).
- `harness_server.py` + `ui-ink` 가 유일 실행 경로.
- pytest 199 + vitest 전 테스트 green.
- PROJECT.md milestone closure 섹션 작성.

---

### Phase Ordering Rationale

- **Phase 1 ≺ Phase 2~3 (물리적 전제)** — 의존성 bump 없이 Phase 2 의 `usePaste`/`useWindowSize` 불가, 프로토콜 정합성 없이 어떤 렌더도 동작 안 함, 하드닝 없이 crash 시 터미널 망가져 beta 불가. 세 리서처가 이 phase 에 각자 다른 이유로 몰아넣은 이유.
- **Phase 2 ≺ Phase 3 (레이어링)** — Remote/Room/Session 은 Phase 2 의 `<Static>`+active slot + `<InputArea>`/`<ConfirmDialog>` + 메시지 id 위에 조건 분기로 얹는 구조. 반대로 Phase 2 의 Confirm 이 입력 주체 격리(TS-C4) 를 의식해 설계되지만, 실제 room 구현은 Phase 3 에서 완결. 이 분리는 아키텍처적으로 자연스러움.
- **Phase 3 에 서버 프로토콜 확장 집결 (재연결 delta · from_self · old_content · cancel · event_id)** — Phase 2 에서도 old_content 가 필요할 수 있으나, "한번에 프로토콜 확장 라운드" 를 가져 서버 drift 를 최소화. PROJECT.md Constraint 가 요구.
- **Phase 4 (testing+beta) ≺ Phase 5 (legacy 삭제) 절대 순서** — PITFALLS §16 사용자 괴리 + §18 bun install 은 fresh VM beta 에서만 확인 가능. beta 에서 blocker 발견 시 legacy 가 있어야 롤백 경로가 남음. 이 순서를 뒤집으면 돌이킬 수 없다.
- **단일 phase 당 complexity** — 5 phase 로 묶어도 Phase 2 가 가장 무거움(31 TS 중 ~20건). 필요 시 roadmapper 가 Phase 2 를 A(Render+Input) / B(Confirm+Tools+Status) 로 쪼개는 옵션이 있으나, coarse 원칙 + vertical slice 원칙에서 현재 5 phase 가 타협점.

### Research Flags

**Phases needing deeper research during planning (/gsd-research-phase 필요):**

- **Phase 2** — Ink 7 의 `usePaste` 가 bun 런타임에서 bracketed paste 를 정확히 전달하는지 공식 호환 매트릭스 부재(STACK LOW confidence). `@inkjs/ui@2.0.0` 과 `ink-select-input@6.2` 의 ink@7 peer 실전 호환이 Phase 1 초반 스모크에서 검증되더라도, Phase 2 의 `<SlashPopup>`(select) + `<ConfirmDialog>`(@inkjs/ui) 가 실전 트래픽에서 깨지는 케이스 점검 필요. 한국어 IME 의 Ink 동작(prompt_toolkit 처럼 composition 완료까지 submit 지연되는가) 도 실증 연구 필요.
- **Phase 3** — WS 프로토콜 확장 5건(`from_self` · `old_content` · `resume_from` · `event_id` · `cancel`) 을 Python `harness_server.py` 측에 구현할 때 Room/turn-taking/active_input_from 기존 로직과 충돌 지점 조사. 특히 `cancel` 메시지가 agent thread 의 asyncio.Event 체인을 안전하게 끊는 방법. PITFALLS §11 의 ring buffer 를 `session/` 레이어에 넣을지 `harness_server.py` 에 얹을지 위치 결정.
- **Phase 4** — 3 클라 동시 재접속 · RTT 200ms 시뮬 · fresh VM `bun install --frozen-lockfile` 을 CI 에서 어떻게 자동화할지. 특히 macOS/Linux arm64/x64 matrix.

**Phases with standard patterns (research-phase 스킵 가능):**

- **Phase 1** — 의존성 bump · tsconfig · ESLint · TTY 가드는 공식 가이드/관행에 확실. STACK.md + PITFALLS §1,3,5,15,19 가 이미 구체적 처방 제공. 추가 연구 없이 실행.
- **Phase 5** — 파일 삭제와 문서 업데이트. 리스크는 Phase 4 에서 소진.

### 서버 WS 프로토콜 확장 요구 (Single List — Requirements 단계에서 누락 금지)

이 항목은 네 리서치가 각자 별도로 제안한 서버측 변경을 단일 리스트로 합친 것. Requirements 정의 시 **전부 요구사항으로 승격** 되어야 하며, roadmap 상으로는 Phase 3 에 집결(단 일부는 Phase 2 에서 필요 시 앞당김 가능).

| # | 확장 | 출처 | 용도 | Phase |
|---|------|------|------|-------|
| 1 | `agent_start` 에 `from_self: bool` 필드 | ARCHITECTURE §4.2 | 관전자/입력자 구분, `<InputArea>` disable 판정 | Phase 3 |
| 2 | `confirm_write` 에 `old_content?: string` 필드(optional) | ARCHITECTURE §Phase 5 | DiffPreview 를 위해 서버가 기존 파일 내용 제공 (없으면 클라가 fs 접근 불가) | Phase 2 or 3 |
| 3 | 클라→서버 `resume_from: <event_id>` 헤더 | PITFALLS §11 | 재연결 시 마지막 수신 event 기준 delta 요청 | Phase 3 |
| 4 | 서버 monotonic `event_id` + room 당 60초 이벤트 ring buffer | PITFALLS §11 | delta 제공의 실제 저장소 | Phase 3 |
| 5 | 클라→서버 `cancel` 메시지 | 통합(Phase 2 Ctrl+C) | 현재 agent turn 취소 (프로세스 종료 아님) | Phase 3 (또는 Phase 2 내 서버 변경 합쳐서) |

주의: PROJECT.md Constraint "기존 이벤트 **의미 변경 금지**, 필드 추가 OK" 를 모두 준수. 위 5건 전부 추가 또는 신규 메시지이며 기존 broadcast 변경 없음.

### Config 제약과 granularity 결정

PROJECT.md 가 roadmap granularity=coarse(3~5 phase) 를 요구. 리서처들의 7~9 phase 제안을 위 5 phase 로 묶었다. 더 줄이려면 Phase 4 를 Phase 5 앞에 암묵적으로 붙여 4 phase 화 가능하나, **외부 2인 beta 와 legacy 삭제는 별도 phase transition 으로 분리하는 것이 사용자 신뢰와 롤백 경로 측면에서 중요** — 5 phase 가 coarse 내 최적.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | npm registry 직접 조회(2026-04-23 시점) + Ink 공식 릴리스 노트 + 로컬 환경(`bun@1.2.19`, `node@22.21.1`) 검증. `@inkjs/ui@2.0.0` 의 ink@7 실전 호환만 MEDIUM — Phase 1 초반 스모크 필수. |
| Features | HIGH | Claude Code 2026-04 공식 가이드 + Ink 7 릴리스 노트 + 기존 REPL `ui/index.js` 관찰 + BB-2 내부 설계 문서 교차. D-1 공유 관전이 "TS 조합물이라 거의 공짜" 라는 주장만 MEDIUM(Phase 3 실증). |
| Architecture | HIGH | `harness_server.py` 실제 코드 프로토콜 전수 매핑 + Zustand/Ink 공식 문서 + 기존 `ui/index.js` 참조 구현 + `.planning/BB-2-DESIGN.md` 내부 설계 크로스체크. |
| Pitfalls | HIGH | Ink GitHub Issue #907, #166, #378, #359, #153 + Claude Code #38810, #47773, #50012, #5925 등 + bun #4529, #9368, #27766 + Python REPL 동형 버그 커밋 이력(`c45e29f`, `c27111a`, `5ba9e6f`) 교차. bun 세부 signal 동작만 MEDIUM. |

**Overall confidence:** HIGH

### Gaps to Address

- **Ink 7 IME 한국어 조합 동작** — prompt_toolkit 은 composition 완료까지 submit 지연시켰음. Ink 7 `useInput` 이 macOS IME dead key/조합 중 Enter 를 어떻게 전달하는지 실증 데이터 부재. **Phase 2 구현과 동시에 검증**, 깨지면 `<MultilineInput>` 에 composition guard 추가.
- **`@inkjs/ui` · `ink-select-input` 의 ink@7 실전 호환** — peer 선언 `>=5` 만. STACK.md 가 Phase 1 초반 스모크 task 지정. 깨지면 자체 ConfirmInput/Select 로 개별 대체.
- **bun signal 처리와 Ink cleanup 상호작용** — `SIGHUP`/`SIGINT` 에서 Ink unmount 가 Node 와 동일하게 돌지 PITFALLS.md MEDIUM confidence. Phase 1 하드닝에서 `bun run` + `trap 'stty sane' EXIT` 이중 안전망으로 실증 후 판단.
- **WS 프로토콜 확장 5건의 Python 구현 난이도** — Room 기존 로직과 충돌 없이 event ring buffer/resume_from/cancel 을 얹는 구체적 지점이 아직 탐색 안 됨. Phase 3 시작 전 /gsd-research-phase 권장.
- **Ink `<Static>` 과 `/undo`/`/clear` 의 상호작용** — 히스토리 수정 시 `<Static>` 을 전체 리렌더로 key remount 후 복귀하는 패턴이 실전에서 안정한지 PITFALLS §6 MEDIUM. Phase 2 초기 스냅샷 테스트에서 검증.
- **3 클라 동시 재접속 thundering herd 시뮬 환경** — Phase 4 에서 자동화할 방법 미확정 (FakeHarnessServer 쪽에 지연 주입 필요).

---

## Sources

### Primary (HIGH confidence)

- Ink GitHub — vadimdemedes/ink (v7.0.1 릴리스 노트, `usePaste`/`useWindowSize`, `<Static>`)
- Ink GitHub Issues #907 (resize), #166 (raw mode), #378 (subprocess), #359 (long view flicker), #153 (resize events)
- Claude Code Issues #38810, #42670, #47773, #50012, #13183, #5925, #35734, #11898, #404, #1072
- bun-sh/bun Issues #4529, #5951, #6686, #9368, #27766
- npm registry CLI 조회 (2026-04-23) — ink@7.0.1, react@19.2.5, zustand@5.0.12, ws@8.20.0, @inkjs/ui@2.0.0, ink-select-input@6.2.0, ink-spinner@5.0.0, diff@9.0.0, cli-highlight@2.1.11, vitest@4.1.5, ink-testing-library@4.0.0
- Zustand 공식 문서 (pmndrs/zustand) + Selectors & Re-rendering + Issue #1796, #2491
- Claude Code Interactive Mode 가이드 2026 · Statusline 공식 문서 · Cheat Sheet 2026
- Shiki `codeToANSI` + `transformerNotationDiff`
- `cli-highlight` (felixfbecker) · `diff@9` (jsdiff)
- WebSocket Reconnection w/ Exponential Backoff · State Sync Recovery · Jitter Backoff 가이드
- Bun WebSocket docs · 공식 single-file executable 문서
- Ink 3 release notes (Static · throttling)

### Secondary (MEDIUM confidence)

- DeepWiki sst/opencode TUI prompt component — 멀티라인 입력 레퍼런스
- heise — "Ink 7.0 fundamentally revises input handling"
- Claude Code Internals Part 11: Terminal UI (Medium, Kotrotsos)
- Interactive REPL & TUI (lttcnly/claude-code via DeepWiki)
- React Ink Component Architecture (instructkr/claude-code)
- test-ink-flickering INK-ANALYSIS.md
- Qwen Code Ink flicker issue
- Reactive UI with Ink and Yoga — Agentic Systems
- wemux — multi-user tmux (presence/mirror 관행)

### Tertiary (LOW confidence — needs validation)

- Claude Code 스택 유출 분석 (다수 미러 repo) — Ink + Bun + TS + Commander 교차 검증, 법적/정식 근거 아님
- bun signal 처리의 Ink cleanup 호환성 (공식 호환 매트릭스 부재)
- `@inkjs/ui@2.0.0`/`ink-select-input@6.2` 의 ink@7 peer 실전 호환 (peer 는 `>=5` 만 선언 — Phase 1 초반 스모크 필요)

### Internal cross-references

- `/Users/johyeonchang/harness/.planning/PROJECT.md` — milestone 정의 · Constraints · Key Decisions · Out of Scope
- `/Users/johyeonchang/harness/.planning/BB-2-DESIGN.md` — 공유 룸 · turn-taking · confirm 격리 설계
- `/Users/johyeonchang/harness/.planning/codebase/CONCERNS.md` · `ENHANCEMENTS.md` — Python 측 버그 이력(§1.12 spinner vs Live, §3 Architecture 잔여, §E-2.2 busy/queue, §E-3.1 Tab)
- `/Users/johyeonchang/harness/harness_server.py` — WS 프로토콜 ground truth (23+ ServerMsg)
- `/Users/johyeonchang/harness/ui/index.js` — 기존 Node 클라이언트, 참조 구현
- `/Users/johyeonchang/harness/ui-ink/src/{App,store,ws,index}.tsx` — 현 스켈레톤 (commit `5d275e3`)
- 커밋 이력: `5ba9e6f` (ED3 resize), `c45e29f` (transient=True Live), `c27111a` (_Spinner 비활성), `43a4d43` (Rich.Live 재작성), `5d275e3` (ui-ink 스켈레톤)
- 개별 리서치 문서: `.planning/research/STACK.md` · `FEATURES.md` · `ARCHITECTURE.md` · `PITFALLS.md`

---
*Research completed: 2026-04-23*
*Ready for roadmap: yes (coarse granularity, 5 phase 통합안 제시)*
