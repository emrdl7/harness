---
phase: 02-core-ux
plan: A
wave: 1
depends_on: []
autonomous: true
files_modified:
  - ui-ink/src/store/messages.ts
  - ui-ink/src/store/input.ts
  - ui-ink/src/store/confirm.ts
  - ui-ink/src/protocol.ts
  - ui-ink/src/ws/dispatch.ts
  - ui-ink/src/ws/client.ts
  - ui-ink/src/__tests__/store.messages.test.ts
  - ui-ink/src/__tests__/store.input.test.ts
  - ui-ink/src/__tests__/store.confirm.test.ts
  - ui-ink/src/__tests__/dispatch.test.ts
requirements:
  - RND-01
  - RND-02
  - RND-03
  - INPT-03
  - CNF-03
  - CNF-04
  - CNF-05
must_haves:
  truths:
    - "completedMessages 배열은 agent_end 수신 시에만 push 된다 (<Static> 안정성 확보)"
    - "activeMessage 는 스트리밍 중 in-place 업데이트되며 완료 시 completedMessages 로 이동 후 null"
    - "input.ts 는 history[] + historyIndex 로 ↑↓ 순회를 지원한다"
    - "input.ts 는 slashOpen 플래그로 SlashPopup 표시 상태를 관리한다"
    - "input.ts 는 ~/.harness/history.txt 파일에 history 를 영속화하며 마운트 시 로드한다 (INPT-03 파일 persistence, Phase 2 SC-2)"
    - "confirm.ts resolve(accept) 는 mode 에 맞는 ClientMsg 를 WS 로 전송하고 mode 를 'none' 으로 되돌린다"
    - "confirm.ts 는 deniedPaths/deniedCmds 를 Set 으로 관리하며 isDenied() 조회 가능"
    - "protocol.ts ClientMsg 에 CancelMsg 가 포함된다"
    - "dispatch.ts 는 slash_result 의 cmd 에 따라 clearMessages / setWorkingDir 등을 트리거한다"
  artifacts:
    - path: "ui-ink/src/store/messages.ts"
      provides: "completedMessages + activeMessage 분리된 상태"
      contains: "completedMessages: Message[]"
    - path: "ui-ink/src/store/input.ts"
      provides: "history + slashOpen + 파일 persistence 확장 상태"
      contains: "history: string[]"
    - path: "ui-ink/src/store/confirm.ts"
      provides: "stickyDeny + resolve(accept) 완성"
      contains: "deniedPaths"
    - path: "ui-ink/src/protocol.ts"
      provides: "CancelMsg 포함 ClientMsg 유니온"
      contains: "CancelMsg"
    - path: "ui-ink/src/ws/dispatch.ts"
      provides: "slash_result cmd 별 분기"
      contains: "case 'clear'"
  key_links:
    - from: "ui-ink/src/store/confirm.ts"
      to: "ui-ink/src/ws/client.ts"
      via: "resolve() → client.send(ConfirmWriteResponse | ConfirmBashResponse)"
      pattern: "client.send\\(\\{type: 'confirm_(write|bash)_response'"
    - from: "ui-ink/src/ws/dispatch.ts"
      to: "ui-ink/src/store/messages.ts"
      via: "agent_end → activeMessage 이동"
      pattern: "messages\\.agentEnd\\(\\)"
    - from: "ui-ink/src/store/input.ts"
      to: "~/.harness/history.txt"
      via: "loadHistory() 마운트 시 1회 + appendHistory() pushHistory 마다"
      pattern: "appendHistory\\("
---

<objective>
Phase 2 기반이 되는 store / protocol / dispatch 계층을 정리한다. UI 층 컴포넌트 재작성(Plan B)과 독립적으로, `<Static>` 안정성을 위한 completedMessages/activeMessage 분리, history/slashOpen 추가 + ~/.harness/history.txt 파일 persistence, confirm sticky-deny + WS 응답 연결, CancelMsg 프로토콜 추가, slash_result 확장 처리를 단일 계약으로 못 박는다. Plan B 가 이 계약 위에서 컴포넌트만 작성하면 된다.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-core-ux/02-CONTEXT.md
@.planning/phases/02-core-ux/02-RESEARCH.md

<interfaces>
<!-- 현재 Phase 1 기준 state — Plan A 의 각 task 가 변경할 계약 -->

현재 `ui-ink/src/store/messages.ts` 의 MessagesState:
```typescript
interface MessagesState {
  messages: Message[]                   // ← 단일 배열, Phase 2 에서 분리
  appendUserMessage: (content: string) => void
  agentStart: () => void
  appendToken: (text: string) => void
  agentEnd: () => void
  appendToolStart: (name: string, args: Record<string, unknown>) => void
  appendToolEnd: (name: string, result: string) => void
  appendSystemMessage: (content: string) => void
  clearMessages: () => void
}
```

현재 `ui-ink/src/store/input.ts`:
```typescript
interface InputState {
  buffer: string
  setBuffer: (v: string) => void
  clearBuffer: () => void
}
```

현재 `ui-ink/src/store/confirm.ts`:
```typescript
export type ConfirmMode = 'none' | 'confirm_write' | 'confirm_bash' | 'cplan_confirm'
interface ConfirmState {
  mode: ConfirmMode
  payload: Record<string, unknown>
  setConfirm: (mode, payload) => void
  clearConfirm: () => void
}
```

