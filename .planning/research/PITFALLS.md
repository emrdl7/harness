# Pitfalls Research — Ink TUI Agent UI

**Domain:** Terminal agent UI (Node + Ink + Zustand + bun + TypeScript) replacing a failed Python(prompt_toolkit + Rich) stack
**Researched:** 2026-04-23
**Confidence:** HIGH (Context7/공식 GitHub issues 다수 교차검증, 일부 MEDIUM — bun 세부 동작)
**Scope note:** 일반 Node.js/React 조언은 제외. Ink/Yoga/React-in-terminal 에 고유하거나, 이전 Python 세션의 실패가 Ink 에서 다른 모양으로 반복되는 함정에 집중.

---

## Critical Pitfalls

### Pitfall 1: Alternate screen 모드 실수로 활성화 (H)

**What goes wrong:**
Ink 튜토리얼 일부 · `ink-big-text` 같은 예제 · `process.stdout.write('\x1b[?1049h')` 직접 호출이 alternate screen 으로 전환. 종료 시 터미널이 primary screen 으로 돌아오면서 세션 중 출력이 전부 사라짐. 사용자는 Cmd+C 로 과거 tool 결과를 복사하던 Claude Code 스타일 UX 를 잃음.

**Why it happens:**
Ink 자체는 alternate screen 을 기본으로 쓰지 않음(중요). 그러나 "fullscreen TUI" 예제를 따라가면 `enterAltScreenCommand` 같은 래퍼가 껴있고, `render(<App />, {exitOnCtrlC: true, patchConsole: true})` 같은 옵션이 alternate screen 처럼 보이는 부작용을 만듦. 또한 tmux/SSH 환경에서 mouse tracking 을 켜면 scrollback 이 사실상 죽음(Claude Code Issue #38810).

**How to avoid:**
- `render()` 호출부를 단 한 곳(`index.tsx`)으로 고정, `patchConsole: false` 명시. 현재 스켈레톤은 `render(<App />)` 이므로 alternate screen 은 꺼져 있음 — 이 상태 유지가 핵심.
- `\x1b[?1049h` / `\x1b[?1049l` / `\x1b[?1000h` (mouse tracking) 가 코드 어디에도 없는지 grep 가드.
- 환경변수 `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` 같은 업계 관행을 참고해, 만약 향후 fullscreen 이 필요하면 opt-in 플래그로만 허용.
- PROJECT.md Constraints 에 "alternate screen 사용 금지" 가 이미 명시됨 — 리뷰 체크리스트에 편입.

**Warning signs:**
- 세션 종료 후 터미널 scrollback 에 방금 본 출력이 없음
- `/usr/bin/tput smcup` 또는 `rmcup` 이 실행되는 strace/dtrace 추적
- tmux 에서 Shift+PageUp 이 안 먹힘 / `screen -h` 출력이 비어있음

**Phase to address:** Phase 1(스켈레톤 고정) — `index.tsx` 렌더 옵션 잠금 + CI grep 가드

---

### Pitfall 2: Terminal resize 시 stale line 잔존 (H)

**What goes wrong:**
터미널 폭을 줄이면 기존 렌더 라인이 wrap 되어 Ink 의 내부 `lastOutput` 줄 카운트보다 실제 행이 많아짐. 다음 re-render 때 Ink 가 "기록된 줄 수" 만큼만 커서를 위로 올려 clear → 상단에 이전 프레임 조각이 영구히 남음. Python prompt_toolkit 에서 겪었던 "renderer 가 wrap 을 추적 못함" 과 **완전히 동일한 버그가 Ink 에도 존재** (GitHub Issue #907, 2026-03-20 시점 open).

**Why it happens:**
Ink renderer 는 출력한 논리 라인 수를 기반으로 ANSI 커서 이동(`\x1b[{n}A`)을 함. 하지만 터미널이 자동 wrap 한 물리 라인 수는 폭에 따라 변함. resize 이벤트에서 full-clear 를 하지 않으므로 mismatch 발생.

**How to avoid:**
- `useStdout()` 의 `stdout.on('resize', ...)` 에서 강제 `stdout.write('\x1b[2J\x1b[H')` (ED2 + Home) 한 뒤 Ink 가 next frame 에서 다시 그리도록 유도. Python REPL 에서 썼던 ED3(`\x1b[3J`) 까지 함께 쏘면 VS Code 계열 xterm.js 에서도 잔상 제거(commit `5ba9e6f` 경험).
- `<Static>` 컴포넌트에 히스토리를 넣었다면 resize 후 강제 remount 대신 `<Static>` 바깥 일반 트리에 넣고 virtualize (아래 Pitfall 6 참조).
- 긴 메시지·wide char · emoji 가 폭 경계에 걸리는 케이스를 vitest + ink-testing-library 스냅샷으로 가드.
- 업스트림 패치가 merge 될 때까지 self-host fork 여지 남겨두기(이슈 #907 fix commit 추적).

**Warning signs:**
- 폭을 줄이고 다시 늘리면 상단에 "유령 문자" 가 남음
- 한국어 / emoji 포함된 메시지에서만 발생 (wcwidth 이슈 동반)
- `cols = stdout.columns` 를 읽고 있는데 resize 후에도 값이 업데이트 안 됨 (stale ref 동반일 수 있음)

**Phase to address:** Phase 2(메시지 리스트 + wrap) — resize 테스트 케이스 필수

---

### Pitfall 3: Raw mode 미복원으로 터미널 먹통 (H)

**What goes wrong:**
Ink 가 `process.stdin.setRawMode(true)` 를 걸어둔 상태에서 프로세스가 비정상 종료되면 터미널이 raw mode 로 남아 에코 · 라인 버퍼 · Ctrl+C 전부 죽음. 사용자는 `stty sane` 또는 `reset` 을 쳐야 복구. 외부 원격 사용자 2인에게 이게 한 번만 발생해도 "망가진 도구" 낙인이 찍힘.

**Why it happens:**
- unhandled promise rejection, native crash, WS handler 에서 throw → React ErrorBoundary 미설정 시 Ink 의 cleanup 이 돌지 않음
- Ink 는 기본적으로 `SIGINT`/`SIGTERM` 에서 `unmount()` 를 부르지만, WS 콜백 내부 `setImmediate`/비동기 예외는 cleanup 을 우회
- pipe/CI 환경에서는 `process.stdin.setRawMode` 가 `undefined` → 에러가 새어나옴 (Ink issue #166, claude-code #404/#1072/#5925)
- bun 은 일부 signal 처리가 Node 와 미묘하게 다름(MEDIUM confidence)

**How to avoid:**
- `process.stdin.isTTY` + `typeof process.stdin.setRawMode === 'function'` 을 `index.tsx` 최상단에서 체크, 둘 중 하나라도 false 면 Ink render 대신 one-shot 모드로 빠짐(PROJECT.md 의 `harness "질문"` 경로).
- 최상위 `process.on('uncaughtException', ...)` / `process.on('unhandledRejection', ...)` / `SIGHUP` 에서 `stdout.write('\x1b[?25h')` (커서 복원) + `stdin.setRawMode(false)` + `stdin.pause()` → 그 다음 exit.
- React `ErrorBoundary` 컴포넌트로 루트 감싸서 렌더 중 throw 가 트리 전체를 죽이지 않게.
- `bun run` 진입 스크립트에서 `trap 'stty sane' EXIT` 로 쉘 레벨 안전망.
- vitest 에서 pipe stdin 케이스 "crash 시 raw mode off 복구" 명시 테스트.

**Warning signs:**
- 사용자 보고: "harness 끄니까 터미널이 이상해요"
- `stty -a` 에서 `-icanon -echo` 가 프로세스 종료 후에도 남아있음
- Ink render 실패 시 콘솔에 `Raw mode is not supported on the current process.stdin` 메시지

**Phase to address:** Phase 1(스켈레톤) — TTY 가드 + 크래시 핸들러가 첫 번째 코드

---

### Pitfall 4: Ink 재렌더가 전체 트리를 훑어 스트리밍 토큰에서 플리커 (H)

**What goes wrong:**
Ollama 가 30~100 tok/s 로 스트리밍. 토큰마다 `appendMessage` → Zustand 브로드캐스트 → 전체 `messages.map(...)` 리렌더. Ink 는 32ms throttle 을 적용하지만, 긴 메시지 리스트가 Yoga layout 을 매번 다시 계산하면서 시각적 flicker + CPU spike. 긴 세션에서는 초당 수백 번 전체 메시지 리스트 wrap 재계산.

**Why it happens:**
Ink 아키텍처는 React state 변경 시 **전체 트리 traversal + 전체 screen redraw**. 이는 버그가 아니라 설계. Yoga 는 모든 노드 위치를 계산하므로 한 컴포넌트 변경이 전체 layout 을 흔듦. 현재 `App.tsx` 는 `messages.map` 을 단일 `<Box>` 안에 렌더 — 토큰마다 전체 히스토리 리레이아웃.

**How to avoid:**
- **완료된 메시지는 `<Static>` 으로 이동**. `<Static items={completedMessages}>` 는 한 번 렌더 후 다시 안 건드림(Ink 3 에서 개선된 핵심 컴포넌트, Claude Code 도 이 패턴). 현재 작성 중인 assistant 메시지만 일반 트리의 "active" 슬롯에서 렌더.
- 토큰 스트리밍은 Zustand 의 별도 슬라이스(`activeTokens: string`)로 분리. `useStore(s => s.activeTokens)` 로만 구독하는 작은 컴포넌트 생성 → 히스토리 컴포넌트는 re-render 안 됨.
- `useShallow` 로 객체 selector 메모이즈: `useStore(useShallow(s => ({busy: s.busy, status: s.status})))` — 현재 App.tsx 는 개별 select 로 이미 나뉘어있음(좋음), 단 `messages` 는 통째로 구독 중이라 문제.
- 토큰 버퍼링: 60Hz(16ms) 보다 자주 들어오는 토큰은 `requestAnimationFrame` 대신 `setTimeout 16` 로 배치.
- Rich.Live 와 `_Spinner` 가 충돌해서 한국 세션에서 깨진 프레임을 반복한 §1.12 경험 — Ink 에서는 "여러 Live 영역" 이 아니라 "하나의 React 트리" 이므로 spinner 와 스트리밍을 같은 트리에서 관리. 별도 `setInterval`로 stdout 직접 쓰는 일 금지.

**Warning signs:**
- CPU 사용률이 토큰 스트리밍 중 100% 근처
- 메시지가 100개 넘어가면 입력 반응이 느려짐
- 터미널이 "깜박" 하며 전체 화면이 일시적으로 비었다 다시 채워짐
- htop 에서 node/bun 프로세스가 busy-spin

**Phase to address:** Phase 2(메시지 리스트) — Static 분리가 초기 아키텍처 결정

---

### Pitfall 5: stdout 에 직접 write 하는 코드와 Ink 의 이중 렌더 (H)

**What goes wrong:**
`console.log` · `process.stdout.write` · child_process stdout pipe · 오래된 `chalk` 예제 등이 Ink 렌더 프레임 중간에 끼어들면 ANSI 커서 위치가 꼬이면서 화면이 반쯤 지워지거나 남아있는 프레임 위에 덧쓰임. Python REPL 의 `_Spinner` thread 가 `rich.Live` 와 경쟁하던 §1.12 버그와 **동형** 문제.

**Why it happens:**
Ink 는 내부적으로 `lastOutput` 과 커서 위치를 추적해 diff renderer 처럼 동작. 외부에서 write 가 들어오면 내부 상태와 실제 터미널 상태가 어긋남. `patchConsole: true`(기본) 는 `console.log` 만 가로채고 `process.stdout.write` 나 자식 프로세스 pipe 는 못 막음.

**How to avoke:**
- **절대 규칙:** 앱 코드 어디에서도 `process.stdout.write` / `console.log` 직접 호출 금지. 출력은 오직 Zustand store → React 컴포넌트 경로.
- Lint 규칙 추가: `no-restricted-syntax` 로 `process.stdout.write`, `console.log/error/warn` 를 `src/**` 에서 금지(단, `index.tsx` 의 크래시 핸들러만 예외). ESLint config 의 첫 번째 방어선.
- child_process 실행은 `tools/*` 결과를 WS 로 받아 store 에 넣는 서버 경로만 사용. 클라이언트에서 `spawn` 금지. 만약 향후 클라 쪽 shell 이 필요하면 `execa` + `stdio: ['pipe', 'pipe', 'pipe']` 로 문자열로 캡처 후 store 에 넣기.
- `ink` 의 `useStdout().write` 도 원칙적으로 안 씀. 쓰려면 반드시 Ink render 가 잠시 멈췄다는 guarantee 필요.
- WS 에러 로깅도 `appendMessage({role:'system', ...})` 로. 현재 `ws.ts` 는 이 규칙 지킴 — 유지.

**Warning signs:**
- 터미널에 반만 그려진 프레임 / "이상한 위치" 에 나타나는 메시지
- `grep -rn 'process.stdout.write\|console.log' src/` 가 non-trivial 결과
- child process 가 tool 결과를 반환하는 동안 UI 가 망가짐
- 입력 프롬프트가 이상한 줄에 나타남

**Phase to address:** Phase 1(스켈레톤) — lint 규칙이 첫 번째 PR

---

### Pitfall 6: `<Static>` 오용으로 과거 메시지 사라짐 / 영원히 사라지지 않음 (M)

**What goes wrong:**
두 가지 정반대 실수가 공존:
1. 모든 메시지를 `<Static>` 에 넣으면 **수정·삭제 불가**. 사용자가 `/undo` 하면 마지막 메시지를 지워야 하는데 Static 은 items 을 줄이면 이전 렌더를 지우지 않음 → 화면에는 남고 데이터는 없는 상태.
2. `<Static>` 의 `items` 에 "아직 스트리밍 중인 메시지" 를 넣으면 첫 렌더 이후 토큰이 반영 안 됨. 사용자는 "답변이 한 글자만 나오다 멈춤" 으로 인식.

**Why it happens:**
`<Static>` 은 "items 에 새로 추가된 것만" 렌더하고 기존 렌더는 건드리지 않음. "완결된 메시지" 에만 쓰라는 계약을 지켜야 함.

**How to avoid:**
- 규칙: **스트리밍 중 = 일반 트리 / 스트리밍 완료 = Static 으로 이동**. `agent_end` 메시지가 올 때 store 가 `activeMessage` 를 `messages` 로 flush.
- `/undo` 등 히스토리 수정 이 필요하면 그 시점에 `<Static>` 을 잠시 쓰지 않고 전체 리렌더로 전환(`key` 강제 변경으로 remount). 이후 다시 Static 모드로 복귀.
- `items` prop 에 넘기는 배열은 append-only 가 되도록 store 단에서 보장. `clearMessages` 는 Static 영역도 `key` 변경으로 remount.

**Warning signs:**
- 스트리밍 중 출력이 업데이트 안 됨
- `/clear` / `/undo` 후 화면에 과거 메시지가 남아있음
- 히스토리 수정 후 다음 메시지가 엉뚱한 위치에 그려짐

**Phase to address:** Phase 2(메시지 리스트), Phase 3(슬래시 `/undo` · `/clear`)

---

### Pitfall 7: Bracketed paste 미처리로 붙여넣기마다 submit (H)

**What goes wrong:**
사용자가 여러 줄 프롬프트를 붙여넣을 때, bracketed paste 마커(`ESC[200~...ESC[201~`)가 처리 안 되면 각 문자가 개별 키스트로크로 들어오면서 줄바꿈 문자가 `Enter submit` 으로 해석됨. 붙여넣기 첫 줄이 즉시 전송되고 나머지는 프롬프트에 망가진 상태로 남음. Claude Code 에서도 여러 번 이슈(#47773, #50012, #13183) — 큰 붙여넣기는 tail 만 살아남거나 CLI 가 hang.

**Why it happens:**
- Ink 의 `useInput` 은 "pasted 여러 문자" 를 한 번에 문자열로 전달(설계상 OK). 그러나 `ink-text-input` 같은 하위 컴포넌트는 단일 키로 처리하며 내부 `onSubmit` 을 Enter 문자에서 트리거.
- 터미널이 bracketed paste 모드를 지원해도 Ink/하위 컴포넌트가 escape marker 를 걸러내지 않으면 `[200~` 이 입력에 리터럴로 찍힘.
- Windows Terminal + PowerShell 에서 bracketed paste 가 engage 안 되는 케이스(claude-code #50012).
- 접근성/음성-텍스트 도구는 아주 빠른 synthetic keystroke 를 보냄 → 같은 증상.

**How to avoid:**
- Ink 공식 `usePaste` hook(Ink 5+) 이 있다면 사용. 없으면 `stdin` 레벨에서 `\x1b[200~` / `\x1b[201~` 마커 기반 버퍼링 직접 구현 후 `useInput` 와 별도 이벤트 채널로 상태에 반영.
- `ink-text-input` 의 `onSubmit` 은 **오직 "paste 가 아닌" Enter 에서만** 호출되어야 함. 내부를 믿지 말고 custom input 컴포넌트 작성 고려.
- 멀티라인 입력은 처음부터 Enter=submit / Shift+Enter=개행 설계(PROJECT.md Active 항목). 붙여넣기 줄바꿈은 무조건 "개행" 으로 처리, submit 트리거 금지.
- paste 버퍼 크기 상한(e.g. 10MB)과 truncation 마커 UI. 초대형 paste 를 조용히 삼키지 않기.
- Ink 를 띄우기 직전 `\x1b[?2004h` (bracketed paste enable) 명시적 전송 후 exit 시 `\x1b[?2004l` 복원.

**Warning signs:**
- 여러 줄 paste 첫 줄만 전송되고 나머지는 프롬프트에 남음
- 입력에 `[200~` / `~[201` 같은 찌꺼기 문자열
- 붙여넣기 여러 번 시도 후 프로세스가 hang
- 음성 받아쓰기 도구로 긴 문장 입력 시 앞부분 손실

**Phase to address:** Phase 3(입력 · 멀티라인) — 초기 멀티라인 구현과 동시에 해결

---

### Pitfall 8: Zustand selector 가 전체 객체를 구독해 모든 자식 리렌더 (M)

**What goes wrong:**
`const {messages, input, busy} = useStore()` 처럼 객체 분해 또는 selector 생략 시 store 의 **어떤 필드라도** 변경되면 컴포넌트 전체 리렌더. 입력 타이핑(`setInput`) 만 해도 messages 리스트가 리렌더 → Pitfall 4 악화.

**Why it happens:**
Zustand 의 기본 equality 는 `Object.is`. selector 없이 쓰면 state 객체 자체가 매 변경마다 새 참조 → 구독자가 무조건 리렌더.

**How to avoid:**
- **규칙:** `useStore` 는 항상 단일 값 selector 로만 사용. `useStore(s => s.messages)`, `useStore(s => s.input)` 각각 별도 hook 호출. 현재 `App.tsx` 는 이 규칙 지킴(좋음). 문서화 필요.
- 여러 필드를 동시에 쓰면 `useShallow`: `const {busy, status} = useStore(useShallow(s => ({busy: s.busy, status: s.status})))`.
- 리스트 컴포넌트와 입력 컴포넌트를 반드시 분리. 입력 컴포넌트는 `input` 만 구독, 리스트 컴포넌트는 `messages` 만 구독.
- WS handler 에서 `useStore.getState()` 직접 호출은 OK — 구독이 아니므로 리렌더 안 일으킴. 현재 `ws.ts` 가 이 패턴 사용(좋음).
- ESLint 커스텀 룰 또는 코드리뷰 체크리스트에 "useStore 의 selector 는 반드시 단일 스칼라 또는 useShallow" 를 명시.

**Warning signs:**
- React DevTools(Ink 지원 제한적) 또는 렌더 카운트 로깅에서 타이핑마다 메시지 리스트 리렌더
- 긴 세션에서 타이핑이 버벅임
- `console.log('render:', Date.now())` 를 컴포넌트에 넣었을 때 예상보다 많이 찍힘

**Phase to address:** Phase 2(메시지 리스트) — 초기 컴포넌트 분리 시 자연스럽게 해결

---

### Pitfall 9: WS handler 의 stale closure (M)

**What goes wrong:**
`ws.on('message', handler)` 를 `useEffect` 에서 한 번만 붙이면 handler 는 초기 렌더 시점의 props/state 를 캡처. 이후 상태가 바뀌어도 handler 는 과거 값을 봄. 예: "현재 활성 room" 이 바뀌었는데 WS 메시지는 옛 room 에 append.

**Why it happens:**
React 함수형 컴포넌트의 closure 는 렌더 시점에 동결. WS 같은 "한 번 등록하고 살아있는 리스너" 는 클로저 트랩의 대표 케이스.

**How to avoid:**
- **규칙:** WS handler 에서 상태를 읽을 때는 반드시 `useStore.getState()` 함수 호출형. React state/props 를 handler 가 직접 참조하지 않음. 현재 `ws.ts` 가 이 패턴 사용(좋음) — 유지.
- 만약 React state 참조가 필요하면 `const ref = useRef(value); ref.current = value;` + handler 내부 `ref.current` 패턴.
- WS 객체 자체는 `useState` 가 아니라 `useRef` 로 보관(현재 `setWs`/`useState` 로 되어있는데, 이는 WS 가 바뀌면 전체 App 리렌더를 유발 — `useRef` + mount effect 로 이관 고려).
- Zustand action 들(`appendMessage` 등)은 참조 안정 — 단순히 `useStore.getState().appendMessage(...)` 로 호출 가능.

**Warning signs:**
- WS 메시지가 "엉뚱한 room/상태" 에 반영됨
- `/cd` 또는 `/mode` 후에도 UI 가 옛 경로·모드로 메시지 라우팅
- 디버그 로그에서 handler 가 참조하는 값이 UI 값과 어긋남

**Phase to address:** Phase 4(WS 프로토콜) — handler 패턴을 초기에 고정

---

### Pitfall 10: WS 재연결 thundering herd (3인이 동시에 재접속) (M)

**What goes wrong:**
집 머신 서버가 잠시 다운되거나 네트워크 블립. 로컬 + 원격 2인 = 3 클라이언트가 **같은 순간에** disconnect. 각자 "즉시 재연결 → 500ms → 1s → 2s..." 동일 타이밍으로 retry → 서버 recovery 중 매 웨이브가 동시에 도달. jitter 가 없으면 서버가 뜨자마자 다시 쓰러짐.

**Why it happens:**
대부분의 "간단한" 재연결 코드는 `setTimeout(reconnect, delay * 2)` 같은 deterministic backoff. 3 클라이언트밖에 안 되지만 각 세션마다 WS 리소스 + Room snapshot 전송이 무거워 서버 부하 증폭.

**How to avoid:**
- jitter 적용 exponential backoff: `delay = base * 2^attempt * (0.5 + Math.random() * 0.5)`. base=500ms, cap=30s, max 10회.
- 연결 성공 후 1회 안정 기간(예: 30s) 후 attempt 를 0 으로 리셋.
- 재연결 시 서버에 `last_seen_event_id` 를 보내 snapshot 이 아닌 delta 만 받기(서버 프로토콜 협의).
- `state_snapshot` 수신 전까지 `disconnected — reconnecting...` UI 로 입력 비활성화. 재연결 중 타이핑된 입력 로컬 버퍼링(간단하지만 혼선 방지 큼).
- `ws.on('error')` 와 `ws.on('close')` 둘 다 핸들. 현재 `ws.ts` 는 `close` 시 status 만 바꾸고 재연결 로직 없음 — 이게 Phase 4 작업.

**Warning signs:**
- 서버 로그에 동일 밀리초에 3개 auth 요청
- 서버 restart 시 CPU 스파이크 후 바로 재크래시
- 원격 사용자 보고: "끊겼다 다시 붙으면 로그가 중복됨"

**Phase to address:** Phase 4(WS 재연결 + 상태 동기) — 프로토콜 확장 포함

---

### Pitfall 11: 재연결 구간에 메시지 유실 (M)

**What goes wrong:**
WS 가 끊긴 사이 서버가 `on_token`/`on_tool` 이벤트 발행. 클라이언트가 재접속하면 `state_snapshot` 은 "현재 스냅샷" 만 주므로 중간의 스트리밍 토큰 · tool 결과가 사라져 UI 로그가 중간 구멍이 남.

**Why it happens:**
Python 쪽 `harness_server.py` 의 `state snapshot` 은 "현재 대화 상태" 중심. 실시간 이벤트 로그 큐는 없음. 현재 ui-ink 스켈레톤도 `state_snapshot` TODO 처리.

**How to avoid:**
- 서버에 monotonic event id 도입(WS 프로토콜 확장). 클라가 `resume_from: <id>` 헤더로 마지막 수신 id 전송.
- 서버는 room 단위로 최근 N초(예: 60s) 이벤트 ring buffer 유지. 재연결 시 buffer 에 있으면 delta, 없으면 full snapshot.
- 클라이언트는 `agent_end` 이벤트가 **반드시** 올 것을 가정하지 말 것. 재연결 시 "busy 였던 turn" 이 끝났는지 확인 못하면 spinner 영구 회전.
- 그러므로 store 에 `activeTurnId` + `turnStatus` 두고 snapshot 에서 `inFlightTurnId`/`busy` 명시적으로 동기화.
- PROJECT.md Constraints 에 "WS 프로토콜 기존 이벤트 의미 변경 금지, 확장 OK" 이미 있음 — `resume_from` 추가는 이 조건 충족.

**Warning signs:**
- 재연결 후 spinner 가 영원히 돌거나, 반대로 답변이 끝났는데 busy 표시
- 재연결 후 마지막 메시지가 잘림
- `/sessions` 로 저장된 로그와 UI 가 불일치

**Phase to address:** Phase 4(WS 프로토콜) — 서버 쪽 event buffer 같이 작업

---

### Pitfall 12: bun ↔ ws 라이브러리 호환성 미세 차이 (M)

**What goes wrong:**
개발은 `bun run` 으로, 원격 사용자는 각자 bun 버전으로 실행. bun 의 built-in WebSocket 과 `ws` npm 패키지 사이에 헤더 대소문자 · ping/pong 주기 · permessage-deflate 동작이 다름. bun issue #4529 에 Node+ws 와 bun 이 "동일 코드로 다르게 동작" 사례.

**Why it happens:**
- bun 은 헤더를 lowercase 로 전송; `ws` 는 원본 casing 보존. Python 서버가 `x-harness-token` 대소문자에 민감하면 한쪽만 깨짐(현재 `harness_server.py:365` 는 `x-harness-token` lowercase 로 보고 있어 괜찮아 보이나 검증 필요).
- bun 의 `WebSocket` 전역 vs 명시적 `import WebSocket from 'ws'` 가 다른 구현체.
- 현재 `ui-ink/src/ws.ts` 는 `import WebSocket from 'ws'` — Node 패키지 명시적 사용. bun 에서도 `ws` 가 설치되면 그것을 사용(대부분).
- bun issue #9368: backpressure 시 `ws` WebSocket 메시지 반복 전송.

**How to avoid:**
- `ws` npm 패키지를 **명시적으로** 사용 (현재 스켈레톤 그대로) — bun native 대신. 여러 사용자 bun 버전 드리프트 방어.
- bun 버전 pin: `package.json` 에 `"engines": {"bun": ">=1.1.x"}` + lock file 커밋.
- 테스트: bun / node 양쪽에서 `bun test` / `node --experimental-vm-modules` 둘 다 green 인지 CI 에서 확인.
- 헤더 서버측에서 case-insensitive 읽기(현재 `ws.request.headers.get(...)` 는 `websockets` 라이브러리가 case-insensitive 처리 — OK).
- permessage-deflate 옵션은 명시적으로 off(기본값 유지) 로 시작. 필요하면 나중에 enable.

**Warning signs:**
- 로컬 개발 잘 되다가 원격 사용자만 연결 실패 / 간헐적 hang
- `WebSocket 1006` close 코드 빈발(abnormal close)
- 토큰 인증이 한쪽 bun 버전에서만 실패

**Phase to address:** Phase 4(WS) + Phase 7(외부 배포 검증)

---

### Pitfall 13: child_process spawn 이 Ink 렌더를 박살냄 (H if needed, but likely N/A)

**What goes wrong:**
클라이언트에서 tool 을 직접 실행하지 않는다면 문제 없음. 그러나 만약 "클라이언트 shortcut" 으로 `spawn('git', ['diff'])` 같은 걸 붙이면, 자식 프로세스 stdout 이 Ink 가 그리는 같은 TTY 로 간섭하며 프레임 전체가 붕괴. bun issue #27766: Ink + concurrent spawn 이 5-10% 확률로 100% CPU hang.

**Why it happens:**
- `stdio: 'inherit'` 는 자식이 parent TTY 에 직접 쓰게 함 → Ink 가 그 쓰기를 모름
- `stdio: 'pipe'` 로 받아도 데이터를 실시간 `stdout.write` 로 쏘면 똑같이 interleave
- bun 의 최근 버그는 spawn 자체가 100% CPU 에서 hang 하는 경우도 있음

**How to avoid:**
- **원칙:** 모든 tool 실행은 서버(`harness_server.py`)에서만. 클라이언트는 WS 로 결과 문자열만 받음. 현재 아키텍처가 이 원칙을 강제함.
- 피할 수 없이 클라 쪽 spawn 이 필요(예: 로컬 파일 에디터 오픈)하면 `stdio: ['ignore', 'pipe', 'pipe']` + 결과를 store 에 넣어 React 트리로 렌더. 절대 `inherit` 금지.
- 편집기 열기같이 "fullscreen 진입" 이 필요하면 Ink 를 `ink-useSuspend` 패턴으로 잠시 unmount → 자식 종료 후 remount. 현재 Ink 버전에 공식 지원 확인 필요.
- bun 버전 최신(1.1.x+)으로 pin → issue #27766 mitigation.

**Warning signs:**
- git diff / less 같은 명령을 띄우는 순간 UI 가 엉킴
- bun run 이 100% CPU 에서 멎음
- 원격 사용자만 특정 명령에서 UI 깨짐(로컬과 환경 차이)

**Phase to address:** Phase 4-5(tool 결과) — 클라 spawn 금지 원칙 문서화

---

### Pitfall 14: React key 충돌로 메시지 순서 뒤섞임 (M)

**What goes wrong:**
현재 `App.tsx` 는 `messages.map((m, i) => <Box key={i} ...>)` — **인덱스 key**. 메시지가 append-only 면 OK지만, `/undo` 후 뒤에 새 메시지가 들어오면 같은 index 에 다른 내용 → React 가 동일 컴포넌트로 보고 상태/DOM 재사용 → 잘못된 메시지 렌더. 스트리밍 중 temporary id(`temp-123`) 가 server id(`msg-456`)로 교체되는 구간에서도 key 가 바뀌면 컴포넌트 destroy/recreate → 스피너·애니메이션 리셋.

**Why it happens:**
React 의 key 는 reconciliation 의 1급 식별자. index key 는 순서 불변 리스트에만 안전. tuple id swap 은 컴포넌트 ID 변화 ⇒ 의도하지 않은 re-mount.

**How to avoid:**
- 메시지에 클라이언트 생성 UUID(`crypto.randomUUID()`) 를 store append 시점에 부여. 서버가 나중에 server id 를 알려줘도 클라 UUID 는 유지.
- Message 타입에 `id: string` 필드 추가. store.appendMessage 가 자동 부여.
- `messages.map(m => <Box key={m.id} ...>)`.
- 서버 id 가 필요한 경우 `meta.serverId` 로 보관. key 는 건드리지 않음.

**Warning signs:**
- `/undo` 후 새 메시지가 옛 메시지 자리에 렌더
- 스트리밍 토큰이 중간에 "점프" 하며 순서 뒤바뀜
- React dev warning "Each child in a list should have a unique key prop"

**Phase to address:** Phase 2(메시지 리스트) — store 스키마 초기 설계

---

### Pitfall 15: Ink 에서 TypeScript strict + JSX inference 함정 (M)

**What goes wrong:**
Ink 의 `<Text>`/`<Box>` props 는 React DOM props 와 다름. TypeScript strict 모드에서 `<div>` 같은 DOM 태그를 실수로 쓰거나 `style={{color: 'red'}}` 같은 브라우저 스타일을 쓰면 컴파일 에러. 반대로 `@types/react` 가 DOM 타입을 끌어와 "아무 태그나 허용" 되는 느슨한 설정이면 런타임 에 Ink 가 해당 태그를 못 그림 → 조용히 빈 출력.

**Why it happens:**
Ink 는 `<div>` 를 지원하지 않음. React 의 JSX pragma 가 브라우저 기본값으로 남아있으면 타입은 통과하나 렌더는 실패.

**How to avoid:**
- `tsconfig.json` 에 `"jsx": "react-jsx"` + `"jsxImportSource": "react"` + `strict: true`. `allowJs: false`.
- 추가: `"types": ["node", "bun-types"]` 만 허용. DOM lib 제거: `"lib": ["ES2022"]` (no `"DOM"`).
- ESLint: Ink 전용 플러그인 없다면 최소한 `no-restricted-syntax` 로 `<div>`, `<span>`, `<button>` JSX element 금지.
- 컴포넌트는 `React.FC` 대신 함수 시그니처 직접 써서 children 타입 명시(현재 App.tsx 는 `React.FC` — Ink 에서는 무방하나 children 없으면 제거 권장).

**Warning signs:**
- "분명 렌더했는데 화면에 안 나옴" 증상
- TypeScript 는 통과하는데 런타임 경고
- `<Box><div>...</div></Box>` 같은 혼종 코드가 생김

**Phase to address:** Phase 1(스켈레톤) — tsconfig + eslint 가 첫 PR

---

### Pitfall 16: Python REPL 사용자 기대 괴리 (H — UX 신뢰 이슈)

**What goes wrong:**
기존 Python REPL 사용자(로컬 사용자 1인 + 원격 2인)는 Python 환경의 미시적 동작에 적응됨:
- prompt_toolkit 의 `Ctrl+R` history search
- `Tab` slash 자동완성의 특정 매칭 알고리즘
- `/save` 로 저장된 세션 포맷
- prompt history(상/하 화살표) persistence 파일 위치
- 한국어 입력 조합(macOS IME)의 완성 시점
- `prompt_toolkit` 의 paste detection 동작

이 중 어느 하나가 "눈에 띄게 다르면" 사용자는 "새 UI 는 기능이 빠졌다" 고 인식. Python 세션 메모리(MEMORY.md)에 이미 "존댓말 강제" 같은 세밀한 교정 기록이 있음 — 사용자가 세부 UX 에 민감함.

**Why it happens:**
Ink + ink-text-input 의 기본 키 바인딩은 Unix readline 표준에 더 가깝고 prompt_toolkit 과 미묘하게 다름. 또한 Ink 의 멀티라인 입력은 표준 컴포넌트가 없어서 직접 구현해야 함.

**How to avoid:**
- **마이그레이션 호환 체크리스트** 를 roadmap Phase 초반에 작성:
  - Ctrl+R history search 등가 기능 구현
  - slash 완성 매칭 규칙 문서화 + 기존과 동일/차이 명시
  - 상/하 화살표 history: `~/.harness/history.txt` 같은 파일에 persist (prompt_toolkit 과 같은 포맷으로 읽고 쓰기)
  - `/save` JSON 포맷 그대로 유지 — 서버 쪽이라 OK
  - macOS IME 한국어 입력 테스트 필수 (prompt_toolkit 은 composition 완료까지 submit 지연시켰음, Ink 동작 검증 필요)
- PROJECT.md 의 "legacy 전부 삭제" 원칙과 충돌하는 부분: **history 파일은 유지**. legacy 코드 삭제 ≠ 사용자 데이터 삭제.
- 릴리스 노트에 "이전과 달라진 점" 섹션 필수.
- 원격 사용자 2인에게 beta 기간 제공, 불만 수집.

**Warning signs:**
- 사용자 보고: "키가 안 먹혀요" / "Tab 이 이상해요"
- "한국어 입력하면 미완성 글자가 전송돼요"
- 세션 history 가 "비어있어요"

**Phase to address:** Phase 3(입력 · 슬래시), Phase 7(beta + 마이그레이션)

---

### Pitfall 17: 느린 SSH / 원격 네트워크에서 render lag 방치 (M)

**What goes wrong:**
집 머신 = 서버, 원격 사용자 2인이 **각자 장비에서 ui-ink 를 로컬 실행** (백엔드 WS 만 집 머신). 그래도 RTT 100-300ms 가 나올 수 있음. 토큰 스트리밍이 네트워크 RTT 에 병목되면서 "한 번에 큰 청크 → 빈 구간 → 큰 청크" 패턴 → UI 가 뚝뚝 끊기는 인상. 또한 SSH 를 통해 ui-ink 를 원격에서 돌리는 시나리오가 있다면(문서화 필요) ANSI escape 전송량 자체가 네트워크에 부담 — Ink 의 전체 redraw 특성과 충돌.

**Why it happens:**
Ink 의 full-redraw 가 매 프레임 수 KB 의 ANSI. RTT 100ms 네트워크에서 60Hz 프레임은 bandwidth 충분하지만 느린 SSH 에서는 queueing delay 발생.

**How to avoid:**
- 토큰 스트리밍 client-side 버퍼링: 16ms (60Hz) 프레임당 flush. store 에 `scheduleTokenFlush` 패턴.
- ui-ink 를 SSH 원격 실행하는 use case 를 공식적으로 "비권장" 으로 못박고 각 장비에서 로컬 실행 + WS 연결이 표준임을 CLIENT_SETUP.md 에 명시(PROJECT.md 에 이미 암시).
- Ink 3 의 "incremental rendering" 옵션이 있다면 opt-in (최신 버전 확인 필요 — 2026-04 기준 merge 여부 MEDIUM confidence).
- Yoga layout 을 적게 트리거하는 구조: `<Static>` 완료 메시지 + 하나의 활성 토큰 컴포넌트.
- 전역 `HARNESS_SLOW_TERMINAL=1` 환경변수로 throttle 더 보수적으로(100ms) 전환하는 escape hatch.

**Warning signs:**
- 원격 사용자 보고: "답변이 뚝뚝 끊겨요"
- ssh 세션에서 문자 에코 lag > 200ms
- 네트워크 툴로 보니 매 토큰마다 수 KB 전송

**Phase to address:** Phase 2(렌더 아키텍처), Phase 7(배포 검증)

---

### Pitfall 18: 외부 사용자의 `bun install` 실패 (native dep · 버전 skew) (M)

**What goes wrong:**
외부 2인이 `git clone + bun install` 을 실행. bun 버전이 다르거나(1.0 vs 1.1), `ws` 의 옵션 모듈 `bufferutil`/`utf-8-validate` 의 네이티브 빌드 실패, Python/node-gyp 부재로 설치 중단.

**Why it happens:**
`ws` 는 performance optional native deps 가짐. macOS 업데이트 후 xcode 미설치 → 빌드 실패. 외부 사용자 환경 일관성 없음.

**How to avoid:**
- `ws` 를 `--optional=false` 없이 설치하되 `package.json` 에 `optionalDependencies: {}` 로 명시(기본값이지만 명시적 문서화).
- 또는 WebSocket 클라이언트를 `ws` 대신 **bun 내장 `WebSocket` 전역** 사용 → native dep 없음. 단 Pitfall 12 주의사항과 trade-off.
- `bun install --frozen-lockfile` 을 클라이언트 setup 문서의 표준 명령으로.
- `engines.bun` pin + mismatch 시 친절한 에러 메시지(`package.json` preinstall script).
- SERVER_SETUP.md(없음, 6.5 지적) 에 대응하는 `CLIENT_SETUP.md` 업데이트 — 특히 설치 troubleshooting 섹션.

**Warning signs:**
- 원격 사용자 setup 첫날 "bun install 안 돼요"
- `node-gyp` 빌드 에러 메시지
- 성공해도 런타임에 "Cannot find module bufferutil" 경고

**Phase to address:** Phase 7(배포 · 외부 검증)

---

### Pitfall 19: TTY 가 없는 환경에서 Ink 실행 (H)

**What goes wrong:**
`harness --print "질문"` (one-shot 모드) 또는 pipe (`echo 'q' | harness`) 에서 stdin 이 TTY 가 아니므로 `setRawMode` 가 undefined/throw → Ink 가 시작도 못 하고 죽음. 또는 하위 에이전트(agentic 시스템에서 harness 를 자식 프로세스로 spawn)의 경우도 마찬가지. Claude Code #5925, #35734, #11898 전부 같은 원인.

**Why it happens:**
Ink 는 interactive TTY 를 전제. `isRawModeSupported` 체크 없이 곧장 enable 시 non-TTY 에서 crash.

**How to avoid:**
- `index.tsx` 최상단 entry guard:
  ```ts
  if (!process.stdin.isTTY || typeof process.stdin.setRawMode !== 'function') {
    // one-shot 모드로 분기 — Ink 대신 plain stdout 으로 결과만 출력
    runOneShot(); // argv 에서 프롬프트 읽어 WS 로 보내고 토큰을 stdout 에 쓰고 종료
    process.exit(0);
  }
  ```
- PROJECT.md Active 의 `harness "질문"` / `--resume` 모드가 이 분기와 정확히 일치.
- CI/자동화 사용자를 위해 `--no-interactive` 플래그도 명시적 제공.

**Warning signs:**
- pipe 입력 시 "Raw mode is not supported" 빨간 에러
- CI 에서 harness 호출이 무조건 fail
- 하위 에이전트가 harness spawn 하면 parent 전체가 죽음

**Phase to address:** Phase 1(스켈레톤), Phase 6(one-shot 모드)

---

### Pitfall 20: "Spinner 가 scroll back 에 매 프레임 찍힘" 의 Ink 재림 (M)

**What goes wrong:**
Python REPL 에서 `Rich.Live(transient=False)` + 내부 spinner 가 터미널 scrollback 을 spinner frame 으로 오염시키던 버그(commits `c45e29f`, `c27111a`). Ink 에서는 "Static 이 아닌 일반 영역" 이 업데이트될 때마다 위로 올라가 지우고 새로 그리므로 scrollback 에는 최종 형태 한 번만 들어가는 게 정상. 하지만 spinner 영역을 `<Static>` 에 실수로 넣거나, spinner text 가 매 프레임마다 `appendMessage` 되면 scrollback 에 스피너 프레임이 수백 줄 쌓임.

**Why it happens:**
`<Static>` 은 append-only — 들어간 items 는 scrollback 에 영구 기록. spinner 는 절대 Static 에 넣으면 안 됨.

**How to avoid:**
- **규칙:** spinner · status bar · 활성 입력 프롬프트 · 진행 중 메시지 = 항상 일반 트리. `<Static>` = 완결된 메시지만.
- `useStore.subscribe(s => s.activeTokens)` 로 토큰 append 시 `appendMessage` 호출하지 않음. active slot 만 갱신.
- scrollback 테스트: 스트리밍 1분 후 `Cmd+↑` 로 스크롤해서 spinner frame 이 없는지 수동 확인.

**Warning signs:**
- 터미널 scrollback 에 `⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏` 패턴이 줄줄이
- 세션 종료 후 scroll up 해서 보면 "⠋" 만 한 줄에 하나씩 수백 줄
- 메시지 사이에 빈 spinner 흔적

**Phase to address:** Phase 2(렌더) — `<Static>` 계약 문서화

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| 모든 메시지를 일반 트리에 렌더 (`<Static>` 미사용) | 구현 간단, `/undo` 쉬움 | 긴 세션에서 CPU/flicker 폭증 (Pitfall 4) | 데모 단계 (메시지 <50개) 만. Phase 2 내에 Static 분리 필수 |
| WS 재연결 없이 수동 재시작 | 첫 구현 1시간 절약 | 사용자 신뢰 손실 (네트워크 블립 = 앱 죽음) | 내부 개발 1~2주만. Phase 4 내에 구현 |
| 인덱스 key 사용 (`key={i}`) | 코드 2글자 | `/undo` 이후 렌더 오염 (Pitfall 14) | 절대 불가 (현재 스켈레톤에 있으므로 Phase 2 첫 작업) |
| bun 내장 WebSocket 대신 `ws` 패키지 | 표준 API, Node 호환 | native dep 설치 이슈 (Pitfall 18) | 당분간 유지. 배포 안정화 후 bun native 로 교체 검토 |
| `React.FC` 사용 + children implicit | 타이핑 편함 | Ink 에서 children 오남용 유도 | 컴포넌트가 간단할 때만. 복잡해지면 함수 시그니처 명시 |
| 한 개의 거대한 `<App>` 컴포넌트 | 프로토타입 빠름 | selector re-render 폭증 (Pitfall 8) | Phase 1 스켈레톤만. Phase 2 초반에 분해 |
| 로깅을 `console.log` 로 | 즉시 디버깅 | Ink 렌더 간섭 (Pitfall 5) | **never acceptable** — 디버그는 파일 로그로 |
| ink-text-input 그대로 사용 | 멀티라인 직접 안 만들어도 됨 | 멀티라인 · bracketed paste · IME 전부 커스텀 필요 | Phase 1 만. Phase 3 에서 custom input 필수 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| harness_server.py WS | 기존 이벤트 의미 변경 (breaking) | 필드 **추가만** 허용. `resume_from` · `event_id` 등 신규 필드로 확장. PROJECT.md Constraints 준수 |
| Python 서버 ↔ TS 클라 JSON | snake_case vs camelCase 혼용 | 서버는 snake_case 유지(기존). 클라 타입에서 받는 쪽만 변환 헬퍼 도입 또는 snake_case 그대로 사용 |
| `HARNESS_TOKEN` env var | 파일에 저장, 쉘 history 노출 | Pitfall 외 §2.4 참조 — macOS keychain 또는 chmod 600 file |
| Room snapshot 수신 | snapshot 받고 바로 messages 에 덮어쓰기 | snapshot 전에 로컬 보낸 "optimistic" 메시지와 merge 로직 필요. server event id 기준 dedupe |
| Ollama 재연결 알림 | 클라가 모름 | 서버의 `[Ollama 재연결 N/3]` 토큰(기존 1.21 fix) 을 그대로 렌더 — 특별한 UI 없이 일반 토큰으로 |
| confirm_write / confirm_bash | timeout 없음 → UI 멈춤 | 클라 쪽 타임아웃(예: 60초) 후 자동 deny + 서버에 응답. 기존 Python 측 sticky-deny 패턴 계승 |
| Ink dev tools | React DevTools 못 씀 | `ink-devtools`(별도 패키지) 또는 로깅 기반 디버깅. 렌더 카운트 훅 자체 구현 |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 전체 messages 배열 매 토큰 리렌더 | 토큰 스트리밍 중 CPU 100%, flicker | Static + active slot 분리 (Pitfall 4) | 메시지 50개 넘으면 체감, 200개에서 고통 |
| Yoga layout 전체 재계산 | resize 또는 메시지 추가마다 렌더 지연 | 중첩 Box 최소화, 긴 텍스트는 wrap="wrap" + 명시적 너비 | 터미널 폭 200+ / 메시지 100+ 동시 |
| Zustand 전역 객체 selector | 입력 타이핑마다 리스트 리렌더 | 단일 값 selector + useShallow (Pitfall 8) | 컴포넌트 10개 + 상태 7개 넘어가면 |
| 토큰을 각 문자마다 store dispatch | 30+ tok/s 에서 렌더 못 따라감 | 16ms 버퍼링 후 flush | 빠른 네트워크 · 빠른 모델에서 즉시 |
| `<Static>` 에 매 프레임 push | scrollback 오염 + append 비용 | `<Static>` 에는 완결된 메시지만 (Pitfall 20) | 세션 5분 넘어가면 |
| WS 메시지 파싱을 메인 스레드에서 | 큰 tool 결과(50KB+) 수신 시 freeze | 대용량 결과는 streaming · 청크 단위 렌더 | tool 결과가 `MAX_TOOL_RESULT_CHARS=20000` 근처 |
| child_process stdio='inherit' | Ink 화면 붕괴 | 클라에서 spawn 금지 (Pitfall 13) | 한 번이라도 발생 |

## Security Mistakes

harness 는 로컬/사내 분위기지만 외부 원격 2인 접속 → 보안 잔류 이슈 존재.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `HARNESS_TOKEN` 을 Zustand store 에 넣고 디버그 로그로 찍기 | 세션 파일 · 터미널 scrollback 으로 누출 | 토큰은 `process.env` 에서만 읽고 store 진입 금지. 로깅 시 항상 `[REDACTED]` |
| WS URL 이 `ws://` 인데 사용자가 외부 망에서 접속 | 평문 전송 | `wss://` 강제 또는 localhost/VPN 전용임을 CLIENT_SETUP 에 큰 글씨로 명시. URL 파싱 후 `wss:` 아니고 `127.0.0.1` 도 아니면 경고 배너 |
| tool 결과를 Ink 로 렌더하며 ANSI escape 그대로 출력 | 악의적 파일 내용이 터미널 escape 로 cursor 제어 (terminal injection) | tool 결과 문자열을 렌더 전 sanitize (ANSI 제거 또는 visible escape 로 변환). `strip-ansi` 같은 라이브러리 사용 |
| confirm 다이얼로그에서 `path` 만 보여주고 내용 미표시 | 사용자가 내용을 모르고 y → 악의적 내용 기록됨 | diff/프리뷰 필수. Python §5.3 이미 개선됨 — Ink 에서도 동급으로 |
| 원격 사용자의 room 격리 우회 | BB-2 로 해결됐지만 클라 측 실수로 다른 room id 로 연결 | `HARNESS_ROOM` 미지정 시 서버가 solo room 자동 생성(현재 동작) 유지. 클라 에서 room 이름 생성 시 사용자에게 확인 |
| `useInput` 에서 키 로깅 | 패스워드 같은 민감 입력이 세션 로그 / 디버그로 | 로깅은 오직 `on_token`/`appendMessage` 경로 — raw 키 스트림 로깅 금지 |
| WS 메시지 `meta.result` 에 파일 내용 통째로 store 에 담기 | 세션 덤프 시 민감 데이터 포함 | tool 결과는 서버측에서 이미 저장 — 클라 store 에는 디스플레이용 미리보기만 (e.g. 첫 2KB) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| spinner 가 "AI 가 작업 중" 외에 상태 정보 없음 | 10초 이상 기다릴 때 뭐가 되고 있는지 모름 | status bar 에 "tool: read_file foo.py" 같은 현재 진행 표시. Claude Code 스타일 |
| confirm_write 다이얼로그가 전체 파일 내용을 한 번에 표시 | 큰 파일에서 화면 범람 | diff 만 보여주고 전체는 `?` 키로 pager (Python §5.3 계승) |
| `/clear` 실행 시 scrollback 까지 날아감 | 사용자가 복사하려던 과거 출력 손실 | `/clear` 는 store messages 만 비움. 터미널 scrollback 은 유지 (Ink 의 non-alternate-screen 특성이 자연히 보존) |
| 원격 사용자 turn 진행 중 본인 입력 가능 | 혼란 · 서버에서 queue 되어 시차 | BB-2 의 turn-taking 을 UI 레벨에서도 명시. 입력 박스에 "⌛ [user2] 작업 중" 오버레이 + 입력 막기 |
| 세션 복원(`--resume`) 시 긴 로딩 블록 | 커다란 세션 load 중 블랙스크린 | 점진 로드 + `<Static>` 에 쌓기. "로딩 중..." 플레이스홀더 |
| 한국어 메시지의 wrap 이 글자 중간에서 끊김 | 가독성 저하 | Ink `wrap="wrap"` 동작 검증 + 필요시 wcwidth 패키지로 정확한 폭 계산 |
| Ctrl+C 가 turn 취소가 아니라 앱 종료 | 긴 tool 실행 중 중간에 못 멈춤 | Ctrl+C 첫 번째 = turn abort, 두 번째(2초 내) = 앱 종료. Claude Code 패턴 |
| 에러 메시지를 시스템 메시지로 평문 출력 | 에러인지 정보인지 구분 어려움 | role='system' + `color='red'` + 아이콘/접두사 |

## "Looks Done But Isn't" Checklist

Ink 데모로 넘기기 쉬우나 실제로 동작 검증이 빠지는 체크리스트.

- [ ] **Resize**: 터미널 폭을 200 → 40 → 200 반복해도 stale line 없음. 긴 한국어 · emoji 메시지 포함해서 검증 (Pitfall 2)
- [ ] **Raw mode 복구**: `kill -9 <pid>` 로 강제 종료 후 터미널이 정상 (에코 / line editing 동작) (Pitfall 3)
- [ ] **Alternate screen**: 세션 종료 후 `Cmd+↑`/`Shift+PgUp` 으로 세션 로그 scrollback 접근 가능 (Pitfall 1)
- [ ] **큰 paste**: 500줄 텍스트 붙여넣기 → 첫 줄에서 submit 안 됨, 줄바꿈 유지, 전체 보존 (Pitfall 7)
- [ ] **IME**: macOS 한국어 입력기로 "안녕하세요" 조합 중 submit 안 됨, 완성 후만 submit (Pitfall 16)
- [ ] **스트리밍 500 토큰 연속**: flicker 없음, CPU 50% 미만, scrollback 에 spinner 찌꺼기 없음 (Pitfall 4, 20)
- [ ] **WS 재연결**: 서버를 kill → restart 했을 때 클라 자동 재연결 + 중간 이벤트 복구 (Pitfall 10, 11)
- [ ] **3 사용자 동시 재연결**: 로컬 + 원격 2인이 같은 서버 restart 겪고 전부 자연스럽게 복구 (Pitfall 10)
- [ ] **non-TTY**: `echo 'test' | harness` 가 crash 대신 one-shot 으로 동작 (Pitfall 19)
- [ ] **`/undo` 후 새 메시지**: 옛 메시지 자리에 덮어쓰기 없음, 순서 정확 (Pitfall 14)
- [ ] **child_process 흔적 없음**: `grep -rn 'spawn\|exec' ui-ink/src/` 가 빈 결과 (Pitfall 13)
- [ ] **`process.stdout.write` / `console.log` 흔적 없음**: lint 에서 차단 (Pitfall 5)
- [ ] **세션 200 메시지**: 입력 타이핑 lag 없음, messages 리스트가 매 타이핑마다 리렌더 안 함 (Pitfall 8)
- [ ] **토큰 인증 실패 시**: 친절한 에러 + 프로세스 정상 종료 (Pitfall 3 크래시 방지)
- [ ] **원격 사용자 setup**: fresh 환경에서 `git clone + bun install + bun start` 10분 이내 (Pitfall 18)
- [ ] **한국어 wrap**: 폭 40에서 한국어 메시지 wrap 시 글자 깨짐 없음
- [ ] **Ctrl+C 2단계**: 첫 번째 = turn 취소, 두 번째 = exit (UX Pitfall)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Raw mode 남은 터미널 | LOW | `stty sane` 또는 `reset` 엔터. 문서에 명시 |
| Alternate screen 잘못 들어감 | MEDIUM | `printf '\033[?1049l'` 로 primary 복귀. 근본 수정은 렌더 옵션 audit |
| Static 에 과도한 push 로 scrollback 오염 | MEDIUM | 세션 재시작 불가피(기존 scrollback 제거). store 로직 수정 후 `<Static>` items 을 완결 메시지로 한정 |
| WS 재연결 무한 루프 | LOW | jitter + max attempts 추가. 설정 중 클라 수동 kill 가능 |
| 메시지 순서 섞임(index key) | LOW | store 에 uuid 필드 추가, 기존 저장 세션은 로드 시 uuid 부여 |
| 메시지 50+개 이후 flicker | HIGH | `<Static>` 분리 설계 재검토. 단순 props 변경으로 해결 안 되고 컴포넌트 구조 재편 필요 |
| native dep 설치 실패로 클라 안 돎 | LOW-MEDIUM | `bun install --verbose` 로그로 원인 파악. fallback: `ws` 를 bun native WebSocket 으로 swap |
| Python 유저가 history 파일 이전 | MEDIUM | 일회성 마이그레이션 스크립트 (`~/.harness/history.txt` → `~/.harness/history-ink.txt` 포맷 변환) |
| TypeScript strict 에러로 빌드 안 됨 | LOW | 점진적 strict(`strict: false` 로 시작) 대신 처음부터 strict + 작은 코드베이스에서 정면 해결 |

## Pitfall-to-Phase Mapping

주관: 아래 로드맵은 PROJECT.md 의 Active 항목을 Phase 로 그룹핑한 **예시 매핑**. 실제 roadmap 생성 시 참조.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Alternate screen | Phase 1 (스켈레톤) | `grep '\\x1b\\[?1049\\|?1000' src/` 빈 결과 + scrollback 수동 확인 |
| 2. Resize stale line | Phase 2 (메시지 렌더) | resize 회귀 테스트 (vitest + ink-testing-library) |
| 3. Raw mode 복원 | Phase 1 | `kill -9` 후 터미널 상태 수동 + CI 에 non-TTY 테스트 |
| 4. 스트리밍 플리커 | Phase 2 | 500 토큰 연속 벤치 (CPU · flicker 육안 + 스냅샷) |
| 5. stdout direct write | Phase 1 | ESLint 규칙 CI 강제 |
| 6. Static 오용 | Phase 2 | `/undo` / `/clear` 후 화면 스냅샷 테스트 |
| 7. Bracketed paste | Phase 3 (입력 · 멀티라인) | 500줄 paste 수동 테스트 + unit 테스트 |
| 8. Zustand selector | Phase 2 | 렌더 카운트 훅 + 100 메시지 타이핑 벤치 |
| 9. Stale closure | Phase 4 (WS) | code review 체크리스트 + 통합 테스트 (room switch 시나리오) |
| 10. Reconnect thundering | Phase 4 | 3 클라 동시 재접속 시뮬레이션 |
| 11. 재연결 구간 유실 | Phase 4 | `resume_from` 프로토콜 설계 + 통합 테스트 |
| 12. bun ↔ ws 호환성 | Phase 4 + Phase 7 | CI 에서 bun/node 양쪽 matrix |
| 13. child_process Ink 충돌 | Phase 4-5 (tool) | `grep spawn` 금지 lint + 렌더 테스트 |
| 14. React key 충돌 | Phase 2 | `/undo` 스냅샷 테스트 + React warning 0 |
| 15. TS strict + Ink JSX | Phase 1 | `tsc --noEmit` green + `lib: ["ES2022"]` 확인 |
| 16. Python 유저 괴리 | Phase 3 (입력) + Phase 7 (beta) | 마이그레이션 체크리스트 + 원격 사용자 beta |
| 17. Slow 네트워크 | Phase 2 + Phase 7 | RTT 200ms 시뮬레이션 테스트 |
| 18. `bun install` 실패 | Phase 7 (배포) | fresh VM 에서 clean install 체크 |
| 19. non-TTY crash | Phase 1 + Phase 6 (one-shot) | pipe 테스트 CI |
| 20. Scrollback spinner 오염 | Phase 2 | scrollback 수동 검증 + `<Static>` 계약 문서 |

## Sources

### GitHub Issues (primary — HIGH confidence)
- [Ink Issue #907 — Terminal resize rendering artifacts](https://github.com/vadimdemedes/ink/issues/907)
- [Ink Issue #166 — setRawMode fails on non-TTY stdin](https://github.com/vadimdemedes/ink/issues/166)
- [Ink Issue #378 — Raw Mode and Subprocesses](https://github.com/vadimdemedes/ink/issues/378)
- [Ink Issue #359 — View longer than screen flickers](https://github.com/vadimdemedes/ink/issues/359)
- [Ink Issue #153 — Terminal resize events](https://github.com/vadimdemedes/ink/issues/153)
- [claude-code #42670 — Alternate screen kills scrollback](https://github.com/anthropics/claude-code/issues/42670)
- [claude-code #38810 — Mouse events break tmux scrollback](https://github.com/anthropics/claude-code/issues/38810)
- [claude-code #47773 — Paste broken in OAuth field](https://github.com/anthropics/claude-code/issues/47773)
- [claude-code #50012 — Large pastes truncated (Windows Terminal)](https://github.com/anthropics/claude-code/issues/50012)
- [claude-code #13183 — Paste bracketed mode hang](https://github.com/anthropics/claude-code/issues/13183)
- [claude-code #404, #1072, #5925, #35734 — Raw mode not supported](https://github.com/anthropics/claude-code/issues/5925)
- [bun Issue #4529 — WebSocket client differs from ws module](https://github.com/oven-sh/bun/issues/4529)
- [bun Issue #9368 — ws repeats messages on backpressure](https://github.com/oven-sh/bun/issues/9368)
- [bun Issue #27766 — Ink + spawn 100% CPU hang](https://github.com/oven-sh/bun/issues/27766)

### Official docs & primary references (HIGH confidence)
- [Ink README (vadimdemedes/ink)](https://github.com/vadimdemedes/ink)
- [Ink 3 release notes (Static 개선 · throttling)](https://vadimdemedes.com/posts/ink-3)
- [Bun WebSocket docs](https://bun.com/docs/runtime/http/websockets)
- [Zustand Selectors & Re-rendering](https://deepwiki.com/pmndrs/zustand/2.3-selectors-and-re-rendering)
- [Zustand docs (pmndrs/zustand)](https://github.com/pmndrs/zustand)

### Patterns & analysis (MEDIUM confidence — 커뮤니티)
- [Claude Code Internals Part 11: Terminal UI](https://kotrotsos.medium.com/claude-code-internals-part-11-terminal-ui-542fe17db016)
- [Interactive REPL & TUI (lttcnly/claude-code)](https://deepwiki.com/lttcnly/claude-code/2-interactive-repl-and-tui)
- [React Ink Component Architecture (instructkr/claude-code)](https://zread.ai/instructkr/claude-code/16-react-ink-component-architecture)
- [test-ink-flickering INK-ANALYSIS.md](https://github.com/atxtechbro/test-ink-flickering/blob/main/INK-ANALYSIS.md)
- [Qwen Code Ink rendering flicker issue](https://github.com/QwenLM/qwen-code/issues/1778)
- [Building Coding CLI with React Ink (ivanleo)](https://ivanleo.com/blog/migrating-to-react-ink)
- [Reactive UI with Ink and Yoga (Agentic Systems)](https://gerred.github.io/building-an-agentic-system/ink-yoga-reactive-ui.html)

### WebSocket reconnection / state sync (HIGH confidence)
- [WebSocket Reconnection Strategies w/ Exponential Backoff](https://dev.to/hexshift/robust-websocket-reconnection-strategies-in-javascript-with-exponential-backoff-40n1)
- [WebSocket Reconnection: State Sync and Recovery Guide](https://websocket.org/guides/reconnection/)
- [Understanding Jitter Backoff](https://biomousavi.com/understanding-jitter-backoff-a-beginners-guide)
- [WebSockets in React: Hooks, Lifecycle, Pitfalls](https://websocket.org/guides/frameworks/react/)

### 내부 교차 참조
- `/Users/johyeonchang/harness/.planning/PROJECT.md` — milestone 정의, Constraints, Key Decisions
- `/Users/johyeonchang/harness/.planning/codebase/CONCERNS.md` — Python 측 버그 이력 (§1.12 spinner vs Live, §3.1 main.py, §6.3 gitignored loadbearing 등)
- `/Users/johyeonchang/harness/ui-ink/src/{App.tsx,store.ts,ws.ts,index.tsx}` — 현재 스켈레톤
- 이전 커밋: `5ba9e6f` (ED3 resize), `c45e29f` (transient=True Live), `c27111a` (_Spinner 비활성) — Python 측 동형 버그 이력

---
*Pitfalls research for: Ink TUI agent UI migration from Python prompt_toolkit stack*
*Researched: 2026-04-23*
