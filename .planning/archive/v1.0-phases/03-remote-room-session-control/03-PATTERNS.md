# Phase 3: Remote Room + Session Control — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 15 (신규 8 + 수정 7)
**Analogs found:** 15 / 15 (모든 파일에 직접 analog 존재 — 신규 패키지 없음)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `ui-ink/src/components/PresenceSegment.tsx` | component (서브) | request-response | `StatusBar.tsx`의 `CtxMeter` 서브컴포넌트 (lines 43–48) | exact |
| `ui-ink/src/components/ReconnectOverlay.tsx` | component (모달) | event-driven | `ConfirmDialog.tsx`의 `ConfirmReadOnlyView` (lines 154–168) | role-match |
| `ui-ink/src/components/ObserverOverlay.tsx` | component (모달) | event-driven | `ConfirmDialog.tsx`의 `ConfirmReadOnlyView` (lines 154–168) | exact |
| `ui-ink/src/components/SystemMessage.tsx` | component | transform | `Message.tsx` role='system' 분기 (lines 80–107) | role-match | **W3 RESOLVED: 별도 파일 불필요 — Message.tsx role='system' + appendSystemMessage()로 충분** |
| `ui-ink/src/utils/userColor.ts` | utility (순수함수) | transform | `ui-ink/src/tty-guard.ts` (lines 1–11) | role-match |
| `ui-ink/src/App.tsx` | component (container) | event-driven | `App.tsx` 현재 구현 (self, 수정) | self |
| `ui-ink/src/components/StatusBar.tsx` | component | request-response | `StatusBar.tsx` 현재 구현 (self, 수정) | self |
| `ui-ink/src/components/Message.tsx` | component | transform | `Message.tsx` 현재 구현 (self, 수정) | self |
| `ui-ink/src/store/room.ts` | store slice | CRUD | `store/room.ts` 현재 구현 (self, 수정) | self |
| `ui-ink/src/ws/client.ts` | ws module | event-driven | `ws/client.ts` 현재 구현 (self, 수정) | self |
| `ui-ink/src/ws/dispatch.ts` | ws module | event-driven | `ws/dispatch.ts` 현재 구현 (self, 수정) | self |
| `ui-ink/src/protocol.ts` | type definitions | request-response | `protocol.ts` 현재 구현 (self, 수정) | self |
| `ui-ink/src/index.tsx` | entry point | request-response | `index.tsx` 현재 구현 (self, 수정) | self |
| `harness_server.py` (Room 클래스·broadcast·_run_session·_dispatch_loop) | server module | event-driven | `harness_server.py` 현재 구현 (self, 수정) | self |
| `ui-ink/src/slash-catalog.ts` | utility (static data) | transform | `slash-catalog.ts` 현재 구현 (self, 수정 가능) | self |

---

## Pattern Assignments

### `ui-ink/src/components/PresenceSegment.tsx` (신규, component, request-response)

**Analog:** `ui-ink/src/components/StatusBar.tsx`의 `CtxMeter` 서브컴포넌트 (lines 43–48)

CtxMeter는 ctxTokens만 격리 구독하여 StatusBar 본체 리렌더를 방지하는 서브컴포넌트 패턴이다. PresenceSegment도 동일 방식으로 room 상태만 격리 구독해야 한다.

**Imports pattern** (CtxMeter 패턴 — `StatusBar.tsx` lines 4–11):
```typescript
import React from 'react'
import {Box, Text} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useRoomStore} from '../store/room.js'
import {userColor} from '../utils/userColor.js'
```

**격리 서브컴포넌트 core pattern** (`StatusBar.tsx` lines 43–48):
```typescript
// CtxMeter — ctxTokens 만 격리 구독 (StatusBar 본체 리렌더 방지)
function CtxMeter() {
  const {ctxTokens} = useStatusStore(useShallow((s) => ({ctxTokens: s.ctxTokens})))
  if (typeof ctxTokens !== 'number') return null
  const pct = Math.min(100, Math.round((ctxTokens / MAX_CTX) * 100))
  return <Text color={theme.muted}>ctx {pct}%</Text>
}
```

**PresenceSegment 적용 패턴** (03-UI-SPEC.md §Presence 세그먼트):
```typescript
// solo 모드(roomName 없음)일 때 null 반환 — CtxMeter의 null 반환 패턴 그대로
function PresenceSegment() {
  const {roomName, members} = useRoomStore(useShallow(s => ({
    roomName: s.roomName,
    members: s.members,
  })))
  if (!roomName) return null  // solo 모드: CtxMeter의 null 반환과 동일 패턴
  // 멤버 순서: 서버 join 순. me는 항상 마지막. separator '·' = gray
  // userColor(m) 로 결정론적 색 배정. 자기 자신은 항상 'cyan'
}
```

