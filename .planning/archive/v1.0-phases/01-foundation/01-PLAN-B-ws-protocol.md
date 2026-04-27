---
phase: 01-foundation
plan: B
type: execute
wave: 1
depends_on: []
files_modified:
  - ui-ink/src/protocol.ts
  - ui-ink/src/ws/client.ts
  - ui-ink/src/ws/parse.ts
  - ui-ink/src/ws/dispatch.ts
  - ui-ink/src/store/messages.ts
  - ui-ink/src/store/input.ts
  - ui-ink/src/store/status.ts
  - ui-ink/src/store/room.ts
  - ui-ink/src/store/confirm.ts
  - ui-ink/src/store/index.ts
autonomous: true
requirements:
  - FND-03
  - FND-04
  - FND-05
  - FND-06
  - FND-07
  - FND-08

must_haves:
  truths:
    - "src/protocol.ts 에 25개 ServerMsg discriminated union 이 정의된다"
    - "dispatch.ts 의 exhaustive switch 에서 미처리 이벤트가 컴파일 에러로 탐지된다"
    - "on_token / on_tool / error.message 이벤트 이름이 코드 어디에도 없다 (token / tool_start+tool_end / error.text 로 교정)"
    - "스트리밍 토큰이 마지막 메시지 content += 방식으로 처리된다 (매 토큰 새 push 금지)"
    - "각 메시지에 crypto.randomUUID() id 가 부여되고 React key 로 사용된다"
    - "store 가 5개 슬라이스(messages/input/status/room/confirm)로 분할된다"
  artifacts:
    - path: "ui-ink/src/protocol.ts"
      provides: "ServerMsg / ClientMsg discriminated union"
      exports: ["ServerMsg", "ClientMsg", "TokenMsg", "AgentStartMsg", "AgentEndMsg", "ErrorMsg"]
    - path: "ui-ink/src/ws/client.ts"
      provides: "HarnessClient 클래스"
      exports: ["HarnessClient"]
    - path: "ui-ink/src/ws/parse.ts"
      provides: "JSON → ServerMsg 파서"
      exports: ["parseServerMsg"]
    - path: "ui-ink/src/ws/dispatch.ts"
      provides: "ServerMsg → store action 디스패처"
      exports: ["dispatch"]
    - path: "ui-ink/src/store/index.ts"
      provides: "통합 스토어 export"
      exports: ["useStore", "useMessagesStore", "useInputStore", "useStatusStore", "useRoomStore", "useConfirmStore"]
  key_links:
    - from: "ui-ink/src/ws/parse.ts"
      to: "ui-ink/src/protocol.ts"
      via: "parseServerMsg 리턴 타입"
      pattern: "ServerMsg"
    - from: "ui-ink/src/ws/dispatch.ts"
      to: "ui-ink/src/store/index.ts"
      via: "useStore.getState() 직접 호출"
      pattern: "useStore.getState"
    - from: "ui-ink/src/ws/client.ts"
      to: "ui-ink/src/ws/dispatch.ts"
      via: "ws.on('message') 콜백"
      pattern: "dispatch"
---

<objective>
WS 레이어와 Zustand 스토어를 재구성해 실제 harness_server.py 프로토콜과 정합성을 맞추고 Phase 2+ 가 의존할 수 있는 타입 안전한 기반을 만든다.

Purpose: 현재 스켈레톤은 on_token/on_tool 이라는 허구의 이벤트 이름을 구독하고, 매 토큰마다 새 메시지를 push 하며, store 가 단일 파일이다. 어떤 렌더도 동작하지 않는 상태다. 이 plan 은 프로토콜 이름 불일치와 store 구조를 전면 교정한다.
Output: src/protocol.ts, src/ws/{client,parse,dispatch}.ts, src/store/{messages,input,status,room,confirm,index}.ts
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/johyeonchang/harness/.planning/PROJECT.md
@/Users/johyeonchang/harness/.planning/ROADMAP.md
@/Users/johyeonchang/harness/.planning/BB-2-DESIGN.md
@/Users/johyeonchang/harness/CLAUDE.md