현재 `ui-ink/src/protocol.ts` ClientMsg:
```typescript
export type ClientMsg = InputMsg | ConfirmWriteResponse | ConfirmBashResponse | SlashMsg | PingMsg
```

현재 `ui-ink/src/ws/dispatch.ts` slash_result case:
```typescript
case 'slash_result':
  messages.appendSystemMessage(`/${msg.cmd} 완료`)
  break
```

CNF-02 (서버 danger_level 미전송) 대응 — 클라이언트 측 패턴 매칭:
```typescript
const DANGEROUS_PATTERNS = [/\brm\b/, /\bsudo\b/, /\bchmod\b/, /\bchown\b/, /[|&;<>`]/, /\$\(/, /\bdd\b/, /\bmkfs\b/, /\beval\b/]
export function classifyCommand(cmd: string): 'safe' | 'dangerous' {
  return DANGEROUS_PATTERNS.some(p => p.test(cmd)) ? 'dangerous' : 'safe'
}
```
</interfaces>
</context>

<tasks>

<task id="A-1" type="auto" tdd="true">
  <name>A-1: messages.ts — completedMessages / activeMessage 분리</name>
  <files>ui-ink/src/store/messages.ts, ui-ink/src/__tests__/store.messages.test.ts</files>
  <read_first>
    - ui-ink/src/store/messages.ts — 현재 단일 messages 배열 + appendToken in-place 로직 파악
    - ui-ink/src/__tests__/ 디렉터리 ls — 기존 messages 테스트 존재 여부 확인
  </read_first>
  <behavior>
    - Test 1: agentStart → activeMessage !== null, completedMessages 길이 불변
    - Test 2: appendToken 2회 호출 후 activeMessage.content === '토큰1토큰2'
    - Test 3: agentEnd 후 activeMessage === null, completedMessages 마지막 원소가 streaming=false 인 assistant
    - Test 4: appendUserMessage 는 completedMessages 에 즉시 push (activeMessage 건드리지 않음)
    - Test 5: appendToolStart/appendToolEnd — Phase 1 과 동일하게 completedMessages 에 들어감 (tool 은 streaming 동안에도 active 가 아님 — completed 배열에서 in-place 업데이트)
    - Test 6: clearMessages → completedMessages=[], activeMessage=null
    - Test 7: appendSystemMessage 는 completedMessages 에 즉시 push
  </behavior>
  <action>
    D-04 (Static/active 경계 = agent_end) 를 반영해 MessagesState 를 다음과 같이 교체한다:

    ```typescript
    // 메시지 슬라이스 — completed(Static 전용) + active(streaming 전용) 분리 (RND-01, RND-02)
    import {create} from 'zustand'

    export interface Message {
      id: string
      role: 'user' | 'assistant' | 'tool' | 'system'
      content: string
      streaming?: boolean
      toolName?: string
      meta?: Record<string, unknown>
    }

    interface MessagesState {
      completedMessages: Message[]    // <Static> 전용 append-only
      activeMessage: Message | null   // 스트리밍 중 assistant — 일반 트리에만 렌더
      appendUserMessage: (content: string) => void
      agentStart: () => void
      appendToken: (text: string) => void
      agentEnd: () => void
      appendToolStart: (name: string, args: Record<string, unknown>) => void
      appendToolEnd: (name: string, result: string) => void
      appendSystemMessage: (content: string) => void
      clearMessages: () => void
    }

    export const useMessagesStore = create<MessagesState>((set) => ({
      completedMessages: [],
      activeMessage: null,

      appendUserMessage: (content) => set((s) => ({
        completedMessages: [...s.completedMessages, {
          id: crypto.randomUUID(), role: 'user', content,
        }],
      })),

      agentStart: () => set(() => ({
        activeMessage: {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '',
          streaming: true,
        },
      })),

      // activeMessage in-place 업데이트 (새 객체 생성은 하지만 배열 push 아님)
      appendToken: (text) => set((s) => {
        if (s.activeMessage && s.activeMessage.role === 'assistant') {
          return {activeMessage: {...s.activeMessage, content: s.activeMessage.content + text}}
        }
        // agentStart 없이 token 수신 방어
        return {
          activeMessage: {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: text,
            streaming: true,
          },
        }
      }),

      // D-04 — agent_end 수신 시에만 completedMessages 로 이동
      agentEnd: () => set((s) => {
        if (!s.activeMessage) return {}
        return {
          completedMessages: [...s.completedMessages, {...s.activeMessage, streaming: false}],
          activeMessage: null,
        }
      }),

      appendToolStart: (name, args) => set((s) => ({
        completedMessages: [...s.completedMessages, {
          id: crypto.randomUUID(),
          role: 'tool',
          content: `[${name}] ${JSON.stringify(args)}`,
          toolName: name,
          streaming: true,
        }],
      })),

      // tool 은 completedMessages 안에서 in-place 업데이트 (streaming → false)
      appendToolEnd: (name, result) => set((s) => {
        const revIdx = [...s.completedMessages].reverse().findIndex(
          (m) => m.role === 'tool' && m.toolName === name && m.streaming,
        )
        if (revIdx === -1) return {}
        const realIdx = s.completedMessages.length - 1 - revIdx
        const updated = {
          ...s.completedMessages[realIdx],
          content: `[${name}] ${result}`,
          streaming: false,
        }
        return {
          completedMessages: [
            ...s.completedMessages.slice(0, realIdx),
            updated,
            ...s.completedMessages.slice(realIdx + 1),
          ],
        }
      }),

      appendSystemMessage: (content) => set((s) => ({
        completedMessages: [...s.completedMessages, {
          id: crypto.randomUUID(), role: 'system', content,
        }],
      })),

      clearMessages: () => set({completedMessages: [], activeMessage: null}),
    }))
    ```

    테스트 파일 `ui-ink/src/__tests__/store.messages.test.ts` 신규 생성 (또는 기존 파일 확장). 각 behavior 에 해당하는 vitest `it()` 블록을 작성한다. beforeEach 에서 `useMessagesStore.setState({completedMessages: [], activeMessage: null})` 로 초기화.

    주의:
    - `<Static>` 안정성의 핵심은 agent_end 이전에는 completedMessages 가 늘어나지 않는다는 것이다 (RND-02).
    - activeMessage 는 일반 트리에서만 렌더된다 — Plan B 의 App.tsx 가 이 계약을 사용한다.
    - `process.stdout.write` / `console.log` 절대 금지 (CLAUDE.md).
    - import 는 `.js` 확장자 사용 (bun/ESM).
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- store.messages</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n 'completedMessages: Message\[\]' ui-ink/src/store/messages.ts` 매칭
    - `grep -n 'activeMessage: Message | null' ui-ink/src/store/messages.ts` 매칭
    - `grep -n 'messages: Message\[\]' ui-ink/src/store/messages.ts` 매칭 없음 (legacy 제거 확인)
    - `cd ui-ink && bun run test` 전체 통과 (behavior 7개 + 기존 테스트)
  </acceptance_criteria>
  <done>
    messages.ts 가 completedMessages/activeMessage 분리 구조로 교체되고, 7개 behavior 테스트 + 기존 테스트가 모두 green.
  </done>
