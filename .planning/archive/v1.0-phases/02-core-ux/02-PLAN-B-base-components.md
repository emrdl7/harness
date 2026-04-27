---
phase: 02-core-ux
plan: B
wave: 1
depends_on: []
autonomous: true
files_modified:
  - ui-ink/src/components/Divider.tsx
  - ui-ink/src/components/StatusBar.tsx
  - ui-ink/src/components/MessageList.tsx
  - ui-ink/src/components/Message.tsx
  - ui-ink/src/slash-catalog.ts
  - ui-ink/src/theme.ts
  - ui-ink/src/App.tsx
  - ui-ink/src/__tests__/components.statusbar.test.tsx
  - ui-ink/src/__tests__/components.divider.test.tsx
  - ui-ink/src/__tests__/components.messagelist.test.tsx
  - ui-ink/src/__tests__/app.smoke.test.tsx
requirements:
  - STAT-01
  - STAT-02
  - RND-04
  - RND-05
  - RND-10
  - RND-11
  - INPT-07
  - INPT-09
  - INPT-10
must_haves:
  truths:
    - "화면 하단 레이아웃이 D-01 순서(Static → active → divider → InputArea|ConfirmDialog → divider → StatusBar)로 고정된다"
    - "Divider 는 가로폭에 맞춰 '─' 문자를 채운 dimColor Text — active↔input 과 input↔statusbar 두 자리에서 사용된다"
    - "StatusBar 는 path / model / mode / turn / ctx% / room 6개 세그먼트를 우선순위 드롭과 함께 렌더한다"
    - "MessageList 는 completedMessages 를 <Static>으로, activeMessage 를 일반 Box 로 렌더한다 (Phase 1 의 단일 map 대체)"
    - "slash-catalog.ts 는 13개 명령을 정적 하드코딩한 불변 배열을 export 한다"
    - "theme.ts 는 role/mode/status 색상 팔레트를 export 한다 (하드코딩 색상 제거의 출발점)"
    - "Ctrl+C (busy) → cancel ClientMsg 전송 + '취소 요청 중…' 시스템 메시지, Ctrl+C (idle) → 2초 내 2회 반복 시 exit"
    - "좁은 폭(예: COLUMNS=40)에서 StatusBar 세그먼트가 우선순위 순으로 드롭되어 넘치지 않는다"
  artifacts:
    - path: "ui-ink/src/components/Divider.tsx"
      provides: "가로폭 자동 채움 dimColor 구분선"
      min_lines: 10
    - path: "ui-ink/src/components/StatusBar.tsx"
      provides: "6 세그먼트 상태 표시줄 + graceful drop"
      min_lines: 60
    - path: "ui-ink/src/components/MessageList.tsx"
      provides: "<Static>(completed) + active(일반 Box) 분리 렌더"
      min_lines: 40
    - path: "ui-ink/src/components/Message.tsx"
      provides: "role 별 prefix/색상 기본 렌더"
      min_lines: 30
    - path: "ui-ink/src/slash-catalog.ts"
      provides: "13개 slash 명령 정적 목록"
      contains: "SLASH_CATALOG"
    - path: "ui-ink/src/theme.ts"
      provides: "색상 팔레트 상수"
      contains: "export const theme"
    - path: "ui-ink/src/App.tsx"
      provides: "D-01..D-03 레이아웃 + Ctrl+C/D + useStdout.columns resize"
      contains: "useStdout"
  key_links:
    - from: "ui-ink/src/components/MessageList.tsx"
      to: "ui-ink/src/store/messages.ts"
      via: "useShallow 로 completedMessages + activeMessage 선택"
      pattern: "completedMessages"
    - from: "ui-ink/src/App.tsx"
      to: "ui-ink/src/components/StatusBar.tsx"
      via: "직접 렌더, useStdout().stdout.columns 를 prop 으로 전달"
      pattern: "<StatusBar"
    - from: "ui-ink/src/App.tsx"
      to: "ui-ink/src/ws/client.ts"
      via: "Ctrl+C busy → client.send({type:'cancel'})"
      pattern: "type: 'cancel'"
---

<objective>
Plan A 가 확정한 store 계약(completedMessages / activeMessage / history / slashOpen / resolve) 위에 Phase 2 의 기반 UI 컴포넌트를 신규 생성하고 App.tsx 를 전면 재작성한다. D-01~D-04 레이아웃, D-07~D-08 Ctrl+C 처리, <Static> 기반 스트리밍 안정성을 확보한다. MultilineInput / SlashPopup / ConfirmDialog / 고급 렌더링(syntax highlight, diff) 은 Wave 2 에서 채워 넣는 전제 — 이 Plan 은 "껍데기와 레이아웃과 상태 표시줄" 까지.
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
<!-- Plan A 가 제공하는 store 계약 — 이 Plan 은 이 계약만 사용 -->

```typescript
// useMessagesStore — Plan A 결과물
interface MessagesState {
  completedMessages: Message[]    // <Static> 전용
  activeMessage: Message | null   // 일반 Box 전용
  // ... (appendUserMessage / agentStart / appendToken / agentEnd / ... 동일)
  clearMessages: () => void
}

// useInputStore — Plan A 결과물
interface InputState {
  buffer: string
  history: string[]
  historyIndex: number
  slashOpen: boolean
  setBuffer(v: string): void
  clearBuffer(): void
  pushHistory(entry: string): void
  historyUp(): void
  historyDown(): void
  setSlashOpen(open: boolean): void
}

// useConfirmStore — Plan A 결과물
interface ConfirmState {
  mode: 'none' | 'confirm_write' | 'confirm_bash' | 'cplan_confirm'
  payload: Record<string, unknown>
  resolve(accept: boolean): void
  // ...
}

// useStatusStore — Plan A 에서 setter 추가됨
interface StatusState {
  connected: boolean
  busy: boolean
  working_dir: string
  model: string
  mode: string
  turns: number
  ctx_tokens?: number
  setWorkingDir(path: string): void
  setModel(model: string): void
  setMode(mode: string): void
  setBusy(busy: boolean): void
  setConnected(connected: boolean): void
  setState(partial: Partial<StatusState>): void
}

// useRoomStore — Phase 1 기존
interface RoomState {
  room: string | null
  members: string[]
}
```