**StatusBar에서 PresenceSegment 세그먼트 등록** (`StatusBar.tsx` lines 116–135):
```typescript
// 기존 roomName 세그먼트 (priority: 30) 교체 대상
// 기존 (lines 126–134):
if (roomName) {
  const roomText = `#${roomName}`
  segments.push({
    key: 'room',
    render: () => <Text color={theme.muted}>{roomText}</Text>,
    textLen: roomText.length,
    priority: 30,  // 유지
  })
}
// 교체 후: render: () => <PresenceSegment /> 로 변경
```

**textLen 계산 주의:** PresenceSegment는 동적 길이이므로 렌더 전 `members.length * 8` 같은 추정값 사용.

---

### `ui-ink/src/components/ReconnectOverlay.tsx` (신규, component, event-driven)

**Analog:** `ui-ink/src/components/ConfirmDialog.tsx`의 `ConfirmReadOnlyView` (lines 154–168)

ReconnectOverlay는 ConfirmReadOnlyView와 동일하게 InputArea를 치환하는 read-only 표시 컴포넌트다. useInput 없음, Box+Text 조합, borderStyle='round'.

**Imports pattern** (`ConfirmDialog.tsx` lines 7–13):
```typescript
import React from 'react'
import {Box, Text} from 'ink'
import {useRoomStore} from '../store/room.js'
```

**InputArea 치환 read-only 컴포넌트 core pattern** (`ConfirmDialog.tsx` lines 154–168):
```typescript
// ConfirmReadOnlyView — useInput 없이 Box+Text 표시만
function ConfirmReadOnlyView({mode, payload}: ReadOnlyProps): React.ReactElement {
  return (
    <Box flexDirection='column' borderStyle='round' borderColor='gray' paddingX={1}>
      <Text color='gray'>{label} (관전 중 — 응답 불가)</Text>
      <Text dimColor>{detail}</Text>
    </Box>
  )
}
```

**ReconnectOverlay 적용 패턴** (03-UI-SPEC.md §재연결 오버레이):
```typescript
// props: { attempt: number } | { failed: true }
// 재연결 중: color='yellow', 10회 실패: color='red'
// borderStyle='round'는 App.tsx 치환 컴포넌트 공통 패턴
interface ReconnectOverlayProps {
  attempt?: number
  failed?: boolean
}
// 텍스트:
// 재연결 중: `disconnected — reconnecting... (attempt ${attempt}/10)`
// 실패:     `disconnected — reconnect failed. Ctrl+C to exit.`
```

**App.tsx에서 치환 우선순위** (`App.tsx` lines 108–112 현재 패턴 확장):
```typescript
// 현재: confirmMode !== 'none' ? <ConfirmDialog /> : <InputArea ... />
// Phase 3 확장:
if (wsState === 'reconnecting') {
  inputArea = <ReconnectOverlay attempt={reconnectAttempt} />
} else if (wsState === 'failed') {
  inputArea = <ReconnectOverlay failed />
} else if (confirmMode !== 'none' && activeIsSelf) {
  inputArea = <ConfirmDialog />
} else if (confirmMode !== 'none' && !activeIsSelf) {
  inputArea = <ConfirmReadOnlyView ... />
} else if (!activeIsSelf) {
  inputArea = <ObserverOverlay username={activeInputFrom} />
} else {
  inputArea = <InputArea onSubmit={handleSubmit} disabled={busy} />
}
```

---

### `ui-ink/src/components/ObserverOverlay.tsx` (신규, component, event-driven)

**Analog:** `ui-ink/src/components/ConfirmDialog.tsx`의 `ConfirmReadOnlyView` (lines 154–168)

ObserverOverlay는 관전자가 에이전트 실행을 지켜볼 때 InputArea 자리에 표시되는 read-only 컴포넌트다. ConfirmReadOnlyView와 구조가 동일하나 borderStyle 없이 단순 Text 1줄로 표시한다.

**Core pattern** (`ConfirmDialog.tsx` lines 154–168에서 변형):
```typescript
// ConfirmReadOnlyView는 borderStyle='round' 사용
// ObserverOverlay는 borderStyle 없이 단순 1줄 — 03-UI-SPEC.md §"A 입력 중" 오버레이
interface ObserverOverlayProps {
  username: string | null
}

