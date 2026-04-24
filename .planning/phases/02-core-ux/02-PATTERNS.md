# Phase 2: Core UX — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 20 (new/modified files from Component Breakdown)
**Analogs found:** 14 / 20 (6 files have no direct analog — new component types)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `ui-ink/src/App.tsx` | component (container) | event-driven | `ui-ink/src/App.tsx` (current) | self (rewrite) |
| `ui-ink/src/store/messages.ts` | store slice | CRUD + streaming | self (extend) | self (extend) |
| `ui-ink/src/store/input.ts` | store slice | CRUD + file I/O | `store/messages.ts` | role-match |
| `ui-ink/src/store/confirm.ts` | store slice | CRUD | self (extend) | self (extend) |
| `ui-ink/src/store/status.ts` | store slice | CRUD | self (no change) | unchanged |
| `ui-ink/src/store/room.ts` | store slice | CRUD | self (no change) | unchanged |
| `ui-ink/src/protocol.ts` | type definitions | request-response | self (extend) | self (extend) |
| `ui-ink/src/ws/dispatch.ts` | ws module | event-driven | self (extend) | self (extend) |
| `ui-ink/src/slash-catalog.ts` | utility (static data) | transform | `ui-ink/src/protocol.ts` (type convention) | partial |
| `ui-ink/src/theme.ts` | utility | transform | `ui-ink/src/tty-guard.ts` | role-match |
| `ui-ink/src/components/MessageList.tsx` | component | streaming | `App.tsx` messages render block | partial |
| `ui-ink/src/components/Message.tsx` | component | transform | `App.tsx` message Box render | partial |
| `ui-ink/src/components/ToolCard.tsx` | component | transform | `App.tsx` tool message render | partial |
| `ui-ink/src/components/DiffPreview.tsx` | component | transform | no analog | none |
| `ui-ink/src/components/InputArea.tsx` | component (container) | event-driven | `App.tsx` input row | partial |
| `ui-ink/src/components/MultilineInput.tsx` | component | event-driven | `App.tsx` useInput block | partial |
| `ui-ink/src/components/SlashPopup.tsx` | component | event-driven | no analog | none |
| `ui-ink/src/components/ConfirmDialog.tsx` | component | event-driven | `App.tsx` useInput + confirm store | partial |
| `ui-ink/src/components/StatusBar.tsx` | component | request-response | `App.tsx` status row | partial |
| `ui-ink/src/components/Divider.tsx` | component | transform | `App.tsx` divider Text | exact |

---

## Pattern Details

### Critical Cross-Cutting Constraints (apply to ALL files)

These patterns are enforced by CLAUDE.md rules and existing CI guards. Every new file must follow them.

**useShallow — multi-field Zustand selector (lines 18-27 of App.tsx):**
```typescript
// 복수 필드 구독 시 반드시 useShallow 적용 — 전체 객체 구독 금지
import {useShallow} from 'zustand/react/shallow'

// 올바른 방식
const {buffer, setBuffer, clearBuffer} = useInputStore(useShallow((s) => ({
  buffer: s.buffer,
  setBuffer: s.setBuffer,
  clearBuffer: s.clearBuffer,
})))

// 단일 필드는 useShallow 불필요
const busy = useStatusStore(s => s.busy)
```

**crypto.randomUUID() for IDs (store/messages.ts lines 29, 34, 57):**
```typescript
// 메시지 id, React key 생성 — index 사용 절대 금지
{id: crypto.randomUUID(), role: 'user', content}
// key prop도 반드시 id 사용
{messages.map((m) => <Box key={m.id} ...>)}
```

**assertNever exhaustive switch (ws/dispatch.ts lines 127-130):**
```typescript
// switch default에 반드시 포함 — 미처리 타입을 컴파일 에러로 탐지
default:
  assertNever(msg)  // never 타입 보장
```

**patchConsole: false (index.tsx line 58):**
```typescript
// render() 호출 시 patchConsole: false 유지 — 변경 금지
render(<App />, {patchConsole: false})
```

**JSX 제약 (Ink에는 DOM 태그 없음):**
```typescript
// 금지: <div>, <span>
// 허용: <Box>, <Text>, <Static>, <Newline>
import {Box, Text, Static, useInput, useApp} from 'ink'
```