Ink API 참고:
- `useStdout()` → `{stdout: NodeJS.WriteStream}` / `stdout.columns` 가 현재 가로폭
- `<Static items={arr}>{(m) => <Box key={m.id}>…</Box>}</Static>` — append-only 최적화
- `useInput((ch, key) => …)` — key 객체: return / backspace / delete / upArrow / downArrow / leftArrow / rightArrow / ctrl / meta / shift / escape / tab
- `<Spacer />` / `flexGrow={1}` 로 우측 정렬 가능
- `ink-spinner` 의 `<Spinner type='dots' />` — D-05 에 따라 <Static> 바깥에서만 사용
</interfaces>
</context>

<tasks>

<task id="B-1" type="auto" tdd="true">
  <name>B-1: Divider.tsx — 가로폭 자동 채움 구분선</name>
  <files>ui-ink/src/components/Divider.tsx, ui-ink/src/__tests__/components.divider.test.tsx</files>
  <read_first>
    - ui-ink/src/components/ 디렉터리 ls — 기존 컴포넌트 네이밍 규칙 파악
    - ui-ink/package.json — ink 버전 / ink-testing-library 사용 가능 여부 확인
  </read_first>
  <behavior>
    - Test 1: <Divider columns={40} /> 렌더 결과에 '─' 가 40개 포함
    - Test 2: <Divider columns={1} /> 렌더 결과에 '─' 가 최소 1개 (음수/0 방어)
    - Test 3: <Divider /> (columns 미지정) — useStdout().stdout.columns 또는 80 기본값 사용
    - Test 4: dimColor 속성이 Text 에 적용되어 있다 (DOM snapshot)
  </behavior>
  <action>
    신규 파일 `ui-ink/src/components/Divider.tsx`:

    ```typescript
    // 구분선 컴포넌트 — D-02 active↔input, input↔statusbar 두 자리에서 사용 (RND-04)
    import React from 'react'
    import {Text, useStdout} from 'ink'

    interface DividerProps {
      columns?: number   // 테스트 편의용 override — 미지정 시 stdout.columns
      char?: string      // 기본 '─'
    }

    export const Divider: React.FC<DividerProps> = ({columns, char = '─'}) => {
      const {stdout} = useStdout()
      const width = Math.max(1, columns ?? stdout?.columns ?? 80)
      return <Text dimColor>{char.repeat(width)}</Text>
    }
    ```

    테스트 `ui-ink/src/__tests__/components.divider.test.tsx`:
    - `ink-testing-library` 의 `render()` 사용
    - 결과 `lastFrame()` 문자열에서 '─' 개수 검증
    - columns={40} → '─'.repeat(40) 포함
    - columns={0} → 최소 1개 (Math.max 방어)
    - 기본값 — process.stdout.columns 또는 80 은 환경의존, 이 케이스는 "1 이상" 만 검증

    주의:
    - JSX 는 Ink 컴포넌트만 (`<div>` `<span>` 금지 — CLAUDE.md).
    - 들여쓰기 2 spaces, single quote, 세미콜론 없음.
    - export 는 default 아닌 named (`export const Divider`).
    - import 는 `.js` 확장자 붙이지 않음 (이 파일은 React/Ink 외부 패키지만 import).
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- components.divider</automated>
  </verify>
  <acceptance_criteria>
    - `ls ui-ink/src/components/Divider.tsx` 파일 존재
    - `grep -n 'dimColor' ui-ink/src/components/Divider.tsx` 매칭
    - `cd ui-ink && bun run test` green (behavior 4개)
  </acceptance_criteria>
  <done>
    Divider 컴포넌트가 존재하고 columns prop / 기본값 / 최소 1개 방어 동작, 테스트 4개 green.
  </done>
</task>

<task id="B-2" type="auto">
  <name>B-2: slash-catalog.ts + theme.ts — 정적 상수 파일</name>
  <files>ui-ink/src/slash-catalog.ts, ui-ink/src/theme.ts</files>
  <read_first>
    - .planning/phases/02-core-ux/02-CONTEXT.md — D-06 SlashCatalog 하드코딩 결정 확인
    - .planning/phases/02-core-ux/02-RESEARCH.md — 13개 slash 명령 목록 (있으면)
    - ui-ink/src/App.tsx — Phase 1 에서 색상을 어떻게 사용했는지 (cyan/yellow/green/gray) 확인
  </read_first>
  <action>
    **신규 파일 `ui-ink/src/slash-catalog.ts`** — D-06 에 따라 정적 하드코딩:

    ```typescript
    // 슬래시 명령 카탈로그 — D-06 정적 하드코딩 (INPT-09, INPT-10)
    // 런타임에 서버로부터 불러오지 않음. 명령 목록 변경 시 이 파일을 직접 편집.

    export interface SlashCommand {
      name: string         // '/' 제외 (예: 'help')
      summary: string      // 한 줄 설명 (한국어)
      usage?: string       // 인자 포맷 힌트 (예: '<path>')
    }

    export const SLASH_CATALOG: readonly SlashCommand[] = Object.freeze([
      {name: 'help',    summary: '명령 목록 표시'},
      {name: 'clear',   summary: '대화 초기화'},
      {name: 'quit',    summary: '세션 종료'},
      {name: 'exit',    summary: '세션 종료 (quit alias)'},
      {name: 'cd',      summary: '작업 디렉터리 변경', usage: '<path>'},
      {name: 'pwd',     summary: '현재 작업 디렉터리 표시'},
      {name: 'model',   summary: '모델 변경', usage: '<name>'},
      {name: 'mode',    summary: '모드 변경 (agent/plan/...)', usage: '<name>'},
      {name: 'save',    summary: '세션 저장', usage: '[name]'},
      {name: 'load',    summary: '세션 불러오기', usage: '<name>'},
      {name: 'history', summary: '명령 히스토리 표시'},
      {name: 'reset',   summary: '컨텍스트 초기화'},
      {name: 'status',  summary: '현재 상태 요약'},
    ])

    export function filterSlash(query: string): readonly SlashCommand[] {
      const q = query.replace(/^\//, '').toLowerCase()
      if (!q) return SLASH_CATALOG
      return SLASH_CATALOG.filter((c) => c.name.toLowerCase().startsWith(q))
    }
    ```

    **신규 파일 `ui-ink/src/theme.ts`** — 하드코딩 색상 팔레트:

    ```typescript
    // 색상 팔레트 — role/mode/status 별 일관된 색 (RND-10, RND-11)
    // Ink 의 color prop 에 그대로 전달 가능한 문자열.

    export const theme = {
      role: {
        user: 'cyan',
        assistant: 'yellow',
        tool: 'green',
        system: 'gray',
      },
      status: {
        connected: 'green',
        disconnected: 'red',
        busy: 'cyan',
      },
      mode: {
        agent: 'yellow',
        plan: 'magenta',
        review: 'blue',
        default: 'white',
      },
      danger: {
        safe: 'green',
        dangerous: 'red',
      },
      muted: 'gray',
    } as const

    export type RoleColor = keyof typeof theme.role
    ```

    주의:
    - 두 파일 모두 pure data/pure function — React 의존 없음, 테스트 불필요 (TypeScript 컴파일이 검증).
    - `as const` + `Object.freeze` 로 런타임/컴파일 불변성 확보.
    - 13개 명령 중 실제 서버가 지원하지 않는 것이 있어도 UI 팝업 목록일 뿐, 서버는 unknown slash → error 응답.
    - import 는 `.js` 확장자 사용 불필요 (이 파일들은 외부 import 없음).
  </action>
  <verify>
    <automated>cd ui-ink && bunx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - `ls ui-ink/src/slash-catalog.ts ui-ink/src/theme.ts` 두 파일 존재
    - `grep -c "name:" ui-ink/src/slash-catalog.ts` = 13 (정확히 13개 명령)
    - `grep -n "export const theme" ui-ink/src/theme.ts` 매칭
    - `cd ui-ink && bunx tsc --noEmit` 에러 0
  </acceptance_criteria>
  <done>
    slash-catalog.ts 에 13개 명령 + filter 헬퍼, theme.ts 에 role/status/mode/danger 팔레트, tsc 통과.
  </done>
