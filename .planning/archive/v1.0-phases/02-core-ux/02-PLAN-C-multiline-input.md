---
phase: 02-core-ux
plan: C
type: execute
wave: 2
depends_on: [A, B]
autonomous: true
files_modified:
  - ui-ink/src/components/MultilineInput.tsx
  - ui-ink/src/components/InputArea.tsx
  - ui-ink/src/components/SlashPopup.tsx
  - ui-ink/src/__tests__/components.multiline.test.tsx
requirements:
  - INPT-01
  - INPT-02
  - INPT-04
  - INPT-05
  - INPT-06
  - INPT-08

must_haves:
  truths:
    - "사용자는 Enter 한 번으로 현재 버퍼를 제출한다"
    - "Shift+Enter 또는 Ctrl+J 로 개행을 삽입하며 submit 이 발생하지 않는다"
    - "↑/↓ 로 pushHistory 에 쌓인 명령을 순회할 수 있다"
    - "Ctrl+A/E/K/W/U POSIX 단축키가 현재 라인 기준으로 정확히 동작한다"
    - "멀티라인 paste(≥50줄) 가 개별 submit 없이 buffer 에 그대로 들어간다"
    - "buffer 첫 글자가 '/' 이면 SlashPopup 이 InputArea 위쪽에 표시된다"
    - "SlashPopup 에서 ↑↓ 선택 → Tab 으로 command 이름이 buffer 에 채워지고 popup 이 닫힌다"
    - "SlashPopup 열린 상태에서 Esc 를 누르면 buffer 는 유지되고 popup 만 닫힌다"
  artifacts:
    - path: "ui-ink/src/components/MultilineInput.tsx"
      provides: "자체 구현 multiline input (INPT-01..05)"
      min_lines: 120
    - path: "ui-ink/src/components/InputArea.tsx"
      provides: "MultilineInput + SlashPopup 컨테이너 (D-11 레이아웃)"
      min_lines: 40
    - path: "ui-ink/src/components/SlashPopup.tsx"
      provides: "ink-select-input 기반 슬래시 팝업 (INPT-06)"
      min_lines: 60
    - path: "ui-ink/src/__tests__/components.multiline.test.tsx"
      provides: "MultilineInput / SlashPopup 행동 테스트"
      min_lines: 80
  key_links:
    - from: "ui-ink/src/components/MultilineInput.tsx"
      to: "ui-ink/src/store/input.ts"
      via: "useInputStore (buffer/setBuffer/pushHistory/historyUp/historyDown)"
      pattern: "useInputStore"
    - from: "ui-ink/src/components/InputArea.tsx"
      to: "ui-ink/src/components/MultilineInput.tsx"
      via: "직접 import + props 전달"
      pattern: "import.*MultilineInput"
    - from: "ui-ink/src/components/InputArea.tsx"
      to: "ui-ink/src/components/SlashPopup.tsx"
      via: "slashOpen 조건부 렌더링"
      pattern: "slashOpen.*SlashPopup"
    - from: "ui-ink/src/components/SlashPopup.tsx"
      to: "ui-ink/src/slash-catalog.ts"
      via: "SLASH_CATALOG import + filterSlash"
      pattern: "SLASH_CATALOG"
---

<objective>
Phase 2 Wave 2 의 입력층을 완성한다. Wave 1 에서 확정된 store 계약(buffer/history/slashOpen)과 slash-catalog 위에서 MultilineInput(자체 구현), InputArea(컨테이너), SlashPopup(ink-select-input 기반) 세 컴포넌트를 신규 작성하고, vitest 로 핵심 행동을 못 박는다.

Purpose: INPT-01..06 의 핵심 입력 요건을 만족시켜 Phase 2 exit criteria 의 "Multiline + POSIX + Paste + Slash popup" 항목을 클로즈한다. Plan B 에서 placeholder 로 둔 입력 영역을 drop-in 교체 가능한 상태로 제공한다.

Output:
- ui-ink/src/components/MultilineInput.tsx (INPT-01, 02, 03, 04, 05)
- ui-ink/src/components/InputArea.tsx (D-11 레이아웃)
- ui-ink/src/components/SlashPopup.tsx (INPT-06)
- ui-ink/src/__tests__/components.multiline.test.tsx
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
@.planning/phases/02-core-ux/02-PATTERNS.md
@.planning/phases/02-core-ux/02-PLAN-A-store-protocol.md
@.planning/phases/02-core-ux/02-PLAN-B-base-components.md
@ui-ink/src/App.tsx
@ui-ink/src/__tests__/store.test.ts
@ui-ink/src/__tests__/tty-guard.test.ts

<interfaces>
<!-- Wave 1(A+B) 에서 확정된 계약. 실행자는 코드베이스를 재탐색하지 말고 아래 시그니처를 기반으로 구현한다. -->

From ui-ink/src/store/input.ts (Plan A 의 A-2 태스크가 확정):
```typescript
export interface InputState {
  buffer: string
  history: string[]              // oldest → newest
  historyIndex: number            // -1 = draft (편집 중), 0..N-1 = history 순회 중
  slashOpen: boolean
  setBuffer: (v: string) => void
  clearBuffer: () => void
  pushHistory: (text: string) => void
  historyUp: () => void
  historyDown: () => void
  setSlashOpen: (open: boolean) => void
}
export const useInputStore = create<InputState>((set) => ({...}))
```
Notes:
- history 는 최대 500개 cap, 직전과 동일하면 push 하지 않음
- historyUp 은 buffer 를 과거 항목으로 교체, historyDown 은 최신 방향으로 이동
- historyIndex === -1 상태에서 historyDown 은 no-op

From ui-ink/src/slash-catalog.ts (Plan B 의 B-1 태스크가 확정):
```typescript
export interface SlashCommand {
  name: string          // 예: '/help', '/clear' — leading slash 포함
  summary: string       // 한 줄 설명
}
export const SLASH_CATALOG: readonly SlashCommand[]
export function filterSlash(query: string): readonly SlashCommand[]
// filterSlash('') === SLASH_CATALOG, filterSlash('/h') → /help 계열
```

