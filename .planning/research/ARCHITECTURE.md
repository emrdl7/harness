# Architecture Patterns

**Domain:** Node + Ink + Zustand + bun + TypeScript 터미널 에이전트 UI (Python WebSocket 백엔드 클라이언트)
**Researched:** 2026-04-23
**Confidence:** HIGH (`harness_server.py` 실제 코드 기준 · 기존 `ui/index.js` 참조 구현 존재)

---

## 0. 요약

현재 `ui-ink/src/` 스켈레톤(4개 파일, ~200 LOC)은 **골격으로는 방향이 맞지만**, `harness_server.py` 의 실제 WS 프로토콜과 **메시지 타입이 어긋나 있어 아무것도 동작하지 않는 상태**다. `ws.ts` 가 `on_token`/`on_tool` 을 listen 하지만 서버는 `token`/`tool_start`/`tool_end` 를 broadcast 한다. 또한 스트리밍이 `appendMessage` 로 매 토큰마다 새 메시지를 push 하는 반 Claude Code 적 패턴이다.

이 문서는 **레이어 경계 · 상태 슬라이스 · WS 이벤트 매핑 · 빌드 순서**를 확정해 다음 phase 들이 참조할 수 있게 한다. 가장 중요한 결정 3가지:

1. **WS 레이어 = React 에서 완전히 분리된 순수 TS 모듈.** `ws.ts` 가 `useStore.getState()` 를 직접 호출하는 현 패턴은 유지하되, **discriminated union 타입으로 메시지를 강제 파싱**하고 **React 훅 경계 밖에서만 `.getState()` 를 호출**한다. 컴포넌트는 `useStore(selector)` 로만 구독.
2. **Zustand = 단일 스토어 + 논리 슬라이스 5개** (`messages / input / status / room / confirm`). 슬라이스마다 selector 를 export 해서 컴포넌트가 필요한 슬라이스만 구독하게 한다 (Ink 는 flexbox 전체 재렌더가 비싸진 않지만, 스트리밍 토큰당 status bar 전체가 re-render 되는 건 부담).
3. **빌드 순서 = 세로 절단 (vertical slice)** 접근. 각 phase 가 end-to-end 로 동작 가능한 상태를 유지하게 설계한다. Phase 1 에서 "사용자 입력 → agent → token stream 출력" 만 되면 그 위에 slash / confirm / diff / room / scroll 을 레이어링할 수 있다.

---

## 1. 컴포넌트 트리

### 1.1 목표 레이아웃 (Claude Code 미러링)

