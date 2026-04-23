# Feature Research — harness ui-ink

**Domain:** Claude Code 급 터미널 에이전트 UI (Ink + React + Zustand + bun + TypeScript). 로컬 1 + 외부 원격 2 = 총 3 사용자, 공유 Room 모델.
**Researched:** 2026-04-23
**Confidence:** HIGH (Ink 7 / Claude Code 공개 문서 / 기존 REPL 코드 관찰에 기반)

## 0. Scope 원칙 (read first)

1. 총 사용자 3명. **100+ 사용자용 기능(팀 관리, admin dashboard, audit log 등) 제안 금지.**
2. 로컬과 원격이 **정확히 동일한 UI** 여야 한다 (PROJECT.md Core Value). "로컬에만 있는 기능"은 자동 anti-feature.
3. Ink 생태계에서 **공식 wrapper(`@inkjs/ui`, `ink-text-input`, `ink-spinner` 등)가 있으면 우선 사용**, 직접 구현은 그 이상이 필요할 때만.
4. Claude Code 와 동일한 터미널 UX 원칙: **alternate screen 사용 금지 · scrollback 보존 · 마우스 트래킹 최소화**.
5. "표 등급"은 Claude Code 2026-04 기준 기본 기능을 지표로 삼음. Claude Code 에 있으면 table stakes 로 간주한 항목이 많다.

---

## 1. Feature Landscape

### 1.1 Table Stakes — Input Surface