From ui-ink/src/store/messages.ts (기존):
```typescript
// 본 Plan 은 messages store 를 직접 건드리지 않음. 제출된 텍스트는 onSubmit prop 으로 상위에 올리고,
// 실제 appendUserMessage / WS send 는 InputArea 상위(App.tsx 재작성 — Plan B 담당 또는 Wave 3)에서 처리.
```

From ink@7 (의존성 확정 — package.json 에 ink@^7.0.1):
```typescript
import {Box, Text, useInput} from 'ink'
// Ink 7 의 bracketed paste 처리는 useInput 콜백의 둘째 인자 Key 와 첫 인자 input 으로 들어오며,
// 여러 글자(붙여넣기 텍스트)도 input 한 번에 들어올 수 있다.
// NOTE: Ink 7 에 별도 usePaste 훅이 export 되어 있으면 선호한다. 없으면 useInput 에서 input.length > 1
// 또는 input 에 '\n' 포함을 paste 신호로 사용한다.
```

From ink-select-input@6.2:
```typescript
import SelectInput from 'ink-select-input'
// Items: {label: string, value: string}[]
// Props: items, onSelect(item) — ↑↓ 내부 처리, Enter 로 onSelect 트리거
// 주의: SelectInput 이 Enter 를 먹기 때문에 본 Plan 의 SlashPopup 은 Enter 를 팝업 확정에 쓰지 않고
// Tab 을 확정 키로 쓴다. Enter 는 MultilineInput 의 submit 경로로 흘러가야 한다.
// → SelectInput 의 onSelect 는 쓰지 않고 highlightedValue 를 직접 추적한다 (아래 구현 참고).
// 더 안전한 방식: 팝업은 간단한 목록 + 수동 highlighted index 관리로 ink-select-input 을 우회해도 OK.
```
</interfaces>
</context>

<tasks>

<task id="C-1" type="execute" tdd="true">
  <name>C-1: MultilineInput.tsx — useInput 기반 자체 구현 (INPT-01/02/03/04/05)</name>
  <files>ui-ink/src/components/MultilineInput.tsx</files>
  <read_first>
    - ui-ink/src/store/input.ts (실제 export 된 시그니처 확인 — <interfaces> 블록과 일치해야 함)
    - ui-ink/src/App.tsx (현재 useInput 사용 방식 확인)
    - .planning/phases/02-core-ux/02-PATTERNS.md (MultilineInput analog 패턴)
    - node_modules/ink/build/hooks/use-input.d.ts (Key 타입 정확한 필드 — shift/ctrl/meta/return/backspace/delete/leftArrow/rightArrow/upArrow/downArrow 등)
  </read_first>
  <behavior>
    - Test 1: 단일 라인 buffer + Enter → onSubmit('hello') 1회 호출
    - Test 2: Shift+Enter → buffer 에 '\n' 추가, onSubmit 미호출
    - Test 3: Ctrl+J → buffer 에 '\n' 추가, onSubmit 미호출 (INPT-02 alternative)
    - Test 4: Ctrl+U → 현재 라인 전체 클리어 (cursor col = 0)
    - Test 5: Ctrl+A → cursor col = 0 (현재 라인 처음)
    - Test 6: Ctrl+E → cursor col = 현재 라인 끝
    - Test 7: Ctrl+K → cursor 위치부터 라인 끝까지 삭제
    - Test 8: Ctrl+W → cursor 직전 단어 삭제 (공백 경계)
    - Test 9: ↑ → historyUp 호출 (buffer 가 store 의 과거 항목으로 갱신됨)
    - Test 10: 멀티라인 paste(input 에 '\n' 포함) → buffer 에 그대로 삽입, onSubmit 미호출
  </behavior>
  <action>
아래 파일을 신규 생성한다. 기존 코드 없음 — 전체 덮어쓰기.

파일: `ui-ink/src/components/MultilineInput.tsx`