```
┌─────────────────────────────────────────────────────────────────────┐
│ <App>                                                               │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ <MessageList> (flexGrow=1)           ← scrollback 유지          │ │
│ │   ❯ 사용자 메시지                                               │ │
│ │   ● assistant 토큰 스트리밍                                     │ │
│ │   ● Read(path)                       ← ToolCard                 │ │
│ │   └ 42 lines                                                    │ │
│ │   ● Write(path)                                                 │ │
│ │   └ saved                                                       │ │
│ │   (DiffPreview — ephemeral, tool 내부)                          │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ ────────────────────────────────────────────────────────────── (top)│
│ <InputArea>                                                         │
│   ❯ 멀티라인 입력…                    ← <MultilineInput>            │
│   ┌── slash popup (conditional overlay) ──┐                         │
│   │ /plan    플랜 후 실행                 │  ← <SlashPopup>         │
│   │ /cplan   Claude 플랜                  │                         │
│   │ /clear   대화 초기화                  │                         │
│   └───────────────────────────────────────┘                         │
│ ────────────────────────────────────────────────────────────── (btm)│
│ <StatusBar>                                                         │
│   ⠋  qwen3  ·  ~/harness  ·  indexed  ·  turns: 3  ·  🟢 2명        │
│ └──── (ConfirmDialog — MODAL, Input 위에 렌더) ──────────┐          │
│       Write path/to/file.ts?                              │          │
│       [y]es  /  [n]o  /  [d] diff                         │          │
│       └──────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 컴포넌트 책임 분해

| 컴포넌트 | 책임 | 구독 슬라이스 | 렌더 트리거 |
|---------|------|----------------|-------------|
| `<App>` | 레이아웃 컨테이너, WS 생명주기 관리, 전역 키바인딩 (Ctrl+C, Ctrl+L, PgUp/Dn) | — (훅만, 값 구독 없음) | mount/unmount |
| `<MessageList>` | 과거 turn 들을 렌더. assistant 스트리밍 중 마지막 메시지 in-place 업데이트 | `messages` | 새 메시지 push / 마지막 메시지 content 변경 |
| `<Message>` | role 별 레이아웃(user/assistant/tool/system). assistant 는 markdown + syntax highlight | `messages[i]` (개별) | 해당 index 의 content 변경 |
| `<ToolCard>` | `tool_start` + `tool_end` 을 하나의 블록으로 렌더. 라벨/색상/인자 요약/결과 힌트 | `messages[i]` (role='tool') | tool 시작 시 pending, 종료 시 결과 업데이트 |
| `<DiffPreview>` | write_file 요청 시 diff hunks 를 render (confirm 전 미리보기) | `confirm.pendingWrite` | 모달 열릴 때만 |
| `<InputArea>` | 멀티라인 입력 + 슬래시 popup 트리거 + history recall (↑/↓) | `input`, `history` | 타이핑마다 |
| `<MultilineInput>` | Enter=제출 / Shift+Enter=개행 / Ctrl+U=지우기 | `input.buffer` | 타이핑마다 |
| `<SlashPopup>` | `/` 로 시작하는 입력일 때 자동완성 후보 리스트 + ↑↓ 선택 | `input.buffer`, (정적 카탈로그) | 입력이 `/` 로 시작하고 길이 변화 |
| `<StatusBar>` | cwd · model · turns · indexed · ctx meter · room presence · busy spinner | `status`, `room.busy`, `room.subscribers` | status/room 변경 |
| `<ConfirmDialog>` | `confirm_write` / `confirm_bash` / `cplan_confirm` 모달. Ink 에서는 **input 영역을 ConfirmDialog 로 치환** | `confirm.mode`, `confirm.payload` | mode 변경 시만 |
| `<RoomPanel>` (선택적) | `/who` 결과 · 멤버 목록. **별도 사이드바 대신 StatusBar 세그먼트로 시작** (MVP). 확장 필요 시 토글 가능한 오버레이. | `room` | room 변경 |

### 1.3 Ink 모달 패턴 (중요)

Ink 는 **HTML `<dialog>` 이나 z-index 개념이 없다.** Yoga flex 만 있다. 따라서 모달은 다음 중 하나:

**선택: 조건부 치환 (input 영역을 ConfirmDialog 로 교체)**

```tsx
// App.tsx 의 하단 영역
{confirm.mode === 'none'
  ? <InputArea />
  : <ConfirmDialog mode={confirm.mode} payload={confirm.payload} />
}
```

근거:
- `ink-overlay` 같은 라이브러리는 정식이 아니며 `measureElement` 해킹 필요.
- Claude Code 자체가 같은 패턴 — confirm 중에는 input 이 사라지고 prompt 가 바뀐다.
- 모달이 스크롤을 가리지 않도록 **하단 고정** 이 맞다.
- `ui/index.js` 의 `mode === 'confirm_write'` 분기가 이미 이 패턴임. 유지.

### 1.4 스트리밍 렌더링 — 마지막 메시지 in-place 업데이트

**현 스켈레톤의 버그:** `appendMessage({role: 'assistant', content: token})` 을 매 토큰마다 호출 → 메시지가 토큰 수만큼 쌓임.

**올바른 패턴:**

```ts
// store 의 actions
appendToken: (text: string) => set((s) => {
  const last = s.messages[s.messages.length - 1];
  if (last?.role === 'assistant' && last.streaming) {
    // in-place concatenate (새 배열 참조만, last 객체는 교체)
    return {
      messages: [
        ...s.messages.slice(0, -1),
        {...last, content: last.content + text}
      ]
    };
  }
  // 새 assistant 버퍼 시작 (agent_start 시 이미 빈 메시지 push 되어있을 수 있음)
  return {
    messages: [...s.messages, {role: 'assistant', content: text, streaming: true}]
  };
}),
agentStart: () => set((s) => ({
  busy: true,
  messages: [...s.messages, {role: 'assistant', content: '', streaming: true}]
})),
agentEnd: () => set((s) => {
  const last = s.messages[s.messages.length - 1];
  if (last?.role === 'assistant' && last.streaming) {
    return {
      busy: false,
      messages: [...s.messages.slice(0, -1), {...last, streaming: false}]
    };
  }
  return {busy: false};
}),
```

`<Message>` 는 `key={i}` 로 구독하되 React 의 동일 key 에 대한 content prop 변경만 diff 되게 한다.

### 1.5 가상화 (Virtualization)

**결정: MVP 에서는 가상화 안 함.**

근거:
- Ink 는 VDOM diff → ANSI escape 재 flush. 1000+ 메시지가 쌓여도 터미널은 scrollback 으로 이미 과거를 보관.
- 현재 turn 의 메시지만 보여도 되면 `messages.slice(-50)` 같은 간단한 슬라이싱으로 충분.
- `/clear` 가 리셋. 세션이 길면 어차피 `compact` 가 요약.
- 가상화가 필요해지는 시점: 수천 개 메시지 한 화면에 수용. 이번 milestone 범위 밖.

**Fallback:** 만약 render lag 가 관찰되면 `useStore((s) => s.messages.slice(-200))` 로 tail 만 구독하고, 과거는 scrollback 이 책임진다.

---

## 2. 상태 아키텍처 (Zustand)

### 2.1 단일 스토어 + 5개 슬라이스

```
┌─── useStore (single) ──────────────────────────────────────┐
│                                                            │
│  ┌── messages slice ──┐  ┌── input slice ──┐              │
│  │ messages: Message[]│  │ buffer: string  │              │
│  │ appendMessage      │  │ cursor: number  │              │
│  │ appendToken        │  │ history: str[]  │              │
│  │ updateLastTool     │  │ slashOpen: bool │              │
│  │ clear              │  │ setBuffer       │              │
│  │ agentStart/End     │  │ recallHistory   │              │
│  └────────────────────┘  └─────────────────┘              │
│                                                            │
│  ┌── status slice ────┐  ┌── room slice ───┐              │
│  │ workingDir         │  │ name: string    │              │
│  │ model              │  │ shared: bool    │              │
│  │ indexed            │  │ subscribers: n  │              │
│  │ turns              │  │ busy: bool      │              │
│  │ ctx: {used, max}   │  │ activeIsSelf    │              │
│  │ claudeAvailable    │  │ setRoom         │              │
│  │ compactCount       │  │ setBusy         │              │
│  │ setState           │  │ setMembers      │              │
│  └────────────────────┘  └─────────────────┘              │
│                                                            │
│  ┌── confirm slice ─────────────────────────────────────┐ │
│  │ mode: 'none'|'write'|'bash'|'cplan'                  │ │
│  │ payload: {path?, command?, diff?, task?}             │ │
│  │ openWrite(path, diff)                                │ │
│  │ openBash(command)                                    │ │
│  │ openCplan(task)                                      │ │
│  │ resolve(accept: bool) // WS 응답 송신 + mode='none'  │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### 2.2 왜 슬라이스 분리인가

- **렌더 성능:** Ink 리렌더는 Yoga layout + ANSI diff → 큰 `<App>` 리렌더는 수십 ms. StatusBar 는 토큰 스트리밍 때마다 리렌더될 필요 없음.
- **selector 로 구독 범위 최소화:**

  ```tsx
  // StatusBar 는 status/room 만
  const {model, workingDir, turns} = useStore((s) => ({
    model: s.model, workingDir: s.workingDir, turns: s.turns,
  }), shallow);
  const busy = useStore((s) => s.busy);

  // MessageList 는 messages 만
  const messages = useStore((s) => s.messages);
  ```

- **테스트 가능성:** 각 슬라이스는 순수 함수 reducer 처럼 `(state, action) → state` 로 단위 테스트 가능.
- **타입 안정성:** 슬라이스별 interface → 조합 시 type-level `&` intersection.

### 2.3 슬라이스 작성 패턴 (Zustand `StateCreator`)

```ts
import {create, StateCreator} from 'zustand';
import {shallow} from 'zustand/shallow';

// messages slice
interface MessagesSlice {
  messages: Message[];
  appendToken: (text: string) => void;
  agentStart: () => void;
  agentEnd: () => void;
  pushToolStart: (name: string, args: unknown) => void;
  updateLastToolEnd: (name: string, result: unknown) => void;
  pushUser: (text: string) => void;
  clear: () => void;
}
const createMessagesSlice: StateCreator<AppState, [], [], MessagesSlice> =
  (set) => ({ /* … */ });

// confirm slice — RPC 를 resolve 하려면 WS 참조 필요
interface ConfirmSlice {
  mode: 'none' | 'write' | 'bash' | 'cplan';
  payload: ConfirmPayload;
  openWrite: (p: WritePayload) => void;
  openBash: (p: BashPayload) => void;
  openCplan: (p: CplanPayload) => void;
  resolve: (accept: boolean) => void; // WS.send 는 외부 주입
}

export type AppState = MessagesSlice & InputSlice & StatusSlice & RoomSlice & ConfirmSlice;
export const useStore = create<AppState>()((...a) => ({
  ...createMessagesSlice(...a),
  ...createInputSlice(...a),
  ...createStatusSlice(...a),
  ...createRoomSlice(...a),
  ...createConfirmSlice(...a),
}));
```