| # | Feature | Why Expected | Complexity | Ink Ready? | Notes |
|---|---------|--------------|------------|-----------|-------|
| TS-I1 | 멀티라인 입력 (Enter=제출 / Shift+Enter=개행 / Ctrl+J=개행) | Claude Code 표준. 한 줄 프롬프트는 현대 에이전트 UX 에 부족. | M | 부분 (`ink-text-input` 은 single-line) | 자체 구현 필요. `useInput` + 자체 버퍼 + cursor 관리. Shift+Enter 는 터미널이 CSI `\r` 로만 전달 → **`\` + Enter 또는 Ctrl+J** 가 실질적 fallback (Claude Code 도 동일 대체). |
| TS-I2 | 프롬프트 continuation 표시 | 2줄째부터 `> ` 같은 연결 문양 없으면 어디가 같은 입력인지 모름. | S | 직접 | 2번째 줄부터 prefix 변경 (`… ` 흐린 색). |
| TS-I3 | 슬래시 command popup (필터·키보드 nav·arg hint) | `/` 치면 목록, 타이핑으로 필터, 화살표/Tab 로 선택. Claude Code 동일. | M | 부분 (`ink-select-input` 기반) | 명령 카탈로그 + fuzzy 필터 + arg schema (예: `/resume <session>`). 기존 `harness_core` 에 이미 카탈로그 존재 — ui-ink 는 메타데이터만 소비. |
| TS-I4 | 히스토리 네비게이션 (↑ / ↓) | 터미널 UX 의 기본. 방금 친 거 다시 올리기. | S | 직접 | 세션당 history 스택. 편집 시 변경분은 별도 slot 으로 스택 최상단 복귀 지원. |
| TS-I5 | 붙여넣기 감지 (bracketed paste) — 명령 실행 금지·자동 멀티라인 전환 | 긴 텍스트 붙여넣을 때 중간 Enter 가 있어도 그 순간 제출되지 않아야. Claude Code 는 paste 시 자동 멀티라인. | M | **Ink 7 `usePaste`** | Ink 7 의 `usePaste` 가 bracketed paste 처리해 주므로 채택. 안 쓰면 paste 가 keystroke loop 로 들어와 중간 Enter 에서 submit 사고 발생. |
| TS-I6 | Tab 자동완성 (경로 / 세션명 / 슬래시 인자) | 현 Python REPL 도 일부 지원 (ENHANCEMENTS §E-3.1). 없으면 기존 사용자가 퇴화로 느낌. | M | 직접 | `/cd <Tab>` → 하위 디렉터리, `/resume <Tab>` → 저장 세션 리스트. WS 로 서버에 `completion` 요청하는 RPC 필요. |
| TS-I7 | Ctrl+C = 현재 agent turn 취소 (프로세스 종료 아님) | Claude Code 동작과 동일해야. 실수로 세션이 죽으면 로컬 작업 손실. | S | 직접 | `useInput(ctrlC)` 로 WS `cancel` 메시지 송신. 두 번째 Ctrl+C 는 종료 확인. |
| TS-I8 | 입력 편집 단축키 (Ctrl+A/E, Ctrl+K, Ctrl+W) | POSIX shell 관습. 없으면 터미널 네이티브감 상실. | S | 직접 | `useInput` 으로 키 라우팅. Home/End, Option+←/→ 도 같이. |

### 1.2 Table Stakes — Output Surface

| # | Feature | Why Expected | Complexity | Ink Ready? | Notes |
|---|---------|--------------|------------|-----------|-------|
| TS-O1 | 토큰 스트리밍 렌더 (markdown append-only) | LLM UX 의 최소 요건. 다 끝난 뒤 뿌리면 "멈춘 것 같다". | M | `<Static>` + 라이브 파트 혼합 | **완성된 메시지는 `<Static>` 으로 scrollback 확정 기록**, 현재 스트리밍 중인 turn 만 live re-render. 이 분리가 Ink 성능+scrollback 의 핵심. |
| TS-O2 | 코드 펜스 syntax highlight (언어 감지) | 코드 출력의 가독성. Claude Code 기본. | M | `@shikijs/cli` `codeToANSI` 또는 `cli-highlight` | **Shiki `codeToANSI` 권장** — 전환기(`transformerNotationDiff`)로 diff 하이라이트까지 일관성 있음. `cli-highlight` 는 가볍지만 diff 처리 빈약. |
| TS-O3 | Diff 렌더 (+/- · line numbers · hunk header) | `confirm_write` 와 `/diff` 의 품질을 결정. | M | Shiki diff transformer | Git diff 스타일 (unified). ± 색, 컨텍스트 흐리게, 라인 번호 좌측 2열. |
| TS-O4 | Tool 결과 요약 (read excerpt · write stats · shell exit code) | 풀 로그를 그대로 쏟으면 스크롤백 오염. Claude Code 는 접힌 블록 + 요약 1줄. | M | 직접 | `read_file`: "read 120 lines (of 340)". `write_file`: "+42 −5, 3.1 KB". `run_command`: "exit 0, 1.2s, 12 lines". 클릭/hover 없으므로 **펼침은 슬래시 (`/last` / `/show <id>`) 또는 별도 screen 단축키**. |
| TS-O5 | 상태 표시 / spinner (thinking · tool running) | 무응답과 대기의 구분 필수 (ENHANCEMENTS §E-2.2). | S | `ink-spinner` | "thinking…", "running write_file…", "queued (1 ahead)" 등 상태 문자열 교체. |
| TS-O6 | Ctx / 토큰 meter (`ctx: 8k/32k 24%`) | Claude Code statusline 표준. 컴팩션 타이밍 판단에 필수. | S | 직접 (status bar 구성 요소) | WS `session_status` 이벤트로 서버가 주기 push. 80% 경고색, 90% 자동 compact 제안. |
| TS-O7 | 스크롤 (PgUp/PgDn · 마우스 휠 자연 스크롤) | 터미널 scrollback 에 의존. **앱 자체 스크롤 구현 금지, 그냥 출력을 흘려보내면 된다**. | S | `<Static>` 활용 | alternate screen 을 쓰지 않으면 **터미널의 기본 scrollback 이 그대로 작동** — 즉 "Ink 는 스크롤을 구현하지 않는 게 정답". |
| TS-O8 | 색·굵기·italic 일관 테마 | 터미널 색 테마 (light/dark) 인지. Claude Code 는 감지 + `/theme`. | S | `chalk` + 감지 | 최소: `COLORFGBG` / `TERM_PROGRAM` 휴리스틱 + `/theme` 수동 스위치. |

### 1.3 Table Stakes — Confirm Dialogs (write / bash)

| # | Feature | Why Expected | Complexity | Ink Ready? | Notes |
|---|---------|--------------|------------|-----------|-------|
| TS-C1 | `confirm_write(path, content)` — 현재 파일과 diff 패널, y/n | 백엔드는 이미 콜백 지원. UX 품질이 곧 신뢰. | M | 직접 (Diff + Select) | unified diff panel + 파일 경로 + 크기 요약. 키: `y`(accept) / `n`(deny) / `a`(always this session) / `s`(skip)(sticky-deny). |
| TS-C2 | `confirm_bash(cmd)` — 커맨드 미리보기 + 위험도 라벨, y/n | shell injection 가드와 직결. sticky-deny 패턴 이미 존재 (memory). | S | 직접 | 한 줄 요약 + 분류 라벨 (`safe` / `mutating` / `destructive`). `always allow <pattern>` 는 이번 MVP 범위 밖. |
| TS-C3 | 동일 턴 내 반복 prompt 억제 | 같은 질문 N 번 뜨면 실수로 y 반복. sticky-deny 는 이미 구현. | S | store | "이 턴에서 이 path/command 에 한해 자동 y" 옵션. |
| TS-C4 | Room 입력 주체만 confirm 가능 (BB-2 DQ2 옵션 D) | 관전자가 y 누르면 거버넌스 붕괴. | S | store + WS filter | `active_input_from === myWsId` 일 때만 키 바인딩 활성화. 아니면 "waiting for X to confirm" 표시. |

### 1.4 Table Stakes — Session / Control

| # | Feature | Why Expected | Complexity | Ink Ready? | Notes |
|---|---------|--------------|------------|-----------|-------|
| TS-S1 | `harness "질문"` one-shot 모드 (응답 출력 후 종료) | 쉘 파이프 호환. `harness "fix this" < error.log`. | S | React 렌더 + 종료 hook | `useApp().exit()` 으로 EOF/agent_end 시 종료. stdout 이 TTY 아닐 때는 ANSI 끄기. |
| TS-S2 | `harness --resume <id>` 모드 | 저장 세션 로드 후 REPL. 기존 Python REPL 에 있음. | S | CLI 파서 + WS | `commander` / `cac` 로 argv 파싱, WS 에 `resume` 메시지. |
| TS-S3 | `harness --room <name>` (공유 룸 참여) | BB-2 DQ1 헤더 옵션. **로컬/원격 동일 UI** 원칙의 핵심 도구. | S | WS header | `x-harness-room` 헤더로 주입. |
| TS-S4 | 터미널 resize 시 scrollback 유지, 레이아웃 artifact 없음 | Python prompt_toolkit 이 여기서 실패해서 Ink 로 교체한 것 (PROJECT.md Evolution). Ink 7 `useWindowSize` 가 해결. | S | `useWindowSize` | 테스트: width 80 ↔ 120 급변경, scrollback 손실 0. |
| TS-S5 | Ctrl+D = 종료 (입력 비어있을 때만) | POSIX 관습. 입력 중이면 무시. | S | 직접 | 버퍼 empty 확인 후 `exit()`. |

### 1.5 Table Stakes — Remote Room (3인 공유)

| # | Feature | Why Expected | Complexity | Ink Ready? | Notes |
|---|---------|--------------|------------|-----------|-------|
| TS-R1 | 멤버 프레즌스 목록 (현재 방에 누구) | 3인 협업 시 "있는 줄 몰랐다" 가 최악. `/who` 는 이미 BB-2 에 존재. | S | store + WS `presence` 이벤트 | status bar 오른쪽 세그먼트: `#team [alice·bob·me]`. join/leave 시 1줄 시스템 메시지. |
| TS-R2 | 입력 주체(active_input_from) 시각화 | "지금 alice 가 치는 중" 이 안 보이면 동시 입력 충돌. | S | store | 타 사용자 입력 중: `[alice is typing…]` subtle line, 내 프롬프트는 disable 표시. |
| TS-R3 | Busy / queued 상태 | Ollama 락 대기 중이면 표시 (ENHANCEMENTS §E-2.2). | S | WS 이벤트 | `queued (1 ahead)` → `running` → `done` 단계. |
| TS-R4 | Join 시 state snapshot (과거 messages 재현) | BB-2 DQ4 옵션 A. 방 합류 시 전체 문맥 없으면 무쓸모. | M | `<Static>` 에 snapshot 주입 | snapshot 이벤트 받고 Zustand `messages` 치환 → `<Static>` 1회 전체 렌더. |
| TS-R5 | 연결 상태 표시 (reconnecting / offline) | WS flakiness 에 대비. Claude Code 수준이면 자동 재연결도 기대. | M | 직접 | status bar 좌측에 `●` / `○` / `↻`. 재연결 시 자동 snapshot 재요청. |
| TS-R6 | 로컬·원격 UI 동등성 | PROJECT.md constraint. 어떤 기능도 분기 금지. | — | — | **이건 기능 아닌 원칙** — 모든 TS 항목이 양쪽에서 동일해야 함. 테스트 케이스로 보증. |