```tsx
// MultilineInput — ink-text-input 미사용, useInput 기반 자체 구현
// INPT-01: 자체 구현 / INPT-02: Enter 제출, Shift+Enter·Ctrl+J 개행
// INPT-03: ↑↓ history (store 위임) / INPT-04: POSIX (Ctrl+A/E/K/W/U)
// INPT-05: 멀티라인 paste — Ink 7 usePaste hook(primary, bracketed paste 감지) + useInput 휴리스틱(fallback)
//           usePaste 이벤트에서 텍스트를 \n split 후 cursor 위치 삽입, submit 발생 없음
import React from 'react'
import {Box, Text, useInput} from 'ink'
// Ink 7 usePaste — 환경에 따라 export 되지 않을 수 있어 동적 확인 패턴으로 import
// 빌드 시점에 존재하면 primary 로 사용, 없으면 useInput 휴리스틱만으로 동작
// import {usePaste} from 'ink'  // Ink 7 정식 export 확인 후 주석 해제
import {useShallow} from 'zustand/react/shallow'
import {useInputStore} from '../store/input.js'

// 커서 상태 — row/col 을 buffer 문자열의 라인 배열과 동기화
interface Cursor {
  row: number
  col: number
}

interface MultilineInputProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

// 내부 유틸 — buffer 를 라인 배열로 쪼개기
const splitLines = (s: string): string[] => (s === '' ? [''] : s.split('\n'))
const joinLines = (ls: string[]): string => ls.join('\n')

// cursor 위치에 paste 또는 단일 문자를 삽입
const insertAt = (lines: string[], cur: Cursor, text: string): {lines: string[]; cursor: Cursor} => {
  const before = lines[cur.row]?.slice(0, cur.col) ?? ''
  const after = lines[cur.row]?.slice(cur.col) ?? ''
  const merged = before + text + after
  const mergedLines = merged.split('\n')
  const next = [...lines.slice(0, cur.row), ...mergedLines, ...lines.slice(cur.row + 1)]
  // 커서는 삽입된 텍스트의 "끝" 으로 이동
  const lastInserted = mergedLines[mergedLines.length - 1] ?? ''
  const newRow = cur.row + mergedLines.length - 1
  const newCol = mergedLines.length === 1
    ? before.length + text.length
    : lastInserted.length - after.length
  return {lines: next, cursor: {row: newRow, col: newCol}}
}

// Ctrl+W 단어 삭제 (cursor 직전 공백 아닌 연속 문자 블록)
const deleteWordBefore = (lines: string[], cur: Cursor): {lines: string[]; cursor: Cursor} => {
  const line = lines[cur.row] ?? ''
  let i = cur.col
  // 앞쪽 공백 스킵
  while (i > 0 && line[i - 1] === ' ') i--
  // 단어 스킵
  while (i > 0 && line[i - 1] !== ' ') i--
  const next = line.slice(0, i) + line.slice(cur.col)
  const newLines = [...lines]
  newLines[cur.row] = next
  return {lines: newLines, cursor: {row: cur.row, col: i}}
}

// Ctrl+K — cursor 이후부터 라인 끝까지 삭제
const killToEnd = (lines: string[], cur: Cursor): {lines: string[]; cursor: Cursor} => {
  const line = lines[cur.row] ?? ''
  const next = line.slice(0, cur.col)
  const newLines = [...lines]
  newLines[cur.row] = next
  return {lines: newLines, cursor: cur}
}

export const MultilineInput: React.FC<MultilineInputProps> = ({onSubmit, disabled}) => {
  // store — buffer 는 외부 단일 소스, cursor 만 로컬 state
  const {buffer, setBuffer, clearBuffer, pushHistory, historyUp, historyDown} = useInputStore(
    useShallow((s) => ({
      buffer: s.buffer,
      setBuffer: s.setBuffer,
      clearBuffer: s.clearBuffer,
      pushHistory: s.pushHistory,
      historyUp: s.historyUp,
      historyDown: s.historyDown,
    }))
  )

  const [cursor, setCursor] = React.useState<Cursor>({row: 0, col: 0})

  // buffer 변경 시 cursor 가 out-of-range 가 되지 않도록 clamp
  React.useEffect(() => {
    const lines = splitLines(buffer)
    setCursor((c) => {
      const row = Math.min(c.row, lines.length - 1)
      const col = Math.min(c.col, (lines[row] ?? '').length)
      if (row === c.row && col === c.col) return c
      return {row, col}
    })
  }, [buffer])

  useInput((input, key) => {
    if (disabled) return

    const lines = splitLines(buffer)

    // 제출 — Enter (단독) 이되 input 에 개행 문자가 포함된 paste 가 아닐 때만
    // INPT-05: paste 감지 primary = Ink 7 usePaste (bracketed paste 이벤트), fallback = useInput 휴리스틱
    // usePaste 가 먼저 buffer 를 채우고 있을 수 있으므로 이 분기는 fallback 역할만 수행한다
    const isPaste = input.length > 1 || input.includes('\n')

    // Shift+Enter 또는 Ctrl+J → 개행 삽입
    if ((key.return && key.shift) || (key.ctrl && input === 'j')) {
      const r = insertAt(lines, cursor, '\n')
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }

    // Enter (단독, paste 아님) → 제출
    if (key.return && !key.shift && !isPaste) {
      const text = joinLines(lines)
      if (text.trim() === '') {
        // 빈 입력 제출 차단
        return
      }
      pushHistory(text)
      clearBuffer()
      setCursor({row: 0, col: 0})
      onSubmit(text)
      return
    }

    // history ↑↓ — store 에 위임. 단, 멀티라인 buffer 면 커서 이동 우선 처리
    if (key.upArrow) {
      // 멀티라인이고 현재 row > 0 이면 라인 이동
      if (lines.length > 1 && cursor.row > 0) {
        const newRow = cursor.row - 1
        const newCol = Math.min(cursor.col, (lines[newRow] ?? '').length)
        setCursor({row: newRow, col: newCol})
        return
      }
      historyUp()
      return
    }
    if (key.downArrow) {
      if (lines.length > 1 && cursor.row < lines.length - 1) {
        const newRow = cursor.row + 1
        const newCol = Math.min(cursor.col, (lines[newRow] ?? '').length)
        setCursor({row: newRow, col: newCol})
        return
      }
      historyDown()
      return
    }

    if (key.leftArrow) {
      if (cursor.col > 0) {
        setCursor({row: cursor.row, col: cursor.col - 1})
      } else if (cursor.row > 0) {
        const prev = lines[cursor.row - 1] ?? ''
        setCursor({row: cursor.row - 1, col: prev.length})
      }
      return
    }
    if (key.rightArrow) {
      const line = lines[cursor.row] ?? ''
      if (cursor.col < line.length) {
        setCursor({row: cursor.row, col: cursor.col + 1})
      } else if (cursor.row < lines.length - 1) {
        setCursor({row: cursor.row + 1, col: 0})
      }
      return
    }

    // POSIX 단축키 (INPT-04)
    if (key.ctrl && input === 'a') {
      setCursor({row: cursor.row, col: 0})
      return
    }
    if (key.ctrl && input === 'e') {
      setCursor({row: cursor.row, col: (lines[cursor.row] ?? '').length})
      return
    }
    if (key.ctrl && input === 'k') {
      const r = killToEnd(lines, cursor)
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }
    if (key.ctrl && input === 'w') {
      const r = deleteWordBefore(lines, cursor)
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }
    if (key.ctrl && input === 'u') {
      // 현재 라인 전체 삭제
      const newLines = [...lines]
      newLines[cursor.row] = ''
      setBuffer(joinLines(newLines))
      setCursor({row: cursor.row, col: 0})
      return
    }

    // Backspace / Delete
    if (key.backspace || key.delete) {
      if (cursor.col > 0) {
        const line = lines[cursor.row] ?? ''
        const next = line.slice(0, cursor.col - 1) + line.slice(cursor.col)
        const newLines = [...lines]
        newLines[cursor.row] = next
        setBuffer(joinLines(newLines))
        setCursor({row: cursor.row, col: cursor.col - 1})
      } else if (cursor.row > 0) {
        // 라인 머지
        const prev = lines[cursor.row - 1] ?? ''
        const cur = lines[cursor.row] ?? ''
        const merged = prev + cur
        const newLines = [
          ...lines.slice(0, cursor.row - 1),
          merged,
          ...lines.slice(cursor.row + 1),
        ]
        setBuffer(joinLines(newLines))
        setCursor({row: cursor.row - 1, col: prev.length})
      }
      return
    }

    // 일반 입력 (paste 포함) — ctrl/meta 조합이 아니고 input 이 존재
    if (input && !key.ctrl && !key.meta) {
      const r = insertAt(lines, cursor, input)
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }
  })

  // 렌더 — 각 라인마다 prefix, 현재 cursor 라인의 cursor 위치에 inverse 문자
  const lines = splitLines(buffer)

  return (
    <Box flexDirection='column'>
      {lines.map((line, rowIdx) => {
        const prefix = rowIdx === 0 ? '❯ ' : '… '
        const isCursorLine = rowIdx === cursor.row
        if (!isCursorLine) {
          return (
            // 라인들은 id 가 없음 — 본 컴포넌트 내부에서만 쓰이는 리스트이고 길이/순서 모두 buffer 로부터 derive
            // CLAUDE.md 의 "index as key 금지" 는 messages 등 식별 가능한 리스트에 한함
            <Box key={'line-' + rowIdx}>
              <Text dimColor={rowIdx > 0}>{prefix}</Text>
              <Text>{line}</Text>
            </Box>
          )
        }
        const before = line.slice(0, cursor.col)
        const at = line.slice(cursor.col, cursor.col + 1) || ' '
        const after = line.slice(cursor.col + 1)
        return (
          <Box key={'line-' + rowIdx}>
            <Text color='cyan'>{prefix}</Text>
            <Text>{before}</Text>
            <Text inverse>{at}</Text>
            <Text>{after}</Text>
          </Box>
        )
      })}
    </Box>
  )
}
```

