# harness — ui-ink milestone Requirements

**Generated:** 2026-04-23
**Source:** `.planning/PROJECT.md` + `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS,SUMMARY}.md`
**Granularity:** coarse (5 phase 예상)

모든 v1 REQ-ID 는 이번 milestone 에 반드시 포함된다. v2 는 같은 milestone 내 여유분. Deferred 는 명시적으로 다음 milestone 후보. Out of Scope 는 이번 milestone 에 절대 들어가지 않는다.

---

## v1 Requirements

### FND — Foundation (Phase 1 전제. 모두 coarse 필수)

- [x] **FND-01**: ui-ink 의 의존성을 `ink@7 / react@19.2 / zustand@5 / @types/react@19.2 / ws@8` 으로 bump 하고, `ink-text-input` 은 제거한다
- [x] **FND-02**: `@inkjs/ui@2 · ink-spinner@5 · ink-select-input@6.2 · ink-link@5 · diff@9 · cli-highlight@2 · vitest@4 · ink-testing-library@4` 을 설치 후 Phase 1 초반에 ink@7 peer 호환 스모크로 검증한다
- [x] **FND-03**: 현재 스켈레톤의 잘못된 WS 이벤트 이름(`on_token`, `on_tool`, `error.message`)을 실제 서버 프로토콜(`token`, `tool_start`+`tool_end`, `error.text`)로 전수 교정한다
- [x] **FND-04**: `src/protocol.ts` 를 신설해 `harness_server.py` 가 broadcast 하는 23+ ServerMsg 를 discriminated union 으로 타입화한다 (exhaustive switch 로 컴파일 시 미처리 탐지)
- [x] **FND-05**: `src/ws/{client,dispatch,parse}.ts` 로 WS 레이어를 순수 TS 모듈로 분리한다 (`HarnessClient` 클래스 — connect / send / reconnect / heartbeat)
- [x] **FND-06**: `src/store/{messages,input,status,room,confirm,index}.ts` 로 Zustand 단일 스토어 5 슬라이스 구조로 분할한다
- [x] **FND-07**: 스트리밍 토큰은 "마지막 메시지 content += " in-place 업데이트로 처리 (매 토큰 새 메시지 push 금지)
- [x] **FND-08**: 각 메시지에 `crypto.randomUUID()` id 부여하고 React key 로 사용한다 (index key 금지)
- [x] **FND-09**: tsconfig 를 `"jsx":"react-jsx"` · `"moduleResolution":"bundler"` · strict · `lib:["ES2022"]` (DOM 제외) 로 고정한다
- [x] **FND-10**: ESLint 로 `process.stdout.write` · `console.log` · `<div>/<span>` JSX · `child_process.spawn` 를 금지한다 (CI 실패)
- [x] **FND-11**: `grep '\x1b\[?1049\|?1000' src/` 가 항상 빈 결과여야 한다는 CI 가드를 넣는다 (alternate screen · mouse tracking 금지)
- [x] **FND-12**: 진입점(`index.tsx`)에 TTY 가드 + one-shot 분기(non-TTY 또는 argv 질문 존재 시 one-shot)
- [x] **FND-13**: `uncaughtException` · `unhandledRejection` · `SIGHUP` · `SIGINT` · `SIGTERM` 핸들러에서 `setRawMode(false)` + 커서 복원 + `stdin.pause()` cleanup 을 수행한다
- [x] **FND-14**: `render(<App/>, { patchConsole: false })` 로 Ink 의 console 가로채기를 끈다
- [x] **FND-15**: `trap 'stty sane' EXIT` 을 포함하는 쉘 진입 스크립트를 제공한다
- [x] **FND-16**: Phase 1 exit criteria — `bun start` → 연결 → 토큰 스트리밍 → `agent_end` end-to-end 스모크가 통과해야 한다

### INPT — Input Surface (Phase 2)