**store.getState() 직접 호출 패턴 (ws/dispatch.ts lines 11-14):**
```typescript
// WS 레이어(React hook 바깥)에서는 getState() 직접 호출
const messages = useMessagesStore.getState()
const status = useStatusStore.getState()
```

---

### `ui-ink/src/App.tsx` (전면 재작성)

**Analog:** `ui-ink/src/App.tsx` (현재 Phase 1 구현)
**Role:** 레이아웃 컨테이너. WS lifecycle, 전역 키 처리, resize useEffect.

**현재 import 패턴 (lines 1-9):**
```typescript
import React, {useEffect, useRef} from 'react'
import {Box, Text, useApp, useInput} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from './store/messages.js'
import {useStatusStore} from './store/status.js'
import {useInputStore} from './store/input.js'
import {HarnessClient} from './ws/client.js'
```

**WS lifecycle 패턴 (lines 34-51) — 변경 없이 재사용:**
```typescript
const clientRef = useRef<HarnessClient | null>(null)

useEffect(() => {
  const url = process.env['HARNESS_URL']
  const token = process.env['HARNESS_TOKEN']
  if (url && token) {
    const client = new HarnessClient({url, token, room: process.env['HARNESS_ROOM']})
    client.connect()
    clientRef.current = client
    return () => {
      client.close()
      clientRef.current = null
    }
  }
}, [])
```

**useInput 전역 키 패턴 (lines 53-80) — Phase 2에서 Ctrl+C/D 확장:**
```typescript
useInput((ch, key) => {
  if (key.ctrl && ch === 'c') { exit(); return }
  if (key.return) {
    const text = buffer.trim()
    clearBuffer()
    if (!text) return
    useMessagesStore.getState().appendUserMessage(text)
    clientRef.current?.send({type: 'input', text})
  }
  // ...
})
```

**JSX 레이아웃 패턴 (lines 85-132):**
```typescript
return (
  <Box flexDirection='column'>
    {/* 컴포넌트 트리 — <div>/<span> 금지, <Box>/<Text> 사용 */}
    <Box flexDirection='column'>...</Box>
    <Text dimColor>{'─'.repeat(40)}</Text>
    <Box>...</Box>
  </Box>
)
```

**Phase 2 delta:**
- `import {useStdout, Static} from 'ink'` 추가
- `spinRef` 제거 → `<Spinner>` from `ink-spinner`
- `messages.map(...)` 인라인 렌더 → `<MessageList>` 컴포넌트로 추출
- 입력 행 인라인 → `<InputArea>` / `<ConfirmDialog>` 조건부 렌더
- 상태 표시줄 인라인 → `<StatusBar>` 컴포넌트로 추출
- `<Divider>` 컴포넌트 사용 (터미널 폭 기반)
- resize useEffect 추가 (`useStdout().stdout.on('resize')`)
- Ctrl+C cancel stub (D-07, D-08): `ctrlCCount useRef` + 2초 타이머

---

### `ui-ink/src/store/messages.ts` (확장)

**Analog:** self (현재 구현을 확장)
**Role:** 메시지 슬라이스. completedMessages/activeMessage 분리 추가.

**현재 인터페이스 패턴 (lines 13-23):**
```typescript
interface MessagesState {
  messages: Message[]
  appendUserMessage: (content: string) => void
  agentStart: () => void
  appendToken: (text: string) => void    // in-place update
  agentEnd: () => void
  appendToolStart: (name: string, args: Record<string, unknown>) => void
  appendToolEnd: (name: string, result: string) => void
  appendSystemMessage: (content: string) => void
  clearMessages: () => void
}
```

**in-place token append 핵심 패턴 (lines 42-61) — 변경 없이 유지:**
```typescript
appendToken: (text) => set((s) => {
  const last = s.messages[s.messages.length - 1]
  if (last?.role === 'assistant' && last.streaming) {
    return {
      messages: [...s.messages.slice(0, -1), {...last, content: last.content + text}]
    }
  }
  // 방어 처리
  return {messages: [...s.messages, {id: crypto.randomUUID(), role: 'assistant', content: text, streaming: true}]}
}),
```

**reverse-find tool 업데이트 패턴 (lines 83-97):**
```typescript
appendToolEnd: (name, result) => set((s) => {
  const idx = [...s.messages].reverse().findIndex(
    (m) => m.role === 'tool' && m.toolName === name && m.streaming
  )
  if (idx === -1) return {}
  const realIdx = s.messages.length - 1 - idx
  // ...
})
```