</task>

<task id="B-3" type="auto" tdd="true">
  <name>B-3: StatusBar.tsx — 6 세그먼트 + 우선순위 드롭</name>
  <files>ui-ink/src/components/StatusBar.tsx, ui-ink/src/__tests__/components.statusbar.test.tsx</files>
  <read_first>
    - ui-ink/src/store/status.ts — 필드 이름 확인 (working_dir / model / mode / turns / ctx_tokens)
    - ui-ink/src/store/room.ts — room 필드 이름 확인
    - ui-ink/src/theme.ts — 방금 만든 팔레트 사용
  </read_first>
  <behavior>
    - Test 1: 넓은 폭(columns=120) — path, model, mode, turn, ctx%, room 6개 세그먼트가 모두 출력됨
    - Test 2: 좁은 폭(columns=40) — path 는 반드시 표시되지만 일부 세그먼트(room, ctx%) 는 드롭
    - Test 3: busy=true — spinner 프레임(<Spinner>) 이 왼쪽에 출력됨
    - Test 4: connected=false — disconnected 표시(red 색)
    - Test 5: ctx_tokens 가 undefined — ctx% 세그먼트 skip
    - Test 6: room=null — room 세그먼트 skip
  </behavior>
  <action>
    신규 파일 `ui-ink/src/components/StatusBar.tsx`:

    ```typescript
    // StatusBar — path / model / mode / turn / ctx% / room 6 세그먼트 (STAT-01, STAT-02)
    // 좁은 폭에서는 우선순위 순으로 세그먼트 드롭 (drop list: room → ctx% → turn → mode → model → path)
    import React from 'react'
    import {Box, Text} from 'ink'
    import Spinner from 'ink-spinner'
    import {useShallow} from 'zustand/react/shallow'
    import {useStatusStore} from '../store/status.js'
    import {useRoomStore} from '../store/room.js'
    import {theme} from '../theme.js'

    interface StatusBarProps {
      columns: number
    }

    interface Segment {
      key: string
      render: () => React.ReactElement
      textLen: number     // 대략적인 가시 길이 (ANSI/색 제외)
      priority: number    // 낮을수록 먼저 드롭
    }

    // D-01 최하단 — busy spinner 좌측, 세그먼트들 우측 흐름
    export const StatusBar: React.FC<StatusBarProps> = ({columns}) => {
      const {connected, busy, working_dir, model, mode, turns, ctx_tokens} = useStatusStore(
        useShallow((s) => ({
          connected: s.connected,
          busy: s.busy,
          working_dir: s.working_dir,
          model: s.model,
          mode: s.mode,
          turns: s.turns,
          ctx_tokens: s.ctx_tokens,
        })),
      )
      const room = useRoomStore(useShallow((s) => s.room))

      // ctx% = ctx_tokens / 32768 (임시 기준; 실제 context window 는 모델별 다름 — Wave 2 에서 정밀화)
      const CTX_CAP = 32768
      const ctxPct = typeof ctx_tokens === 'number'
        ? Math.min(100, Math.round((ctx_tokens / CTX_CAP) * 100))
        : undefined

      // 세그먼트 정의 — priority 낮은 것부터 좁은 폭에서 드롭됨
      const segments: Segment[] = []

      // path — priority 최고 (절대 드롭 안 됨)
      const pathText = shortenPath(working_dir ?? '')
      segments.push({
        key: 'path',
        render: () => <Text color={theme.muted}>{pathText}</Text>,
        textLen: pathText.length,
        priority: 100,
      })

      if (model) {
        segments.push({
          key: 'model',
          render: () => <Text color={theme.muted}>{model}</Text>,
          textLen: model.length,
          priority: 80,
        })
      }

      if (mode) {
        const modeColor = (theme.mode as Record<string, string>)[mode] ?? theme.mode.default
        segments.push({
          key: 'mode',
          render: () => <Text color={modeColor}>{mode}</Text>,
          textLen: mode.length,
          priority: 60,
        })
      }

      if (typeof turns === 'number') {
        const turnText = `turn ${turns}`
        segments.push({
          key: 'turn',
          render: () => <Text color={theme.muted}>{turnText}</Text>,
          textLen: turnText.length,
          priority: 50,
        })
      }

      if (ctxPct !== undefined) {
        const ctxText = `ctx ${ctxPct}%`
        segments.push({
          key: 'ctx',
          render: () => <Text color={theme.muted}>{ctxText}</Text>,
          textLen: ctxText.length,
          priority: 40,
        })
      }

      if (room) {
        const roomText = `#${room}`
        segments.push({
          key: 'room',
          render: () => <Text color={theme.muted}>{roomText}</Text>,
          textLen: roomText.length,
          priority: 30,
        })
      }

      // connected 상태 — path 앞에 고정 표시
      const connText = connected ? '● connected' : '○ disconnected'
      const connColor = connected ? theme.status.connected : theme.status.disconnected

      // 좁은 폭 처리 — 총 길이 + separator(' | ') 계산
      const SEP = ' | '
      const fixedLen = connText.length + 2 /* busy spinner + space */ + 1 /* trailing */
      const budget = Math.max(0, columns - fixedLen)

      // priority 높은 순으로 포함 여부 결정
      const sorted = [...segments].sort((a, b) => b.priority - a.priority)
      const kept: Segment[] = []
      let used = 0
      for (const seg of sorted) {
        const cost = seg.textLen + (kept.length > 0 ? SEP.length : 0)
        if (used + cost <= budget) {
          kept.push(seg)
          used += cost
        }
      }
      // 원래 priority 순서(path → ... → room)로 다시 정렬
      kept.sort((a, b) => b.priority - a.priority)

      return (
        <Box>
          {busy
            ? <Text color={theme.status.busy}><Spinner type='dots'/>{' '}</Text>
            : <Text>{'  '}</Text>}
          <Text color={connColor}>{connText}</Text>
          {kept.map((seg, i) => (
            <React.Fragment key={seg.key}>
              <Text color={theme.muted}>{SEP}</Text>
              {seg.render()}
            </React.Fragment>
          ))}
        </Box>
      )
    }

    // path 축약 — 홈은 ~, 절대경로는 마지막 2 세그먼트만
    function shortenPath(p: string): string {
      if (!p) return ''
      const home = process.env['HOME']
      let out = p
      if (home && p.startsWith(home)) out = '~' + p.slice(home.length)
      const parts = out.split('/').filter(Boolean)
      if (parts.length > 2) {
        return (out.startsWith('/') ? '/' : '') + '…/' + parts.slice(-2).join('/')
      }
      return out
    }
    ```

    테스트 `ui-ink/src/__tests__/components.statusbar.test.tsx`:
    - `ink-testing-library` + zustand setState 로 각 시나리오 세팅
    - render 전 `useStatusStore.setState({connected:true, busy:false, working_dir:'/home/user/project', model:'qwen2.5-coder:32b', mode:'agent', turns:3, ctx_tokens:1000})` 등
    - `<StatusBar columns={120}/>` / `<StatusBar columns={40}/>` lastFrame() 문자열 검증
    - behavior 6 각각 검증
    - Fragment key 경고 방지 위해 `key={seg.key}` 확인

    주의:
    - Spinner 는 ink-spinner 의 `<Spinner type='dots'/>` — D-05 에 따라 `<Static>` 바깥에서만 사용. StatusBar 는 일반 트리에 있으므로 OK.
    - 하드코딩된 CTX_CAP=32768 은 임시 — Wave 2 에서 모델별 정밀화.
    - 색상은 theme.ts 에서만 가져옴 (RND-10 color token 일원화 준비).
    - `process.env['HOME']` 접근 — bracket notation 사용 (TypeScript strict 환경 기본).
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- components.statusbar</automated>
  </verify>
  <acceptance_criteria>
    - `ls ui-ink/src/components/StatusBar.tsx` 파일 존재
    - `grep -n 'Spinner' ui-ink/src/components/StatusBar.tsx` 매칭 (ink-spinner 사용)
    - `grep -n 'priority' ui-ink/src/components/StatusBar.tsx` 매칭 (드롭 로직 존재)
    - `cd ui-ink && bun run test` green (behavior 6개)
  </acceptance_criteria>
  <done>
    StatusBar 가 6 세그먼트를 렌더하고 좁은 폭에서 priority 순 드롭 동작, 6개 behavior 테스트 green.
  </done>
</task>

<task id="B-4" type="auto" tdd="true">
  <name>B-4: MessageList.tsx + Message.tsx — Static/active 분리 렌더</name>
  <files>ui-ink/src/components/MessageList.tsx, ui-ink/src/components/Message.tsx, ui-ink/src/__tests__/components.messagelist.test.tsx</files>
  <read_first>
    - ui-ink/src/store/messages.ts — Plan A 결과 (completedMessages / activeMessage 구조)
    - ui-ink/src/App.tsx — Phase 1 의 messages.map 로직 참고 (role 별 prefix/색상)
    - ui-ink/src/theme.ts — role 색상 사용
  </read_first>
  <behavior>
    - Test 1: completedMessages=[user1, assistant1], activeMessage=null — 2 메시지 렌더, user prefix='❯ ', assistant prefix='● '
    - Test 2: completedMessages=[], activeMessage={role:'assistant',content:'...'} — assistant 메시지 1개만 렌더
    - Test 3: completedMessages=[user1], activeMessage={role:'assistant',content:'streaming...'} — 2개 렌더, 순서대로
    - Test 4: Message 컴포넌트 단독 — role='system' 일 때 gray 색 + prefix='  '
    - Test 5: Message — role='tool' 일 때 green 색 + prefix='└ '
    - Test 6: ink-testing-library 로 렌더 시 React key warning 0 (id 기반 key 사용 검증 — console.error 가로채기)
  </behavior>
  <action>
    **신규 파일 `ui-ink/src/components/Message.tsx`** — 단일 메시지 기본 렌더 (syntax highlight / diff 는 Wave 2 에서 확장):

    ```typescript
    // 단일 Message 기본 렌더 — role 별 prefix + 색상 (RND-10, RND-11)
    // 코드 블록 / diff / syntax highlight 는 Wave 2 에서 확장.
    import React from 'react'
    import {Box, Text} from 'ink'
    import type {Message as MessageType} from '../store/messages.js'
    import {theme} from '../theme.js'

    interface MessageProps {
      message: MessageType
    }

    const PREFIX: Record<MessageType['role'], string> = {
      user: '❯ ',
      assistant: '● ',
      tool: '└ ',
      system: '  ',
    }

    export const Message: React.FC<MessageProps> = ({message}) => {
      const color = theme.role[message.role]
      const prefix = PREFIX[message.role]
      return (
        <Box marginBottom={0}>
          <Text color={color} bold={message.role !== 'system'}>{prefix}</Text>
          <Text wrap='wrap'>{message.content}</Text>
        </Box>
      )
    }
    ```

    **신규 파일 `ui-ink/src/components/MessageList.tsx`** — D-04 경계 구현:

    ```typescript
    // MessageList — completedMessages 는 <Static>, activeMessage 는 일반 Box (RND-01, RND-02)
    // <Static>: append-only 로 이미 렌더된 프레임을 재렌더하지 않음 → scrollback 안정
    // active: in-place 업데이트로 매 토큰마다 리렌더 가능
    import React from 'react'
    import {Box, Static} from 'ink'
    import {useShallow} from 'zustand/react/shallow'
    import {useMessagesStore} from '../store/messages.js'
    import {Message} from './Message.js'

    export const MessageList: React.FC = () => {
      const completed = useMessagesStore(useShallow((s) => s.completedMessages))
      const active = useMessagesStore(useShallow((s) => s.activeMessage))

      return (
        <Box flexDirection='column'>
          <Static items={completed}>
            {(m) => <Message key={m.id} message={m}/>}
          </Static>
          {active ? (
            <Box flexDirection='column'>
              <Message message={active}/>
            </Box>
          ) : null}
        </Box>
      )
    }
    ```

    테스트 `ui-ink/src/__tests__/components.messagelist.test.tsx`:
    - vitest + ink-testing-library
    - beforeEach 에서 `useMessagesStore.setState({completedMessages: [...], activeMessage: ...})`
    - lastFrame() 에서 prefix / content 문자열 존재 검증
    - React key warning 검증: `const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})` 후 render → `expect(errSpy).not.toHaveBeenCalledWith(expect.stringContaining('unique "key"'))`

    주의:
    - `<Static>` 내부에서 `<Spinner>` 나 상태 의존 컴포넌트 렌더 금지 (D-05) — Message 는 순수 prop 기반이라 OK.
    - `<Static>` 은 items 배열의 참조 identity 를 보고 새 항목만 렌더한다. Plan A 의 `completedMessages: [...s.completedMessages, ...]` 패턴(새 배열, 기존 항목은 동일 참조)과 호환.
    - activeMessage 는 매 token 마다 새 객체 (`{...s.activeMessage, content: ...}`) → Message 컴포넌트가 새 props 로 리렌더 → 정상 동작.
    - JSX 에 `<div>` `<span>` 쓰지 않기 (Box/Text 만).
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- components.messagelist</automated>
  </verify>
  <acceptance_criteria>
    - `ls ui-ink/src/components/Message.tsx ui-ink/src/components/MessageList.tsx` 두 파일 존재
    - `grep -n '<Static' ui-ink/src/components/MessageList.tsx` 매칭
    - `grep -n 'activeMessage' ui-ink/src/components/MessageList.tsx` 매칭
    - `grep -n 'key={m.id}' ui-ink/src/components/MessageList.tsx` 매칭 (index key 금지 확인)
    - `cd ui-ink && bun run test` green (behavior 6개)
  </acceptance_criteria>
  <done>
    MessageList 가 <Static>+active 분리 렌더, Message 가 role 별 prefix/색상 적용, 6개 behavior 테스트 green.
  </done>
</task>

<task id="B-5" type="auto">
  <name>B-5: App.tsx — 레이아웃 D-01..D-04 + Ctrl+C/D D-07..D-08 전면 재작성</name>
  <files>ui-ink/src/App.tsx</files>
  <read_first>
    - ui-ink/src/App.tsx — Phase 1 전체 코드 이해
    - ui-ink/src/ws/client.ts — HarnessClient.send/close 시그니처
    - ui-ink/src/store/confirm.ts (Plan A 결과) — bindConfirmClient export
  </read_first>
  <action>
    D-01~D-04, D-07~D-08 을 반영해 App.tsx 를 전면 재작성한다. 이 Plan 은 MultilineInput / SlashPopup / ConfirmDialog 컴포넌트 구현 전이므로 입력 영역은 Phase 1 수준의 단순 buffer + Text 를 임시로 유지하되, 레이아웃 구조와 키 처리 골격을 완성한다.

    ```typescript
    // App — D-01..D-04 레이아웃 + D-07..D-08 Ctrl+C/D (INPT-07)
    // MultilineInput / SlashPopup / ConfirmDialog 는 Wave 2 에서 교체됨 — 이 파일의 입력 영역은 placeholder.
    import React, {useEffect, useRef, useState} from 'react'
    import {Box, Text, useApp, useInput, useStdout} from 'ink'
    import {useShallow} from 'zustand/react/shallow'
    import {useMessagesStore} from './store/messages.js'
    import {useStatusStore} from './store/status.js'
    import {useInputStore} from './store/input.js'
    import {useConfirmStore, bindConfirmClient} from './store/confirm.js'
    import {HarnessClient} from './ws/client.js'
    import {MessageList} from './components/MessageList.js'
    import {StatusBar} from './components/StatusBar.js'
    import {Divider} from './components/Divider.js'
    import {theme} from './theme.js'

    export const App: React.FC = () => {
      const {exit} = useApp()
      const {stdout} = useStdout()

      const {buffer, setBuffer, clearBuffer, pushHistory, historyUp, historyDown} = useInputStore(
        useShallow((s) => ({
          buffer: s.buffer,
          setBuffer: s.setBuffer,
          clearBuffer: s.clearBuffer,
          pushHistory: s.pushHistory,
          historyUp: s.historyUp,
          historyDown: s.historyDown,
        })),
      )

      const busy = useStatusStore(useShallow((s) => s.busy))
      const confirmMode = useConfirmStore(useShallow((s) => s.mode))

      const clientRef = useRef<HarnessClient | null>(null)
      const lastCtrlCRef = useRef<number>(0)

      // WS 연결 + confirm store 바인딩
      useEffect(() => {
        const url = process.env['HARNESS_URL']
        const token = process.env['HARNESS_TOKEN']
        if (!url || !token) return
        const client = new HarnessClient({
          url,
          token,
          room: process.env['HARNESS_ROOM'],
        })
        client.connect()
        clientRef.current = client
        bindConfirmClient(client)
        return () => {
          bindConfirmClient(null)
          client.close()
          clientRef.current = null
        }
      }, [])

      // RND-04: resize 강제 clear — ED2+ED3+Home escape (Python 경험: ED3 필수)
      // SIGWINCH 시 Ink 가 재렌더하지만, ED3(scrollback clear)까지 발행해야 stale line 잔재가 사라짐
      const [_resizeCount, setResizeCount] = useState(0)
      useEffect(() => {
        const handleResize = () => {
          // ED2(\x1b[2J 화면 클리어) + ED3(\x1b[3J scrollback 클리어) + Home(\x1b[H 커서 원점)
          stdout.write('\x1b[2J\x1b[3J\x1b[H')
          setResizeCount((c) => c + 1)  // Ink 재렌더 trigger 용 더미 state
        }
        stdout.on('resize', handleResize)
        return () => {
          stdout.off('resize', handleResize)
        }
      }, [stdout])

      // 입력 처리 — confirm 모드일 때는 본 useInput 이 처리하지 않음 (ConfirmDialog 가 처리; Wave 2)
      // 현재는 confirm 모드에서도 placeholder 로 ConfirmDialog 미구현 상태 → 이 useInput 이 y/n 만 최소 처리
      useInput((ch, key) => {
        // D-07, D-08: Ctrl+C
        if (key.ctrl && ch === 'c') {
          if (busy) {
            // busy 시 — cancel 전송 + 안내
            const client = clientRef.current
            if (client) {
              client.send({type: 'cancel'})
            }
            useMessagesStore.getState().appendSystemMessage('취소 요청 중…')
            lastCtrlCRef.current = Date.now()
            return
          }
          // idle 시 — 2초 내 2회 반복 → exit
          const now = Date.now()
          if (now - lastCtrlCRef.current < 2000) {
            exit()
            return
          }
          lastCtrlCRef.current = now
          useMessagesStore.getState().appendSystemMessage('다시 Ctrl+C 를 누르면 종료됩니다')
          return
        }

        // Ctrl+D — idle 일 때 즉시 exit (관용)
        if (key.ctrl && ch === 'd') {
          if (!buffer && !busy) {
            exit()
            return
          }
        }

        // confirm 모드에서는 최소한의 y/n 처리만 (Wave 2 의 ConfirmDialog 에서 본격 처리)
        if (confirmMode !== 'none') {
          if (ch === 'y' || ch === 'Y') {
            useConfirmStore.getState().resolve(true)
            return
          }
          if (ch === 'n' || ch === 'N' || key.escape) {
            useConfirmStore.getState().resolve(false)
            return
          }
          return
        }

        // history 순회
        if (key.upArrow) {
          historyUp()
          return
        }
        if (key.downArrow) {
          historyDown()
          return
        }

        if (key.return) {
          const text = buffer.trim()
          clearBuffer()
          if (!text) return
          pushHistory(text)
          useMessagesStore.getState().appendUserMessage(text)
          const client = clientRef.current
          if (client) {
            client.send({type: 'input', text})
          } else {
            useMessagesStore.getState().appendSystemMessage(
              '(연결 안 됨 — HARNESS_URL / HARNESS_TOKEN 필요)',
            )
          }
          return
        }
        if (key.backspace || key.delete) {
          setBuffer(buffer.slice(0, -1))
          return
        }
        if (ch && !key.ctrl && !key.meta) {
          setBuffer(buffer + ch)
        }
      })

      const columns = stdout?.columns ?? 80

      // D-01 레이아웃: [MessageList(Static + active)] → [Divider] → [InputArea | ConfirmDialog] → [Divider] → [StatusBar]
      return (
        <Box flexDirection='column'>
          <MessageList/>

          <Divider columns={columns}/>

          {confirmMode !== 'none' ? (
            // ConfirmDialog placeholder (Wave 2 에서 교체) — D-03 동일 위치 규칙만 지킴
            <Box>
              <Text color={theme.status.busy} bold>[confirm {confirmMode}] y/n · esc</Text>
            </Box>
          ) : (
            // InputArea placeholder (Wave 2 의 MultilineInput 로 교체)
            <Box>
              <Text color={theme.role.user} bold>❯ </Text>
              <Text>{buffer}</Text>
              <Text color={theme.role.user}>▌</Text>
            </Box>
          )}

          <Divider columns={columns}/>

          <StatusBar columns={columns}/>
        </Box>
      )
    }
    ```

    주의:
    - `<Static>` 내부에 spinner/상태 컴포넌트 금지 (D-05). StatusBar 의 Spinner 는 일반 트리이므로 OK.
    - RND-04: `stdout.on('resize', ...)` 로 수동 handler 등록 필수 — SIGWINCH 시 ED2(화면 클리어)만으로는 부족, ED3(scrollback 클리어)까지 발행해야 이전 폭의 stale line 이 사라진다 (Python 경험 재발 방지). Ink 내부 재렌더는 setResizeCount 더미 state 로 trigger.
    - `process.stdout.write` / `console.log` / `child_process` 사용 금지 — lint 에서 자동 차단.
    - 레이아웃 순서(MessageList → Divider → Input/Confirm → Divider → StatusBar)는 D-01, D-02 에 정확히 일치해야 한다.
    - confirm 모드 y/n 최소 처리는 "플레이스홀더" — ConfirmDialog 가 구현되는 Wave 2 에서 이 Ink useInput 분기는 제거되고 ConfirmDialog 내부 useInput 이 대체한다.
    - spinner 프레임 수동 회전(spinRef) 로직 완전 제거 — StatusBar 의 `<Spinner type='dots'/>` 가 담당.
    - Phase 1 App.tsx 의 인라인 렌더(messages.map, ─.repeat(40) 등) 전부 제거 — 새 컴포넌트로 대체.
  </action>
  <verify>
    <automated>cd ui-ink && bunx tsc --noEmit && bun run test -- app.smoke</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n '<MessageList' ui-ink/src/App.tsx` 매칭
    - `grep -n '<StatusBar' ui-ink/src/App.tsx` 매칭
    - `grep -n '<Divider' ui-ink/src/App.tsx` 정확히 2개 매칭 (D-02: active↔input, input↔statusbar)
    - `grep -n 'bindConfirmClient' ui-ink/src/App.tsx` 매칭 (connect/close 양쪽)
    - `grep -n "type: 'cancel'" ui-ink/src/App.tsx` 매칭 (D-07)
    - `grep -n "stdout.on..resize" ui-ink/src/App.tsx` 매칭 (RND-04 resize handler)
    - `grep -n 'SPIN' ui-ink/src/App.tsx` 매칭 0 (Phase 1 수동 스피너 제거 확인)
    - `grep -n "'─'.repeat" ui-ink/src/App.tsx` 매칭 0 (Divider 로 교체 확인)
    - `cd ui-ink && bunx tsc --noEmit` 에러 0
  </acceptance_criteria>
  <done>
    App.tsx 가 D-01~D-04 레이아웃 + D-07~D-08 Ctrl+C 처리 + bindConfirmClient 주입을 구현하고 tsc 통과.
  </done>