### 1.6 Table Stakes — Status Bar

| # | Feature | Why Expected | Complexity | Ink Ready? | Notes |
|---|---------|--------------|------------|-----------|-------|
| TS-B1 | 세그먼트: `path · model · mode · turn · ctx% · room[members]` | Claude Code statusline 관습. 1줄에 전부. | S | 직접 | Zustand `statusSlice` → 컴포넌트 세그먼트 매핑. 80col 이하일 때 축약 전략(권장: `ctx` 과 `room` 우선). |
| TS-B2 | 좁은 터미널 graceful 축약 | 100col 미만에서 한 세그먼트가 전부 먹으면 안 됨. | S | `useWindowSize` | 우선순위 기반 drop (`model` → `mode` → `path` 축약 순). |

---

## 2. Differentiators (3인 원격 페어에 특화)

> Claude Code 단일 사용자 UX 와 **확실히 다른 가치**만 추린다. "혼자서도 좋은 기능" 은 여기서 제외 — table stakes 로 밀어냈음.

| # | Feature | Value Proposition | Complexity | Ink Ready? | Notes |
|---|---------|-------------------|------------|-----------|-------|
| D-1 | **공유 관전 모드** — 입력 주체가 아닌 사용자는 에이전트 스트리밍을 실시간 관전 | Cursor/Claude Code 에 없는 유일한 가치축. BB-2 의 본질. | M | 직접 (broadcast) | TS-O1 위에 WS `broadcast` 붙이면 자연히 성립. UI 측은 "자기가 입력 주체가 아닐 때 프롬프트 비활성 + 상단에 observing 라벨". |
| D-2 | **명시적 핸드오프 (`/pass <user>` 또는 `/yield`)** | turn-taking 이 거부(BB-2 DQ3 옵션 B)라면 "이제 너 쳐" 가 명시 신호. 말싸움 방지. | S | 슬래시 추가 | 서버 측에서 `active_input_from` 이관 이벤트 발행, 양쪽 UI 는 프롬프트 활성/비활성 swap. |
| D-3 | **관전 중 라이트 반응 (`/nod`, `/stop`, 짧은 채팅 `: 메시지`)** | 관전자가 턴을 뺏지 않고 신호만 보내는 low-friction 채널. 페어 프로그래밍의 본질적 상호작용. | S | 슬래시 + 채팅 render | 메시지 타입 `user_comment` 신설, 모든 멤버에게 broadcast, messages 에 누적은 하지만 agent 입력으로는 들어가지 않음. |
| D-4 | **"누가 이 메시지 보냈나" 속성 표기** | 3명 방에서 user 메시지 앞에 `[alice]` 같은 prefix 가 없으면 로그가 무의미. | S | render | `messages[i].author_display` (서버 payload). 색은 사용자별 해시. |
| D-5 | **Confirm 관전 뷰** | 내가 입력 주체 아닐 때도 "alice 가 write_file 에 대해 y/n 고민 중" 을 보는 것이 감사+신뢰 요소. 버튼은 비활성. | S | render | TS-C4 와 동일 store, 뷰만 read-only variant. |
| D-6 | **Join 시 "최근 30초 활동" 하이라이트** | state snapshot 전체는 길 수 있음. 신규 joiner 가 "방금 무슨 일 있었나" 를 빨리 파악. | S | render | snapshot 수신 후 최근 활동 3~5건을 배너로 표출, 5초 후 일반 스크롤에 편입. |
| D-7 | **색상별 사용자 식별 (닉네임 + 색 해시)** | 3명이라 짧은 색 맵으로 충분. prefix 텍스트만으론 훑을 때 놓침. | S | `chalk` | `hash(nick) % palette.length`. 동적 추가도 안정. |
| D-8 | **One-shot 결과의 방 공유 옵션 (`harness --room team "질문"`)** | 원격 사용자가 CI/스크립트에서 쏜 one-shot 결과를 방 멤버가 보게 됨. | S | CLI + WS | `--room` 지정 시 solo 가 아니라 해당 room 에 메시지 게시 + 바로 종료. |