- [ ] **INPT-01**: `<MultilineInput>` 을 자체 구현한다 (`ink-text-input` 는 사용하지 않음)
- [ ] **INPT-02**: Enter = 제출, Shift+Enter · Ctrl+J = 개행. 연속 줄은 프롬프트 continuation 표시
- [ ] **INPT-03**: ↑/↓ 로 `~/.harness/history.txt` 기반 히스토리 탐색 (Python REPL 포맷 유지, 마이그레이션 없이 즉시 사용 가능)
- [ ] **INPT-04**: POSIX 편집 단축키 지원 — Ctrl+A (줄 처음) / Ctrl+E (줄 끝) / Ctrl+K (뒤 삭제) / Ctrl+W (단어 삭제) / Ctrl+U (전체 삭제)
- [ ] **INPT-05**: Ink 7 `usePaste` + bracketed paste 마커(`\x1b[?2004h`/`\x1b[?2004l`) 로 붙여넣기마다 submit 되는 사고를 차단한다 (500줄 paste 스모크 통과)
- [ ] **INPT-06**: 슬래시 popup(`<SlashPopup>`) — `ink-select-input` 기반, 실시간 필터, 방향키 네비, Tab/Enter 로 보완, Esc 로 닫기
- [ ] **INPT-07**: 슬래시 카탈로그(`src/slash-catalog.ts`)를 `harness_core` 의 13개 명령 메타에서 그대로 파생한다 (drift 금지)
- [ ] **INPT-08**: Tab 자동완성 — 슬래시 인자(경로, 세션 이름, room 이름 등)
- [ ] **INPT-09**: Ctrl+C 는 현재 턴만 취소하고 프로세스는 유지 (2초 내 Ctrl+C 두번째 입력 시 exit)
- [ ] **INPT-10**: Ctrl+D 로 종료 (단, 입력 버퍼 비어있을 때만)

### RND — Rendering (Phase 2)

- [ ] **RND-01**: 완결 메시지는 `<Static>`, 스트리밍 중 active slot 은 일반 트리 — 이 경계를 컴포넌트 구조로 고정한다
- [ ] **RND-02**: spinner · 진행 메시지를 `<Static>` 에 push 하지 않는다 (Python `c45e29f`/`c27111a` 동형 버그 금지)
- [ ] **RND-03**: Zustand selector 는 단일 값만 구독한다 (`useStore(s => s.messages)` 패턴 금지, `useShallow` 적용)
- [ ] **RND-04**: 터미널 resize 시 `\x1b[2J\x1b[3J\x1b[H` 강제 clear (Python `5ba9e6f` ED3 경험 이식). 한국어/emoji 폭 경계 스냅샷 회귀 테스트
- [ ] **RND-05**: 토큰 스트리밍 시 전체 messages 트리 리렌더 0 회 (500 토큰 연속 스트리밍 CPU 50% 미만)
- [ ] **RND-06**: 코드 펜스 ``` 블록은 `cli-highlight` 로 언어 감지 + syntax highlight
- [ ] **RND-07**: unified diff 는 `diff@9 structuredPatch` 로 hunk 분해 + ± 색 + 라인 번호
- [ ] **RND-08**: tool 결과는 `<ToolCard>` 로 1줄 요약 (예: `read 120 lines (of 340)` · `+42 −5, 3.1 KB` · `exit 0, 1.2s`) + 선택적 상세 펼침
- [ ] **RND-09**: ctx/토큰 meter 를 status bar 가 아닌 별도 경로로 업데이트 (리렌더 스코프 격리)
- [ ] **RND-10**: 테마는 `COLORFGBG` / `TERM_PROGRAM` 자동 감지 + `/theme` 수동 override
- [ ] **RND-11**: alternate screen · mouse tracking 관련 escape 를 절대 출력하지 않는다 (FND-11 의 CI 가드 유효)

### CNF — Confirm Dialogs (Phase 2)

- [ ] **CNF-01**: `confirm_write` 다이얼로그 — 경로 + `<DiffPreview>` + y/n/d(diff 상세) 키. InputArea 를 조건부 치환 (Ink z-index 없음 대응)
- [ ] **CNF-02**: `confirm_bash` 다이얼로그 — 커맨드 프리뷰 + 위험도 라벨(`tools/shell.py` classifier 결과 반영) + y/n 키
- [ ] **CNF-03**: Sticky-deny — 동일 턴 내 동일 `confirm_*` 반복 시 클라에서 즉시 거부 (서버 round-trip 절약)
- [ ] **CNF-04**: Confirm 격리 — `room.activeIsSelf === true` 일 때만 confirm 다이얼로그 활성. 관전자는 read-only 뷰만 표시
- [ ] **CNF-05**: `cplan_confirm` 도 동일 다이얼로그 프레임 재사용

### STAT — Status Bar (Phase 2)

- [ ] **STAT-01**: 기본 세그먼트 — `path · model · mode · turn · ctx% · room[members]`
- [ ] **STAT-02**: 좁은 터미널 폭에서 우선순위 기반 drop (ctx% → room → mode → turn → path 순으로 축약)

### REM — Remote Room (Phase 3)

- [ ] **REM-01**: `x-harness-room` 헤더로 방 지정 (`--room <name>` CLI 인자 또는 `HARNESS_ROOM` env var)
- [ ] **REM-02**: Presence 렌더 — `room_joined` · `room_member_joined` · `room_member_left` · `room_busy` · `state_snapshot` 처리. StatusBar 세그먼트 `🟢 2명 [alice·me]`
- [ ] **REM-03**: Join 시 `state_snapshot` 으로 과거 turn 히스토리 일괄 로드 (`<Static>` key remount 패턴)
- [ ] **REM-04**: `room.activeIsSelf` 플래그로 관전 모드 판정. 관전자 `<InputArea>` disabled + "A is typing" 오버레이
- [ ] **REM-05**: Join/leave 시 system 메시지 1줄을 `<Static>` 히스토리에 append
- [ ] **REM-06**: 로컬 ↔ 원격 동등성 — 두 모드의 UX 가 동일함을 통합 테스트로 보증 (`ws://127.0.0.1` vs `ws://external-host` 동일 시나리오 green)