### 2.4 Immutable 업데이트

Zustand 는 자동 immutable 이 아님 (set reducer 를 수동 작성). **React 가 diff 하려면 새 배열/객체 참조 필수.** 배열은 `[...arr, item]` / `arr.slice(0, -1)`. 객체는 `{...obj, field: new}`.

Immer middleware 는 **도입하지 않는다** (MVP). 근거:
- 5개 슬라이스 규모는 수동 spread 로 충분.
- Immer + TS slices 조합은 타입 이슈가 많다 ([zustand#1796](https://github.com/pmndrs/zustand/discussions/1796)).
- 스트리밍 hot path 는 Immer 의 Proxy 오버헤드가 측정 가능.

도입 조건: 슬라이스가 8+ 개로 늘고 중첩 객체 업데이트가 2 depth 이상 빈번해지면 재검토.

### 2.5 WS → 스토어 브릿지

`ws.ts` 는 React 훅 밖의 순수 모듈이라 `useStore.getState()` / `useStore.setState()` 로 직접 접근한다. 이는 정확한 사용법이다 ([Zustand docs — outside React](https://zustand.docs.pmnd.rs/guides/practice-with-no-store-actions)).

**중요한 invariant:** WS 가 reducer 를 직접 호출하지 않는다. 이벤트 → **store action 호출** → action 이 여러 슬라이스를 atomic 업데이트. WS 레이어는 "이 이벤트가 뭔지" 만 안다; "이 이벤트가 어느 슬라이스를 건드리는지" 는 action 이 안다.

```ts
// ws.ts
ws.on('message', (raw) => {
  const msg = parseServerMsg(raw); // discriminated union
  const store = useStore.getState();
  dispatch(msg, store);
});

// dispatch.ts
function dispatch(msg: ServerMsg, store: AppState) {
  switch (msg.type) {
    case 'token': store.appendToken(msg.text); break;
    case 'agent_start': store.agentStart(); break;
    case 'agent_end': store.agentEnd(); store.setBusy(false); break;
    case 'tool_start': store.pushToolStart(msg.name, msg.args); break;
    case 'tool_end': store.updateLastToolEnd(msg.name, msg.result); break;
    case 'confirm_write': store.openWrite({path: msg.path}); break;
    // …
    default: {
      const _exhaustive: never = msg; // 컴파일 시 미처리 이벤트 탐지
    }
  }
}
```

---

## 3. WebSocket 클라이언트 레이어 (`src/ws.ts`)

### 3.1 `harness_server.py` 의 실제 프로토콜

**서버 → 클라이언트 이벤트 (모두 `type` 필드):**

| type | payload 필드 | 발신 | 현재 `ws.ts` 처리? |
|------|--------------|------|---------------------|
| `ready` | `room: string` | 연결 직후 | ✗ TODO |
| `state` | `working_dir, turns, indexed, claude_available, compact_count` | 연결 + 각 입력 후 | ✗ 없음 |
| `state_snapshot` | `turns, messages: list` | room join 시 기존 세션 있을 때 | ✗ TODO |
| `room_joined` | `room, shared, subscribers, busy` | 연결 직후 | ✗ TODO |
| `room_member_joined` | `subscribers` | 공유 룸에 새 멤버 | ✗ 없음 |
| `room_member_left` | `subscribers` | 멤버 이탈 | ✗ 없음 |
| `room_busy` | — | 다른 사용자가 입력 중 | ✗ 없음 |
| `agent_start` | — | agent 실행 시작 (broadcast) | ✓ (잘못된 이름 `agent_start` 맞음) |
| `agent_end` | — | agent 실행 종료 | ✓ |
| `token` | `text` | 스트리밍 토큰 | ✗ (현재 `on_token` 으로 오해) |
| `tool_start` | `name, args` | 툴 호출 직전 | ✗ (현재 `on_tool` 으로 오해) |
| `tool_end` | `name, result` | 툴 결과 | ✗ (현재 `on_tool` 으로 오해) |
| `claude_start`/`claude_token`/`claude_end` | `text` | @claude 또는 /cplan 경로 | ✗ 없음 |
| `confirm_write` | `path` | write_file 전 승인 요청 (active ws 에만) | ✗ TODO |
| `confirm_bash` | `command` | bash 전 승인 요청 | ✗ TODO |
| `cplan_confirm` | `task` | cplan 플랜 완료 후 실행 승인 | ✗ TODO |
| `queue`/`queue_ready` | `position?` | Ollama 대기열 | ✗ 없음 |
| `slash_result` | `cmd, …(cmd별 필드)` | 슬래시 완료 결과 | ✗ 없음 |
| `info` | `text` | 정보 메시지 (압축 등) | ✗ 없음 |
| `error` | `text` | 에러 (주의: `text` 이지 `message` 아님) | ✗ 현재 `msg.message` 로 잘못 파싱 |
| `quit` | — | /quit 슬래시 | ✗ 없음 |
| `pong` | — | ping 응답 | ✗ 없음 |

**클라이언트 → 서버 이벤트:**

| type | payload | 언제 |
|------|---------|------|
| `input` | `text: string` | 사용자 입력 (자동 슬래시/@claude 는 서버가 프리픽스로 라우팅) |
| `confirm_write_response` | `result: bool` | confirm_write 응답 |
| `confirm_bash_response` | `result: bool` | confirm_bash 응답 |
| `cplan_execute` | `task: string` | cplan 승인 시 |
| `ping` | — | heartbeat (구현 시) |

**주의:** 서버는 `slash` 라는 별도 타입 **없음**. 입력이 `/` 로 시작하면 서버가 `input` 으로 받아 내부에서 `handle_slash` 로 라우팅한다. 즉 `slash` 는 클라 타입이 아니라 UI 의 편의 용어이며 **전송은 `input` 으로 통일**한다. 현 `ws.ts` 주석의 "클라 → 서버: …/slash" 는 부정확하므로 수정 대상.

### 3.2 Discriminated Union 타입 정의

```ts
// src/protocol.ts — 서버가 보내는 모든 이벤트
export type ServerMsg =
  | {type: 'ready'; room: string}
  | {type: 'state'; working_dir: string; turns: number; indexed: boolean;
     claude_available: boolean; compact_count: number}
  | {type: 'state_snapshot'; turns: number; messages: ChatMessage[]}
  | {type: 'room_joined'; room: string; shared: boolean;
     subscribers: number; busy: boolean}
  | {type: 'room_member_joined'; subscribers: number}
  | {type: 'room_member_left'; subscribers: number}
  | {type: 'room_busy'}
  | {type: 'agent_start'}
  | {type: 'agent_end'}
  | {type: 'token'; text: string}
  | {type: 'tool_start'; name: string; args: Record<string, unknown>}
  | {type: 'tool_end'; name: string; result: ToolResult}
  | {type: 'claude_start'}
  | {type: 'claude_token'; text: string}
  | {type: 'claude_end'}
  | {type: 'confirm_write'; path: string}
  | {type: 'confirm_bash'; command: string}
  | {type: 'cplan_confirm'; task: string}
  | {type: 'queue'; position: number}
  | {type: 'queue_ready'}
  | {type: 'slash_result'; cmd: string} & SlashResultExtras
  | {type: 'info'; text: string}
  | {type: 'error'; text: string}
  | {type: 'quit'}
  | {type: 'pong'};

// 클라 → 서버
export type ClientMsg =
  | {type: 'input'; text: string}
  | {type: 'confirm_write_response'; result: boolean}
  | {type: 'confirm_bash_response'; result: boolean}
  | {type: 'cplan_execute'; task: string}
  | {type: 'ping'};

export interface ToolResult {
  ok: boolean;
  error?: string; stderr?: string; stdout?: string;
  // read_file 전용
  content?: string; total_lines?: number; start_line?: number; end_line?: number;
  // list_files
  files?: string[];
  // run_command / run_python
  returncode?: number;
  // git_*
  output?: string;
  // 기타 임의
  [k: string]: unknown;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
}

// slash_result 는 cmd 별 추가 필드가 다름 → 별도 union
export type SlashResultExtras =
  | {cmd: 'clear' | 'help' | 'learn' | 'init'}
  | {cmd: 'undo'; ok: boolean}
  | {cmd: 'save'; filename: string}
  | {cmd: 'resume'; turns: number; ok?: boolean}
  | {cmd: 'index'; indexed: number; skipped: number}
  | {cmd: 'cd'; working_dir: string}
  | {cmd: 'files'; tree: FileTreeNode}
  | {cmd: 'sessions'; sessions: SessionInfo[]}
  | {cmd: 'who'; room: string; shared: boolean; busy: boolean;
     members: {self: boolean; active: boolean}[]; count: number}
  | {cmd: 'improve'; backup: string; validation: unknown[]};
```

**런타임 검증:** MVP 에서는 `parseServerMsg` 가 `JSON.parse` 후 `msg.type` 을 switch 하는 것으로 충분. 나중에 규모가 커지면 Zod 도입 고려 — 단 서버가 신뢰된 경로라 validation overhead 는 당장 불필요.

### 3.3 Connection 생명주기

```ts
// src/ws.ts
export class HarnessClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pingTimer: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private readonly opts: ConnectOptions;
  private closed = false;

  constructor(opts: ConnectOptions) { this.opts = opts; }

  connect() {
    const headers: Record<string,string> = {'x-harness-token': this.opts.token};
    if (this.opts.room) headers['x-harness-room'] = this.opts.room;
    this.ws = new WebSocket(this.opts.url, {headers});

    this.ws.on('open', () => this.onOpen());
    this.ws.on('message', (raw) => this.onMessage(raw));
    this.ws.on('close', () => this.onClose());
    this.ws.on('error', (e) => this.onError(e));
  }

  send(msg: ClientMsg) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
    // 닫혀있으면 buffer? MVP = drop + UI 에 표시
  }

  close() { this.closed = true; this.ws?.close(); /* clear timers */ }

  private onOpen() {
    this.reconnectAttempts = 0;
    useStore.getState().setConnection('open');
    // ping 타이머: 30초마다 ping → 60초 안에 pong 없으면 reconnect
    this.pingTimer = setInterval(() => this.send({type: 'ping'}), 30_000);
  }

  private onMessage(raw: WebSocket.RawData) {
    const msg = parseServerMsg(raw.toString());
    if (!msg) return;
    dispatch(msg, useStore.getState());
  }

  private onClose() {
    if (this.pingTimer) clearInterval(this.pingTimer);
    useStore.getState().setConnection('closed');
    if (!this.closed) this.scheduleReconnect();
  }

  private onError(e: Error) {
    useStore.getState().pushSystem(`ws error: ${e.message}`);
  }

  private scheduleReconnect() {
    // 지수 백오프 1s, 2s, 4s, 8s, max 30s
    const delay = Math.min(30_000, 1000 * 2 ** this.reconnectAttempts);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }
}
```

### 3.4 Confirm RPC 상관관계 (구체)

서버 측 구조 (이미 구현됨):
- `confirm_write(path)` 는 agent 스레드에서 호출됨 → asyncio.Event 를 대기.
- 서버가 `{type: 'confirm_write', path}` 을 active ws 에만 송신.
- 클라가 `{type: 'confirm_write_response', result: bool}` 을 송신.
- `_dispatch_loop` 가 받아서 `state._confirm_event.set()` → agent 스레드 깨어남.

**클라 측 설계:**

상관관계는 **암묵적** 이다 — 서버가 한 번에 하나의 `confirm_*` 만 보냄 (active_input_from 격리 + busy lock). 따라서 클라는 correlation ID 없이 "현재 열린 모달이 곧 현재 대기 중인 confirm" 이라고 가정 가능.

```ts
// confirm slice
interface ConfirmSlice {
  mode: 'none' | 'write' | 'bash' | 'cplan';
  payload: {path?: string; command?: string; task?: string; diff?: string};
  openWrite: (p: {path: string; diff?: string}) => void;
  openBash: (p: {command: string}) => void;
  openCplan: (p: {task: string}) => void;
  resolve: (accept: boolean) => void;
}

// 초기화 시 WS 인스턴스 주입
function createConfirmSlice(ws: HarnessClient): StateCreator<...> {
  return (set, get) => ({
    mode: 'none',
    payload: {},
    openWrite: (p) => set({mode: 'write', payload: p}),
    openBash: (p) => set({mode: 'bash', payload: p}),
    openCplan: (p) => set({mode: 'cplan', payload: p}),
    resolve: (accept) => {
      const {mode, payload} = get();
      if (mode === 'write') {
        ws.send({type: 'confirm_write_response', result: accept});
      } else if (mode === 'bash') {
        ws.send({type: 'confirm_bash_response', result: accept});
      } else if (mode === 'cplan') {
        if (accept) ws.send({type: 'cplan_execute', task: payload.task!});
        // reject 는 서버에 알릴 필요 없음 (서버는 실행 안 하는 게 default)
      }
      set({mode: 'none', payload: {}});
    },
  });
}
```

**timeout 처리:** 서버는 60초 타임아웃 후 `_confirm_result=False` 로 진행. 클라도 같은 타임아웃에 맞춰 모달 자동 닫기 (시각적 피드백) — **다만 서버가 이미 false 로 처리 중이므로 클라 응답은 무시된다**. 그래서 로컬 타임아웃은 UX 용이지 프로토콜용이 아니다.

### 3.5 Backpressure / 메시지 큐

- 수신: `ws` 라이브러리가 내부 버퍼. ink 가 매 토큰마다 setState → Yoga reflow. 극도로 빠른 토큰 스트림에서 render backpressure 가능. Phase 2 에서 측정 후 필요 시 **토큰 batching** (16ms throttle + requestAnimationFrame 대신 setTimeout flush).
- 송신: MVP = 단순 `send`. readyState 검사만.

### 3.6 에러 전파

```ts
// 3 계층 에러:
// 1. ws 계층 (연결 실패, JSON parse 실패): StatusBar 'disconnected' + system message
// 2. 서버 에러 이벤트 (type='error'): message 리스트에 system 메시지
// 3. UI 로직 에러 (React): ErrorBoundary (MVP 에선 console)
```

---

## 4. 데이터 플로우 — 전형적인 턴

```
┌─ User 입력: "src/foo.ts 읽어봐" ──────────────────────────────────────┐
│                                                                       │
│ 1. <MultilineInput> onChange → store.setBuffer('src/foo.ts 읽어봐')   │
│ 2. Enter → store.submit() →                                           │
│      store.pushUser('src/foo.ts 읽어봐')                              │
│      store.clearBuffer()                                              │
│      ws.send({type: 'input', text: 'src/foo.ts 읽어봐'})              │
│                                                                       │
│ 3. 서버: input → _dispatch_loop → _handle_input → run_agent           │
│    room.busy = true, room.active_input_from = ws                      │
│                                                                       │
│ ┌─ 서버 broadcast 이벤트들 (빠른 시퀀스) ────────────────────────────┐│
│ │ 4. {type: 'agent_start'} → store.agentStart()                     ││
│ │    → messages.push({role: 'assistant', content: '', streaming: t})││
│ │    → busy = true → StatusBar 스피너 on                            ││
│ │                                                                    ││
│ │ 5. {type: 'token', text: '파일을'} → store.appendToken('파일을')   ││
│ │    → messages[-1].content = '파일을' (in-place)                    ││
│ │    → <Message> 만 재렌더 (selector 가 filter)                     ││
│ │ 5'.{type: 'token', text: ' 읽어'} → '파일을 읽어'                 ││
│ │ 5".{type: 'token', text: '겠습니다'} → '파일을 읽어겠습니다'      ││
│ │                                                                    ││
│ │ 6. {type: 'tool_start', name:'read_file', args:{path:'src/foo.ts'}}││
│ │    → store.pushToolStart('read_file', {path: 'src/foo.ts'})       ││
│ │    → messages.push({role: 'tool', content: 'Read(src/foo.ts)',    ││
│ │                     meta: {name, args, status: 'pending'}})       ││
│ │    → <ToolCard> 렌더 (pending 스피너)                             ││
│ │                                                                    ││
│ │ 7. {type: 'tool_end', name:'read_file', result:{ok:t, content:…}} ││
│ │    → store.updateLastToolEnd('read_file', result)                 ││
│ │    → messages[-1].meta.status = 'ok', hint = '42 lines'           ││
│ │    → <ToolCard> 렌더 (완료)                                       ││
│ │                                                                    ││
│ │ 8. {type: 'agent_start'} — wait, 서버는 reflection round 안 찍음   ││
│ │    (단일 라운드라면). multi-round 시 8..10 반복                   ││
│ │                                                                    ││
│ │ 9. {type: 'token', text: '...'} → agent 최종 답변 스트리밍        ││
│ │                                                                    ││
│ │10. {type: 'agent_end'} → store.agentEnd()                         ││
│ │    → messages[-1].streaming = false                                ││
│ │    → busy = false → 스피너 off                                    ││
│ │                                                                    ││
│ │11. {type: 'state', working_dir, turns, ...} → store.setState(...)  ││
│ │    → StatusBar 갱신                                               ││
│ └────────────────────────────────────────────────────────────────────┘│
│                                                                       │
│ 12. <InputArea> 다시 활성화 (busy=false 구독해서 자동 복원)           │
└───────────────────────────────────────────────────────────────────────┘
```

### 4.1 Write 가 개입된 턴 (confirm 경로)

```
…steps 1-6 동일…
6'. {type: 'tool_start', name:'write_file', args:{path, content}}
    → pushToolStart (pending)
7'. 서버: write_file 실행 → confirm_write 콜백 → active ws 에
    {type: 'confirm_write', path: 'src/foo.ts'} 송신
    → store.openWrite({path: 'src/foo.ts'})
    → confirm.mode = 'write'
    → <InputArea> 언마운트 / <ConfirmDialog> 마운트
    → "Write src/foo.ts? (y/n/d)" 표시

유저 액션 A. y 키 → store.resolve(true)
    → ws.send({type: 'confirm_write_response', result: true})
    → confirm.mode = 'none', <InputArea> 재마운트
    → 서버 _dispatch_loop 가 받음 → event.set() → agent 스레드 재개
    → write_file 실행 → 이어서 {type: 'tool_end', result: {ok: true}}
    → store.updateLastToolEnd → <ToolCard> 완료 표시
    …ensuing agent_end, state 이벤트…

유저 액션 B. n 키 → resolve(false) → 서버는 tool_end ok=false 로 broadcast
```

### 4.2 공유 룸 — 관전자 시나리오

- A (입력자) + B (관전자) 가 같은 룸
- A 가 `"읽어봐"` 입력
- 서버: `agent_start` / `token`*N / `tool_start` / `tool_end` / `agent_end` **모두 broadcast**
- B 의 UI: 자신이 입력 안 했는데도 스트리밍 토큰이 쌓이고 스피너 돈다
- 그런데 `confirm_write` 는 A 에게만 `send` — B 는 모달을 못 본다
- 따라서 B 의 `<ToolCard>` 는 pending 상태로 멈춰있다가 A 가 승인하면 `tool_end` broadcast 로 완료
- B 의 `room.activeIsSelf = false` 이므로 `<InputArea>` 는 disable (혹은 "A 가 입력 중" 표시), `room.busy = true` 유지

이 시나리오는 **store.room 슬라이스에 activeIsSelf 플래그가 있어야** 정상 동작한다 — `room_joined` 이후 `agent_start` 의 context 에서 "내가 active 인가?" 가 결정되어야 하는데, **서버는 현재 active_input_from 을 broadcast 하지 않는다**. → **프로토콜 확장 제안:** agent_start 에 `from_self: bool` 필드 추가 (원래 서버가 아는 정보, 각 ws 마다 `s is room.active_input_from` 비교해서 다르게 보낼 수 있음).

### 4.3 Room busy 상태 시퀀스

```
A 가 입력 → _dispatch_loop: room.busy = true, active_input_from = A.ws
           → _spawn_input_task(room, _handle_input(A.ws, room, text))
           → [agent_start 등 broadcast]
B 가 입력 시도 → _dispatch_loop: room.busy check → broadcast room_busy → 무시
           → A/B 모두 room_busy 수신, B 의 UI 는 "busy" 표시
A 완료 → _handle_input finally: room.busy = false, active_input_from = None
```

---

## 5. 이벤트 → 상태 액션 매핑 테이블

**서버 → 클라이언트:**

| Server Event | Store Action | Slice | UI 영향 |
|--------------|--------------|-------|---------|
| `ready` | `setConnection('ready')` | status | StatusBar 'connected' |
| `state` | `setStatus(...)` | status | StatusBar 세그먼트 갱신 |
| `state_snapshot` | `loadSnapshot(messages, turns)` | messages, status | 히스토리 일괄 로드 |
| `room_joined` | `setRoom({name, shared, subs, busy})` | room | 상단 배너 + StatusBar presence |
| `room_member_joined` | `setSubscribers(n)` | room | system 메시지 + presence 갱신 |
| `room_member_left` | `setSubscribers(n)` | room | system 메시지 |
| `room_busy` | `pushSystem('다른 사용자가 입력 중')` | messages (system) | 안내 |
| `agent_start` | `agentStart()` | messages, room | 스트리밍 버퍼 시작, busy=true, 스피너 |
| `agent_end` | `agentEnd()` | messages, room | streaming=false, busy=false |
| `token` | `appendToken(text)` | messages | 마지막 assistant 메시지 content+= |
| `tool_start` | `pushToolStart(name, args)` | messages | ToolCard pending |
| `tool_end` | `updateLastToolEnd(name, result)` | messages | ToolCard 완료/실패 |
| `claude_start` | `claudeStart()` | messages | Claude 스트리밍 버퍼 |
| `claude_token` | `appendClaudeToken(text)` | messages | 마지막 claude 메시지 |
| `claude_end` | `claudeEnd()` | messages | 완료 |
| `confirm_write` | `confirm.openWrite({path})` | confirm | 모달 표시 (Input 치환) |
| `confirm_bash` | `confirm.openBash({command})` | confirm | 모달 표시 |
| `cplan_confirm` | `confirm.openCplan({task})` | confirm | 모달 표시 |
| `queue` | `setQueue(position)` | status | StatusBar 'queue 3' |
| `queue_ready` | `clearQueue()` | status | 'queue' 제거 |
| `slash_result` | `applySlashResult(cmd, data)` | (cmd 별) | /clear→messages=[], /who→room, 기타 |
| `info` | `pushSystem(text, 'info')` | messages | system 메시지 dim |
| `error` | `pushSystem(text, 'error')` | messages | system 메시지 red |
| `quit` | `shutdown()` | — | 프로세스 종료 |
| `pong` | `bumpHeartbeat()` | (internal) | heartbeat 타이머 리셋 |

**클라 → 서버:**

| User Action | Store Action | WS Send |
|-------------|--------------|---------|
| Enter 입력 | `pushUser(text) + clearBuffer()` | `{type:'input', text}` |
| confirm y | `confirm.resolve(true)` | `{type:'confirm_write_response', result:true}` 등 |
| confirm n | `confirm.resolve(false)` | `{type:'confirm_*_response', result:false}` |
| cplan y | `confirm.resolve(true)` | `{type:'cplan_execute', task}` |
| /quit 입력 | (내부 없음, 서버가 quit 이벤트로 응답) | `{type:'input', text:'/quit'}` |
| Ctrl+C | `shutdown()` (로컬 종료) | ws.close() |

---

## 6. 테스트 아키텍처

### 6.1 테스트 가능한 레이어 (우선순위 순)

1. **순수 로직 (최우선)** — `dispatch.ts`, store reducers, `parseServerMsg`, tool 메타 매핑 (TOOL_META)
   - bun test / vitest 로 단위 테스트
   - Mock 불필요, deterministic
2. **WS 레이어** — `HarnessClient` 클래스
   - Node 의 `ws` 모듈을 mock 하거나 local WebSocket server 로 end-to-end
   - 연결/재연결/heartbeat/backoff 타이밍
3. **컴포넌트** — `<MessageList>`, `<ConfirmDialog>`, `<ToolCard>`
   - [`ink-testing-library`](https://github.com/vadimdemedes/ink-testing-library) 로 렌더 + `lastFrame()` 스냅샷
4. **통합 테스트** — 가짜 서버가 스크립트된 시퀀스를 보내고 UI 가 기대대로 반응
   - 로컬 WS 서버 + HarnessClient + store + ink-testing-library
   - 시나리오: "agent 턴 1개", "confirm_write accept", "room busy", "reconnect"

### 6.2 레이어별 테스트 샘플

```ts
// 1. 순수 로직
test('appendToken in-place updates last assistant message', () => {
  const store = createTestStore();
  store.agentStart();
  store.appendToken('Hello');
  store.appendToken(' world');
  expect(store.messages[store.messages.length - 1]).toMatchObject({
    role: 'assistant', content: 'Hello world', streaming: true,
  });
  expect(store.messages.filter(m => m.role === 'assistant')).toHaveLength(1);
});

// 2. 프로토콜 파서
test('parseServerMsg rejects unknown type', () => {
  expect(parseServerMsg('{"type":"bogus"}')).toBeNull();
});

// 3. 컴포넌트
import {render} from 'ink-testing-library';
test('ConfirmDialog renders path and y/n hint', () => {
  const {lastFrame} = render(<ConfirmDialog mode="write" payload={{path:'foo.ts'}} />);
  expect(lastFrame()).toContain('Write foo.ts');
  expect(lastFrame()).toMatch(/y.*n/i);
});

// 4. 통합 — 가짜 서버
test('full turn: input → token → agent_end', async () => {
  const server = new FakeHarnessServer();
  const client = new HarnessClient({url: server.url, token: 'x'});
  client.connect();
  await server.expectClientInput('hi');
  server.broadcast({type: 'agent_start'});
  server.broadcast({type: 'token', text: 'hello'});
  server.broadcast({type: 'agent_end'});
  await sleep(10);
  const state = useStore.getState();
  expect(state.messages.at(-1)).toMatchObject({content: 'hello', streaming: false});
  expect(state.busy).toBe(false);
});
```

### 6.3 테스트 툴체인 결정

- **러너:** `bun test` 1순위 (ui-ink 의 기본 bun 스택). React 렌더 테스트가 ESM 문제 생기면 `vitest` 대체.
- **UI:** `ink-testing-library`.
- **WS mock:** `ws.Server` 로 로컬 서버. 실제 `harness_server.py` 연동 smoke 는 별도 스크립트.
- **Python 쪽 회귀:** 기존 pytest 199건 유지. ui-ink 가 프로토콜 깨지 않는 한 블랙박스.

---

## 7. 빌드 순서 (Phase Build Order)

**원칙:** 각 phase 끝에 end-to-end 동작하는 상태 유지 (vertical slice). "먼저 인프라 다 만들고 마지막에 연결" 패턴 지양.

### Phase 1 — Smoke Path (최소 기능 end-to-end)

**목표:** `bun start` → harness_server.py 에 연결 → 텍스트 입력 → 토큰 스트림 → agent_end. 이게 되면 다음 phase 들이 레이어링 가능.

빌드:
1. `src/protocol.ts` — ServerMsg / ClientMsg discriminated union 타입
2. `src/parse.ts` — `parseServerMsg` (type switch)
3. `src/store/` 분할 — `messages.ts`, `input.ts`, `status.ts`, `room.ts`, `confirm.ts` 슬라이스 + `index.ts` 조합
4. `src/ws/client.ts` — `HarnessClient` 클래스 (connect, send, onMessage, onClose 기본)
5. `src/ws/dispatch.ts` — ServerMsg → store action 매핑 (exhaustive switch)
6. `src/App.tsx` — `<MessageList>` + 단일 라인 input 만 (기존 TextInput 재사용)
7. `src/components/MessageList.tsx`, `src/components/Message.tsx` — role 별 기본 렌더
8. 스트리밍 in-place 업데이트 검증

**Exit criteria:**
- `"hello"` 입력 → assistant 토큰 렌더 → 완료
- 기존 `ui/index.js` 와 동등 smoke 동작
- bun test 로 store/parse/dispatch 단위 테스트 통과

**필수 수정 (현 스켈레톤):**
- `ws.ts` 의 `on_token` / `on_tool` → `token` / `tool_start` / `tool_end` 로 교체
- `error.message` → `error.text` 로 교정
- `appendMessage(assistant)` 누적 버그 → `appendToken` in-place 로 교체

### Phase 2 — Tool Rendering + Status Bar

의존: Phase 1.

빌드:
9. `src/components/ToolCard.tsx` — TOOL_META 테이블 (ui/index.js 에서 포팅), pending/ok/err 상태 시각화
10. `src/components/StatusBar.tsx` — 세그먼트 (model, cwd, turns, indexed, ctx, compact_count, claude_available)
11. `state` 이벤트 처리 → status slice 갱신
12. 스피너 컴포넌트 (busy 상태 연동)

**Exit:** `"src/foo 읽어봐"` 턴이 ToolCard 로 제대로 렌더. StatusBar 가 cwd/turns 갱신.

### Phase 3 — Confirm Dialogs (Write, Bash, Cplan)

의존: Phase 1, 2.

빌드:
13. `src/store/confirm.ts` — 슬라이스 완성 (openWrite/openBash/openCplan/resolve)
14. `src/components/ConfirmDialog.tsx` — mode 별 프롬프트. y/n/d 키 처리 (`useInput`)
15. `<App>` 하단 영역: `confirm.mode==='none' ? <InputArea/> : <ConfirmDialog/>`
16. diff 미리보기 (Phase 5 에서 확장 — MVP 에선 path 만 표시)

**Exit:** write_file 요청 시 모달 등장, y → 서버 진행, n → 취소. bash 도 동일. cplan 도 동일.

### Phase 4 — Multiline Input + Slash Popup

의존: Phase 1-3.

빌드:
17. `src/components/MultilineInput.tsx` — Enter 제출 / Shift+Enter 개행 / ↑↓ 히스토리. `ink-text-input` 은 단일 라인 한계 — 자체 구현 필요.
18. `src/components/SlashPopup.tsx` — buffer 가 `/` 로 시작 시 후보 리스트 + ↑↓ 선택 + Tab 자동완성
19. 슬래시 카탈로그 `src/slash-catalog.ts` — 13 개 명령 (`main.py` 것과 동일하게 유지 필요)
20. `slash_result` 이벤트 → 슬래시별 UI 표시 (files tree, sessions 목록, who 등)

**Exit:** 멀티라인 입력 가능. `/` 타이핑 시 popup. 슬래시 결과 예쁘게 렌더.

### Phase 5 — Diff Rendering + Syntax Highlight

의존: Phase 2, 3.

빌드:
21. diff 라이브러리 선정 — [`diff`](https://www.npmjs.com/package/diff) npm 패키지로 unified hunks 생성. `write_file` 의 `content` + 기존 파일 내용 비교 (기존 파일 내용은 서버가 제공 안 함 → **프로토콜 확장**: `confirm_write` 에 `old_content` 필드 선택적 추가)
22. syntax highlight — [`cli-highlight`](https://www.npmjs.com/package/cli-highlight) (Ink 친화적)
23. `<DiffPreview>` — ConfirmDialog 안에 삽입. `d` 키로 접었다 펼치기
24. tool_end 의 read_file / write_file 결과에 syntax highlight 적용

**Exit:** Write confirm 시 diff 미리보기. Read 결과 코드 펜스 하이라이트.

### Phase 6 — Scroll + Keyboard Nav

의존: Phase 1.

빌드:
25. PgUp/PgDn/Home/End 처리 — 터미널 scrollback 은 OS 가 관리, Ink 는 관여 안 함. **실질적으로는 `useInput` 으로 PgUp/Dn 을 빈 핸들러 (브라우저 pass-through)**. Alternate screen 금지 확인.
26. Ctrl+L clear (시각적 clear — scrollback 보존)
27. Ctrl+U / Ctrl+K / Ctrl+W — 입력 편집 단축키

**Exit:** Cmd+C 로 과거 출력 복사 가능. scrollback 유지.

### Phase 7 — Room Presence (Shared Room UX)

의존: Phase 1.

빌드:
28. `room_joined` / `room_member_*` / `room_busy` / `state_snapshot` 처리 (store.room)
29. StatusBar 에 '🟢 2명' 세그먼트
30. `room.activeIsSelf=false` 면 `<InputArea>` disabled + "A 가 입력 중" 표시
31. state_snapshot 수신 시 메시지 리스트 일괄 로드 (새 join 시 과거 턴 복원)
32. **프로토콜 확장:** `agent_start` 에 `from_self: bool` 필드 추가 (서버 broadcast 시 각 ws 마다 s is room.active_input_from 비교)

**Exit:** 두 클라이언트를 같은 room 으로 접속 → 한쪽 입력 시 다른쪽 관전. 관전자 UI 가 올바르게 disabled.

### Phase 8 — One-Shot + Resume

의존: Phase 1-4.

빌드:
33. `harness "질문"` one-shot: 인자 있으면 연결 후 `input` 전송 → `agent_end` 대기 → 토큰 stdout 출력 → 종료
34. `harness --resume <id>` → `input: '/resume <id>'` 전송 후 일반 REPL 전환
35. CLI 인자 파싱 (`commander` 또는 자체 `process.argv`)

**Exit:** 셸에서 `bun start "What is 2+2?"` → 답만 프린트하고 exit.

### Phase 9 — Legacy 삭제 + 최종 정리

의존: 모든 phase.

빌드:
36. `ui/index.js` 삭제
37. `main.py` REPL 경로 (cli/ 모듈) 삭제
38. `CLIENT_SETUP.md` 갱신 (bun 기준)
39. 문서: WS 프로토콜 명세 파일 (PROTOCOL.md) 공식화
40. 회귀 테스트 한 라운드

**Exit:** Python 쪽 legacy 코드 제거, ui-ink 가 유일한 클라.

### 7.1 의존성 그래프 (ASCII)

```
     [P1 Smoke]
         │
    ┌────┼────┬──────┐
    ▼    ▼    ▼      ▼
  [P2]  [P4] [P6]  [P7]
  Tool  Slash Scroll Room
   │    │
   ▼    ▼
  [P3] ─┘
 Confirm
   │
   ▼
  [P5]
  Diff
         │
         ▼
        [P8]
       OneShot
         │
         ▼
        [P9]
       Cleanup
```

---

## 8. 현 스켈레톤 Critique (Honest)

### 8.1 유지 (Keep as-is)

- `src/index.tsx` — `render(<App />)` 인라인 모드 (alternate screen 없음) — 정확함. 유지.
- `package.json` — Ink 5 + React 18 + Zustand 4 + ws 8 + bun — 적절한 최신 버전.
- `App.tsx` 의 전체 레이아웃 프레임 (message list → rule → input → rule → status) — Claude Code 와 동일한 구조, 유지.
- `ws.ts` 의 header 주입 (`x-harness-token`, `x-harness-room`) — 서버와 맞음.
- `store.ts` 의 5개 기본 필드 (messages, input, status, busy) — 올바른 최소셋.

### 8.2 치명적 버그 (반드시 수정, Phase 1 요구사항)

- **프로토콜 이름 불일치** — `on_token`/`on_tool` 은 서버가 보내지 않는 이름. 실제는 `token`/`tool_start`/`tool_end`. **연결해도 아무것도 렌더 안 됨.** (ws.ts:47-55)
- **error.message** — 서버는 `text` 로 보냄. (ws.ts:64)
- **스트리밍 토큰마다 새 메시지 push** — 화면 폭탄. in-place append 로 교체. (ws.ts:47-49)
- **ConnectOptions 의 `token` required** — 실제 서버는 HARNESS_TOKENS 비어있으면 시작조차 안 함. 정상. 유지. (ws.ts:19)
- **현재 `ws.ts` 는 신뢰하지 않을 이벤트가 많다** — 누락: `state`, `state_snapshot`, `confirm_*`, `cplan_confirm`, `room_*`, `queue`, `slash_result`, `info`, `claude_*`, `quit`, `pong`, `tool_start`/`tool_end`, `token`. 거의 전부. TODO 주석은 있으나 Phase 1 에서 즉시 구현 필요.

### 8.3 구조적 변경 (Phase 1 착수 시)

- **단일 파일 `store.ts` → `src/store/` 디렉토리로 분할.** 5 슬라이스 패턴. 현재 단일 interface 는 30줄인데 이번 milestone 에서 200+ 줄로 불어날 예정. 분할이 먼저.
- **`src/protocol.ts` 신규.** Discriminated union 타입 정의. ws.ts 는 여기서 import.
- **`src/ws.ts` → `src/ws/` 디렉토리.** `client.ts` (HarnessClient 클래스), `dispatch.ts` (메시지 → action), `parse.ts` (JSON → ServerMsg). 현재는 `connect` 함수가 직접 setState — 클래스로 감싸서 lifecycle 관리 가능하게.
- **`WebSocket | null` useState** — App.tsx 에서 제거. WS 는 React 상태가 아니라 module-level 싱글톤 또는 React context.
- **spinner 로직** — App.tsx 에 있음. `<Spinner/>` 컴포넌트로 분리. `ink-spinner` 사용 가능하나 폭/프레임 다르면 자체.

### 8.4 의존성 추가 (Phase 2-5)

- `ink-spinner` (or 자체) — spinner
- `diff` — diff hunks
- `cli-highlight` — syntax highlight in ink
- 자체 구현 (ink 에 없음): multiline input, slash popup

### 8.5 제거 대상

- `ink-text-input` — 단일 라인 한계 때문에 Phase 4 에서 자체 `<MultilineInput>` 으로 교체. 일단 Phase 1 smoke 에서는 남김.

### 8.6 테스트 부재

- 현재 `package.json` 에 test script 없음, ink-testing-library 없음. Phase 1 에서 **함께 도입**. "테스트 나중에" 는 회귀 가드 없는 상태로 8 phase 레이어링하다 3개 phase 전에 깨진 걸 발견한다.

---

## 9. 스케일 고려사항

| 관점 | 100 메시지 | 1000 메시지 | 10k+ 메시지 |
|------|-----------|-------------|-------------|
| MessageList 렌더 | OK, diff 빠름 | 측정: 토큰당 <16ms 인지 | tail -200 슬라이싱 or 가상화 |
| Token 스트림 backpressure | — | 측정 필요 | requestAnimationFrame throttle |
| 세션 길이 → context | 서버가 compact | 서버가 compact | 서버가 compact |
| Store 업데이트 | — | Zustand selector + shallow 필수 | devtools 비활성 (무효화 비용) |

**현 milestone 스케일:** 단일 세션 평균 30-50 turn, messages 100-200 → 가상화 불필요.

---

## 10. Sources

- [vadimdemedes/ink — React in terminal](https://github.com/vadimdemedes/ink) (HIGH, 공식)
- [ink-testing-library](https://github.com/vadimdemedes/ink-testing-library) (HIGH, 공식)
- [Zustand docs — no-store actions pattern](https://zustand.docs.pmnd.rs/guides/practice-with-no-store-actions) (HIGH, 공식)
- [zustand#1796 — TS + Immer + slices 문제](https://github.com/pmndrs/zustand/discussions/1796) (HIGH, 공식 이슈)
- [zustand#2491 — TS slices 패턴](https://github.com/pmndrs/zustand/discussions/2491) (HIGH, 공식 이슈)
- [TypeScript discriminated unions — 실무 예시](https://www.codespud.com/2025/discriminated-unions-examples-typescript/) (MEDIUM, 블로그)
- [Exploring UIs in terminal — Ink 가이드](https://cekrem.github.io/posts/do-more-stuff-cli-tool-part-1/) (MEDIUM, 블로그)
- `/Users/johyeonchang/harness/harness_server.py` (HIGH, 내부 코드 — 프로토콜 확정 근거)
- `/Users/johyeonchang/harness/ui/index.js` (HIGH, 내부 코드 — 기존 클라 동작 참조)
- `/Users/johyeonchang/harness/.planning/BB-2-DESIGN.md` (HIGH, 내부 설계 문서)