</task>

<task id="A-2" type="auto" tdd="true">
  <name>A-2: input.ts — history + slashOpen + 파일 persistence 확장 (INPT-03)</name>
  <files>ui-ink/src/store/input.ts, ui-ink/src/__tests__/store.input.test.ts</files>
  <read_first>
    - ui-ink/src/store/input.ts — 현재 buffer only 구조 확인
    - ui-ink/src/__tests__/ 디렉터리 ls — 기존 input 테스트 존재 여부
  </read_first>
  <behavior>
    - Test 1: 초기 상태 — buffer='', history=[], historyIndex=-1, slashOpen=false
    - Test 2: pushHistory('hello') → history=['hello'], historyIndex=-1 (커서 리셋)
    - Test 3: pushHistory 는 동일 문자열 연속 중복 저장 안 함 (마지막과 같으면 skip)
    - Test 4: history 최대 500개로 cap — 501번째 push 시 가장 오래된 것 제거
    - Test 5: historyUp() — index=0, buffer 가 history[length-1] 로 교체됨
    - Test 6: historyUp 추가 호출 — index=1, buffer 가 history[length-2] 로 교체
    - Test 7: historyDown() — index 감소, -1 에 도달하면 buffer 복원값(또는 빈문자열)
    - Test 8: setSlashOpen(true) → slashOpen=true
    - Test 9: loadHistory() — ~/.harness/history.txt 파일이 없으면 [] 반환 (파일 생성 안 함)
    - Test 10: loadHistory() — 파일에 'a\nb\nc\n' 있으면 ['c','b','a'] 역순 반환 (최신이 pop 대상)
    - Test 11: appendHistory('x') — 디렉터리 자동 생성 + 파일에 'x\n' 한 줄 append
    - Test 12: hydrate() — loadHistory 결과를 store.history 에 로드 (초기 마운트 시 1회)
    - Test 13: pushHistory() action 이 내부적으로 appendHistory() 를 호출 (파일에 즉시 반영)
  </behavior>
  <action>
    INPT-03 (history ↑↓ + 파일 persistence) 및 SlashPopup 표시 플래그 요구사항을 반영:

    ```typescript
    // 입력 슬라이스 — buffer + history + slashOpen + 파일 persistence (INPT-03, RND-05)
    import {create} from 'zustand'
    import {readFileSync, appendFileSync, mkdirSync, existsSync} from 'node:fs'
    import {homedir} from 'node:os'
    import {join, dirname} from 'node:path'

    const HISTORY_MAX = 500
    // ~/.harness/history.txt — Python REPL 과 동일 경로 (INPT-03)
    export const HISTORY_PATH = join(homedir(), '.harness', 'history.txt')

    // 파일에서 history 를 읽어 "오래된 → 최신" 배열로 반환.
    // 파일 형식: 한 줄당 한 항목, 가장 위가 오래된 것 (append 로 쌓이므로 자연스러움).
    // 반환 배열 순서는 store.history 와 동일 (oldest first), 최대 HISTORY_MAX 개로 truncate.
    export function loadHistory(): string[] {
      try {
        if (!existsSync(HISTORY_PATH)) return []
        const raw = readFileSync(HISTORY_PATH, 'utf8')
        const lines = raw.split('\n').filter((l) => l.length > 0)
        // 파일이 MAX 초과로 커졌을 때는 뒤쪽(최신) 500 개만 사용
        return lines.slice(-HISTORY_MAX)
      } catch {
        // 읽기 실패는 치명적이지 않음 — 세션은 빈 history 로 계속
        return []
      }
    }

    // history.txt 에 한 줄 추가. 디렉터리 없으면 생성. 실패해도 swallow.
    export function appendHistory(text: string): void {
      try {
        const dir = dirname(HISTORY_PATH)
        if (!existsSync(dir)) mkdirSync(dir, {recursive: true})
        // trailing newline 포함 — Python readline 포맷 호환
        appendFileSync(HISTORY_PATH, text + '\n', 'utf8')
      } catch {
        // 디스크 full / 권한 문제 등 — UI 는 계속 동작
      }
    }

    interface InputState {
      buffer: string
      history: string[]         // 오래된 → 최신 순
      historyIndex: number      // -1 = 미선택 (buffer 편집 중)
      slashOpen: boolean
      setBuffer: (v: string) => void
      clearBuffer: () => void
      pushHistory: (entry: string) => void
      historyUp: () => void     // 이전 history 를 buffer 에 로드
      historyDown: () => void   // 최신 방향으로 이동
      setSlashOpen: (open: boolean) => void
      hydrate: () => void       // 마운트 시 1회 — history.txt 로드
    }

    export const useInputStore = create<InputState>((set, get) => ({
      buffer: '',
      history: [],
      historyIndex: -1,
      slashOpen: false,

      setBuffer: (v) => set({buffer: v}),
      clearBuffer: () => set({buffer: '', historyIndex: -1}),

      pushHistory: (entry) => {
        const trimmed = entry.trim()
        if (!trimmed) return
        const state = get()
        // 직전 항목과 동일하면 파일에도 쓰지 않고 skip
        if (state.history[state.history.length - 1] === trimmed) {
          set({historyIndex: -1})
          return
        }
        const next = [...state.history, trimmed]
        if (next.length > HISTORY_MAX) next.shift()
        set({history: next, historyIndex: -1})
        // 파일 persistence — 실패해도 메모리 상태는 유지됨
        appendHistory(trimmed)
      },

      historyUp: () => set((s) => {
        if (s.history.length === 0) return {}
        const nextIdx = Math.min(s.historyIndex + 1, s.history.length - 1)
        const entry = s.history[s.history.length - 1 - nextIdx]
        return {historyIndex: nextIdx, buffer: entry ?? ''}
      }),

      historyDown: () => set((s) => {
        if (s.historyIndex <= 0) {
          return {historyIndex: -1, buffer: ''}
        }
        const nextIdx = s.historyIndex - 1
        const entry = s.history[s.history.length - 1 - nextIdx]
        return {historyIndex: nextIdx, buffer: entry ?? ''}
      }),

      setSlashOpen: (open) => set({slashOpen: open}),

      // App.tsx 마운트 시 useEffect 에서 1회 호출 — history.txt 를 메모리로 로드
      hydrate: () => {
        const loaded = loadHistory()
        if (loaded.length > 0) {
          set({history: loaded, historyIndex: -1})
        }
      },
    }))
    ```

    테스트 파일 `ui-ink/src/__tests__/store.input.test.ts` 신규 생성. 각 behavior 를 vitest `it()` 로 구현.
    - beforeEach 에서 setState 로 메모리 초기값 복구
    - 파일 테스트는 `HISTORY_PATH` 를 `tmpdir()/harness-test-<nanoid>/history.txt` 로 monkey-patch 하거나, `vi.mock('node:fs')` 로 readFileSync/appendFileSync/mkdirSync/existsSync 를 stub
    - Test 9/10: mock fs 로 readFileSync return 값 제어 후 loadHistory() 결과 검증
    - Test 11: mock appendFileSync spy 로 호출 인자 검증
    - Test 12: hydrate() 호출 후 store.history 가 loadHistory() 결과와 일치
    - Test 13: pushHistory() 호출 후 appendFileSync spy 가 호출됐는지 검증

    주의:
    - `node:fs` / `node:os` / `node:path` prefix 사용 — bun/ESM 호환
    - 파일 실패는 swallow — UI 계속 동작 (`appendHistory` 가 throw 해도 sync store 는 정상)
    - `HISTORY_PATH` export — 테스트에서 monkey-patch 가능하도록
    - Python REPL 과 동일 경로 (`~/.harness/history.txt`) — 추후 호환성 위해 포맷은 "한 줄당 한 항목"
    - slashOpen 은 단순 boolean — 팝업의 내부 상태(선택된 인덱스 등)는 Plan D 의 SlashPopup 컴포넌트가 자체 관리
    - import 는 `.js` 확장자 (상대 경로만 해당; node:fs 등은 built-in 이므로 확장자 불필요)
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- store.input</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n 'history: string\[\]' ui-ink/src/store/input.ts` 매칭
    - `grep -n 'slashOpen: boolean' ui-ink/src/store/input.ts` 매칭
    - `grep -n 'historyUp' ui-ink/src/store/input.ts` 및 `historyDown` 매칭
    - `grep -n 'appendHistory' ui-ink/src/store/input.ts` 매칭 (파일 persistence)
    - `grep -n 'history.txt' ui-ink/src/store/input.ts` 매칭 (~/.harness/history.txt 경로)
    - `grep -n 'hydrate' ui-ink/src/store/input.ts` 매칭 (마운트 훅)
    - `cd ui-ink && bun run test` 전체 통과 (exit 0)
  </acceptance_criteria>
  <done>
    input.ts 가 history/historyIndex/slashOpen + loadHistory/appendHistory/hydrate 를 노출하고 13개 behavior 테스트가 green.
  </done>
</task>

<task id="A-3" type="auto" tdd="true">
  <name>A-3: confirm.ts — stickyDeny + resolve + WS 응답 연결</name>
  <files>ui-ink/src/store/confirm.ts, ui-ink/src/ws/client.ts, ui-ink/src/__tests__/store.confirm.test.ts</files>
  <read_first>
    - ui-ink/src/store/confirm.ts — 현재 mode/payload/setConfirm/clearConfirm 구조
    - ui-ink/src/ws/client.ts — HarnessClient.send 시그니처 확인 (ClientMsg 타입)
  </read_first>
  <behavior>
    - Test 1: 초기 deniedPaths/deniedCmds 는 비어있는 Set
    - Test 2: addDenied('path', '/etc/passwd') → isDenied('path','/etc/passwd')===true
    - Test 3: addDenied('cmd', 'rm -rf /') → isDenied('cmd','rm -rf /')===true, 'cmd2' 는 false
    - Test 4: clearDenied() → 두 Set 모두 비워짐
    - Test 5: resolve(true) with mode='confirm_write' — client.send 가 {type:'confirm_write_response', accept:true} 로 호출되고, mode 가 'none' 으로 되돌아감
    - Test 6: resolve(false) with mode='confirm_write' payload.path='/foo' — deniedPaths 에 '/foo' 추가 (sticky deny)
    - Test 7: resolve(false) with mode='confirm_bash' payload.command='rm -rf /' — deniedCmds 에 명령 추가
    - Test 8: resolve(true) with mode='cplan_confirm' — client.send 가 {type:'cplan_confirm_response', accept:true} 호출 (만약 서버에 해당 응답 타입이 있으면; 없으면 info 로만 처리하고 mode='none')
  </behavior>
  <action>
    CNF-03 (sticky deny), CNF-04 (y/n 결정), CNF-05 (재질문 억제) 를 구현한다.

    ```typescript
    // confirm 다이얼로그 슬라이스 (CNF-03, CNF-04, CNF-05)
    import {create} from 'zustand'
    import type {ClientMsg} from '../protocol.js'
    import type {HarnessClient} from '../ws/client.js'

    export type ConfirmMode = 'none' | 'confirm_write' | 'confirm_bash' | 'cplan_confirm'
    export type DenyKind = 'path' | 'cmd'

    // WS 응답을 보낼 client 를 런타임에 주입 (store → client 순환 의존 회피)
    let boundClient: HarnessClient | null = null
    export function bindConfirmClient(client: HarnessClient | null): void {
      boundClient = client
    }

    interface ConfirmState {
      mode: ConfirmMode
      payload: Record<string, unknown>
      deniedPaths: Set<string>
      deniedCmds: Set<string>
      setConfirm: (mode: ConfirmMode, payload: Record<string, unknown>) => void
      clearConfirm: () => void
      addDenied: (kind: DenyKind, key: string) => void
      isDenied: (kind: DenyKind, key: string) => boolean
      clearDenied: () => void
      resolve: (accept: boolean) => void
    }

    export const useConfirmStore = create<ConfirmState>((set, get) => ({
      mode: 'none',
      payload: {},
      deniedPaths: new Set<string>(),
      deniedCmds: new Set<string>(),

      setConfirm: (mode, payload) => set({mode, payload}),
      clearConfirm: () => set({mode: 'none', payload: {}}),

      addDenied: (kind, key) => set((s) => {
        if (kind === 'path') {
          const next = new Set(s.deniedPaths); next.add(key)
          return {deniedPaths: next}
        }
        const next = new Set(s.deniedCmds); next.add(key)
        return {deniedCmds: next}
      }),

      isDenied: (kind, key) => {
        const s = get()
        return kind === 'path' ? s.deniedPaths.has(key) : s.deniedCmds.has(key)
      },

      clearDenied: () => set({deniedPaths: new Set(), deniedCmds: new Set()}),

      resolve: (accept) => {
        const s = get()
        const mode = s.mode
        const payload = s.payload

        // WS 응답 전송
        let response: ClientMsg | null = null
        if (mode === 'confirm_write') {
          response = {type: 'confirm_write_response', accept}
          if (!accept && typeof payload['path'] === 'string') {
            get().addDenied('path', payload['path'] as string)
          }
        } else if (mode === 'confirm_bash') {
          response = {type: 'confirm_bash_response', accept}
          if (!accept && typeof payload['command'] === 'string') {
            get().addDenied('cmd', payload['command'] as string)
          }
        } else if (mode === 'cplan_confirm') {
          // cplan 은 현재 서버 측 응답 타입이 없음 — 로컬 상태만 변경
          response = null
        }

        if (response && boundClient) {
          boundClient.send(response)
        }
        set({mode: 'none', payload: {}})
      },
    }))
    ```

    `ui-ink/src/ws/client.ts` 수정: HarnessClient 가 생성/close 될 때 `bindConfirmClient(this)` / `bindConfirmClient(null)` 호출하도록 한다. 구체 위치:
    - constructor 끝 또는 첫 connect() 에서 `bindConfirmClient(this)`
    - close() / disposal 시 `bindConfirmClient(null)`

    읽을 것: 먼저 `ui-ink/src/ws/client.ts` 를 열어 현재 HarnessClient 의 constructor/close 위치를 확인 후 위 2 라인을 삽입한다. 기존 동작 변경 없이 side-effect 만 추가.

    테스트 파일 `ui-ink/src/__tests__/store.confirm.test.ts`:
    - vitest 의 `vi.fn()` 으로 mockClient = `{send: vi.fn()}` 를 만들고 `bindConfirmClient(mockClient as unknown as HarnessClient)` 로 주입
    - 각 behavior 에 맞게 setConfirm → resolve → mockClient.send 호출 인자 검사
    - afterEach 에서 `bindConfirmClient(null)` + `useConfirmStore.setState({mode:'none', payload:{}, deniedPaths:new Set(), deniedCmds:new Set()})`

    주의:
    - `boundClient` 는 모듈 스코프 변수 — 테스트 격리를 위해 afterEach 에서 반드시 null 로 되돌린다.
    - cplan_confirm 은 현재 서버 프로토콜에 응답 타입이 없어 로컬 상태만 정리 (추후 서버 확장 시 재방문).
    - ConfirmMode 타입은 기존 유지 (Plan B 의 ConfirmDialog 가 이 타입을 import).
    - Set<string> 업데이트는 새 Set 생성 방식 (불변성 — zustand 가 참조 변경을 감지하도록).
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- store.confirm</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n 'deniedPaths: Set<string>' ui-ink/src/store/confirm.ts` 매칭
    - `grep -n 'resolve:' ui-ink/src/store/confirm.ts` 매칭
    - `grep -n 'bindConfirmClient' ui-ink/src/store/confirm.ts` 및 `ui-ink/src/ws/client.ts` 양쪽 매칭
    - `cd ui-ink && bun run test` 전체 green (behavior 8개)
  </acceptance_criteria>
  <done>
    confirm.ts 가 sticky deny + resolve(accept) + WS 전송을 수행하고, HarnessClient 가 바인딩 주입/해제하며, 8개 behavior 테스트 green.
  </done>