### SES — Session Control (Phase 3)

- [ ] **SES-01**: One-shot — `harness "질문"` 으로 REPL 없이 answer 출력 후 exit. non-TTY 시 ANSI off
- [ ] **SES-02**: Resume — `harness --resume <id>` 로 저장 세션 로드 후 REPL 모드
- [ ] **SES-03**: `--room <name> "질문"` 조합 — 방 one-shot (D-8). 결과 broadcast 범위는 구현 시 결정
- [ ] **SES-04**: Terminal resize 는 `useStdout().stdout.on('resize')` 로 감지 후 RND-04 clear 루틴 수행

### WSR — WS Reconnect + Cancel (Phase 3)

- [ ] **WSR-01**: 재연결은 jitter exponential backoff — `delay = base * 2^n * (0.5 + Math.random()*0.5)`, max 10회, 30초 cap, 안정 30초 후 attempts 리셋
- [ ] **WSR-02**: 재연결 중에는 `disconnected — reconnecting...` 오버레이 + InputArea disabled + 로컬 입력 버퍼링
- [ ] **WSR-03**: 안정 재연결 후 `resume_from: <last_event_id>` 헤더로 delta 재요청 (서버가 ring buffer 에서 delta 전달)
- [ ] **WSR-04**: INPT-09 의 Ctrl+C 첫 번째가 `cancel` 메시지를 WS 로 송신 → 현재 agent turn 만 중단 (프로세스 유지)

### PEXT — Server WS Protocol Extensions (Phase 2 또는 3)

> `harness_server.py` 및 경우에 따라 `harness_core`/`session/` 에 서버측 변경 필요. PROJECT.md Constraint "기존 이벤트 의미 변경 금지, 필드 추가 OK" 준수.

- [ ] **PEXT-01**: `agent_start` 이벤트에 `from_self: bool` 필드 추가 (클라 측 관전자/입력자 구분용)
- [ ] **PEXT-02**: `confirm_write` 이벤트에 `old_content?: string` optional 필드 추가 (클라의 DiffPreview 위해)
- [ ] **PEXT-03**: 서버에 monotonic `event_id` 부여 + `Room` 당 60초 이벤트 ring buffer 구현 (delta 제공 저장소)
- [ ] **PEXT-04**: 클라 → 서버 `resume_from: <event_id>` 헤더 파싱 + 해당 id 이후 이벤트를 순서대로 재송신
- [ ] **PEXT-05**: 클라 → 서버 `cancel` 메시지 타입 신설 + agent asyncio task 안전 중단 경로 (기존 turn_end 와 동일하게 `active_input_from` 해제 · `busy=False`)