</task>

<task id="B-6" type="auto">
  <name>B-6: App 통합 smoke 테스트 + 금지 패턴 CI 가드</name>
  <files>ui-ink/src/__tests__/app.smoke.test.tsx, ui-ink/scripts/guard-forbidden.sh</files>
  <read_first>
    - ui-ink/package.json — scripts 에 lint/test/typecheck 및 ci 스크립트 구조 확인
    - ui-ink/ 루트 — scripts/ 디렉터리 존재 여부
  </read_first>
  <action>
    **테스트 파일 `ui-ink/src/__tests__/app.smoke.test.tsx`** — App 전체 렌더 smoke:

    ```typescript
    // App smoke — 전체 트리 렌더 + 금지 패턴 런타임 검증
    import React from 'react'
    import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'
    import {render} from 'ink-testing-library'
    import {App} from '../App.js'
    import {useMessagesStore} from '../store/messages.js'
    import {useStatusStore} from '../store/status.js'
    import {useConfirmStore} from '../store/confirm.js'
    import {useInputStore} from '../store/input.js'

    describe('App smoke', () => {
      beforeEach(() => {
        useMessagesStore.setState({completedMessages: [], activeMessage: null})
        useStatusStore.setState({
          connected: true, busy: false,
          working_dir: '/tmp', model: 'm', mode: 'agent',
          turns: 0, ctx_tokens: 0,
        })
        useConfirmStore.setState({mode: 'none', payload: {}})
        useInputStore.setState({buffer: '', history: [], historyIndex: -1, slashOpen: false})
      })

      it('renders without error (empty state)', () => {
        delete process.env['HARNESS_URL']
        const {lastFrame, unmount} = render(<App/>)
        expect(lastFrame()).toBeTruthy()
        // 레이아웃 필수 요소 존재
        expect(lastFrame()).toContain('─')          // Divider
        expect(lastFrame()).toContain('❯')          // InputArea prefix
        unmount()
      })

      it('renders completed + active messages', () => {
        delete process.env['HARNESS_URL']
        useMessagesStore.setState({
          completedMessages: [
            {id: '1', role: 'user', content: 'hello'},
          ],
          activeMessage: {id: '2', role: 'assistant', content: 'stream…', streaming: true},
        })
        const {lastFrame, unmount} = render(<App/>)
        const frame = lastFrame() ?? ''
        expect(frame).toContain('hello')
        expect(frame).toContain('stream')
        unmount()
      })

      it('confirm mode shows placeholder instead of input', () => {
        delete process.env['HARNESS_URL']
        useConfirmStore.setState({mode: 'confirm_write', payload: {path: '/foo'}})
        const {lastFrame, unmount} = render(<App/>)
        const frame = lastFrame() ?? ''
        expect(frame).toContain('confirm confirm_write')
        unmount()
      })

      it('does NOT emit alternate screen or mouse tracking escapes', () => {
        delete process.env['HARNESS_URL']
        const {lastFrame, unmount} = render(<App/>)
        const frame = lastFrame() ?? ''
        // alternate screen: \x1b[?1049h, mouse: \x1b[?1000h 계열
        expect(frame).not.toMatch(/\x1b\[\?1049[hl]/)
        expect(frame).not.toMatch(/\x1b\[\?100[0-3][hl]/)
        unmount()
      })
    })
    ```

    **가드 스크립트 `ui-ink/scripts/guard-forbidden.sh`** — 금지 패턴 grep 가드 (CI 에서 호출):

    ```bash
    #!/usr/bin/env bash
    # 금지 패턴 CI 가드 — CLAUDE.md 절대 금지 사항
    set -euo pipefail

    cd "$(dirname "$0")/.."

    FAIL=0

    check() {
      local desc="$1"
      local pattern="$2"
      shift 2
      if grep -rnE "$pattern" src/ --include='*.ts' --include='*.tsx' "$@" >/dev/null; then
        echo "FAIL: $desc"
        grep -rnE "$pattern" src/ --include='*.ts' --include='*.tsx' "$@" || true
        FAIL=1
      else
        echo "OK: $desc"
      fi
    }

    # process.stdout.write / console.log (테스트 파일 제외)
    check 'no process.stdout.write (non-test)' '\bprocess\.stdout\.write\b' --exclude-dir=__tests__
    check 'no console.log (non-test)'           '\bconsole\.log\b'           --exclude-dir=__tests__

    # child_process — 절대 금지
    check 'no child_process import' "from ['\"]child_process['\"]"

    # DOM 태그 (Ink 에는 없음)
    check 'no <div>' '<div[ >]'
    check 'no <span>' '<span[ >]'

    # alternate screen / mouse tracking escapes
    check 'no alternate screen escape' '\\x1b\[\?1049'
    check 'no mouse tracking escape'   '\\x1b\[\?100[0-3]'

    if [[ $FAIL -eq 1 ]]; then
      echo ''
      echo '금지 패턴이 감지되었습니다. CLAUDE.md 참조.'
      exit 1
    fi
    echo ''
    echo '모든 금지 패턴 체크 통과.'
    ```

    그리고 `ui-ink/package.json` 의 scripts 에 엔트리 추가 (기존 scripts 유지):

    ```json
    "guard": "bash scripts/guard-forbidden.sh",
    "ci": "bun run typecheck && bun run test && bun run guard"
    ```

    (typecheck 스크립트가 없으면 `"typecheck": "tsc --noEmit"` 도 추가.)

    chmod:
    ```bash
    chmod +x ui-ink/scripts/guard-forbidden.sh
    ```

    주의:
    - smoke 테스트는 HARNESS_URL 을 지워서 WS 연결 시도를 skip 시킨다 (HarnessClient 가 연결 실패해도 렌더는 계속).
    - guard-forbidden.sh 는 테스트 디렉터리(`__tests__`) 를 제외 — 테스트에서는 console.error spy 등이 필요할 수 있음.
    - `process.stdout.columns` 참조는 금지 대상이 아님(읽기 only). `process.stdout.write` 호출만 금지.
    - guard 스크립트의 패턴은 false-positive 최소화를 위해 word boundary (\b) 사용.
  </action>
  <verify>
    <automated>cd ui-ink && bun run test && bash scripts/guard-forbidden.sh</automated>
  </verify>
  <acceptance_criteria>
    - `ls ui-ink/src/__tests__/app.smoke.test.tsx ui-ink/scripts/guard-forbidden.sh` 둘 다 존재
    - `test -x ui-ink/scripts/guard-forbidden.sh` 실행 권한 있음
    - `cd ui-ink && bash scripts/guard-forbidden.sh` exit 0
    - `cd ui-ink && bun run test` 전체 green (smoke 4개 포함)
    - `grep -n '"guard"' ui-ink/package.json` 매칭 (scripts 에 등록)
  </acceptance_criteria>
  <done>
    App smoke 테스트 4개 green + guard 스크립트 통과 + package.json scripts 에 guard/ci 등록.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Ink render → terminal | App 출력이 터미널 제어 시퀀스를 포함할 수 있음 — alternate screen / mouse escape 유출 시 scrollback 파괴 |