</task>

<task id="A-4" type="auto" tdd="true">
  <name>A-4: protocol.ts — CancelMsg 추가 (D-07)</name>
  <files>ui-ink/src/protocol.ts</files>
  <read_first>
    - ui-ink/src/protocol.ts — 현재 ClientMsg 유니온 확인
  </read_first>
  <behavior>
    - Test (컴파일 타임): `const m: ClientMsg = {type: 'cancel'}` 가 타입 에러 없이 통과
    - grep: `export interface CancelMsg { type: 'cancel' }` 존재
  </behavior>
  <action>
    D-07 (Ctrl+C → busy 시 cancel 전송) 를 위한 타입 추가. 파일 하단 "클라 → 서버 메시지 타입들" 섹션에 삽입:

    ```typescript
    export interface CancelMsg            { type: 'cancel' }

    export type ClientMsg =
      | InputMsg | ConfirmWriteResponse | ConfirmBashResponse | SlashMsg | PingMsg | CancelMsg
    ```

    서버 측 `cancel` 핸들러 존재 여부는 Plan A 의 범위 밖 — UI 는 send 만 하고, 서버가 해석하지 못하면 무시되거나 error 로 돌아온다 (기존 error case 에서 처리).

    주의: assertNever 헬퍼는 ServerMsg 전용이므로 ClientMsg 확장에는 영향 없음.
  </action>
  <verify>
    <automated>cd ui-ink && bunx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n 'CancelMsg' ui-ink/src/protocol.ts` 정의 1 + 유니온 1 = 2 매칭
    - `cd ui-ink && bunx tsc --noEmit` 에러 0
  </acceptance_criteria>
  <done>
    ClientMsg 유니온에 CancelMsg 가 추가되고 tsc 통과.
  </done>
</task>

<task id="A-5" type="auto" tdd="true">
  <name>A-5: dispatch.ts — slash_result cmd 별 확장</name>
  <files>ui-ink/src/ws/dispatch.ts, ui-ink/src/store/status.ts, ui-ink/src/__tests__/dispatch.test.ts</files>
  <read_first>
    - ui-ink/src/ws/dispatch.ts — slash_result 현재 case
    - ui-ink/src/store/status.ts — setState / setWorkingDir 존재 여부 확인 (없으면 추가해야 함)
    - .planning/phases/02-core-ux/02-RESEARCH.md — SlashCatalog 의 13개 명령 목록 참조
  </read_first>
  <behavior>
    - Test 1: dispatch({type:'slash_result', cmd:'clear'}) → useMessagesStore.getState().completedMessages === [], activeMessage===null
    - Test 2: dispatch({type:'slash_result', cmd:'cd', path:'/tmp'}) → useStatusStore.getState().working_dir === '/tmp'
    - Test 3: dispatch({type:'slash_result', cmd:'model', model:'qwen2.5-coder:32b'}) → status.model 업데이트
    - Test 4: dispatch({type:'slash_result', cmd:'mode', mode:'plan'}) → status.mode 업데이트
    - Test 5: 알려지지 않은 cmd — appendSystemMessage('/unknown 완료') fallback (기존 동작 유지)
    - Test 6: dispatch({type:'slash_result', cmd:'help'}) — 시스템 메시지 출력 (help_text 필드 있으면 본문으로)
  </behavior>
  <action>
    현재 `case 'slash_result':` 단일 분기를 cmd 별 switch 로 확장:

    ```typescript
    case 'slash_result': {
      const cmd = msg.cmd
      // 구조분해 시 any 방지 — msg 는 SlashResultMsg, 추가 필드는 [key:string]: unknown
      switch (cmd) {
        case 'clear':
          messages.clearMessages()
          break
        case 'cd': {
          const path = typeof msg['path'] === 'string' ? (msg['path'] as string) : undefined
          if (path) status.setWorkingDir(path)
          messages.appendSystemMessage(`cd ${path ?? ''}`)
          break
        }
        case 'model': {
          const model = typeof msg['model'] === 'string' ? (msg['model'] as string) : undefined
          if (model) status.setModel(model)
          messages.appendSystemMessage(`model: ${model ?? ''}`)
          break
        }
        case 'mode': {
          const mode = typeof msg['mode'] === 'string' ? (msg['mode'] as string) : undefined
          if (mode) status.setMode(mode)
          messages.appendSystemMessage(`mode: ${mode ?? ''}`)
          break
        }
        case 'help': {
          const text = typeof msg['help_text'] === 'string'
            ? (msg['help_text'] as string)
            : '/help'
          messages.appendSystemMessage(text)
          break
        }
        default:
          messages.appendSystemMessage(`/${cmd} 완료`)
      }
      break
    }
    ```

    **전제 조건** — `ui-ink/src/store/status.ts` 에 `setWorkingDir(path)`, `setModel(model)`, `setMode(mode)` 메서드가 필요하다. Phase 1 의 status 스토어가 이미 setState 로 batch 업데이트만 가지고 있다면 개별 setter 를 추가한다:

    ```typescript
    // status.ts 에 추가 (기존 setState 유지)
    setWorkingDir: (working_dir: string) => set({working_dir}),
    setModel: (model: string) => set({model}),
    setMode: (mode: string) => set({mode}),
    ```

    status.ts 를 먼저 읽어 현재 상태 키 이름(working_dir / workingDir 등)을 확인한 후 일관된 네이밍을 사용한다. Phase 1 의 state_snapshot 처리를 보면 `working_dir` snake_case 가 이미 사용 중.

    테스트 `ui-ink/src/__tests__/dispatch.test.ts` 신규 생성 (또는 기존 파일 확장):
    - beforeEach 에서 모든 관련 스토어 초기화
    - 각 behavior 에 맞는 dispatch 호출 후 getState() 검증
    - vitest `it()` 6개

    주의:
    - 서버에서 오는 payload 필드 이름은 CONTEXT/RESEARCH 에 명시되지 않았지만 기존 Python 백엔드 `cli/slash.py` 패턴에 맞춰 path/model/mode/help_text 로 가정한다. 필드가 없으면 시스템 메시지 fallback.
    - unknown cmd 는 반드시 appendSystemMessage fallback (exhaustive switch 강제하지 않음 — 서버가 미래에 새 cmd 추가해도 에러 안 남).
    - exhaustive switch 의 `assertNever(msg)` default 는 최상위 ServerMsg 에만 적용 — cmd 는 문자열이므로 해당 없음.
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- dispatch</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "case 'clear':" ui-ink/src/ws/dispatch.ts` 매칭
    - `grep -n "case 'cd':" ui-ink/src/ws/dispatch.ts` 매칭
    - `grep -n 'setWorkingDir' ui-ink/src/store/status.ts` 매칭
    - `cd ui-ink && bun run test` 전체 green
  </acceptance_criteria>
  <done>
    dispatch 가 slash_result 의 5개 cmd 를 분기 처리하고, status.ts 에 개별 setter 추가, 6개 behavior 테스트 green.
  </done>