### DIFF — Differentiators (v1.1 — 같은 milestone 내 여유분)

- [ ] **DIFF-01** (D-1): 공유 관전 모드 — 관전자가 에이전트 토큰 스트리밍을 라이브 시청 (REM-04 + RND-01 조합물)
- [ ] **DIFF-02** (D-4): 메시지 author 표기 — 각 user 메시지에 `[alice]` prefix 자동 부착
- [ ] **DIFF-03** (D-5): Confirm 관전 뷰 — 입력 주체 아닌 관전자에게는 read-only 모달 (CNF-04 의 일부)
- [ ] **DIFF-04** (D-7): 사용자 색 해시 — 토큰 기반 deterministic 색 생성, StatusBar · author prefix 색상 통일
- [ ] **DIFF-05** (D-8): `--room <name> "질문"` one-shot room 공유 (SES-03 과 같은 항목)

### TST — Testing + Docs + Beta (Phase 4)

- [ ] **TST-01**: vitest 4 + ink-testing-library 4 단위 테스트 — `parseServerMsg` · store reducer · dispatch exhaustive switch · `<MultilineInput>` 키 시퀀스 · TTY 가드
- [ ] **TST-02**: Fake harness WS 서버 + `HarnessClient` 통합 테스트 — agent 턴 / confirm_write accept / room busy / reconnect delta / one-shot / 3인 동시 재접속
- [ ] **TST-03**: 회귀 스냅샷 — 500 토큰 스트리밍 · 한국어+emoji wrap · resize 200↔40 · `/undo` + 새 메시지 · Static 오염 0
- [ ] **TST-04**: CI matrix — bun + Node 22 양쪽 green, `tsc --noEmit` + ESLint 가드 + Python pytest 199건
- [ ] **TST-05**: PITFALLS.md 의 "Looks Done But Isn't" 체크리스트 17건 수동 검증
- [ ] **TST-06**: `CLIENT_SETUP.md` 재작성 — `git clone + bun install --frozen-lockfile + bun start`, env var, troubleshooting(native dep · bun 버전 mismatch · macOS IME)
- [ ] **TST-07**: WS 프로토콜 명세 `PROTOCOL.md` 작성 — 23+ 기존 이벤트 + PEXT-01..05 확장
- [ ] **TST-08**: 외부 2인 beta 라운드 — fresh VM 에서 10분 내 설치 · REPL UX · Ctrl+R 등가 확인 · macOS IME · history persist · `/save` 포맷 · blocker 0 확인
- [ ] **TST-09**: 릴리스 노트 "이전과 달라진 점" 섹션 작성 (Python REPL 과의 UX 차이 가이드)

### LEG — Legacy Deletion (Phase 5 — TST 모두 green 이후에만)

- [ ] **LEG-01**: `ui/index.js` 삭제
- [ ] **LEG-02**: `main.py` REPL 경로 + `cli/intent.py · cli/render.py · cli/claude.py · cli/setup.py · cli/callbacks.py · cli/slash.py` 삭제
- [ ] **LEG-03**: `cli/tui.py` · `cli/app.py` · 기타 Python UI 실험 잔재 제거
- [ ] **LEG-04**: `main.py` 가 필요하다면 `harness_server.py` 서버 엔트리만 래핑하는 thin shim 으로 축소. 그렇지 않으면 삭제
- [ ] **LEG-05**: `.planning/codebase/CONCERNS.md` §1.12(spinner vs Live) · §3 Architecture 잔여 중 Python REPL 관련 항목 close 처리
- [ ] **LEG-06**: PROJECT.md Evolution — Active → Validated 이동, Key Decisions 의 Outcome 확정
- [ ] **LEG-07**: 최종 회귀 — pytest 199 + vitest 전 테스트 green · `grep -rn "prompt_toolkit" .` 빈 결과
- [ ] **LEG-08**: milestone closure 섹션 PROJECT.md 에 추가

---

## v2 Requirements (같은 milestone 여유 시, 없어도 milestone 완료)