**store 초기화 패턴 (dispatch.test.ts line 9):**
```typescript
// 테스트에서 store 상태 직접 리셋
useMessagesStore.setState({messages: []})
```

**Phase 2 delta:**
- `messages: Message[]` → `completedMessages: Message[]` + `activeMessage: Message | null` 분리
- `agentStart()` → `activeMessage` 생성
- `appendToken()` → `activeMessage.content` in-place update
- `agentEnd()` → `activeMessage`를 `completedMessages`에 push + `activeMessage = null`
- `clearMessages()` → `completedMessages: []`, `activeMessage: null` 동시 초기화
- 기존 테스트의 `messages` 참조를 `completedMessages` + `activeMessage` 검증으로 업데이트

---

### `ui-ink/src/store/input.ts` (확장)

**Analog:** `ui-ink/src/store/messages.ts` (동일 create 패턴)
**Role:** 입력 버퍼 슬라이스. history, slashOpen 상태 추가.

**현재 구현 (lines 1-14) — 기반 패턴:**
```typescript
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

**Phase 2 delta:**
- `history: string[]`, `historyIndex: number` (-1 = 현재 버퍼) 추가
- `slashOpen: boolean` 추가
- `loadHistory()` / `appendHistory()` actions 추가 (node:fs 동기 I/O)
- `HISTORY_PATH = join(homedir(), '.harness', 'history.txt')`
- import 추가: `import {readFileSync, appendFileSync, existsSync, mkdirSync} from 'node:fs'`

---

### `ui-ink/src/store/confirm.ts` (확장)

**Analog:** self (현재 구현을 확장)
**Role:** Confirm 다이얼로그 슬라이스. stickyDeny 상태 추가.

**현재 인터페이스 패턴 (lines 4-18):**
```typescript
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

**Phase 2 delta:**
- `deniedPaths: Set<string>` 추가 (sticky-deny for confirm_write)
- `deniedCmds: Set<string>` 추가 (sticky-deny for confirm_bash)
- `addDenied(type: 'path' | 'cmd', key: string)` action 추가
- `isDenied(type: 'path' | 'cmd', key: string): boolean` selector 추가
- `clearDenied()` action 추가 (agentEnd 시 호출)
- `resolve(accept: boolean)` action 추가 — HarnessClient.send 직접 호출 패턴: `client.send({type: 'confirm_write_response', accept})`

---

### `ui-ink/src/protocol.ts` (확장)

**Analog:** self (현재 구현을 확장)
**Role:** WS 메시지 타입 정의. CancelMsg 추가.

**현재 ClientMsg union 패턴 (lines 55-62):**
```typescript
export interface InputMsg             { type: 'input';                  text: string }
export interface ConfirmWriteResponse { type: 'confirm_write_response'; accept: boolean }
export interface ConfirmBashResponse  { type: 'confirm_bash_response';  accept: boolean }
export interface SlashMsg             { type: 'slash';                  name: string; args?: string }
export interface PingMsg              { type: 'ping' }

export type ClientMsg =
  | InputMsg | ConfirmWriteResponse | ConfirmBashResponse | SlashMsg | PingMsg
```

**assertNever 패턴 (lines 66-68) — 변경 없이 유지:**
```typescript
export function assertNever(x: never): never {
  throw new Error(`Unhandled ServerMsg type: ${(x as { type: string }).type}`)
}
```

**Phase 2 delta:**
- `export interface CancelMsg { type: 'cancel' }` 추가
- `ClientMsg` union에 `| CancelMsg` 추가
- ServerMsg union은 변경 없음

---

### `ui-ink/src/ws/dispatch.ts` (확장)

**Analog:** self (현재 구현을 확장)
**Role:** ServerMsg exhaustive switch 디스패처.

**exhaustive switch 패턴 (lines 10-131) — 케이스 추가 시 동일 패턴:**
```typescript
export function dispatch(msg: ServerMsg): void {
  const messages = useMessagesStore.getState()
  const status = useStatusStore.getState()
  // ...

  switch (msg.type) {
    case 'token':
      messages.appendToken(msg.text)
      break
    // ...
    case 'slash_result':
      // Phase 2에서 cmd별 처리로 교체
      messages.appendSystemMessage(`/${msg.cmd} 완료`)
      break
    default:
      assertNever(msg)  // 반드시 유지
  }
}
```