</task>

<task id="A-6" type="auto">
  <name>A-6: 기존 테스트 회귀 확인 + TypeScript 엄격 검증</name>
  <files>ui-ink/src/__tests__/ (기존 파일 업데이트)</files>
  <read_first>
    - ui-ink/src/__tests__/ 디렉터리 ls — Phase 1 에서 추가된 테스트 목록 파악
    - ui-ink/package.json scripts — test / typecheck 명령 확인
  </read_first>
  <action>
    Phase 1 테스트 중 `messages` 배열을 직접 참조하는 기존 파일이 있다면 `completedMessages` 로 교체한다. 대상 예:
    - `useMessagesStore.getState().messages` → `.completedMessages` 또는 `.activeMessage` 로 치환
    - 스트리밍 상태를 테스트하던 코드 — 종료 전에는 `activeMessage.content` 로, 종료 후에는 `completedMessages[n]` 로 검증

    실행 순서:
    1. `cd ui-ink && bun run test` 실행 — 빨간 테스트 목록 수집
    2. 각 실패 테스트를 열어 `messages` 접근 지점을 분리 구조로 교정
    3. `bun run test` 다시 실행 — 전체 green 확인
    4. `bunx tsc --noEmit` 실행 — 타입 에러 0 확인
    5. `bun run lint` (eslint) 실행 — `process.stdout.write` / `console.log` / `child_process` / DOM 태그 사용 0 확인

    Plan A 에서 신규 작성/확장한 테스트 (A-1, A-2, A-3, A-5) 는 이미 green 상태여야 한다. 이 task 는 Phase 1 잔존 테스트의 회귀를 처리한다.

    주의:
    - 이 task 는 "기존 테스트 업데이트만" — 새 behavior 추가 금지.
    - 만약 Phase 1 에 messages 배열을 렌더링하는 테스트가 있다면 (App.tsx 렌더 테스트 등) 그건 Plan B 범위다. Plan A 의 이 task 는 store 레벨 회귀만 처리한다.
  </action>
  <verify>
    <automated>cd ui-ink && bun run test && bunx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - `cd ui-ink && bun run test` 전체 green
    - `cd ui-ink && bunx tsc --noEmit` 에러 0
    - `grep -rn 'useMessagesStore.getState().messages\b' ui-ink/src/__tests__/` 매칭 0 (legacy 접근자 제거)
  </acceptance_criteria>
  <done>
    Phase 1 테스트 잔존 에러 0, tsc strict mode 통과, legacy `messages` 접근자 테스트 코드에서 제거.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| store → ws client | store.resolve() 가 WS 응답을 전송. bindConfirmClient 주입이 실패하면 silent no-op |