- [ ] **D2-01** (D-2): `/pass <user>` 슬래시 — 명시적 input 주체 핸드오프. `active_input_from` 이관 서버 API 필요 (PEXT 에 없음 — 이 자체가 서버 변경)
- [ ] **D2-02** (D-3): 관전 채팅 — `/nod` · `/stop` · free-form 메시지 타입. 새 WS 이벤트 계열 필요
- [ ] **D2-03** (D-6): Join 시 최근 활동 하이라이트 — state_snapshot 위에 "최근 N분 강조" 렌더 레이어
- [ ] **D2-04**: 바이너리 배포 prototype — `bun build --compile` 로 단일 실행파일 생성 스모크

---

## Out of Scope (이번 milestone 절대 불가 — 이유 명시)

- **Alternate screen / 풀스크린 TUI** — PROJECT.md Constraint "터미널 scrollback 유지", AF-1, Pitfall 1
- **마우스 트래킹** (`\x1b[?1000h` 계열) — AF-2, 터미널 텍스트 선택 파손
- **Electron / 웹 UI / 브라우저 클라이언트** — AF-5, 터미널 네이티브 UX 가 목표
- **Python UI 병존** (Textual · prompt_toolkit Application 유지) — MEMORY.md 명시 금지, AF-7, PROJECT.md Key Decision
- **자체 스크롤 뷰포트** (앱 내부 up/down 스크롤) — AF-9, 터미널 scrollback 사용
- **CRDT 실시간 공동 편집** — AF-10, 3인 스케일 과잉
- **로그인/프로필/아바타 시스템** — AF-11, 토큰=사용자 + 색 해시로 대체
- **서버측 원격 관리 UI (권한 매트릭스 · admin console)** — AF-8, env var `HARNESS_TOKENS` 수준에서 멈춤
- **알림 센터 / 히스토리 검색 UI** — AF-12, 쉘의 `grep`/`less`/`jq` 사용
- **LLM 실시간 자동완성** — AF-13, 관전자에 prediction broadcast 사고 위험
- **테마 에디터 / 플러그인 마켓** — AF-14, 파일 편집 + `/theme` 로 충분
- **바이너리 배포 / 자동 업데이트 / Homebrew / npm 글로벌** — PROJECT.md Out of Scope, 3인 스케일에 과잉
- **백엔드 언어 교체 (Python → TS 등)** — PROJECT.md Out of Scope, 이번 milestone 은 UI 만
- **Claude API 직접 호출** — `tools/claude_cli.py` (Claude CLI `--print` 위임) 이 이미 충분
- **진화 엔진 대규모 개편** — 이번 milestone 의 목표 아님, 소규모 수정만 허용

---

## Requirement Quality

- 각 REQ-ID 는 atomic · testable · user-centric (또는 개발자 관찰 가능)
- "well-configured", "properly handled" 같은 주관 언어 금지. 전부 grep 가능 / 테스트 가능 / 관찰 가능
- Phase 매핑은 ROADMAP.md 가 확정 (아래 Traceability 는 roadmap 생성 시 채움)

---

## Traceability

**Generated by ROADMAP.md on 2026-04-23. 85/85 v1 REQ-ID mapped, 100% coverage, 0 duplicates.**