**D- 목록에서 의도적으로 제외된 것**: 실시간 커서 공유, CRDT 텍스트 편집, 음성/화상, 팀 권한 매트릭스, 전용 admin UI — 3인 스케일에 과한 복잡도.

---

## 3. Anti-Features (do NOT build — 각각 이유 명시)

> 이 섹션은 한 줄이 아니라 **왜 짓지 말아야 하는지, 대체 방안은 무엇인지** 를 기재한다.

| # | Feature | 왜 요청/유혹되는가 | 왜 해롭다 | 대체 방안 |
|---|---------|-----|-----|------|
| AF-1 | **Alternate screen / 풀스크린 TUI** (htop 스타일) | "화려하고 완전 제어" | 터미널 scrollback 상실 → Cmd+C 복사 불가, 스크롤 불가. Claude Code 가 의도적으로 회피. PROJECT.md Evolution 에서 이미 결정. | Ink `<Static>` + inline render 로 스크롤백 유지. |
| AF-2 | **마우스 트래킹 (VT mouse sequences)** | "클릭으로 버튼 조작, 휠 스크롤" | 터미널 기본 텍스트 선택이 망가짐(사용자가 출력 복사 불가). VS Code terminal, macOS Terminal.app 상호작용도 파손. | 전부 키보드 바인딩. 마우스 휠은 **트래킹 꺼둔 상태에서 터미널 자체 scrollback** 이 처리. |
| AF-3 | **자동 업데이트 (사용자 동의 없이)** | "항상 최신 유지" | git clone 배포 모델. 사용자가 `git pull` 시점을 통제. 서버·클라이언트 버전 skew 조용히 생기면 디버깅 지옥. | `harness --version` + 서버 핸드셰이크에 버전 비교, 불일치 시 경고만. |
| AF-4 | **로컬에만 존재하는 기능** (예: 로컬 GPU status 패널, 로컬 파일 트리 인라인 뷰어) | "집에서만 쓸 때 편하다" | PROJECT.md Core Value 직접 위배: "로컬과 원격이 동일한 경험". 양쪽 분기하는 순간 유지 비용 2배, 에이전트가 혼동. | 서버가 제공 가능한 동일 API (WS `status_snapshot`) 로만 전달. |
| AF-5 | **Electron / 웹뷰 임베드 / GUI 창** | "렌더링 옵션 다양" | 터미널 네이티브 UX 포기. 배포 사이즈 폭증. PROJECT.md Out of Scope 명시. | 터미널 ANSI + Ink. 끝. |
| AF-6 | **오픈 세션 `exec` (임의 shell) 리모트 실행 경로** | "원격으로 디버깅 편하게" | 샌드박스(`tools/shell.py` classifier)가 우회됨. 토큰 탈취 시 피해 무한. | 기존 confirm_bash + `HARNESS_TOKENS` + shell classifier 유지. 우회로 만들지 않음. |
| AF-7 | **Textual / prompt_toolkit application 모드 등 Python UI 병존** | "기존 코드 살리자" | 사용자 명시 금지 (PROJECT.md Key Decision, memory MEMORY.md). 에이전트 혼동 재발. | Python REPL 경로는 milestone 내 삭제. `harness_server.py` 만 남김. |
| AF-8 | **Slash command 서버 측 원격 관리** (권한 매트릭스 UI, admin console, audit log UI) | "협업 = 엔터프라이즈 기능" | 3인 스케일에 과함. 유지 비용 >> 가치. 토큰별 권한은 env var(ENHANCEMENTS §E-2.6) 수준으로 충분. | `HARNESS_TOKENS="alice:full,bob:readonly"` 수준에서 멈춤. UI 개발 없음. |
| AF-9 | **자체 스크롤 뷰포트 (앱 내부에서 up/down 으로 과거 출력 이동)** | "완전한 제어" | 1) AF-1 로 alternate screen 쓰지 않기로 했으니 불필요. 2) 구현하면 복붙/검색이 깨짐. | 터미널 scrollback 사용. Ink `<Static>` 으로 append-only. |
| AF-10 | **CRDT 실시간 공동 편집 (입력 동시 타이핑)** | "Google Docs 감성" | 3인 · CLI agent 세션 시나리오에 복잡도 과잉. turn-taking 거부 모델(BB-2 DQ3 B)로 충분. | D-2 `/pass` 명시 핸드오프. |
| AF-11 | **로그인/프로필/아바타 시스템** | "멀티유저니까 당연" | 토큰 == 사용자. 계정 시스템 만들면 배포 복잡도·DB 필요성 ↑. | `HARNESS_TOKENS` 에 `nick:perm` pair. 아바타는 D-7 색 해시로 대체. |
| AF-12 | **알림 센터 / 히스토리 검색 UI / 필터 패널** | "기능 풍부" | CLI 가 할 일이 아님. 쉘의 `grep`, `jq`, `less` 가 있음. | 로그는 JSONL (`session/logger.py`) 로 이미 존재, `/logs` 슬래시는 범위 밖. |
| AF-13 | **입력 중 토큰 실시간 예측/보완 (LLM 자동완성)** | "fancy" | 에이전트 호출 비용 + 3인 공유 환경에서 prediction 이 broadcast 되면 사고 발생 (오타 중 예측이 방 전체 공유). | Table-stake Tab 자동완성(TS-I6) 수준까지만. |
| AF-14 | **테마 에디터 / 플러그인 스토어 / 스킬 마켓플레이스** | "커스터마이징" | 3인 프로젝트. 파일 수정으로 충분. | `.harness.toml` 편집 + `/theme light|dark`. |