| dispatch → store | slash_result cmd 값(문자열)이 신뢰 입력. 서버 변조 시 clearMessages/cd 등 부작용 가능 |
| store → fs (~/.harness/history.txt) | appendHistory/loadHistory 가 사용자 홈 디렉터리에 파일 쓰기/읽기 수행 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02A-01 | T (Tampering) | dispatch slash_result | mitigate | cmd 필드는 화이트리스트 switch — unknown cmd 는 appendSystemMessage fallback 만 수행, 파괴적 액션 없음 |
| T-02A-02 | D (DoS) | input.ts history | mitigate | HISTORY_MAX=500 로 unbounded growth 차단; loadHistory 는 파일 read 시 slice(-500) |
| T-02A-03 | I (Info) | confirm.ts resolve | accept | 응답 payload 는 accept:boolean 만 — 추가 민감정보 없음, 서버 동일 세션 채널 재사용 |
| T-02A-04 | R (Repudiation) | deniedPaths/Cmds | accept | sticky deny 는 세션 내 메모리 — 로그/감사 요구 없음, 프로세스 종료 시 소멸 |
| T-02A-05 | I (Info) | ~/.harness/history.txt 평문 저장 | accept | Python REPL 과 동일 포맷/경로 — 사용자 홈 디렉터리 권한 700 보장을 OS 가 담당. 비밀번호/토큰 입력 방어는 UI 레벨 스코프 밖 |
| T-02A-06 | T (Tampering) | history.txt 외부 편집 | accept | 파일이 외부에서 조작되어도 loadHistory 는 line split 만 수행 — 실행 경로 없음, pushHistory 가 결국 append 로 덮음 |
</threat_model>