| useInput → ws client | Ctrl+C 처리에서 cancel 메시지를 전송 — 서버가 cancel 을 해석 못하면 error 로 돌아오지만 UI 는 "취소 요청 중…" 로 낙관적 표시 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02B-01 | T (Tampering) | Ink render output | mitigate | guard-forbidden.sh + smoke 테스트가 alternate screen / mouse tracking escape 방출을 정적/런타임 양쪽 검사 |
| T-02B-02 | D (DoS) | App 렌더 루프 | mitigate | <Static> 로 completedMessages 는 재렌더 없음, activeMessage 만 토큰당 업데이트 — 500 토큰 스트리밍에서도 완결 프레임은 고정 |
| T-02B-03 | R (Repudiation) | Ctrl+C cancel | accept | 2회 확인 패턴으로 실수 종료 방지 (D-08); cancel 서버 미지원 시 error 메시지로 사용자에게 표시됨 |
| T-02B-04 | I (Info) | StatusBar path | mitigate | shortenPath() 로 절대경로 축약 — 홈 경로는 ~ 로 치환, 중간 디렉터리는 '…' 로 마스킹 |
</threat_model>

<verification>
```bash
cd /Users/johyeonchang/harness/ui-ink
bun run test
bunx tsc --noEmit
bash scripts/guard-forbidden.sh

# 계약 검증
grep -rn '<div\|<span' src/                          # 0 매칭 기대
grep -rn 'process\.stdout\.write\|console\.log' src/ --exclude-dir=__tests__  # 0 매칭 기대
grep -n '<Static' src/components/MessageList.tsx
grep -n 'priority' src/components/StatusBar.tsx
grep -n 'bindConfirmClient' src/App.tsx
grep -n "stdout.on..resize" src/App.tsx            # RND-04 resize handler 존재
grep -c 'name:' src/slash-catalog.ts                 # = 13 기대

# Python 백엔드 회귀 확인 (ui-ink 컴포넌트 변경이 Python 백엔드에 영향 없음을 재확인)
.venv/bin/python -m pytest --tb=short -q   # 199건 이상 통과

# 선택: 실제 렌더 육안 확인 (수동)
# HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=dev bun start
```
</verification>

<success_criteria>
- 모든 6개 task 의 acceptance_criteria 통과
- `bun run test` 전체 green (Plan B 신규 + Phase 1 회귀)
- `bunx tsc --noEmit` strict 통과
- `bash scripts/guard-forbidden.sh` 통과 — 금지 패턴 0건
- `<Static>` 경계가 App 트리 내 MessageList 에서 명확히 드러남 (D-04)
- App.tsx 에 Divider 가 정확히 2번, 순서가 D-01 대로
- Wave 2 의 MultilineInput / SlashPopup / ConfirmDialog 가 이 Plan 의 컴포넌트 슬롯(Input/Confirm placeholder 자리) 에 drop-in 가능한 구조
</success_criteria>

<output>
완료 후 `.planning/phases/02-core-ux/02-PLAN-B-SUMMARY.md` 작성:
- 생성된 컴포넌트 파일 목록 + 각 props 인터페이스
- App.tsx 레이아웃 트리 ASCII 요약
- Wave 2 에서 교체될 placeholder 위치 명시 (InputArea placeholder, ConfirmDialog placeholder)
- guard-forbidden.sh 가 감시하는 금지 패턴 목록
</output>