export const ObserverOverlay: React.FC<ObserverOverlayProps> = ({username}) => {
  // 03-UI-SPEC.md: dimColor italic / username 색 = userColor(username_token)
  // "alice 입력 중..." 형식
  return (
    <Box>
      <Text color={userColor(username ?? '')} bold>{username ?? '상대방'}</Text>
      <Text dimColor italic> 입력 중...</Text>
    </Box>
  )
}
```

**activeIsSelf 연동** (`ConfirmDialog.tsx` lines 44–66의 activeIsSelf 체크 패턴):
```typescript
// ConfirmDialog에서 activeIsSelf 체크:
const activeIsSelf = useRoomStore((s) => s.activeIsSelf)
if (!activeIsSelf) {
  return <ConfirmReadOnlyView mode={mode as Exclude<ConfirmMode, 'none'>} payload={payload} />
}
// ObserverOverlay는 App.tsx의 치환 우선순위에서 !activeIsSelf 조건으로 표시됨
```

---

### `ui-ink/src/components/SystemMessage.tsx` (신규, component, transform) ← W3 RESOLVED: 구현 불필요

**Analog:** `ui-ink/src/components/Message.tsx` (lines 80–107) — role='system' 분기

SystemMessage는 join/leave 시스템 이벤트를 1줄로 표시하는 경량 컴포넌트다. Message.tsx의 role='system' 렌더 패턴을 추출하여 별도 컴포넌트로 만든다.

**Message.tsx role='system' core pattern** (lines 80–107에서 관련 부분):
```typescript
// Message.tsx에서 role별 prefix와 색상:
const PREFIX: Record<MessageType['role'], string> = {
  user: '❯ ',
  assistant: '● ',
  tool: '└ ',
  system: '  ',  // system prefix = 공백 2칸
}
// color = theme.role[message.role] (system → 'gray')
// bold = message.role !== 'system' → system은 bold 없음
return (
  <Box marginBottom={0} flexDirection='column'>
    <Box>
      <Text color={color} bold={message.role !== 'system'}>{prefix}</Text>
      <Text wrap='wrap'>{seg.text}</Text>
    </Box>
  </Box>
)
```

**SystemMessage 적용 패턴** (03-UI-SPEC.md §Join/Leave 시스템 메시지):
```typescript
// 03-UI-SPEC.md: dimColor + italic. 아이콘 포함:
// room_member_joined: '↗ {username} 님이 참여했습니다'
// room_member_left:   '↘ {username} 님이 나갔습니다'
// room_joined:        '↗ {roomName} 방에 입장했습니다 ({N}명)'
// username 색 = userColor(username_token)
interface SystemMessageProps {
  icon: '↗' | '↘'
  username: string
  text: string  // '님이 참여했습니다' 등 나머지 텍스트
}
// <Static>에 append — message.role = 'system'으로 처리하거나 별도 타입으로 분리
```

**message role 확장 vs 별도 컴포넌트:** Message.tsx에 `role: 'system'`이 이미 존재하므로, `content`에 아이콘+텍스트를 포함하여 `appendSystemMessage()`로 처리하는 방식이 가장 단순하다. 단, username 색 해시가 필요하면 Message.tsx를 수정하거나 SystemMessage 별도 컴포넌트를 사용한다.

**W3 RESOLVED (checker B1 대응):** SystemMessage.tsx 별도 파일을 생성하지 않음. dispatch.ts에서 `appendSystemMessage('↗ ${msg.user} 님이 참여했습니다')` 형태로 처리하고, Message.tsx의 `role='system'` 분기가 렌더를 담당한다. Plan 03-03/06 어디에도 SystemMessage.tsx 생성 태스크를 추가하지 않는다.

---

### `ui-ink/src/utils/userColor.ts` (신규, utility, transform)

**Analog:** `ui-ink/src/tty-guard.ts` (lines 1–11) — 순수함수 유틸 컨벤션

tty-guard.ts는 export 함수만 있는 순수 함수 유틸 파일이다. userColor.ts도 동일 구조를 따른다.

**tty-guard.ts 순수함수 파일 패턴** (lines 1–11):
```typescript
// TTY 가드 유틸 — 테스트 가능한 독립 함수로 추출 (FND-12)
// index.tsx 에서 임포트해 사용

export function isInteractiveTTY(stdin: NodeJS.ReadStream): boolean {
  return stdin.isTTY === true && typeof stdin.setRawMode === 'function'
}
```

**userColor.ts 적용 패턴** (03-UI-SPEC.md §사용자 색 해시 + RESEARCH.md Pattern 11):
```typescript
// 사용자 색 해시 유틸 (DIFF-04)
// 모든 컴포넌트에서 import하여 사용. store 불필요. 순수함수.
const PALETTE = ['cyan', 'green', 'yellow', 'magenta', 'blue', 'red', 'white', 'greenBright']

function _hash(token: string): number {
  return token.split('').reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) & 0xffff, 0)
}