<verification>
```bash
cd /Users/johyeonchang/harness/ui-ink
bun run test
bunx tsc --noEmit
bun run lint  # ESLint 금지 규칙 (process.stdout.write / console.log / child_process / DOM 태그)

# 계약 검증
grep -n 'completedMessages: Message\[\]' src/store/messages.ts
grep -n 'activeMessage: Message | null' src/store/messages.ts
grep -n 'history: string\[\]' src/store/input.ts
grep -n 'slashOpen: boolean' src/store/input.ts
grep -n 'appendHistory' src/store/input.ts
grep -n 'history.txt' src/store/input.ts
grep -n 'deniedPaths: Set<string>' src/store/confirm.ts
grep -n 'resolve:' src/store/confirm.ts
grep -n 'CancelMsg' src/protocol.ts
grep -n "case 'clear':" src/ws/dispatch.ts
```
</verification>

<success_criteria>
- 모든 6개 task 의 acceptance_criteria 통과
- `bun run test` 전체 green (Plan A 신규 + Phase 1 회귀)
- `bunx tsc --noEmit` strict mode 통과
- `bun run lint` 금지 패턴 0건
- Plan B 가 이 계약만 import 해서 컴포넌트를 구현할 수 있는 상태
- ~/.harness/history.txt 파일 persistence 동작 (INPT-03 Phase 2 SC-2 closing)
</success_criteria>

<output>
완료 후 `.planning/phases/02-core-ux/02-PLAN-A-SUMMARY.md` 작성:
- 변경된 store 계약 diff 요약
- 추가된 테스트 수 / 전체 테스트 수
- Plan B 가 사용할 수 있는 public API (completedMessages, activeMessage, history, hydrate 등)
- ~/.harness/history.txt 파일 포맷 및 App.tsx 마운트 시 hydrate() 호출 위치 가이드
</output>
</content>
</invoke>