**Phase 2 delta:**
- `slash_result` case 확장: `msg.cmd` 값에 따라 분기
  - `'clear'` → `messages.clearMessages()`
  - `'cd'` → `status.setState({working_dir: msg.working_dir as string})`
  - 그 외 → 현재 시스템 메시지 유지
- `agent_end` case에 `confirm.clearDenied()` 추가 (CNF-03)
- 새 케이스 추가 시 `assertNever` default 반드시 유지

---

### `ui-ink/src/slash-catalog.ts` (신규)

**Analog:** `ui-ink/src/protocol.ts` (인터페이스 정의 파일 컨벤션)
**Role:** 13개 슬래시 명령 정적 목록.

**파일 구조 패턴 (protocol.ts 컨벤션):**
```typescript
// 파일 상단 주석 — REQ-ID 명시
// 슬래시 명령 카탈로그 (INPT-07, D-06)
// 정적 하드코딩. harness_core 변경 시 수동 동기화 필요.

export interface SlashCommand {
  name: string         // '/help' 형식
  description: string
  argHint?: string     // '/resume <id>' 형식
}

export const SLASH_CATALOG: SlashCommand[] = [
  // 13개 명령 — RESEARCH.md Pattern 4 목록 그대로
]
```

**Phase 2 delta:** 신규 파일. RESEARCH.md Pattern 4의 13개 명령 정의 사용.

---

### `ui-ink/src/theme.ts` (신규)

**Analog:** `ui-ink/src/tty-guard.ts` (순수 함수 유틸 컨벤션)
**Role:** 터미널 테마 감지 유틸.

**tty-guard.ts 순수 함수 패턴 (lines 1-11):**
```typescript
// 파일 상단 주석 — 목적과 사용처 명시
// TTY 가드 유틸 — 테스트 가능한 독립 함수로 추출 (FND-12)
// index.tsx 에서 임포트해 사용

export function isInteractiveTTY(stdin: NodeJS.ReadStream): boolean {
  return stdin.isTTY === true && typeof stdin.setRawMode === 'function'
}
```

**Phase 2 delta:**
- 신규 파일. 동일한 순수 함수 파일 구조 사용.
- `export type Theme = 'dark' | 'light'`
- `export function detectTheme(): Theme` — `process.env.COLORFGBG` / `process.env.TERM_PROGRAM` 파싱
- `export const DEFAULT_COLORS` — theme별 색 팔레트 객체

---

### `ui-ink/src/components/MessageList.tsx` (신규)

**Analog:** `App.tsx` messages render 블록 (lines 86-109)
**Role:** Static + active slot 분리 컴포넌트.

**현재 messages 렌더 패턴 (App.tsx lines 88-108) — 분리 전:**
```typescript
<Box flexDirection='column'>
  {messages.map((m) => (
    <Box key={m.id} marginBottom={0}>
      <Text color={...} bold={...}>{prefix}</Text>
      <Text wrap='wrap'>{m.content}</Text>
    </Box>
  ))}
</Box>
```

**useShallow 구독 패턴 (App.tsx lines 18-19):**
```typescript
const messages = useMessagesStore(useShallow((s) => s.messages))
```

**Phase 2 delta:**
- 신규 파일. `<Static>` + active slot 분리 패턴 도입:
```typescript
import {Box, Text, Static} from 'ink'
import Spinner from 'ink-spinner'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'

// completedMessages는 useShallow, activeMessage는 단일 필드
const completedMessages = useMessagesStore(useShallow(s => s.completedMessages))
const activeMessage = useMessagesStore(s => s.activeMessage)
const busy = useStatusStore(s => s.busy)

return (
  <Box flexDirection='column'>
    <Static items={completedMessages}>
      {(msg) => <Message key={msg.id} message={msg} />}
    </Static>
    {busy && <Spinner type='dots' />}
    {activeMessage && <Message message={activeMessage} />}
  </Box>
)
```

---

### `ui-ink/src/components/Message.tsx` (신규)

**Analog:** `App.tsx` 메시지 Box 렌더 블록 (lines 88-108)
**Role:** 단일 메시지 role별 렌더 + syntax highlight.