export function userColor(token: string): string {
  // 자기 자신은 항상 cyan — 기존 user role 색과 통일 (03-UI-SPEC.md)
  const myToken = process.env['HARNESS_TOKEN'] ?? ''
  if (token === myToken || token === 'me') return 'cyan'
  return PALETTE[_hash(token) % PALETTE.length]
}
```

---

### `ui-ink/src/App.tsx` (수정, component container, event-driven)

**Analog:** `App.tsx` 현재 구현 (self)

**현재 imports** (lines 1–14):
```typescript
import React, {useCallback, useEffect, useRef, useState} from 'react'
import {Box, useApp, useInput, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from './store/messages.js'
import {useStatusStore} from './store/status.js'
import {useInputStore} from './store/input.js'
import {useConfirmStore, bindConfirmClient} from './store/confirm.js'
import {HarnessClient} from './ws/client.js'
import {MessageList} from './components/MessageList.js'
import {StatusBar} from './components/StatusBar.js'
import {Divider} from './components/Divider.js'
import {InputArea} from './components/InputArea.js'
import {ConfirmDialog} from './components/ConfirmDialog.js'
```

**Phase 3 추가 imports:**
```typescript
// 추가할 imports
import {useRoomStore} from './store/room.js'
import {ReconnectOverlay} from './components/ReconnectOverlay.js'
import {ObserverOverlay} from './components/ObserverOverlay.js'
```

**WS lifecycle 패턴** (lines 28–45 — 변경 없이 유지):
```typescript
useEffect(() => {
  const url = process.env['HARNESS_URL']
  const token = process.env['HARNESS_TOKEN']
  if (!url || !token) return
  const client = new HarnessClient({url, token, room: process.env['HARNESS_ROOM']})
  client.connect()
  clientRef.current = client
  bindConfirmClient(client)
  return () => {
    bindConfirmClient(null)
    client.close()
    clientRef.current = null
  }
}, [])
```

**Ctrl+C cancel 교정** (lines 71–73 — `{type: 'input', text: '/cancel'}` → `{type: 'cancel'}`):
```typescript
// 현재 (잘못된 임시 구현 — WSR-04):
clientRef.current?.send({type: 'input', text: '/cancel'})
// 교정 후:
clientRef.current?.send({type: 'cancel'})
```

**치환 우선순위 확장** (lines 108–112 현재 패턴에서 확장):
```typescript
// 현재:
{confirmMode !== 'none' ? <ConfirmDialog /> : <InputArea onSubmit={handleSubmit} disabled={busy} />}

// Phase 3 확장 — wsState/activeIsSelf 조건 추가:
const wsState = useRoomStore(s => s.wsState)
const reconnectAttempt = useRoomStore(s => s.reconnectAttempt)
const activeIsSelf = useRoomStore(s => s.activeIsSelf)
const activeInputFrom = useRoomStore(s => s.activeInputFrom)

let inputArea: React.ReactNode
if (wsState === 'reconnecting') {
  inputArea = <ReconnectOverlay attempt={reconnectAttempt} />
} else if (wsState === 'failed') {
  inputArea = <ReconnectOverlay failed />
} else if (confirmMode !== 'none' && activeIsSelf) {
  inputArea = <ConfirmDialog />
} else if (confirmMode !== 'none' && !activeIsSelf) {
  // ConfirmReadOnlyView — ConfirmDialog 내부에서 !activeIsSelf 분기가 이미 처리
  inputArea = <ConfirmDialog />
} else if (!activeIsSelf) {
  inputArea = <ObserverOverlay username={activeInputFrom} />
} else {
  inputArea = <InputArea onSubmit={handleSubmit} disabled={busy} />
}
```

**레이아웃 JSX** (lines 101–118 — 구조 변경 없음):
```typescript
return (
  <Box flexDirection='column'>
    <MessageList/>
    <Divider columns={columns}/>
    {inputArea}  {/* 치환 우선순위 결과 */}
    <Divider columns={columns}/>
    <StatusBar columns={columns}/>
  </Box>
)
```

---

### `ui-ink/src/components/StatusBar.tsx` (수정, component, request-response)

**Analog:** `StatusBar.tsx` 현재 구현 (self)

**CtxMeter 격리 패턴** (lines 43–48 — PresenceSegment 동일 패턴으로 적용):
```typescript
// RND-09: ctxTokens 만 격리 구독 — StatusBar 본체 리렌더 방지
function CtxMeter() {
  const {ctxTokens} = useStatusStore(useShallow((s) => ({ctxTokens: s.ctxTokens})))
  if (typeof ctxTokens !== 'number') return null
  const pct = Math.min(100, Math.round((ctxTokens / MAX_CTX) * 100))
  return <Text color={theme.muted}>ctx {pct}%</Text>
}
```

**room 세그먼트 교체 위치** (lines 126–134):
```typescript
// 기존 roomName 단순 텍스트 세그먼트 (priority: 30) → PresenceSegment 서브컴포넌트로 교체
// textLen은 roomName이 없으면 0, 있으면 members * 평균 길이 추정
if (roomName) {
  segments.push({
    key: 'room',
    render: () => <PresenceSegment />,  // ← 교체
    textLen: roomName.length + 10,      // ← 동적 추정
    priority: 30,
  })
}
```

**세그먼트 정의 패턴** (lines 72–134 — 구조 변경 없음):
```typescript
interface Segment {
  key: string
  render: () => React.ReactElement
  textLen: number
  priority: number
}
```

---

### `ui-ink/src/components/Message.tsx` (수정, component, transform)

**Analog:** `Message.tsx` 현재 구현 (self)

**현재 role별 prefix 패턴** (lines 13–18):
```typescript
const PREFIX: Record<MessageType['role'], string> = {
  user: '❯ ',
  assistant: '● ',
  tool: '└ ',
  system: '  ',
}
```

**author prefix 추가 위치** (lines 80–107 — JSX 반환부):
```typescript
// 현재:
export const Message: React.FC<MessageProps> = ({message}) => {
  const color = theme.role[message.role]
  const prefix = PREFIX[message.role]
  // ...
  return (
    <Box marginBottom={0} flexDirection='column'>
      <Box>
        <Text color={color} bold={message.role !== 'system'}>{prefix}</Text>
        {/* 세그먼트 렌더 */}
      </Box>
    </Box>
  )
}

// Phase 3 추가 — roomName 존재 시 author prefix 조건부 렌더 (DIFF-02):
// message.meta?.author 필드 활용 (store에서 appendUserMessage 시 author 포함)
const roomName = useRoomStore(s => s.roomName)
// user 메시지이고 room 모드일 때만 [author] prefix 표시
// solo 모드(roomName 없음): prefix 미표시 (03-UI-SPEC.md §Author Prefix)
```

**segments 렌더 패턴** (lines 94–103 — React key 규칙):
```typescript
{segments.map((seg, idx) => {
  // id + idx 조합 key — 단순 index 금지
  const key = `${message.id}-seg-${idx}`
  // ...
})}
```

---

### `ui-ink/src/store/room.ts` (수정, store slice, CRUD)

**Analog:** `store/room.ts` 현재 구현 (self)

**현재 인터페이스** (lines 1–30):
```typescript
interface RoomState {
  roomName: string
  members: string[]
  activeInputFrom: string | null
  activeIsSelf: boolean
  busy: boolean
  setRoom: (name: string, members: string[]) => void
  addMember: (user: string) => void
  removeMember: (user: string) => void
  setActiveInputFrom: (user: string | null) => void
  setActiveIsSelf: (v: boolean) => void
  setRoomBusy: (v: boolean) => void
}
```

**Phase 3 추가 필드** (RESEARCH.md Pattern 7 — store/room.ts 확장):
```typescript
// 추가할 필드들:
wsState: 'connected' | 'reconnecting' | 'failed'
reconnectAttempt: number
lastEventId: number | null
// 추가할 actions:
setWsState: (s: RoomState['wsState']) => void
setReconnectAttempt: (n: number) => void
setLastEventId: (id: number) => void
```

**Zustand create 패턴** (lines 18–30 — 기존 패턴 그대로):
```typescript
export const useRoomStore = create<RoomState>((set) => ({
  // 초기값
  wsState: 'connected',
  reconnectAttempt: 0,
  lastEventId: null,
  // actions
  setWsState: (s) => set({wsState: s}),
  setReconnectAttempt: (n) => set({reconnectAttempt: n}),
  setLastEventId: (id) => set({lastEventId: id}),
}))
```

---

### `ui-ink/src/ws/client.ts` (수정, ws module, event-driven)

**Analog:** `ws/client.ts` 현재 구현 (self)

**현재 close 핸들러 stub** (lines 49–53 — Phase 3에서 확장):
```typescript
this.ws.on('close', () => {
  useStatusStore.getState().setConnected(false)
  this._clearPing()
  // Phase 3 에서 jitter backoff reconnect 추가  ← 이 주석 자리에 구현
})
```

**WSR-01 jitter backoff 추가 패턴** (RESEARCH.md Pattern 6):
```typescript
// private 필드 추가:
private backoff = {attempts: 0, stableTimer: null as ReturnType<typeof setTimeout> | null}

private _scheduleReconnect(): void {
  const {attempts} = this.backoff
  if (attempts >= 10) {
    useRoomStore.getState().setWsState('failed')
    return
  }
  // WSR-01 공식: delay = base * 2^n * (0.5 + Math.random() * 0.5), cap 30s
  const base = 1000
  const cap = 30_000
  const delay = Math.min(base * Math.pow(2, attempts) * (0.5 + Math.random() * 0.5), cap)
  this.backoff.attempts++
  useRoomStore.getState().setReconnectAttempt(this.backoff.attempts)
  useRoomStore.getState().setWsState('reconnecting')
  setTimeout(() => this.connect(), delay)
}
```

**connect() 헤더 확장** (lines 26–32 — x-resume-from 헤더 추가):
```typescript
// 현재:
connect(): void {
  const headers: Record<string, string> = {
    'x-harness-token': this.opts.token,
  }
  if (this.opts.room) headers['x-harness-room'] = this.opts.room
  // Phase 3 추가 — WSR-03 delta replay:
  const lastEventId = useRoomStore.getState().lastEventId
  if (lastEventId != null) headers['x-resume-from'] = String(lastEventId)
  this.ws = new WebSocket(this.opts.url, {headers})
```

**send 패턴** (lines 60–63 — 변경 없음):
```typescript
send(msg: ClientMsg): void {
  if (this.ws?.readyState === WebSocket.OPEN) {
    this.ws.send(JSON.stringify(msg))
  }
}
```

---

### `ui-ink/src/ws/dispatch.ts` (수정, ws module, event-driven)

**Analog:** `ws/dispatch.ts` 현재 구현 (self)

**exhaustive switch 패턴** (lines 10–163 — 케이스 추가 시 동일 구조):
```typescript
export function dispatch(msg: ServerMsg): void {
  const messages = useMessagesStore.getState()
  const status = useStatusStore.getState()
  const room = useRoomStore.getState()
  const confirm = useConfirmStore.getState()

  switch (msg.type) {
    // ... 기존 케이스들 ...
    default:
      assertNever(msg)  // 반드시 유지
  }
}
```

**Phase 3 추가 케이스들:**

`event_id 추적` (모든 케이스 진입 전 — RESEARCH.md Pattern 7):
```typescript
// dispatch() 함수 시작부에 추가:
if ('event_id' in msg && typeof msg.event_id === 'number') {
  useRoomStore.getState().setLastEventId(msg.event_id)
}
```

`agent_start from_self 처리` (lines 29–32 교체):
```typescript
case 'agent_start':
  messages.agentStart()
  status.setBusy(true)
  // Phase 3 추가 — PEXT-01 from_self 필드:
  room.setActiveIsSelf(msg.from_self ?? true)  // 구버전 호환: undefined → true
  break
```

`state_snapshot 히스토리 로드` (lines 83–91 확장):
```typescript
case 'state_snapshot':
  status.setState({
    working_dir: msg.working_dir,
    model: msg.model,
    mode: msg.mode,
    turns: msg.turns,
    ctx_tokens: msg.ctx_tokens,
  })
  // Phase 3 추가 — REM-03 메시지 히스토리 로드:
  if (msg.messages && Array.isArray(msg.messages)) {
    messages.loadSnapshot(msg.messages)  // store/messages.ts에 loadSnapshot action 추가 필요
  }
  break
```

`agent_cancelled 신규 케이스` (PEXT-05):
```typescript
case 'agent_cancelled':
  messages.agentEnd()  // agentEnd와 동일하게 busy 초기화
  status.setBusy(false)
  messages.appendSystemMessage('에이전트 실행이 취소되었습니다')
  break
```

`room_joined 프로토콜 불일치 수정` (lines 64–66 교체):
```typescript
// 현재 (불일치): room.setRoom(msg.room, msg.members)
// 서버 실제 전송: {room, shared, subscribers: number, busy}
// members: string[] 필드가 없음 — RESEARCH.md Pitfall H
case 'room_joined':
  room.setRoom(msg.room, [])  // members는 room_member_joined 이벤트로 점진 추가
  // 또는 서버 수정으로 members 필드 추가 후: room.setRoom(msg.room, msg.members)
  break
```

`room_member_joined/left 시스템 메시지 교정` (lines 68–75 교체):
```typescript
// 현재: messages.appendSystemMessage(`[${msg.user}] 님이 참가했습니다`)
// 03-UI-SPEC.md 기준으로 아이콘 추가:
case 'room_member_joined':
  room.addMember(msg.user)
  messages.appendSystemMessage(`↗ ${msg.user} 님이 참여했습니다`)
  break
case 'room_member_left':
  room.removeMember(msg.user)
  messages.appendSystemMessage(`↘ ${msg.user} 님이 나갔습니다`)
  break
```

---

### `ui-ink/src/protocol.ts` (수정, type definitions, request-response)

**Analog:** `protocol.ts` 현재 구현 (self)

**현재 ServerMsg union 패턴** (lines 41–51 — 타입 추가 위치):
```typescript
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
```

**Phase 3 타입 수정:**
```typescript
// AgentStartMsg — from_self 필드 추가 (PEXT-01):
export interface AgentStartMsg   { type: 'agent_start'; from_self?: boolean }

// ConfirmWriteMsg — old_content 필드 추가 (PEXT-02):
export interface ConfirmWriteMsg { type: 'confirm_write'; path: string; old_content?: string }

// RoomJoinedMsg — 서버 실제 전송과 일치시키기 (Pitfall H):
// 서버: {room, shared, subscribers: number, busy}
export interface RoomJoinedMsg   { type: 'room_joined'; room: string; shared: boolean; subscribers: number; busy: boolean; members?: string[] }

// AgentCancelledMsg 신규 (PEXT-05):
export interface AgentCancelledMsg { type: 'agent_cancelled' }

// ServerMsg union에 추가:
// | AgentCancelledMsg
```

**assertNever 패턴** (lines 67–69 — 변경 없음):
```typescript
export function assertNever(x: never): never {
  throw new Error(`Unhandled ServerMsg type: ${(x as { type: string }).type}`)
}
```

---

### `ui-ink/src/index.tsx` (수정, entry point, request-response)

**Analog:** `index.tsx` 현재 구현 (self)

**현재 one-shot stub** (lines 44–54):
```typescript
if (!isInteractive) {
  const query = process.argv[2]
  if (query) {
    // eslint-disable-next-line no-restricted-syntax
    process.stdout.write(`[one-shot] ${query}\n`)  // ← stub
  } else {
    process.stderr.write('[harness] non-TTY 환경. HARNESS_URL / HARNESS_TOKEN 으로 연결하세요.\n')
  }
  process.exit(0)
}
```

**Phase 3 확장 패턴** (RESEARCH.md Pattern 9 — SES-01/02):
```typescript
// argv 파싱 패턴 (기존 process.argv 접근 방식 유지):
if (!isInteractive) {
  const resumeIdx = process.argv.indexOf('--resume')
  const resumeId = resumeIdx > -1 ? process.argv[resumeIdx + 1] : undefined
  const roomIdx = process.argv.indexOf('--room')
  const roomName = roomIdx > -1 ? process.argv[roomIdx + 1] : process.env['HARNESS_ROOM']
  const query = resumeId
    ? undefined
    : process.argv.find((a, i) => i >= 2 && !a.startsWith('--') && process.argv[i-1] !== '--room' && process.argv[i-1] !== '--resume')

  const url = process.env['HARNESS_URL']
  const token = process.env['HARNESS_TOKEN']
  if (!url || !token) {
    process.stderr.write('[harness] HARNESS_URL / HARNESS_TOKEN 필요\n')
    process.exit(1)
  }
  // SES-01: one-shot — dynamic import로 모듈 분리
  if (query) {
    const {runOneShot} = await import('./one-shot.js')
    await runOneShot({url, token, room: roomName, query, ansi: process.stdout.isTTY ?? false})
    process.exit(0)
  }
  // SES-02: --resume — ConnectOptions에 resumeSession 추가 (일반 render 경로)
  // ...
}
// Ink render — 변경 없음 (lines 56–58):
render(<App />, {patchConsole: false})
```

**cleanup 헬퍼 패턴** (lines 12–27 — 변경 없음):
```typescript
function cleanup(code = 1): never {
  try {
    // eslint-disable-next-line no-restricted-syntax
    process.stdout.write('\x1b[?25h')
    if (typeof process.stdin.setRawMode === 'function') process.stdin.setRawMode(false)
    process.stdin.pause()
  } catch { /* 무시 */ }
  process.exit(code)
}
```

---

### `harness_server.py` — Room 클래스 + broadcast (수정, server module, event-driven)

**Analog:** `harness_server.py` 현재 구현 (self)

**현재 Room dataclass** (lines 122–133):
```python
@dataclass
class Room:
    name: str
    state: Session
    subscribers: set = field(default_factory=set)
    busy: bool = False
    active_input_from: object = None
    input_tasks: set = field(default_factory=set)
```

**PEXT-03 Room 확장 패턴:**
```python
# 파일 상단 import 추가 (표준 라이브러리):
from collections import deque
import time

# Room 클래스 필드 추가:
@dataclass
class Room:
    name: str
    state: Session
    subscribers: set = field(default_factory=set)
    busy: bool = False
    active_input_from: object = None
    input_tasks: set = field(default_factory=set)
    # PEXT-03: monotonic event_id + 60초 ring buffer
    event_counter: int = field(default=0)
    event_buffer: deque = field(default_factory=lambda: deque(maxlen=10000))
```

**현재 broadcast 함수** (lines 82–98):
```python
async def broadcast(room: 'Room', **kwargs):
    if not room.subscribers:
        return
    payload = json.dumps(kwargs, ensure_ascii=False)
    dead = []
    for s in list(room.subscribers):
        try:
            await s.send(payload)
        except Exception:
            dead.append(s)
    for s in dead:
        room.subscribers.discard(s)
```

**PEXT-03 broadcast 확장 패턴:**
```python
async def broadcast(room: 'Room', **kwargs):
    # event_id 부여 + ring buffer 기록 (PEXT-03)
    room.event_counter += 1
    kwargs['event_id'] = room.event_counter
    now = time.monotonic()
    room.event_buffer.append((room.event_counter, now, dict(kwargs)))
    # TTL 60초 초과 항목 eager cleanup
    while room.event_buffer and (now - room.event_buffer[0][1]) > 60:
        room.event_buffer.popleft()

    if not room.subscribers:
        return
    payload = json.dumps(kwargs, ensure_ascii=False)
    dead = []
    for s in list(room.subscribers):
        try:
            await s.send(payload)
        except Exception:
            dead.append(s)
    for s in dead:
        room.subscribers.discard(s)
```

---

### `harness_server.py` — _run_session + _dispatch_loop (수정, server module, event-driven)

**현재 _run_session 진입부** (lines 711–731):
```python
async def _run_session(ws):
    room_header = (ws.request.headers.get('x-harness-room', '') or '').strip()
    room_name = room_header if room_header else f'_solo_{uuid.uuid4().hex}'
    is_shared = bool(room_header)
    room = _get_or_create_room(room_name)
    room.subscribers.add(ws)
    state = room.state
    try:
        await send_state(ws, state)
        await send(ws, type='ready', room=room_name)
        await send(ws, type='room_joined',
                   room=room_name,
                   shared=is_shared,
                   subscribers=len(room.subscribers),
                   busy=room.busy)
```

**PEXT-04 resume_from 파싱 추가 위치 (room_header 파싱 직후):**
```python
# x-harness-room 파싱 이후 즉시:
resume_from_str = (ws.request.headers.get('x-resume-from', '') or '').strip()
resume_from = int(resume_from_str) if resume_from_str.isdigit() else None
```

**PEXT-04 delta 재송신 (room_joined 이후):**
```python
# state_snapshot 전송 전에:
if resume_from is not None:
    for (eid, ts, payload_dict) in list(room.event_buffer):
        if eid > resume_from:
            await send(ws, **payload_dict)
```

**현재 _dispatch_loop 구조** (lines 654–709):
```python
async def _dispatch_loop(ws, room: 'Room', queue: asyncio.Queue):
    state = room.state
    while True:
        msg = await queue.get()
        if msg is None:
            return
        t = msg.get('type')

        if t == 'input':
            # ... busy 체크 + spawn
        elif t == 'cplan_execute':
            # ...
        elif t == 'confirm_write_response':
            if ws is not room.active_input_from:  # DQ2 가드
                continue
            # ...
        elif t == 'ping':
            await send(ws, type='pong')
```

**PEXT-05 cancel 케이스 추가:**
```python
elif t == 'cancel':
    # DQ3: 입력 주체(active_input_from)만 취소 가능 — confirm_write_response 가드와 동일 패턴
    if ws is not room.active_input_from:
        continue
    for task in list(room.input_tasks):
        task.cancel()
    await broadcast(room, type='agent_cancelled')
```

**PEXT-01 agent_start per-subscriber 함수:**
```python
# broadcast() 아래에 추가:
async def _broadcast_agent_start(room: 'Room', requester_ws):
    '''agent_start는 per-subscriber — from_self 플래그가 구독자마다 다름 (PEXT-01).
    broadcast()와 동일한 dead 처리 패턴 사용.
    '''
    dead = []
    for s in list(room.subscribers):
        try:
            await send(s, type='agent_start', from_self=(s is requester_ws))
        except Exception:
            dead.append(s)
    for s in dead:
        room.subscribers.discard(s)
```

**PEXT-02 confirm_write old_content 추가:**
```python
# 현재 (lines 188-203):
# asyncio.run_coroutine_threadsafe(
#     send(ws, type='confirm_write', path=path), loop  # ← content 미포함
# )
# 교정:
def _read_existing_file(path: str) -> str | None:
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None

# send 호출 변경:
asyncio.run_coroutine_threadsafe(
    send(ws, type='confirm_write', path=path,
         old_content=_read_existing_file(path)), loop
)
```

**_handle_input CancelledError 처리 추가** (lines 617–635):
```python
async def _handle_input(ws, room: 'Room', text: str):
    try:
        if text.startswith('/'):
            await handle_slash(ws, room, text)
        elif text.startswith('@claude '):
            await run_claude(ws, room, text[8:].strip(), add_to_session=True)
        else:
            await run_agent(ws, room, text)
            await broadcast_state(room)
    except asyncio.CancelledError:
        # PEXT-05: 정상 취소 경로 — busy/active_input_from은 finally에서 정리
        pass
    except Exception as e:
        await broadcast(room, type='error', text=f'입력 처리 오류: {e}')
    finally:
        room.busy = False
        room.active_input_from = None
```

---

## Shared Patterns (전체 파일 공통 적용)

### 1. useShallow 멀티 필드 구독
**Source:** `App.tsx` (lines 20–22), `StatusBar.tsx` (lines 52–62), `ConfirmDialog.tsx` (lines 34–43)
**Apply to:** 모든 신규/수정 컴포넌트 파일
```typescript
// 복수 필드 구독 시 반드시 useShallow
import {useShallow} from 'zustand/react/shallow'
const {field1, field2} = useSomeStore(useShallow(s => ({field1: s.field1, field2: s.field2})))
// 단일 필드는 useShallow 불필요
const busy = useStatusStore(s => s.busy)
```

### 2. .js 확장자 ESM import
**Source:** 모든 기존 ts 파일 (import 일관성)
**Apply to:** 모든 신규 파일의 로컬 import
```typescript
import {useRoomStore} from '../store/room.js'      // .js 확장자 필수
import {userColor} from '../utils/userColor.js'
import {ReconnectOverlay} from '../components/ReconnectOverlay.js'
```

### 3. crypto.randomUUID() for ID
**Source:** `store/messages.ts` (lines 31, 38, 53)
**Apply to:** SystemMessage 등 id가 필요한 모든 메시지 생성
```typescript
id: crypto.randomUUID()  // React key. index 금지
```

### 4. assertNever exhaustive switch
**Source:** `ws/dispatch.ts` (lines 160–162)
**Apply to:** `dispatch.ts` 확장 시 default case 유지
```typescript
default:
  assertNever(msg)  // 새 타입 추가 시 컴파일 에러로 탐지
```

### 5. store.getState() 직접 호출 (WS 레이어)
**Source:** `ws/dispatch.ts` (lines 11–14), `ws/client.ts` (lines 35, 50)
**Apply to:** `dispatch.ts` 신규 케이스, `client.ts` backoff 로직
```typescript
// React hook 바깥 (WS 레이어)에서는 .getState() 사용
useRoomStore.getState().setWsState('reconnecting')
useRoomStore.getState().setLastEventId(msg.event_id)
```

### 6. Ink JSX 제약
**Source:** `CLAUDE.md` + 모든 기존 컴포넌트
**Apply to:** 모든 신규 컴포넌트
```typescript
// 허용: <Box>, <Text>, <Static>, <Newline>
// 금지: <div>, <span>, process.stdout.write, console.log
import {Box, Text} from 'ink'
```

### 7. Python 서버 DQ2 입력 주체 가드
**Source:** `harness_server.py` (lines 692–694, 700–701)
**Apply to:** PEXT-05 cancel 케이스
```python
# confirm_write_response / confirm_bash_response 와 동일 패턴
if ws is not room.active_input_from:
    continue
```

### 8. Python broadcast dead 처리 패턴
**Source:** `harness_server.py` broadcast (lines 82–98)
**Apply to:** `_broadcast_agent_start()` 신규 함수
```python
dead = []
for s in list(room.subscribers):
    try:
        await s.send(payload)
    except Exception:
        dead.append(s)
for s in dead:
    room.subscribers.discard(s)
```

---

## No Analog Found

Phase 3에서 완전히 새로운 패턴이 필요한 파일: 없음. 모든 신규 파일은 기존 코드에서 직접 추출 가능한 analog를 보유한다.

단, 아래 사항은 RESEARCH.md 패턴을 직접 사용해야 한다 (codebase에 전례 없음):

| 구현 사항 | 이유 | 참조 위치 |
|-----------|------|-----------|
| WSR-01 jitter exponential backoff 공식 | 수학 공식 — codebase에 전례 없음 | RESEARCH.md Pattern 6 |
| `_read_existing_file()` 헬퍼 | 신규 Python 헬퍼 — 단순 파일 읽기 | RESEARCH.md Pattern 2 |
| `snapshotKey` Static remount 패턴 | store/messages.ts에 아직 미구현 | RESEARCH.md Pattern 8 |
| `one-shot.ts` 신규 파일 | WS 경량 클라이언트 — 전례 없음 | RESEARCH.md Pattern 9 |

---

## Metadata

**Analog search scope:** `ui-ink/src/` 전체 + `harness_server.py` (lines 82–759)
**Files scanned:** 11개 TypeScript + 1개 Python (harness_server.py 주요 함수)
**Pattern extraction date:** 2026-04-24