---

## 4. Feature Dependencies

```
[TS-I5 usePaste(Ink7)] ──enables──> [TS-I1 멀티라인 입력 안전성]
                                         └──required for──> [TS-I3 슬래시 popup] (슬래시는 한 줄이지만 멀티라인 모드 전환 로직과 얽힘)

[TS-O1 스트리밍(<Static>+live)] ──foundation for──> [TS-O4 tool 결과 요약]
                                                         └──foundation for──> [D-1 공유 관전]

[TS-R4 state snapshot] ──required for──> [TS-R6 UI 동등성 실질 보증]
                                              └──required for──> [D-6 최근 활동 하이라이트]

[TS-C4 입력 주체 confirm 격리] ──requires──> [TS-R2 active_input_from 시각화]
                                                 └──requires──> [TS-R1 presence]

[D-1 관전] ──requires──> [TS-O1, TS-R1, TS-R2]
[D-2 /pass] ──requires──> [TS-R2, 서버 active_input_from API 확장]
[D-3 /nod · /stop · 채팅] ──requires──> [D-4 author 표기]

[TS-S4 resize 안정] ──relies on──> [Ink 7 useWindowSize]

AF-1 (alternate screen) ──conflicts with──> [TS-O7 scroll, TS-R6 동등성, AF-9]
AF-2 (mouse tracking) ──conflicts with──> [터미널 기본 텍스트 선택 · TS-O7]
```