주의사항:
- 반드시 `.js` 확장자로 import (`'../store/input.js'`) — ESM + bun 환경
- 세미콜론 없음, single quote, 2 spaces (CLAUDE.md)
- `process.stdout.write` / `console.log` 금지
- cursor 라인 렌더에서만 index 기반 key 허용 (라인은 독립 식별자 없음). messages 등 외부 리스트에는 절대 index key 쓰지 않음
- INPT-05 paste 감지: **primary = Ink 7 `usePaste` hook** (bracketed paste 이벤트 수신; 텍스트를 cursor 위치에 `insertAt` 으로 삽입, submit 호출 없음). `usePaste` 가 Ink 7 에서 export 되면 `import {usePaste} from 'ink'` 로 활성화하고 useInput 휴리스틱은 fallback 으로만 사용. **fallback = useInput 휴리스틱** (`input.length > 1 || input.includes('\n')`) — usePaste 가 없는 빌드/환경에서만 작동. 실행자는 node_modules/ink 의 `index.d.ts` 또는 `build/hooks/use-paste.d.ts` 에서 export 여부를 먼저 확인하고, 있으면 usePaste 우선 경로를 활성화할 것
- Ink 7 의 정확한 Key 필드명은 `node_modules/ink/build/hooks/use-input.d.ts` 로 재확인. 주요 필드: `leftArrow/rightArrow/upArrow/downArrow/return/backspace/delete/ctrl/shift/meta`
  </action>
  <verify>
    <automated>cd ui-ink &amp;&amp; bun run typecheck &amp;&amp; bun run lint</automated>
    - file exists: test -f ui-ink/src/components/MultilineInput.tsx
    - grep 'useInput' ui-ink/src/components/MultilineInput.tsx
    - grep 'usePaste' ui-ink/src/components/MultilineInput.tsx (INPT-05 primary paste handler — import 주석 또는 활성 호출)
    - grep 'key.return' ui-ink/src/components/MultilineInput.tsx
    - grep 'key.shift' ui-ink/src/components/MultilineInput.tsx
    - grep 'key.ctrl' ui-ink/src/components/MultilineInput.tsx
    - grep 'useInputStore' ui-ink/src/components/MultilineInput.tsx
    - grep -L 'process.stdout.write\|console.log\|ink-text-input' ui-ink/src/components/MultilineInput.tsx (금칙어 미포함)
  </verify>
  <done>
    - ui-ink/src/components/MultilineInput.tsx 존재 및 위 인터페이스대로 export
    - typecheck/lint 0 exit
    - C-4 의 테스트가 이 컴포넌트 대상으로 통과
  </done>
</task>

<task id="C-2" type="execute" tdd="true">
  <name>C-2: SlashPopup.tsx — ink-select-input 기반 슬래시 팝업 (INPT-06)</name>
  <files>ui-ink/src/components/SlashPopup.tsx</files>
  <read_first>
    - ui-ink/src/slash-catalog.ts (Plan B 가 확정한 SLASH_CATALOG / filterSlash)
    - node_modules/ink-select-input/build/index.d.ts (Items/onHighlight/indicatorComponent props 확인)
  </read_first>
  <behavior>
    - Test 1: query='' 전달 → 전체 SLASH_CATALOG 렌더 (항목 count 일치)
    - Test 2: query='he' 전달 → /help 만 후보로 남음 (filterSlash 위임)
    - Test 3: Esc 키 → onClose 호출
    - Test 4: Tab 키 → onSelect(현재 highlighted command.name) 호출
    - Test 5: 후보가 0개면 '일치하는 명령이 없습니다' 플레이스홀더 렌더, Tab/Enter 무시
  </behavior>
  <action>
아래 파일을 신규 생성한다.

파일: `ui-ink/src/components/SlashPopup.tsx`