**현재 role별 색상/prefix 패턴 (App.tsx lines 90-106):**
```typescript
<Text
  color={
    m.role === 'user' ? 'cyan'
      : m.role === 'assistant' ? 'yellow'
      : m.role === 'tool' ? 'green'
      : 'gray'
  }
  bold={m.role !== 'system'}
>
  {m.role === 'user' ? '❯ '
    : m.role === 'assistant' ? '● '
    : m.role === 'tool' ? '└ '
    : '  '}
</Text>
<Text wrap='wrap'>{m.content}</Text>
```

**Phase 2 delta:**
- 신규 파일. props: `{message: Message}`
- role === 'tool' → `<ToolCard>` 렌더
- role === 'assistant' → 코드 펜스 파싱 + `cli-highlight` syntax highlight
- `highlight(code, {language, ignoreIllegals: true})` try/catch 래핑 필수 (fallback: 원본 반환)
- `<Text wrap='wrap'>` 사용 유지

---

### `ui-ink/src/components/ToolCard.tsx` (신규)

**Analog:** `App.tsx` tool 메시지 렌더 (role === 'tool' 분기)
**Role:** tool_start/end 1줄 요약 + 상세 펼침.

**현재 tool 렌더 패턴 (App.tsx lines 98-102):**
```typescript
// 단순 content 표시 — Phase 2에서 ToolCard로 교체
<Text color='green' bold>└ </Text>
<Text wrap='wrap'>{m.content}</Text>
```

**Phase 2 delta:**
- 신규 파일. props: `{message: Message}`
- `TOOL_META: Record<string, (args, result) => string>` 정적 테이블
- `useState(false)` 로컬 expanded 상태 — store 불필요
- pending(streaming:true) → `<Spinner>` + 도구명 표시
- completed → TOOL_META 요약 1줄 또는 fallback `[{name}]`
- Enter/Space 키 toggle (useInput + isFocused 패턴)

---

### `ui-ink/src/components/DiffPreview.tsx` (신규)

**Analog:** 없음 — 프로젝트 내 diff 렌더 컴포넌트 미존재
**Role:** diff@9 structuredPatch 결과를 Ink Box로 렌더.

**Phase 2 범위:** `old_content` 없음 (PEXT-02는 Phase 3). 새 내용 처음 10줄 미리보기만.

**참조 패턴 (RESEARCH.md Pattern 8):**
```typescript
import {Text} from 'ink'
// hunk.lines를 +/- 색으로 렌더
{hunk.lines.map((line, i) => (
  <Text
    key={`${hunkIdx}-${i}`}  // index key 금지 — hunkIdx+i 조합 사용
    color={line.startsWith('+') ? 'green' : line.startsWith('-') ? 'red' : undefined}
    dimColor={!line.startsWith('+') && !line.startsWith('-')}
  >
    {line}
  </Text>
))}
```

**주의:** key prop은 `hunkIdx-lineIdx` 조합 문자열 사용 (단순 index 금지).

---

### `ui-ink/src/components/InputArea.tsx` (신규)

**Analog:** `App.tsx` 입력 행 (lines 113-119)
**Role:** MultilineInput + SlashPopup 컨테이너.

**현재 입력 행 패턴 (App.tsx lines 114-119):**
```typescript
<Box>
  <Text color='cyan' bold>❯ </Text>
  <Text>{buffer}</Text>
  <Text color='cyan'>▌</Text>
</Box>
```

**Phase 2 delta:**
- 신규 파일. `<Box flexDirection='column'>` 래퍼
- `slashOpen` 구독: `useInputStore(s => s.slashOpen)`
- D-11: SlashPopup이 InputArea 바로 위에 위치:
```typescript
<Box flexDirection='column'>
  {slashOpen && <SlashPopup buffer={buffer} onSelect={handleSlashSelect} />}
  <MultilineInput onSubmit={handleSubmit} clientRef={clientRef} />
</Box>
```

---

### `ui-ink/src/components/MultilineInput.tsx` (신규)

**Analog:** `App.tsx` useInput 블록 (lines 53-80)
**Role:** 핵심 입력 구현. INPT-01..05, 09, 10.

**현재 useInput 패턴 (App.tsx lines 53-80) — 확장 기반:**
```typescript
useInput((ch, key) => {
  if (key.ctrl && ch === 'c') { exit(); return }
  if (key.return) { /* submit */ return }
  if (key.backspace || key.delete) { setBuffer(buffer.slice(0, -1)); return }
  if (ch && !key.ctrl && !key.meta) { setBuffer(buffer + ch) }
})
```