### Dependency Notes

- **Ink 7 전제**: TS-I5 (`usePaste`), TS-S4 (`useWindowSize`) 둘 다 Ink 7 hooks. Ink 6 이하 사용 시 직접 구현 필요 → **STACK.md 에서 Ink ≥ 7 고정 권장**.
- **Snapshot 품질이 원격 UX 전체의 한계값**: TS-R4 가 깨지면 TS-R6 동등성 원칙이 실질적으로 무너진다. 최우선 통합 테스트 대상.
- **D-1 은 TS 들의 조합** — 추가 구현이 거의 없어도 자연히 성립. 즉 "공유 관전" 은 설계 의도만 잃지 않으면 0 cost 에 가깝다.
- **Confirm 격리 체인**: TS-R1 → TS-R2 → TS-C4 순서. 서버(이미 BB-2 에서 처리) 와 UI 양쪽 모두 각 단계 완성 없으면 다음 단계 가치 없음.

---

## 5. MVP Definition

### 5.1 Launch with (v1 = 이번 milestone)

Python REPL 을 교체하려면 **TS 전 항목이 회귀 없이** 구현되어야 한다. 하나라도 빠지면 기존 사용자가 "다운그레이드" 로 인식.

- [ ] TS-I1 멀티라인 입력 — 기존 REPL 동등
- [ ] TS-I2 continuation 표기
- [ ] TS-I3 슬래시 popup + 필터 + arg hint
- [ ] TS-I4 히스토리
- [ ] TS-I5 `usePaste`
- [ ] TS-I6 Tab 자동완성 (최소: 경로, `/resume` 세션명)
- [ ] TS-I7 Ctrl+C 취소
- [ ] TS-I8 입력 편집 단축키
- [ ] TS-O1 스트리밍 (`<Static>` + live)
- [ ] TS-O2 syntax highlight (Shiki `codeToANSI`)
- [ ] TS-O3 diff render
- [ ] TS-O4 tool 요약
- [ ] TS-O5 spinner/상태
- [ ] TS-O6 ctx meter
- [ ] TS-O7 스크롤 (즉, alternate screen 쓰지 않기)
- [ ] TS-O8 테마 기본
- [ ] TS-C1 confirm_write
- [ ] TS-C2 confirm_bash
- [ ] TS-C3 반복 억제 (sticky-deny — 서버 기존 로직 활용)
- [ ] TS-C4 입력 주체 격리
- [ ] TS-S1 one-shot
- [ ] TS-S2 resume
- [ ] TS-S3 `--room`
- [ ] TS-S4 resize 안정
- [ ] TS-S5 Ctrl+D
- [ ] TS-R1 presence
- [ ] TS-R2 active_input 시각화
- [ ] TS-R3 busy/queue
- [ ] TS-R4 snapshot 재현
- [ ] TS-R5 연결 상태/자동 재연결
- [ ] TS-R6 동등성 원칙 (테스트로 보증)
- [ ] TS-B1/B2 status bar