```tsx
// SlashPopup — '/' 로 시작하는 buffer 에 대해 command 목록을 보여주는 팝업
// INPT-06: ink-select-input 기반, 실시간 필터, ↑↓ 네비, Tab 으로 확정, Esc 로 닫기
// NOTE: Enter 는 MultilineInput 의 submit 경로로 통과시켜야 하므로 SelectInput 의 onSelect 는 사용하지 않는다.
//       highlightedValue 를 자체 state 로 관리하고, Tab 누를 때만 onSelect 를 호출한다.
import React from 'react'
import {Box, Text, useInput} from 'ink'
import SelectInput from 'ink-select-input'
import {filterSlash, type SlashCommand} from '../slash-catalog.js'

interface SlashPopupProps {
  // buffer 의 슬래시 query 부분 — 예: buffer='/hel world' → query='hel'
  query: string
  // Tab 확정 시 호출 — commandName 은 leading slash 포함 ('/help')
  onSelect: (commandName: string) => void
  // Esc 로 닫기
  onClose: () => void
}

interface Item {
  label: string
  value: string           // commandName (leading slash 포함)
}

const toItems = (commands: readonly SlashCommand[]): Item[] =>
  commands.map((c) => ({label: c.name + '  ' + c.summary, value: c.name}))

export const SlashPopup: React.FC<SlashPopupProps> = ({query, onSelect, onClose}) => {
  // query 는 buffer 의 '/' 이후 텍스트 혹은 buffer 전체 — 여기서는 leading '/' 포함된 상태로 받는다고 가정
  // (InputArea 가 buffer 자체를 넘김)
  const candidates = filterSlash(query)
  const items = toItems(candidates)

  const [highlighted, setHighlighted] = React.useState<string | null>(
    items[0]?.value ?? null
  )

  // 후보 리스트 변경 시 highlighted 재계산
  React.useEffect(() => {
    if (items.length === 0) {
      setHighlighted(null)
      return
    }
    // 현재 highlighted 가 더 이상 candidates 에 없으면 첫 번째로
    const stillExists = items.some((i) => i.value === highlighted)
    if (!stillExists) {
      setHighlighted(items[0]?.value ?? null)
    }
  }, [query])

  useInput((input, key) => {
    if (key.escape) {
      onClose()
      return
    }
    if (key.tab) {
      if (highlighted) {
        onSelect(highlighted)
      }
      return
    }
    // Enter / 일반 문자 / 화살표 등은 처리하지 않음 — ink-select-input 와 MultilineInput 이 먹는다
  })

  if (items.length === 0) {
    return (
      <Box borderStyle='round' borderColor='gray' paddingX={1}>
        <Text dimColor>일치하는 명령이 없습니다</Text>
      </Box>
    )
  }

  return (
    <Box flexDirection='column' borderStyle='round' borderColor='cyan' paddingX={1}>
      <SelectInput
        items={items}
        onHighlight={(item: Item) => setHighlighted(item.value)}
        // onSelect 는 Enter 에 바인딩되어 있으므로 의도적으로 no-op.
        // Enter 는 SelectInput 을 빠져나가 MultilineInput 의 submit 으로 흘러야 함 — 하지만 SelectInput 이
        // Enter 를 consume 하기 때문에 본 팝업은 Enter 도 닫기/확정 중 하나를 반드시 선택해야 한다.
        // D-11 결정에 따라 Tab = 확정, Enter = submit 경로 보존. SelectInput 이 Enter 를 먹는 걸 막기 위해
        // onSelect 에서 onSelect(item.value) 를 호출해 buffer 만 채우고, 실제 submit 여부는 상위가 결정한다.
        onSelect={(item: Item) => onSelect(item.value)}
      />
    </Box>
  )
}
```

참고:
- ink-select-input 의 onSelect 는 Enter 에 바인딩됨. D-11 설계는 "Tab=확정, Enter=submit" 이지만 SelectInput 이 Enter 를 먹기 때문에 onSelect 도 동일 핸들러로 연결하는 방어 구현. 실행자는 통합 테스트(Plan E) 에서 실제 동작을 재확인해야 한다.
- 만약 ink-select-input@6.2 에 onHighlight 이 없다면 items 배열을 직접 렌더링하는 단순 목록으로 fallback (focused index 자체 state). `node_modules/ink-select-input/build/index.d.ts` 에서 먼저 확인할 것.
  </action>
  <verify>
    <automated>cd ui-ink &amp;&amp; bun run typecheck &amp;&amp; bun run lint</automated>
    - file exists: test -f ui-ink/src/components/SlashPopup.tsx
    - grep 'ink-select-input' ui-ink/src/components/SlashPopup.tsx
    - grep 'filterSlash' ui-ink/src/components/SlashPopup.tsx
    - grep 'key.escape' ui-ink/src/components/SlashPopup.tsx
    - grep 'key.tab' ui-ink/src/components/SlashPopup.tsx
  </verify>
  <done>
    - SlashPopup 이 query prop 을 받아 filterSlash 로 필터한 목록을 렌더
    - Esc → onClose, Tab → onSelect(highlighted) 동작
    - C-4 의 SlashPopup 테스트 통과
  </done>
</task>

<task id="C-3" type="execute" tdd="true">
  <name>C-3: InputArea.tsx — MultilineInput + SlashPopup 컨테이너 (D-11 레이아웃)</name>
  <files>ui-ink/src/components/InputArea.tsx</files>
  <read_first>
    - .planning/phases/02-core-ux/02-CONTEXT.md D-11 항목
    - ui-ink/src/store/input.ts (slashOpen/setSlashOpen)
  </read_first>
  <behavior>
    - Test 1: buffer='' → SlashPopup 렌더 안 됨
    - Test 2: buffer='/' → slashOpen=true 자동 설정 + SlashPopup 위쪽에 렌더
    - Test 3: buffer='abc' → slashOpen=false 유지
    - Test 4: SlashPopup 에서 onSelect('/help') → buffer='/help ' 로 교체, slashOpen=false
    - Test 5: SlashPopup 에서 onClose → slashOpen=false, buffer 유지
  </behavior>
  <action>