**Phase 2 delta:**
- 신규 파일. 단순 buffer → `lines: string[]` + `cursor: {row, col}`
- `usePaste` 추가: `import {useInput, usePaste, Text, Box} from 'ink'`
- `key.return && !key.shift` → submit (Enter)
- `(key.return && key.shift) || (ch === '\x0a' && !key.return)` → 개행
- Ctrl+A/E/K/W/U POSIX 단축키
- `key.upArrow`/`key.downArrow` → history 탐색 (store의 historyIndex)
- 커서 위치를 inverse 색으로 표시 (Text inverse prop)
- `onSubmit` prop으로 부모에 텍스트 전달

---

### `ui-ink/src/components/SlashPopup.tsx` (신규)

**Analog:** 없음 — 프로젝트 내 select input 컴포넌트 미존재
**Role:** ink-select-input 기반 슬래시 명령 팝업.

**참조 패턴 (RESEARCH.md Pattern 4):**
```typescript
import SelectInput from 'ink-select-input'
import {SLASH_CATALOG} from '../slash-catalog.js'

// buffer 첫 글자 '/' 이후 쿼리로 필터링
const query = buffer.slice(1).toLowerCase()
const filtered = SLASH_CATALOG.filter(cmd =>
  cmd.name.slice(1).startsWith(query) || cmd.description.includes(query)
)

const items = filtered.map(cmd => ({
  label: `${cmd.name}  ${cmd.description}`,
  value: cmd.name,
}))
```

**주의:** `ink-select-input`의 Tab 동작이 예상과 다를 경우 즉시 자체 구현으로 전환 (RESEARCH.md Risk Factors 참조).

---

### `ui-ink/src/components/ConfirmDialog.tsx` (신규)

**Analog:** `App.tsx` useInput + confirm store 구독 패턴
**Role:** 3 모드 confirm 다이얼로그 (write/bash/cplan).

**confirm store 구독 패턴 — useShallow 필수 (RESEARCH.md Pattern 5):**
```typescript
import {useShallow} from 'zustand/react/shallow'
import {useConfirmStore} from '../store/confirm.js'
import {useRoomStore} from '../store/room.js'

const {mode, payload, clearConfirm} = useConfirmStore(useShallow(s => ({
  mode: s.mode,
  payload: s.payload,
  clearConfirm: s.clearConfirm,
})))
const activeIsSelf = useRoomStore(s => s.activeIsSelf)

// CNF-04: activeIsSelf=false면 read-only
if (!activeIsSelf) return <ConfirmReadOnlyView mode={mode} payload={payload} />

useInput((ch, key) => {
  if (ch === 'y') { resolve(true); return }
  if (ch === 'n') { resolve(false); return }
  if (ch === 'd' && mode === 'confirm_write') { toggleDiff(); return }
  if (key.escape) { resolve(false); return }
})
```

**Phase 2 delta:**
- 신규 파일. `clientRef: React.RefObject<HarnessClient>` prop 필요
- `resolve(accept)` → store의 `confirm.resolve(accept)` 호출 (내부에서 client.send)
- `classifyCommand(cmd: string): 'safe' | 'dangerous'` 로컬 함수 (CNF-02)
- `<DiffPreview>` 조건부 렌더 (d 키 toggle)
- Phase 2: `confirm_write`는 경로 + 새 내용 10줄 미리보기 (old_content 없음)

---

### `ui-ink/src/components/StatusBar.tsx` (신규)

**Analog:** `App.tsx` 상태 표시줄 (lines 124-129)
**Role:** 세그먼트 렌더 + useWindowSize 폭 기반 drop.

**현재 상태 표시줄 패턴 (App.tsx lines 124-129):**
```typescript
<Box>
  {busy && <Text color='cyan'>{spinFrame + ' '}</Text>}
  <Text color={connected ? 'green' : 'red'}>
    {connected ? '● connected' : '○ disconnected'}
  </Text>
</Box>
```

**store 단일 필드 구독 패턴 (STAT-01, RND-09 격리):**
```typescript
import {useWindowSize} from 'ink'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'

// 각 필드를 독립 selector로 구독 — useShallow 없이 단일 값
const {columns} = useWindowSize()
const workingDir = useStatusStore(s => s.workingDir)
const model = useStatusStore(s => s.model)
const mode = useStatusStore(s => s.mode)
const turns = useStatusStore(s => s.turns)
const connected = useStatusStore(s => s.connected)
// RND-09: ctxTokens는 별도 <CtxMeter> 서브컴포넌트로 격리
```