### 5.2 Add right after (v1.1 — 같은 milestone 여유분)

- [ ] D-1 공유 관전 (TS 조합이므로 거의 공짜)
- [ ] D-4 author 표기 (payload 필드 하나)
- [ ] D-5 confirm 관전 뷰 (read-only variant)
- [ ] D-7 사용자 색 해시
- [ ] D-8 `--room` one-shot

### 5.3 Future consideration (v1.2+ 또는 다음 milestone)

- [ ] D-2 `/pass` 핸드오프 — 서버 API 확장 필요
- [ ] D-3 `/nod`, `/stop`, 관전 채팅 — 메시지 타입 신설, UX 디자인 라운드 필요
- [ ] D-6 최근 활동 하이라이트 — UX 튜닝 후

### 5.4 Explicit **NOT** doing (이번 및 다음 milestone 모두)

AF-1 ~ AF-14 전부. 특히 문서에 못 박을 것:
- AF-1 alternate screen
- AF-2 mouse tracking
- AF-4 로컬 전용 기능
- AF-7 Python UI 병존
- AF-10 CRDT

---

## 6. Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| TS-I1 멀티라인 입력 | HIGH | MEDIUM | P1 |
| TS-I3 슬래시 popup | HIGH | MEDIUM | P1 |
| TS-I5 usePaste | HIGH | LOW (Ink 7) | P1 |
| TS-I6 Tab 자동완성 | MEDIUM | MEDIUM | P1 |
| TS-I7 Ctrl+C | HIGH | LOW | P1 |
| TS-O1 스트리밍 | HIGH | MEDIUM | P1 |
| TS-O2 syntax highlight | HIGH | MEDIUM | P1 |
| TS-O3 diff render | HIGH | MEDIUM | P1 |
| TS-O4 tool 요약 | HIGH | MEDIUM | P1 |
| TS-O6 ctx meter | MEDIUM | LOW | P1 |
| TS-O7 scroll (alt-screen 회피) | HIGH | LOW | P1 |
| TS-C1 confirm_write | HIGH | MEDIUM | P1 |
| TS-C2 confirm_bash | HIGH | LOW | P1 |
| TS-C4 입력 주체 격리 | HIGH | LOW | P1 |
| TS-S1 one-shot | MEDIUM | LOW | P1 |
| TS-S2 resume | MEDIUM | LOW | P1 |
| TS-S3 `--room` | HIGH | LOW | P1 |
| TS-S4 resize 안정 | HIGH | LOW (Ink 7 hook) | P1 |
| TS-R1 presence | HIGH | LOW | P1 |
| TS-R2 active_input 시각화 | HIGH | LOW | P1 |
| TS-R3 busy/queue | MEDIUM | LOW | P1 |
| TS-R4 snapshot | HIGH | MEDIUM | P1 |
| TS-R5 재연결 | MEDIUM | MEDIUM | P1 |
| TS-B1 status bar | HIGH | LOW | P1 |
| D-1 공유 관전 | HIGH | LOW (조합물) | P1 |
| D-4 author 표기 | HIGH | LOW | P1 |
| D-5 confirm 관전 | MEDIUM | LOW | P2 |
| D-7 사용자 색 | MEDIUM | LOW | P2 |
| D-8 --room one-shot | MEDIUM | LOW | P2 |
| D-2 /pass 핸드오프 | MEDIUM | MEDIUM | P2 |
| D-3 /nod · 관전 채팅 | MEDIUM | MEDIUM | P2 |
| D-6 최근 활동 하이라이트 | LOW | MEDIUM | P3 |

**Priority key:**
- **P1** — 이번 milestone (v1). Python REPL 대체 요건.
- **P2** — 같은 milestone 여유가 있으면, 아니면 직후 1.1.
- **P3** — 다음 milestone 후보.

---

## 7. Competitor / Reference Feature Analysis