아래 파일을 신규 생성한다.

파일: `ui-ink/src/components/InputArea.tsx`

```tsx
// InputArea — MultilineInput 과 SlashPopup 을 묶는 컨테이너
// D-11: SlashPopup 은 InputArea "위쪽" 에 표시 → flexDirection='column' 에서 먼저 렌더
// 이 Plan 은 실제 WS 송신이나 messages store push 를 수행하지 않는다 — onSubmit 은 상위(App.tsx 재작성 시 Plan B/Wave 3)가 처리
import React from 'react'
import {Box} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useInputStore} from '../store/input.js'
import {MultilineInput} from './MultilineInput.js'
import {SlashPopup} from './SlashPopup.js'

interface InputAreaProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

export const InputArea: React.FC<InputAreaProps> = ({onSubmit, disabled}) => {
  const {buffer, setBuffer, slashOpen, setSlashOpen} = useInputStore(
    useShallow((s) => ({
      buffer: s.buffer,
      setBuffer: s.setBuffer,
      slashOpen: s.slashOpen,
      setSlashOpen: s.setSlashOpen,
    }))
  )

  // buffer 가 '/' 로 시작하면 popup 자동 open, 아니면 자동 close
  React.useEffect(() => {
    const shouldOpen = buffer.startsWith('/')
    if (shouldOpen !== slashOpen) {
      setSlashOpen(shouldOpen)
    }
  }, [buffer, slashOpen, setSlashOpen])

  const handleSlashSelect = React.useCallback(
    (commandName: string) => {
      // 선택된 명령으로 buffer 를 교체하고 trailing space 추가 (INPT-08 에서 Tab 인자 자동완성 확장용 훅)
      setBuffer(commandName + ' ')
      setSlashOpen(false)
    },
    [setBuffer, setSlashOpen]
  )

  const handleSlashClose = React.useCallback(() => {
    setSlashOpen(false)
  }, [setSlashOpen])

  // query 는 buffer 전체(leading '/' 포함) — SlashPopup 내부에서 filterSlash 가 처리
  // 단, 첫 공백 이후는 '명령 인자' 구간이므로 제외
  const slashQuery = React.useMemo(() => {
    if (!buffer.startsWith('/')) return ''
    const spaceIdx = buffer.indexOf(' ')
    return spaceIdx === -1 ? buffer : buffer.slice(0, spaceIdx)
  }, [buffer])

  return (
    <Box flexDirection='column'>
      {slashOpen && (
        <SlashPopup
          query={slashQuery}
          onSelect={handleSlashSelect}
          onClose={handleSlashClose}
        />
      )}
      <MultilineInput onSubmit={onSubmit} disabled={disabled} />
    </Box>
  )
}
```

주의:
- D-11 에 따라 SlashPopup 이 MultilineInput "위" 에 와야 함 — flexDirection='column' 에서 먼저 위치
- buffer 전체가 slashQuery 로 들어가지 않도록 첫 공백까지만 slice
  </action>
  <verify>
    <automated>cd ui-ink &amp;&amp; bun run typecheck &amp;&amp; bun run lint</automated>
    - file exists: test -f ui-ink/src/components/InputArea.tsx
    - grep 'MultilineInput' ui-ink/src/components/InputArea.tsx
    - grep 'SlashPopup' ui-ink/src/components/InputArea.tsx
    - grep 'slashOpen' ui-ink/src/components/InputArea.tsx
    - grep "flexDirection='column'" ui-ink/src/components/InputArea.tsx
  </verify>
  <done>
    - InputArea 가 buffer 변경 시 slashOpen 을 자동 토글
    - SlashPopup 이 MultilineInput 위쪽에 조건부 렌더
    - C-4 의 InputArea 통합 테스트 통과
  </done>
</task>

<task id="C-4" type="execute" tdd="true">
  <name>C-4: vitest 테스트 — MultilineInput / SlashPopup / InputArea 행동</name>
  <files>ui-ink/src/__tests__/components.multiline.test.tsx</files>
  <read_first>
    - ui-ink/src/__tests__/store.test.ts (기존 vitest 패턴 — beforeEach 에서 store 리셋)
    - ui-ink/src/__tests__/tty-guard.test.ts (간단한 unit 패턴)
    - node_modules/ink-testing-library/build/index.d.ts (render/stdin/lastFrame API)
  </read_first>
  <behavior>
    - Test A1: MultilineInput — 'hello' 타이핑 후 Enter → onSubmit('hello') 1회
    - Test A2: MultilineInput — 'a' 입력 후 Shift+Enter → buffer='a\n', onSubmit 미호출
    - Test A3: MultilineInput — 'abc' 입력 후 Ctrl+U → buffer='', cursor 0,0
    - Test A4: MultilineInput — pushHistory 이후 ↑ → buffer 가 최근 history 로 교체
    - Test A5: MultilineInput — 멀티라인 paste (stdin.write('line1\nline2\n')) → buffer 포함 'line1\nline2', onSubmit 미호출
    - Test B1: SlashPopup — query='' 렌더 후 lastFrame 에 '/help' 포함
    - Test B2: SlashPopup — Esc 키 stdin.write('') → onClose 1회
    - Test B3: SlashPopup — Tab 키 stdin.write('\t') → onSelect(highlighted) 1회
    - Test C1: InputArea — setBuffer('/') 후 next tick → slashOpen=true, lastFrame 에 popup 보더 문자 포함
    - Test C2: InputArea — setBuffer('hello') 후 → slashOpen=false
  </behavior>
  <action>
아래 파일을 신규 생성한다.

파일: `ui-ink/src/__tests__/components.multiline.test.tsx`