**Phase 2 delta:**
- 신규 파일. `<CtxMeter>` 서브컴포넌트 분리 (ctxTokens만 구독, 리렌더 격리)
- STAT-02: `buildSegments(columns, {...})` 함수로 폭 기반 세그먼트 우선순위 drop
- 우선순위: connected → model → turn → ctx% → mode → room → path

---

### `ui-ink/src/components/Divider.tsx` (신규)

**Analog:** `App.tsx` 구분선 Text (lines 111, 121)
**Role:** 터미널 폭만큼 `─` 문자 반복.

**현재 구분선 패턴 (App.tsx lines 111, 121):**
```typescript
<Text dimColor>{'─'.repeat(40)}</Text>
```

**Phase 2 delta:**
- 신규 파일. `useWindowSize()` 적용:
```typescript
import {Text} from 'ink'
import {useWindowSize} from 'ink'

export const Divider: React.FC = () => {
  const {columns} = useWindowSize()
  return <Text dimColor>{'─'.repeat(columns)}</Text>
}
```

---

## Shared Patterns

### 1. Zustand store 생성 패턴
**Source:** `ui-ink/src/store/messages.ts` (lines 25-104), `ui-ink/src/store/input.ts` (lines 10-14)
**Apply to:** 모든 store slice 파일

```typescript
import {create} from 'zustand'

// interface 먼저 정의, 그 다음 create
interface FooState {
  field: Type
  action: (arg: Type) => void
}

export const useFooStore = create<FooState>((set) => ({
  field: initialValue,
  action: (arg) => set({field: arg}),
  // 이전 상태 필요 시: (arg) => set((s) => ({field: ...s.field}))
}))
```

### 2. dispatch.ts store 직접 접근 패턴
**Source:** `ui-ink/src/ws/dispatch.ts` (lines 11-14)
**Apply to:** `ws/dispatch.ts` (확장), store의 `resolve` action (client.send 직접 호출)

```typescript
// React hook 바깥에서 store 접근 — 반드시 .getState() 사용
const messages = useMessagesStore.getState()
const status = useStatusStore.getState()
```

### 3. Ink 컴포넌트 import 패턴
**Source:** `ui-ink/src/App.tsx` (lines 3-4)
**Apply to:** 모든 컴포넌트 파일

```typescript
import React from 'react'
import {Box, Text, useInput, useApp} from 'ink'  // DOM 태그 없음
// Static, useWindowSize, usePaste, useStdout는 필요 시 추가
```

### 4. 테스트 파일 구조 패턴
**Source:** `ui-ink/src/__tests__/store.test.ts`, `dispatch.test.ts`
**Apply to:** Phase 2에서 추가하는 모든 테스트 파일

```typescript
import {describe, it, expect, beforeEach} from 'vitest'
// store 테스트: beforeEach에서 setState({}) 로 초기화
// 컴포넌트 테스트: ink-testing-library render() 사용
beforeEach(() => {
  useMessagesStore.setState({messages: []})
  // 모든 관련 store 초기화
})
```

### 5. .js 확장자 import 패턴
**Source:** 모든 기존 ts 파일
**Apply to:** 모든 새 파일의 로컬 import

```typescript
// bun + TypeScript에서 항상 .js 확장자 사용 (ESM 규칙)
import {useMessagesStore} from '../store/messages.js'
import {HarnessClient} from '../ws/client.js'
import {assertNever} from '../protocol.js'
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `components/DiffPreview.tsx` | component | transform | 프로젝트에 diff 렌더 컴포넌트 전례 없음. RESEARCH.md Pattern 8 코드 예시 사용 |
| `components/SlashPopup.tsx` | component | event-driven | 프로젝트에 select input 컴포넌트 전례 없음. ink-select-input README 패턴 사용 |

---

## Metadata

**Analog search scope:** `ui-ink/src/` 전체 (App.tsx, store/*.ts, ws/*.ts, protocol.ts, tty-guard.ts, index.tsx, __tests__/*.ts)
**Files scanned:** 13
**Pattern extraction date:** 2026-04-24