| REQ-ID | Phase | Plan | Status |
|--------|-------|------|--------|
| FND-01 | Phase 1 | TBD | Pending |
| FND-02 | Phase 1 | TBD | Pending |
| FND-03 | Phase 1 | TBD | Pending |
| FND-04 | Phase 1 | TBD | Pending |
| FND-05 | Phase 1 | TBD | Pending |
| FND-06 | Phase 1 | TBD | Pending |
| FND-07 | Phase 1 | TBD | Pending |
| FND-08 | Phase 1 | TBD | Pending |
| FND-09 | Phase 1 | TBD | Pending |
| FND-10 | Phase 1 | TBD | Pending |
| FND-11 | Phase 1 | TBD | Pending |
| FND-12 | Phase 1 | TBD | Pending |
| FND-13 | Phase 1 | TBD | Pending |
| FND-14 | Phase 1 | TBD | Pending |
| FND-15 | Phase 1 | TBD | Pending |
| FND-16 | Phase 1 | TBD | Pending |
| INPT-01 | Phase 2 | TBD | Pending |
| INPT-02 | Phase 2 | TBD | Pending |
| INPT-03 | Phase 2 | TBD | Pending |
| INPT-04 | Phase 2 | TBD | Pending |
| INPT-05 | Phase 2 | TBD | Pending |
| INPT-06 | Phase 2 | TBD | Pending |
| INPT-07 | Phase 2 | TBD | Pending |
| INPT-08 | Phase 2 | TBD | Pending |
| INPT-09 | Phase 2 | TBD | Pending |
| INPT-10 | Phase 2 | TBD | Pending |
| RND-01 | Phase 2 | TBD | Pending |
| RND-02 | Phase 2 | TBD | Pending |
| RND-03 | Phase 2 | TBD | Pending |
| RND-04 | Phase 2 | TBD | Pending |
| RND-05 | Phase 2 | TBD | Pending |
| RND-06 | Phase 2 | TBD | Pending |
| RND-07 | Phase 2 | TBD | Pending |
| RND-08 | Phase 2 | TBD | Pending |
| RND-09 | Phase 2 | TBD | Pending |
| RND-10 | Phase 2 | TBD | Pending |
| RND-11 | Phase 2 | TBD | Pending |
| CNF-01 | Phase 2 | TBD | Pending |
| CNF-02 | Phase 2 | TBD | Pending |
| CNF-03 | Phase 2 | TBD | Pending |
| CNF-04 | Phase 2 | TBD | Pending |
| CNF-05 | Phase 2 | TBD | Pending |
| STAT-01 | Phase 2 | TBD | Pending |
| STAT-02 | Phase 2 | TBD | Pending |
| REM-01 | Phase 3 | TBD | Pending |
| REM-02 | Phase 3 | TBD | Pending |
| REM-03 | Phase 3 | TBD | Pending |
| REM-04 | Phase 3 | TBD | Pending |
| REM-05 | Phase 3 | TBD | Pending |
| REM-06 | Phase 3 | TBD | Pending |
| SES-01 | Phase 3 | TBD | Pending |
| SES-02 | Phase 3 | TBD | Pending |
| SES-03 | Phase 3 | TBD | Pending |
| SES-04 | Phase 3 | TBD | Pending |
| WSR-01 | Phase 3 | TBD | Pending |
| WSR-02 | Phase 3 | TBD | Pending |
| WSR-03 | Phase 3 | TBD | Pending |
| WSR-04 | Phase 3 | TBD | Pending |
| PEXT-01 | Phase 3 | TBD | Pending |
| PEXT-02 | Phase 3 | TBD | Pending |
| PEXT-03 | Phase 3 | TBD | Pending |
| PEXT-04 | Phase 3 | TBD | Pending |
| PEXT-05 | Phase 3 | TBD | Pending |
| DIFF-01 | Phase 3 | TBD | Pending |
| DIFF-02 | Phase 3 | TBD | Pending |
| DIFF-03 | Phase 3 | TBD | Pending |
| DIFF-04 | Phase 3 | TBD | Pending |
| DIFF-05 | Phase 3 | TBD | Pending |
| TST-01 | Phase 4 | TBD | Pending |
| TST-02 | Phase 4 | TBD | Pending |
| TST-03 | Phase 4 | TBD | Pending |
| TST-04 | Phase 4 | TBD | Pending |
| TST-05 | Phase 4 | TBD | Pending |
| TST-06 | Phase 4 | TBD | Pending |
| TST-07 | Phase 4 | TBD | Pending |
| TST-08 | Phase 4 | TBD | Pending |
| TST-09 | Phase 4 | TBD | Pending |
| LEG-01 | Phase 5 | TBD | Pending |
| LEG-02 | Phase 5 | TBD | Pending |
| LEG-03 | Phase 5 | TBD | Pending |
| LEG-04 | Phase 5 | TBD | Pending |
| LEG-05 | Phase 5 | TBD | Pending |
| LEG-06 | Phase 5 | TBD | Pending |
| LEG-07 | Phase 5 | TBD | Pending |
| LEG-08 | Phase 5 | TBD | Pending |

**Coverage:** 85/85 v1 REQ-ID (100%) · duplicates: 0 · orphans: 0

---

*Last updated: 2026-04-23 via /gsd-roadmap (traceability 채움)*