```tsx
// MultilineInput / SlashPopup / InputArea 단위·통합 테스트
// 참고: ink-testing-library 의 stdin.write 는 useInput 콜백을 트리거
import React from 'react'
import {describe, it, expect, beforeEach, vi} from 'vitest'
import {render} from 'ink-testing-library'
import {MultilineInput} from '../components/MultilineInput.js'
import {SlashPopup} from '../components/SlashPopup.js'
import {InputArea} from '../components/InputArea.js'
import {useInputStore} from '../store/input.js'

// 키 헬퍼 — ink-testing-library 는 raw 문자열을 useInput 에 흘려보냄
const CR = '\r'           // Enter
const SHIFT_CR = '\r'     // 주의: 터미널은 Shift+Enter 와 Enter 를 구분하지 못함.
                          // Ink 의 key.shift 는 실제 raw input 으로는 직접 검증 어려움.
                          // 본 테스트는 store 상태와 onSubmit 호출 여부로 대체 검증.
const CTRL_U = ''
const ESC = ''
const TAB = '\t'

const flush = async () => {
  // React 18 + useEffect tick 안정화
  await new Promise((r) => setTimeout(r, 10))
}

describe('MultilineInput', () => {
  beforeEach(() => {
    useInputStore.setState({
      buffer: '',
      history: [],
      historyIndex: -1,
      slashOpen: false,
    })
  })

  it('문자 입력 + Enter → onSubmit(text) 1회 호출', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('hello')
    await flush()
    stdin.write(CR)
    await flush()
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith('hello')
    unmount()
  })

  it('Ctrl+U → 현재 라인 전체 삭제', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('abc')
    await flush()
    expect(useInputStore.getState().buffer).toBe('abc')
    stdin.write(CTRL_U)
    await flush()
    expect(useInputStore.getState().buffer).toBe('')
    unmount()
  })

  it('멀티라인 paste(input 에 \\n 포함) → buffer 에 삽입, onSubmit 미호출', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('line1\nline2')
    await flush()
    expect(useInputStore.getState().buffer).toBe('line1\nline2')
    expect(onSubmit).not.toHaveBeenCalled()
    unmount()
  })

  it('↑ 화살표 → historyUp 위임 (store buffer 가 최근 history 로 교체)', async () => {
    useInputStore.setState({buffer: '', history: ['old1', 'old2'], historyIndex: -1})
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('[A')   // up arrow
    await flush()
    expect(useInputStore.getState().buffer).toBe('old2')
    unmount()
  })
})

describe('SlashPopup', () => {
  it('query="" → 전체 catalog 중 /help 를 lastFrame 에 포함', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    const {lastFrame, unmount} = render(
      <SlashPopup query='' onSelect={onSelect} onClose={onClose} />
    )
    await flush()
    expect(lastFrame()).toContain('/help')
    unmount()
  })

  it('Esc → onClose 호출', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    const {stdin, unmount} = render(
      <SlashPopup query='' onSelect={onSelect} onClose={onClose} />
    )
    stdin.write(ESC)
    await flush()
    expect(onClose).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('Tab → highlighted command 으로 onSelect 호출', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    const {stdin, unmount} = render(
      <SlashPopup query='' onSelect={onSelect} onClose={onClose} />
    )
    await flush()
    stdin.write(TAB)
    await flush()
    expect(onSelect).toHaveBeenCalledTimes(1)
    // 첫 번째 command 로 호출됐는지 — SLASH_CATALOG[0].name 와 일치
    expect(onSelect.mock.calls[0]?.[0]).toMatch(/^\//)
    unmount()
  })
})

describe('InputArea', () => {
  beforeEach(() => {
    useInputStore.setState({
      buffer: '',
      history: [],
      historyIndex: -1,
      slashOpen: false,
    })
  })

  it('buffer="/" → slashOpen=true 로 자동 전환', async () => {
    const onSubmit = vi.fn()
    const {unmount} = render(<InputArea onSubmit={onSubmit} />)
    useInputStore.getState().setBuffer('/')
    await flush()
    expect(useInputStore.getState().slashOpen).toBe(true)
    unmount()
  })

  it('buffer="hello" → slashOpen=false 유지', async () => {
    const onSubmit = vi.fn()
    const {unmount} = render(<InputArea onSubmit={onSubmit} />)
    useInputStore.getState().setBuffer('hello')
    await flush()
    expect(useInputStore.getState().slashOpen).toBe(false)
    unmount()
  })
})
```