| Feature | Claude Code (2026-04) | Gemini CLI | tmux + wemux (pair ref) | harness ui-ink 방향 |
|---------|-----------------------|-----------|--------------------------|---------------------|
| 멀티라인 입력 | `\` + Enter, Shift+Enter (터미널 별), Ctrl+J | 유사 | N/A | **동일 UX 채택** (TS-I1) |
| 슬래시 popup | 필터·키보드·arg hint | 유사 | N/A | **동일 UX 채택** (TS-I3) |
| `/vim` 모드 | 2026 최신 | ✗ | N/A | 채택 안 함 (scope 초과) |
| `/btw` 도중 끼어들기 | 2026-03 | ✗ | N/A | D-3 `/nod` 가 유사 정신 (방 공유니까 다중) |
| Status line | 커스텀 script 주입 | 제한적 | `status-right` 문자열 | **Zustand slice 직접** — 동일 UX 지만 구현 단순화 (TS-B1) |
| Ctx / token meter | `used_percentage` 필드 stdin | ✗ 표준 없음 | N/A | **채택** (TS-O6) |
| 공유 관전 | ✗ (단일 사용자) | ✗ | Mirror 모드 | **D-1 채택** — 본질적 차별점 |
| 명시 핸드오프 | ✗ | ✗ | `detach` / `attach` 로 간접 | **D-2 `/pass`** 로 구조화 |
| Presence 목록 | ✗ | ✗ | `wemux users`, `status_users` | **TS-R1 채택** |
| Alternate screen | 사용 안 함 (Ink) | Ink 기반 유사 | 사용 함 | **사용 안 함 (AF-1)** |
| 마우스 트래킹 | 최소 | 최소 | 옵션 | **사용 안 함 (AF-2)** |
| Bracketed paste | 사용 (Ink 7 usePaste) | 사용 | 터미널 기본 | **사용** (TS-I5) |

---

## 8. Confidence Assessment

| Claim | Confidence | Basis |
|-------|------------|-------|
| Ink 7 `usePaste`, `useWindowSize` 존재·동작 | HIGH | Ink 7 공식 릴리스 노트 |
| Claude Code 가 alternate screen 을 피한다 | HIGH | Ink 기반 + `<Static>` 공식 문서 + 공개 이슈 다수 |
| Claude Code 멀티라인 입력 단축키 | HIGH | Claude Code 2026 공식 가이드 |
| Shiki `codeToANSI` + diff transformer 로 터미널 diff 하이라이트 가능 | HIGH | Shiki 공식 문서 |
| `ink-text-input` 이 single-line only | HIGH | 패키지 README / 이슈 |
| wemux 스타일 presence 가 3인 UX 에 충분 | MEDIUM | 2011~ 관행 + 3인 스케일 가정 |
| D-1 공유 관전이 "거의 공짜" | MEDIUM | TS 조합 논리 근거. BB-2 broadcast 가 실제 어떻게 구현되는지 Phase 2 검증 필요 |
| sticky-deny 관련 기존 서버 로직 재사용 가능 | HIGH | memory MEMORY.md + BB-2-DESIGN 참조 |

---

## Sources

- [vadimdemedes/ink (GitHub)](https://github.com/vadimdemedes/ink)
- [Ink 7.0 릴리스 — `usePaste`, `useWindowSize` 도입](https://github.com/vadimdemedes/ink/releases/tag/v7.0.0)
- [heise — "Ink 7.0 fundamentally revises input handling"](https://www.heise.de/en/news/React-in-the-Terminal-Ink-7-0-fundamentally-revises-input-handling-11249949.html)
- [Ink 공식 `<Static>` · `usePaste` · `useInput` 문서](https://github.com/vadimdemedes/ink/blob/master/readme.md)
- [`ink-text-input` (single-line 제한 확인)](https://github.com/vadimdemedes/ink-text-input)
- [Claude Code Interactive Mode 공식 가이드 (2026)](https://claudefa.st/blog/guide/mechanics/interactive-mode)
- [Claude Code Cheat Sheet 2026](https://computingforgeeks.com/claude-code-cheat-sheet/)
- [Claude Code Statusline 공식 문서](https://code.claude.com/docs/en/statusline)
- [Claude Code Changelog (2026)](https://claudefa.st/blog/guide/changelog)
- [Claude Code bracketed paste 관련 이슈](https://github.com/anthropics/claude-code/issues/3134)
- [Shiki `codeToANSI` CLI 패키지](https://shiki.style/packages/cli)
- [Shiki `transformerNotationDiff`](https://github.com/shikijs/shiki/issues/297)
- [`cli-highlight`](https://github.com/felixfbecker/cli-highlight)
- [wemux — multi-user tmux, presence / mirror / pair 모드](https://github.com/zolrath/wemux)
- [프로젝트 내부 참조: `.planning/PROJECT.md`, `.planning/BB-2-DESIGN.md`, `.planning/codebase/ENHANCEMENTS.md`, `ui-ink/README.md`]

---
*Feature research for: Claude Code 급 Ink 기반 터미널 에이전트 UI, 3인 공유 Room*
*Researched: 2026-04-23*