<interfaces>
<!-- harness_server.py 가 실제로 broadcast/send 하는 이벤트 (ground truth) -->
서버 → 클라 이벤트 (25종):
  token          { type: 'token', text: string }
  tool_start     { type: 'tool_start', name: string, args: object }
  tool_end       { type: 'tool_end', name: string, result: string }
  agent_start    { type: 'agent_start' }
  agent_end      { type: 'agent_end' }
  error          { type: 'error', text: string }        ← .message 아님, .text
  confirm_write  { type: 'confirm_write', path: string }
  confirm_bash   { type: 'confirm_bash', command: string }
  cplan_confirm  { type: 'cplan_confirm', task: string }
  ready          { type: 'ready', room: string }
  room_joined    { type: 'room_joined', room: string, members: string[] }
  room_member_joined { type: 'room_member_joined', user: string }
  room_member_left   { type: 'room_member_left', user: string }
  room_busy      { type: 'room_busy' }
  state_snapshot { type: 'state_snapshot', ... }  (state payload 와 동일 구조)
  state          { type: 'state', working_dir: string, model: string, mode: string, turns: number, ctx_tokens?: number }
  slash_result   { type: 'slash_result', cmd: string, [key: string]: unknown }
  info           { type: 'info', text: string }
  quit           { type: 'quit' }
  queue          { type: 'queue', position: number }
  queue_ready    { type: 'queue_ready' }
  pong           { type: 'pong' }
  claude_start   { type: 'claude_start' }
  claude_end     { type: 'claude_end' }
  claude_token   { type: 'claude_token', text: string }

클라 → 서버 이벤트:
  input          { type: 'input', text: string }
  confirm_write_response  { type: 'confirm_write_response', accept: boolean }
  confirm_bash_response   { type: 'confirm_bash_response', accept: boolean }
  slash          { type: 'slash', name: string, args?: string }
  ping           { type: 'ping' }