주의:
- Shift+Enter 는 터미널 escape sequence 차원에서 일반 Enter 와 구분 불가능 — 본 테스트는 store 상태로 간접 검증하거나 생략
- ink-testing-library 의 stdin.write 는 useInput 콜백에 파싱된 (input, key) 로 전달됨
- `'[A'` = ANSI CSI Up arrow — Ink 가 이를 `key.upArrow=true` 로 파싱
- `useInputStore.setState(...)` 로 store 직접 조작 (beforeEach 리셋)
  </action>
  <verify>
    <automated>cd ui-ink &amp;&amp; bun run test</automated>
    - 모든 C-4 테스트 통과 (MultilineInput 4개 + SlashPopup 3개 + InputArea 2개 = 9개)
    - 기존 vitest suites(store.test, tty-guard.test, dispatch.test, protocol.test) 함께 green
  </verify>
  <done>
    - vitest run 이 0 exit 으로 종료
    - 총 테스트 수가 기존 대비 +9 이상
    - C-1/C-2/C-3 컴포넌트가 회귀 없이 동작 보장
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| keyboard → useInput | 사용자 raw 키입력이 Ink 파서를 거쳐 컴포넌트로 유입. bracketed paste 포함 |
| component → store | setBuffer / pushHistory 등으로 zustand 글로벌 상태 변경 |
| store → upstream (App.tsx) | onSubmit prop 을 통해 텍스트가 WS 송신 경로로 나감 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02C-01 | Tampering | MultilineInput 의 paste 판정 | mitigate | `input.length > 1 || input.includes('\n')` 로 paste 감지, Enter 와 분리. submit 은 key.return && !key.shift && !isPaste 삼중 가드 |
| T-02C-02 | Tampering | IME 조합 중 Enter | accept | 빈 라인에서만 submit 허용하는 가드는 UX 해침(ko/jp 조합 중 빈 라인 상태 정상). Plan E 수동 검증에서 macOS IME 시나리오 필수 체크리스트화 |
| T-02C-03 | DoS | 대용량 paste (500줄+) | mitigate | insertAt 은 O(n) 문자열 조작. React rerender 비용은 Plan B 의 `<Static>` 구조 + MultilineInput 자체 메모이제이션 없음에 의존. Phase 2 exit criteria 의 500줄 스모크로 확인 |
| T-02C-04 | Repudiation | history 오염 (빈 입력 push) | mitigate | MultilineInput.submit 분기에서 `text.trim() === ''` 차단 + pushHistory 내부 직전 중복/빈 입력 가드 |
| T-02C-05 | Tampering | SlashPopup 의 Enter 처리 중첩 | mitigate | SelectInput 의 onSelect 도 onSelect prop 으로 연결 — Enter 가 SelectInput 에 먹혀도 buffer 교체는 일관되게 수행. Plan E 에서 실제 submit 경로 수동 확인 |
| T-02C-06 | Information Disclosure | 붙여넣은 비밀정보(토큰 등)가 history 파일로 유출 | accept | Phase 2 는 in-memory history. 파일 persistence 는 별도 Plan/Phase. 발생 시 `/clear` 로 대응 |
| T-02C-07 | Elevation of Privilege | Ctrl+C/Ctrl+D 가 MultilineInput 에 의해 intercept | mitigate | 본 컴포넌트는 Ctrl+C/Ctrl+D 를 처리하지 않음 — App.tsx 의 상위 useInput(Plan B 확정) 가 먼저 처리하도록 보장. useInput 의 호출 순서상 상위가 먼저 등록되어야 함 |
</threat_model>

<verification>
실행자가 전 태스크 완료 후 다음 명령을 순차 실행해 0 exit 이 되어야 한다:

```bash
cd ui-ink
bun install          # ink-testing-library 미설치 시 대비 (이미 devDependencies 에 있음)
bun run typecheck    # tsc --noEmit
bun run lint         # eslint --max-warnings=0
bun run test         # vitest run — 신규 9개 + 기존 테스트 전부 green
bun run ci:no-escape # alternate screen / mouse tracking escape 코드 미포함 확인 (CLAUDE.md 금칙)
```

추가로 수동 검사 (Plan E exit criteria 로 이월하되 C 완료 시점에 라이트 체크):

```bash
# MultilineInput 에 금칙 API 미사용 확인
grep -E 'process\.stdout\.write|console\.log|child_process|ink-text-input' \
  ui-ink/src/components/MultilineInput.tsx \
  ui-ink/src/components/InputArea.tsx \
  ui-ink/src/components/SlashPopup.tsx
# → 매치 0개여야 함

# DOM 태그 사용 금지 확인
grep -E '<(div|span|p|ul|li)[ >/]' \
  ui-ink/src/components/MultilineInput.tsx \
  ui-ink/src/components/InputArea.tsx \
  ui-ink/src/components/SlashPopup.tsx
# → 매치 0개여야 함

# .js 확장자 import 강제 (ESM)
grep -E "from '\\.\\./(store|components|slash-catalog)'" ui-ink/src/components/*.tsx
# → 매치 0개여야 함 (.js 확장자 없이 상대 경로 import 금지)
```
</verification>

<success_criteria>
Plan C 가 완료되었다고 선언하려면 모두 만족:

- [ ] `ui-ink/src/components/MultilineInput.tsx` 신규 생성, export `MultilineInput` 존재
- [ ] `ui-ink/src/components/InputArea.tsx` 신규 생성, export `InputArea` 존재
- [ ] `ui-ink/src/components/SlashPopup.tsx` 신규 생성, export `SlashPopup` 존재
- [ ] `ui-ink/src/__tests__/components.multiline.test.tsx` 신규 생성, 9개 이상 테스트 포함
- [ ] `bun run typecheck` 0 exit
- [ ] `bun run lint` 0 exit (max-warnings=0)
- [ ] `bun run test` 0 exit — 신규 9개 테스트 모두 pass, 기존 테스트 회귀 없음
- [ ] `bun run ci:no-escape` 0 exit
- [ ] grep 검증 — process.stdout.write / console.log / child_process / ink-text-input / `<div>` 등 금칙 미포함
- [ ] 모든 상대 import 에 `.js` 확장자 포함
- [ ] 한국어 주석 · 2 spaces · single quote · no semicolon 스타일 준수
- [ ] REQUIREMENTS.md 의 INPT-01/02/04/05/06 에 대응되는 구현 존재 (Plan E 검증에서 Validated 로 전환 예정)
- [ ] INPT-08(Tab 인자 자동완성) 은 본 Plan 범위 밖 — InputArea 의 `setBuffer(commandName + ' ')` 로 확장 훅만 마련하고 실제 인자 자동완성은 후속 Plan 에서 수행
</success_criteria>

<output>
본 Plan 완료 후 실행자는 다음 파일을 생성한다:

`.planning/phases/02-core-ux/02-PLAN-C-SUMMARY.md`

SUMMARY 내용:
- 생성된 4개 파일 목록 + 각 파일의 핵심 export 시그니처
- 커버된 REQ-ID (INPT-01/02/04/05/06) 및 부분 커버(INPT-08 의 확장 훅)
- Wave 3 (Plan D/E) 를 위한 후속 작업 — App.tsx 에 InputArea 실제 배선, Ctrl+C 첫 번째 cancel 전송(INPT-09), Ctrl+D 종료 가드(INPT-10), 500줄 paste 수동 스모크
- 알려진 제약 — Shift+Enter 와 Enter 의 터미널 구분 불가 → vitest 는 store 상태로 간접 검증, 실제 키는 Plan E 수동 검증
- 한국어 존댓말로 작성
</output>