<!-- 현재 스켈레톤 파일 목록 (교체 대상) -->
삭제/교체 대상: ui-ink/src/ws.ts, ui-ink/src/store.ts
이 파일들의 역할을 src/ws/*.ts 와 src/store/*.ts 로 분산한다.

<!-- ARCHITECTURE.md 의 appendToken 패턴 -->
appendToken: (text: string) => set((s) => {
  const last = s.messages[s.messages.length - 1]
  if (last?.role === 'assistant' && last.streaming) {
    return { messages: [...s.messages.slice(0, -1), {...last, content: last.content + text}] }
  }
  return { messages: [...s.messages, {id: crypto.randomUUID(), role: 'assistant', content: text, streaming: true}] }
})
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task B-1: src/protocol.ts 신설 — 25개 ServerMsg discriminated union</name>
  <files>ui-ink/src/protocol.ts</files>
  <read_first>
    - /Users/johyeonchang/harness/harness_server.py (send/broadcast 호출에서 실제 type 값과 페이로드 필드 확인 — 위 interfaces 참조)
    - /Users/johyeonchang/harness/.planning/research/ARCHITECTURE.md (discriminated union 패턴 확인)
  </read_first>
  <action>
`ui-ink/src/protocol.ts` 를 새로 생성한다. 기존 ws.ts / store.ts 는 이 태스크에서 수정하지 않는다.

아래 구조를 따른다:

```typescript
// harness WS 프로토콜 타입 정의 (FND-04)
// ground truth: harness_server.py 의 send/broadcast 호출

// 서버 → 클라 메시지 타입들
export interface TokenMsg       { type: 'token';           text: string }
export interface ToolStartMsg   { type: 'tool_start';      name: string; args: Record<string, unknown> }
export interface ToolEndMsg     { type: 'tool_end';        name: string; result: string }
export interface AgentStartMsg  { type: 'agent_start' }
export interface AgentEndMsg    { type: 'agent_end' }
export interface ErrorMsg       { type: 'error';           text: string }   // .text, NOT .message
export interface InfoMsg        { type: 'info';            text: string }
export interface ConfirmWriteMsg { type: 'confirm_write';  path: string }
export interface ConfirmBashMsg  { type: 'confirm_bash';   command: string }
export interface CplanConfirmMsg { type: 'cplan_confirm';  task: string }
export interface ReadyMsg        { type: 'ready';          room: string }
export interface RoomJoinedMsg   { type: 'room_joined';    room: string; members: string[] }
export interface RoomMemberJoinedMsg { type: 'room_member_joined'; user: string }
export interface RoomMemberLeftMsg  { type: 'room_member_left';   user: string }
export interface RoomBusyMsg     { type: 'room_busy' }
export interface StateSnapshotMsg { type: 'state_snapshot'; working_dir: string; model: string; mode: string; turns: number; ctx_tokens?: number; messages?: unknown[] }
export interface StateMsg        { type: 'state';          working_dir: string; model: string; mode: string; turns: number; ctx_tokens?: number }
export interface SlashResultMsg  { type: 'slash_result';   cmd: string;  [key: string]: unknown }
export interface QuitMsg         { type: 'quit' }
export interface QueueMsg        { type: 'queue';          position: number }
export interface QueueReadyMsg   { type: 'queue_ready' }
export interface PongMsg         { type: 'pong' }
export interface ClaudeStartMsg  { type: 'claude_start' }
export interface ClaudeEndMsg    { type: 'claude_end' }
export interface ClaudeTokenMsg  { type: 'claude_token';   text: string }

// discriminated union — 모든 서버 메시지
export type ServerMsg =
  | TokenMsg | ToolStartMsg | ToolEndMsg
  | AgentStartMsg | AgentEndMsg
  | ErrorMsg | InfoMsg
  | ConfirmWriteMsg | ConfirmBashMsg | CplanConfirmMsg
  | ReadyMsg
  | RoomJoinedMsg | RoomMemberJoinedMsg | RoomMemberLeftMsg | RoomBusyMsg
  | StateSnapshotMsg | StateMsg
  | SlashResultMsg
  | QuitMsg | QueueMsg | QueueReadyMsg | PongMsg
  | ClaudeStartMsg | ClaudeEndMsg | ClaudeTokenMsg

// 클라 → 서버 메시지 타입들
export interface InputMsg              { type: 'input';                  text: string }
export interface ConfirmWriteResponse  { type: 'confirm_write_response'; accept: boolean }
export interface ConfirmBashResponse   { type: 'confirm_bash_response';  accept: boolean }
export interface SlashMsg              { type: 'slash';                  name: string; args?: string }
export interface PingMsg               { type: 'ping' }

export type ClientMsg =
  | InputMsg | ConfirmWriteResponse | ConfirmBashResponse | SlashMsg | PingMsg
```

exhaustive switch 가드 헬퍼도 추가한다:
```typescript
// exhaustive switch 가드 — dispatch.ts 에서 미처리 이벤트를 컴파일 에러로 탐지
export function assertNever(x: never): never {
  throw new Error(`Unhandled ServerMsg type: ${(x as { type: string }).type}`)
}
```
  </action>
  <verify>
    <automated>cd /Users/johyeonchang/harness/ui-ink && grep -c "export interface\|export type" src/protocol.ts</automated>
  </verify>
  <acceptance_criteria>
    - src/protocol.ts 파일 존재
    - `export type ServerMsg =` 포함
    - `export type ClientMsg =` 포함
    - `export function assertNever` 포함
    - `TokenMsg`, `ToolStartMsg`, `ToolEndMsg`, `AgentStartMsg`, `AgentEndMsg`, `ErrorMsg` 인터페이스 모두 포함
    - `ConfirmWriteMsg`, `ConfirmBashMsg`, `RoomJoinedMsg`, `StateSnapshotMsg`, `SlashResultMsg` 포함
    - ErrorMsg 의 필드가 `.text` (`.message` 아님)
    - grep `on_token\|on_tool\|error\.message` src/protocol.ts → 0건
  </acceptance_criteria>
  <done>src/protocol.ts 생성, 25개 타입 정의, assertNever 헬퍼 포함</done>
</task>

<task type="auto" tdd="false">
  <name>Task B-2: src/store/ 5 슬라이스 + src/ws/{parse,dispatch,client}.ts</name>
  <files>
    ui-ink/src/store/messages.ts,
    ui-ink/src/store/input.ts,
    ui-ink/src/store/status.ts,
    ui-ink/src/store/room.ts,
    ui-ink/src/store/confirm.ts,
    ui-ink/src/store/index.ts,
    ui-ink/src/ws/parse.ts,
    ui-ink/src/ws/dispatch.ts,
    ui-ink/src/ws/client.ts
  </files>
  <read_first>
    - /Users/johyeonchang/harness/ui-ink/src/protocol.ts (방금 생성 — 타입 임포트 기준)
    - /Users/johyeonchang/harness/ui-ink/src/store.ts (현 단일 store — 기존 Message/StatusSegment 타입 참조)
    - /Users/johyeonchang/harness/ui-ink/src/ws.ts (현 ws.ts — on_token/on_tool 등 교정 대상 패턴 확인)
    - /Users/johyeonchang/harness/.planning/research/ARCHITECTURE.md (appendToken in-place 패턴, store 슬라이스 설계)
  </read_first>
  <action>
9개 파일을 신규 생성한다. 기존 `src/store.ts` 와 `src/ws.ts` 는 이 태스크에서 삭제하지 않는다 (Plan C 의 App.tsx/index.tsx 교체 후 삭제). 단, 새 파일들이 기존 파일을 import 하지 않도록 주의.

디렉토리 생성:
- `ui-ink/src/store/`
- `ui-ink/src/ws/`

---

**src/store/messages.ts** — 메시지 슬라이스:

```typescript
// 메시지 슬라이스 — 스트리밍 in-place 업데이트 패턴 (FND-07, FND-08)
import {create} from 'zustand'

export interface Message {
  id: string               // crypto.randomUUID() — React key 용 (FND-08)
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  streaming?: boolean      // 스트리밍 중인 assistant 메시지
  toolName?: string        // tool 메시지용
  meta?: Record<string, unknown>
}

interface MessagesState {
  messages: Message[]
  appendUserMessage: (content: string) => void
  agentStart: () => void
  appendToken: (text: string) => void    // in-place update, NOT push (FND-07)
  agentEnd: () => void
  appendToolStart: (name: string, args: Record<string, unknown>) => void
  appendToolEnd: (name: string, result: string) => void
  appendSystemMessage: (content: string) => void
  clearMessages: () => void
}

export const useMessagesStore = create<MessagesState>((set) => ({
  messages: [],

  appendUserMessage: (content) => set((s) => ({
    messages: [...s.messages, {id: crypto.randomUUID(), role: 'user', content}]
  })),

  agentStart: () => set((s) => ({
    messages: [...s.messages, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      streaming: true
    }]
  })),

  // 마지막 assistant streaming 메시지에 in-place append (새 push 금지)
  appendToken: (text) => set((s) => {
    const last = s.messages[s.messages.length - 1]
    if (last?.role === 'assistant' && last.streaming) {
      return {
        messages: [
          ...s.messages.slice(0, -1),
          {...last, content: last.content + text}
        ]
      }
    }
    // agentStart 없이 토큰이 오는 경우 방어 처리
    return {
      messages: [...s.messages, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: text,
        streaming: true
      }]
    }
  }),

  agentEnd: () => set((s) => {
    const last = s.messages[s.messages.length - 1]
    if (last?.role === 'assistant' && last.streaming) {
      return {
        messages: [...s.messages.slice(0, -1), {...last, streaming: false}]
      }
    }
    return {}
  }),

  appendToolStart: (name, args) => set((s) => ({
    messages: [...s.messages, {
      id: crypto.randomUUID(),
      role: 'tool',
      content: `[${name}] ${JSON.stringify(args)}`,
      toolName: name,
      streaming: true
    }]
  })),

  appendToolEnd: (name, result) => set((s) => {
    const idx = [...s.messages].reverse().findIndex(
      (m) => m.role === 'tool' && m.toolName === name && m.streaming
    )
    if (idx === -1) return {}
    const realIdx = s.messages.length - 1 - idx
    const updated = {...s.messages[realIdx], content: `[${name}] ${result}`, streaming: false}
    return {
      messages: [
        ...s.messages.slice(0, realIdx),
        updated,
        ...s.messages.slice(realIdx + 1)
      ]
    }
  }),

  appendSystemMessage: (content) => set((s) => ({
    messages: [...s.messages, {id: crypto.randomUUID(), role: 'system', content}]
  })),

  clearMessages: () => set({messages: []}),
}))
```

---

**src/store/input.ts** — 입력 슬라이스:

```typescript
// 입력 슬라이스
import {create} from 'zustand'

interface InputState {
  buffer: string
  setBuffer: (v: string) => void
  clearBuffer: () => void
}

export const useInputStore = create<InputState>((set) => ({
  buffer: '',
  setBuffer: (v) => set({buffer: v}),
  clearBuffer: () => set({buffer: ''}),
}))
```

---

**src/store/status.ts** — 상태 표시줄 슬라이스:

```typescript
// 상태 표시줄 슬라이스
import {create} from 'zustand'

export interface StatusSegment {
  label: string
  color?: string
}

interface StatusState {
  connected: boolean
  workingDir: string
  model: string
  mode: string
  turns: number
  ctxTokens?: number
  busy: boolean
  setConnected: (v: boolean) => void
  setState: (s: {working_dir?: string; model?: string; mode?: string; turns?: number; ctx_tokens?: number}) => void
  setBusy: (v: boolean) => void
}

export const useStatusStore = create<StatusState>((set) => ({
  connected: false,
  workingDir: '',
  model: '',
  mode: '',
  turns: 0,
  ctxTokens: undefined,
  busy: false,
  setConnected: (v) => set({connected: v}),
  setState: (s) => set((cur) => ({
    workingDir: s.working_dir ?? cur.workingDir,
    model: s.model ?? cur.model,
    mode: s.mode ?? cur.mode,
    turns: s.turns ?? cur.turns,
    ctxTokens: s.ctx_tokens ?? cur.ctxTokens,
  })),
  setBusy: (v) => set({busy: v}),
}))
```

---

**src/store/room.ts** — 룸 슬라이스:

```typescript
// 룸 슬라이스 (Phase 3 에서 확장 예정)
import {create} from 'zustand'

interface RoomState {
  roomName: string
  members: string[]
  activeInputFrom: string | null  // turn-taking (BB-2-DESIGN)
  activeIsSelf: boolean
  busy: boolean
  setRoom: (name: string, members: string[]) => void
  addMember: (user: string) => void
  removeMember: (user: string) => void
  setActiveInputFrom: (user: string | null) => void
  setActiveIsSelf: (v: boolean) => void
  setRoomBusy: (v: boolean) => void
}

export const useRoomStore = create<RoomState>((set) => ({
  roomName: '',
  members: [],
  activeInputFrom: null,
  activeIsSelf: true,
  busy: false,
  setRoom: (name, members) => set({roomName: name, members}),
  addMember: (user) => set((s) => ({members: [...s.members.filter(m => m !== user), user]})),
  removeMember: (user) => set((s) => ({members: s.members.filter(m => m !== user)})),
  setActiveInputFrom: (user) => set({activeInputFrom: user}),
  setActiveIsSelf: (v) => set({activeIsSelf: v}),
  setRoomBusy: (v) => set({busy: v}),
}))
```

---

**src/store/confirm.ts** — confirm 다이얼로그 슬라이스:

```typescript
// confirm 다이얼로그 슬라이스 (Phase 2 에서 완성)
import {create} from 'zustand'

export type ConfirmMode = 'none' | 'confirm_write' | 'confirm_bash' | 'cplan_confirm'

interface ConfirmState {
  mode: ConfirmMode
  payload: Record<string, unknown>
  setConfirm: (mode: ConfirmMode, payload: Record<string, unknown>) => void
  clearConfirm: () => void
}

export const useConfirmStore = create<ConfirmState>((set) => ({
  mode: 'none',
  payload: {},
  setConfirm: (mode, payload) => set({mode, payload}),
  clearConfirm: () => set({mode: 'none', payload: {}}),
}))
```

---

**src/store/index.ts** — 통합 re-export:

```typescript
// 스토어 통합 export (FND-06)
export {useMessagesStore} from './messages.js'
export type {Message} from './messages.js'
export {useInputStore} from './input.js'
export {useStatusStore} from './status.js'
export type {StatusSegment} from './status.js'
export {useRoomStore} from './room.js'
export {useConfirmStore} from './confirm.js'
export type {ConfirmMode} from './confirm.js'
```

---

**src/ws/parse.ts** — JSON → ServerMsg 파서:

```typescript
// JSON raw → ServerMsg 파서 (FND-04, FND-05)
import type {ServerMsg} from '../protocol.js'

export function parseServerMsg(raw: string): ServerMsg | null {
  try {
    const obj = JSON.parse(raw) as {type?: unknown}
    if (typeof obj?.type !== 'string') return null
    return obj as ServerMsg
  } catch {
    return null
  }
}
```

---

**src/ws/dispatch.ts** — ServerMsg → store action 디스패처 (exhaustive switch):

```typescript
// ServerMsg → store action exhaustive switch 디스패처 (FND-04, FND-05)
// WS 레이어는 React 훅 바깥에서 useStore.getState() 를 직접 호출한다.
import type {ServerMsg} from '../protocol.js'
import {assertNever} from '../protocol.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'

export function dispatch(msg: ServerMsg): void {
  const messages = useMessagesStore.getState()
  const status = useStatusStore.getState()
  const room = useRoomStore.getState()
  const confirm = useConfirmStore.getState()

  switch (msg.type) {
    case 'token':
      messages.appendToken(msg.text)
      break

    case 'tool_start':
      messages.appendToolStart(msg.name, msg.args)
      break

    case 'tool_end':
      messages.appendToolEnd(msg.name, msg.result)
      break

    case 'agent_start':
      messages.agentStart()
      status.setBusy(true)
      break

    case 'agent_end':
      messages.agentEnd()
      status.setBusy(false)
      break

    case 'error':
      messages.appendSystemMessage(`오류: ${msg.text}`)
      status.setBusy(false)
      break

    case 'info':
      messages.appendSystemMessage(msg.text)
      break

    case 'confirm_write':
      confirm.setConfirm('confirm_write', {path: msg.path})
      break

    case 'confirm_bash':
      confirm.setConfirm('confirm_bash', {command: msg.command})
      break

    case 'cplan_confirm':
      confirm.setConfirm('cplan_confirm', {task: msg.task})
      break

    case 'ready':
      status.setConnected(true)
      break

    case 'room_joined':
      room.setRoom(msg.room, msg.members)
      break

    case 'room_member_joined':
      room.addMember(msg.user)
      messages.appendSystemMessage(`[${msg.user}] 님이 참가했습니다`)
      break

    case 'room_member_left':
      room.removeMember(msg.user)
      messages.appendSystemMessage(`[${msg.user}] 님이 나갔습니다`)
      break

    case 'room_busy':
      room.setRoomBusy(true)
      break

    case 'state':
    case 'state_snapshot':
      status.setState({
        working_dir: msg.working_dir,
        model: msg.model,
        mode: msg.mode,
        turns: msg.turns,
        ctx_tokens: msg.ctx_tokens,
      })
      break

    case 'slash_result':
      // Phase 2 에서 cmd 별 처리 확장 예정 — 현재는 시스템 메시지로 표시
      messages.appendSystemMessage(`/${msg.cmd} 완료`)
      break

    case 'quit':
      // Phase 3 의 useApp().exit() 연동 — 현재는 상태 표시만
      messages.appendSystemMessage('서버 종료 요청')
      break

    case 'queue':
      messages.appendSystemMessage(`큐 대기 중 (${msg.position}번째)`)
      break

    case 'queue_ready':
      messages.appendSystemMessage('큐 준비 완료')
      break

    case 'pong':
      // heartbeat 응답 — 무시
      break

    case 'claude_start':
      status.setBusy(true)
      break

    case 'claude_end':
      status.setBusy(false)
      break

    case 'claude_token':
      messages.appendToken(msg.text)
      break

    default:
      // exhaustive switch — 위에서 처리 안 된 타입은 컴파일 에러
      assertNever(msg)
  }
}
```

---

**src/ws/client.ts** — HarnessClient 클래스:

```typescript
// HarnessClient — WS 연결 · send · heartbeat (FND-05)
// reconnect / backoff 는 Phase 3 (WSR-01) 에서 완성
import WebSocket from 'ws'
import {parseServerMsg} from './parse.js'
import {dispatch} from './dispatch.js'
import {useStatusStore} from '../store/status.js'

export interface ConnectOptions {
  url: string
  token: string
  room?: string
}

export class HarnessClient {
  private ws: WebSocket | null = null
  private opts: ConnectOptions
  private pingInterval: ReturnType<typeof setInterval> | null = null

  constructor(opts: ConnectOptions) {
    this.opts = opts
  }

  connect(): void {
    const headers: Record<string, string> = {
      'x-harness-token': this.opts.token,
    }
    if (this.opts.room) headers['x-harness-room'] = this.opts.room

    this.ws = new WebSocket(this.opts.url, {headers})

    this.ws.on('open', () => {
      useStatusStore.getState().setConnected(true)
      // heartbeat
      this.pingInterval = setInterval(() => {
        this.send({type: 'ping'})
      }, 30_000)
    })

    this.ws.on('message', (raw) => {
      const msg = parseServerMsg(raw.toString())
      if (msg) dispatch(msg)
    })

    this.ws.on('close', () => {
      useStatusStore.getState().setConnected(false)
      this._clearPing()
      // Phase 3 에서 jitter backoff reconnect 추가
    })

    this.ws.on('error', (err) => {
      const {appendSystemMessage} = (await import('../store/messages.js')).useMessagesStore.getState()
      appendSystemMessage(`ws 오류: ${err.message}`)
    })
  }

  send(msg: import('../protocol.js').ClientMsg): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  close(): void {
    this._clearPing()
    this.ws?.close()
    this.ws = null
  }

  private _clearPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }
}
```

주의:
- `ws.on('error')` 콜백 안 동적 import 는 TypeScript 에서 async 가 필요하다. 대신 생성자에서 import 를 미리 받거나, 파일 상단에 import 해둔다. 아래와 같이 수정:

```typescript
// 파일 상단에서 import
import {useMessagesStore} from '../store/messages.js'

// ws.on('error') 콜백에서
this.ws.on('error', (err) => {
  useMessagesStore.getState().appendSystemMessage(`ws 오류: ${err.message}`)
})
```

기존 `src/store.ts` 와 `src/ws.ts` 는 이 태스크에서 삭제하지 않는다. Plan C(App.tsx / index.tsx 재작성) 에서 임포트 교체 후 삭제한다.
  </action>
  <verify>
    <automated>cd /Users/johyeonchang/harness/ui-ink && ls src/store/ && ls src/ws/ && grep 'assertNever' src/ws/dispatch.ts && grep 'appendToken' src/store/messages.ts && echo "OK"</automated>
  </verify>
  <acceptance_criteria>
    - src/store/ 디렉토리에 messages.ts, input.ts, status.ts, room.ts, confirm.ts, index.ts 6개 파일 존재
    - src/ws/ 디렉토리에 parse.ts, dispatch.ts, client.ts 3개 파일 존재
    - dispatch.ts 에 `assertNever(msg)` 호출 포함 (exhaustive switch)
    - dispatch.ts 에 `case 'on_token':`, `case 'on_tool':` 없음 (교정된 이름 사용)
    - dispatch.ts 에 `case 'token':`, `case 'tool_start':`, `case 'tool_end':` 포함
    - dispatch.ts 에 `case 'error':` 에서 `msg.text` 사용 (`msg.message` 아님)
    - messages.ts 에 `appendToken` 함수 내 `...s.messages.slice(0, -1), {...last, content: last.content + text}` 패턴 포함
    - messages.ts 에 `crypto.randomUUID()` 호출 포함
    - store/index.ts 에 6개 슬라이스 re-export 포함
    - grep `on_token\|on_tool\|error\.message` src/ws/ → 0건
    - grep `key=\{i\}\|key={i}` src/store/ → 0건 (index key 금지)
  </acceptance_criteria>
  <done>9개 파일 생성 완료, 프로토콜 이름 교정, appendToken in-place, UUID id 적용</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| WS ws.on('message') → dispatch | 서버에서 오는 JSON 이 악의적 형식일 수 있음 |
| parseServerMsg → dispatch | 파싱 실패 시 null 반환, 미파싱 이벤트 무시 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01B-01 | Tampering | WS 메시지 파싱 | mitigate | parseServerMsg 에서 JSON.parse 실패 시 null 반환, dispatch 에서 null 무시. 악의적 JSON 은 드롭 처리 |
| T-01B-02 | Spoofing | x-harness-token 헤더 | mitigate | HARNESS_TOKEN env var 를 ws 연결 헤더로 전송. 로컬 전용 서버이므로 네트워크 노출 없음 |
| T-01B-03 | Denial of Service | 고속 token 이벤트 스트림 | accept | 로컬 서버 + 3인 이하 스케일. appendToken 은 in-place 업데이트로 Zustand set 최소화 |
| T-01B-04 | Information Disclosure | ClientMsg 에 token 포함 | mitigate | HARNESS_TOKEN 은 env var 에서만 읽고 코드에 하드코딩 금지. assertNever 로 미처리 메시지 타입 컴파일 탐지 |
</threat_model>

<verification>
```bash
# 1. protocol.ts ServerMsg union 확인
grep 'export type ServerMsg' /Users/johyeonchang/harness/ui-ink/src/protocol.ts

# 2. 잘못된 이벤트 이름 없는지 확인
grep -r 'on_token\|on_tool\|error\.message' /Users/johyeonchang/harness/ui-ink/src/

# 3. dispatch exhaustive switch 확인
grep 'assertNever' /Users/johyeonchang/harness/ui-ink/src/ws/dispatch.ts

# 4. appendToken in-place 패턴 확인
grep 'slice(0, -1)' /Users/johyeonchang/harness/ui-ink/src/store/messages.ts

# 5. UUID id 부여 확인
grep 'randomUUID' /Users/johyeonchang/harness/ui-ink/src/store/messages.ts

# 6. 5 슬라이스 파일 확인
ls /Users/johyeonchang/harness/ui-ink/src/store/
ls /Users/johyeonchang/harness/ui-ink/src/ws/
```
</verification>

<success_criteria>
- src/protocol.ts 에 25개 ServerMsg discriminated union 정의
- dispatch.ts 의 default 브랜치에 assertNever 로 exhaustive switch 강제
- on_token / on_tool / error.message 가 codebase 에서 0건
- appendToken 이 마지막 메시지 in-place += 로 동작
- 각 메시지에 crypto.randomUUID() id 부여
- src/store/ 에 5 슬라이스 + index.ts
</success_criteria>

<output>
완료 후 `/Users/johyeonchang/harness/.planning/phases/01-foundation/01-B-SUMMARY.md` 생성.
</output>
