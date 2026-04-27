---
phase: 02-core-ux
plan: D
wave: 2
depends_on: [A, B]
autonomous: true
files_modified:
  - ui-ink/src/components/ConfirmDialog.tsx
  - ui-ink/src/components/DiffPreview.tsx
  - ui-ink/src/components/ToolCard.tsx
  - ui-ink/src/__tests__/components.confirm.test.tsx
requirements:
  - CNF-01
  - CNF-02
  - CNF-04
  - CNF-05
  - RND-07
  - RND-08
---

<objective>
Plan D — Phase 2 Wave 2 구현: ConfirmDialog (세 가지 모드: confirm_write / confirm_bash / cplan_confirm) + DiffPreview (Phase 2 placeholder) + ToolCard (TOOL_META 기반 1줄 요약 + 상세 펼침).

Wave 1 (Plan A confirm store + Plan B dispatch 이벤트 라우팅) 완료 후 실행. 이 Plan 은 **프레젠테이션 레이어만** 담당 — store 로직 (sticky-deny 의 `addDenied`/`isDenied`/`clearDenied`, `mode`/`payload`/`resolve`) 은 이미 Plan A 에 존재. Dispatch 에서 setConfirm 호출도 Plan B 가 처리.

**Purpose:**
- CNF-01 (confirm_write 다이얼로그), CNF-02 (confirm_bash + danger-level 라벨), CNF-04 (관전자는 read-only), CNF-05 (cplan_confirm 동일 프레임) 을 UI 로 실현
- RND-07 (DiffPreview — Phase 2 는 placeholder, Phase 3 PEXT-02 에서 old_content 수신 후 diff@9 연결)
- RND-08 (ToolCard — 1줄 요약 기본, Claude 판단으로 상세 펼침)

**Output artifacts:**
- `ui-ink/src/components/ConfirmDialog.tsx` — 네 가지 서브뷰 (write / bash / cplan / read-only) + sticky-deny hook
- `ui-ink/src/components/DiffPreview.tsx` — Phase 2 placeholder (경로 + 새 내용 처음 10줄)
- `ui-ink/src/components/ToolCard.tsx` — TOOL_META 요약 + Space/Enter 로컬 토글
- `ui-ink/src/__tests__/components.confirm.test.tsx` — vitest + ink-testing-library
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/phases/02-core-ux/02-CONTEXT.md
@.planning/phases/02-core-ux/02-RESEARCH.md

# Plan A / B SUMMARY (Wave 1 결과물) — 실행 시점에 존재
@.planning/phases/02-core-ux/02-PLAN-A-SUMMARY.md
@.planning/phases/02-core-ux/02-PLAN-B-SUMMARY.md

# 소스 참조
@ui-ink/src/store/confirm.ts
@ui-ink/src/store/room.ts
@ui-ink/src/protocol.ts

<interfaces>
<!-- Plan A 완료 후 confirm store 확정 인터페이스 (재작성 대상) -->
<!-- Executor 는 Plan A SUMMARY 에서 최신 시그니처를 확인해야 함 -->

From ui-ink/src/store/confirm.ts (Plan A 확장 후 확정 시그니처):
```typescript
export type ConfirmMode = 'none' | 'confirm_write' | 'confirm_bash' | 'cplan_confirm'

interface ConfirmState {
  mode: ConfirmMode
  payload: Record<string, unknown>       // {path} | {command} | {task}
  deniedPaths: Set<string>
  deniedCmds: Set<string>
  // setConfirm 은 2-인자 (mode, payload) — resolve 는 별도 store 필드로 존재
  setConfirm: (mode: ConfirmMode, payload: Record<string, unknown>) => void
  clearConfirm: () => void
  addDenied: (kind: 'path' | 'cmd', key: string) => void
  isDenied: (kind: 'path' | 'cmd', key: string) => boolean
  clearDenied: () => void
  // resolve(accept) — 내부적으로 boundClient.send + addDenied + mode='none' 처리
  // Plan A 가 bindConfirmClient(client) 로 주입한 HarnessClient 를 사용
  resolve: (accept: boolean) => void
}
```

From ui-ink/src/store/room.ts (Plan A/B 에서 제공):
```typescript
// activeIsSelf: 현재 턴 소유자가 자기 자신인가 (관전자면 false)
activeIsSelf: boolean
```

From ui-ink/src/protocol.ts:
```typescript
export interface ConfirmWriteMsg { type: 'confirm_write'; path: string }
export interface ConfirmBashMsg  { type: 'confirm_bash'; command: string }
export interface CplanConfirmMsg { type: 'cplan_confirm'; task: string }

// 주의: harness_server.py line 200-220 확인 결과 danger_level 필드는 서버가 보내지 않음
// → 클라이언트에서 command 문자열 패턴 매칭으로 분류
```

From ui-ink/src/store/session.ts (Plan A 완료 후, tool_start/tool_end 데이터 저장):
```typescript
// ToolCard 가 소비할 구조 (Plan A SUMMARY 확인 필요)
interface ToolInvocation {
  id: string           // 유니크 id (nanoid 등)
  name: string         // tool name
  args: Record<string, unknown>
  result?: string      // tool_end 전에는 undefined
  status: 'pending' | 'ok' | 'err'
}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>D-1: ConfirmDialog.tsx — 다이얼로그 컴포넌트 (CNF-01/02/04/05)</name>
  <files>ui-ink/src/components/ConfirmDialog.tsx</files>

  <read_first>
    - `ui-ink/src/store/confirm.ts` — Plan A 확장 후 최종 인터페이스 (resolve / deniedPaths / addDenied / isDenied)
    - `ui-ink/src/store/room.ts` — `activeIsSelf` selector
    - `ui-ink/src/protocol.ts` — `ConfirmWriteMsg` / `ConfirmBashMsg` / `CplanConfirmMsg` 의 payload 필드명
    - `ui-ink/src/components/InputArea.tsx` — App.tsx 에서 치환되는 위치와 폭/스타일 기준
    - `ui-ink/src/App.tsx` — 이 Plan 범위는 컴포넌트만이지만, 치환 지점(`{confirm.mode === 'none' ? <InputArea /> : <ConfirmDialog />}`)을 Plan E 가 수정한다는 점을 명심. 이 파일은 **수정하지 않는다**.
    - `harness_server.py` line 200-220 — `confirm_bash` / `confirm_write` 가 **danger_level 필드를 전송하지 않는다**는 점 재확인
  </read_first>

  <action>
**파일 전체를 새로 생성한다.** 수정 대상 기존 파일 없음.

```tsx
// ConfirmDialog — CNF-01/02/04/05 구현
// - confirm_write: 경로 + DiffPreview placeholder + y/n/d/Esc 힌트
// - confirm_bash: 커맨드 + 위험도 라벨 + y/n/Esc 힌트
// - cplan_confirm: task 문자열 + y/n/Esc 힌트 (CNF-05 — confirm_write 와 동일 프레임)
// - activeIsSelf=false: ConfirmReadOnlyView (관전자는 의사결정 불가, CNF-04)
// - sticky-deny: isDenied hit → 즉시 resolve(false) (Plan A store 사용)
import React, {useEffect} from 'react'
import {Box, Text, useInput} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useConfirmStore} from '../store/confirm.js'
import {useRoomStore} from '../store/room.js'
import {DiffPreview} from './DiffPreview.js'

// CNF-02: 서버가 danger_level 을 보내지 않으므로 클라 판정
const DANGEROUS_PATTERNS: RegExp[] = [
  /\brm\b/,
  /\bsudo\b/,
  /\bchmod\b/,
  /\bchown\b/,
  /[|&;<>`]/,       // 쉘 메타문자 / 파이프 / 리디렉션
  /\$\(/,           // command substitution
  /\bdd\b/,
  /\bmkfs\b/,
  /\beval\b/,
]

export function classifyCommand(cmd: string): 'safe' | 'dangerous' {
  return DANGEROUS_PATTERNS.some((p) => p.test(cmd)) ? 'dangerous' : 'safe'
}

export function ConfirmDialog(): React.ReactElement | null {
  // useShallow 로 필요한 필드만 subscribe (CLAUDE.md 금지 사항: 전체 store selector 금지)
  const {mode, payload, resolve, addDenied, isDenied, clearConfirm} = useConfirmStore(
    useShallow((s) => ({
      mode: s.mode,
      payload: s.payload,
      resolve: s.resolve,
      addDenied: s.addDenied,
      isDenied: s.isDenied,
      clearConfirm: s.clearConfirm,
    }))
  )
  const activeIsSelf = useRoomStore((s) => s.activeIsSelf)
  const [showDiff, setShowDiff] = React.useState(false)

  // CNF-03 sticky-deny 자동 판정: mode 가 활성화되는 순간 1회 체크
  useEffect(() => {
    if (mode === 'none' || !resolve) return
    const key =
      mode === 'confirm_write' ? (payload['path'] as string | undefined) :
      mode === 'confirm_bash'  ? (payload['command'] as string | undefined) :
      undefined
    if (!key) return
    const kind: 'path' | 'cmd' = mode === 'confirm_write' ? 'path' : 'cmd'
    if (isDenied(kind, key)) {
      resolve(false)
      clearConfirm()
    }
  }, [mode, payload, resolve, isDenied, clearConfirm])

  // mode 가 없으면 렌더하지 않는다 (App.tsx 에서 이미 분기하지만 이중 가드)
  if (mode === 'none' || !resolve) return null

  // CNF-04: 관전자는 read-only
  if (!activeIsSelf) {
    return <ConfirmReadOnlyView mode={mode} payload={payload} />
  }

  const handleAccept = () => {
    resolve(true)
    clearConfirm()
    setShowDiff(false)
  }
  const handleDeny = () => {
    // sticky-deny 등록 (다음 동일 요청 자동 거부)
    const key =
      mode === 'confirm_write' ? (payload['path'] as string | undefined) :
      mode === 'confirm_bash'  ? (payload['command'] as string | undefined) :
      undefined
    if (key) {
      addDenied(mode === 'confirm_write' ? 'path' : 'cmd', key)
    }
    resolve(false)
    clearConfirm()
    setShowDiff(false)
  }

  useInput((ch, key) => {
    if (ch === 'y' || ch === 'Y') { handleAccept(); return }
    if (ch === 'n' || ch === 'N') { handleDeny(); return }
    if (key.escape) { handleDeny(); return }
    if ((ch === 'd' || ch === 'D') && mode === 'confirm_write') {
      setShowDiff((v) => !v)
    }
  })

  // CNF-01: confirm_write
  if (mode === 'confirm_write') {
    const path = (payload['path'] as string) ?? '(경로 없음)'
    const content = payload['content'] as string | undefined
    return (
      <Box flexDirection='column' borderStyle='round' borderColor='yellow' paddingX={1}>
        <Text color='yellow'>파일 쓰기 확인</Text>
        <Text>경로: <Text bold>{path}</Text></Text>
        {showDiff && <DiffPreview path={path} newContent={content} />}
        <Text dimColor>
          <Text color='green'>y</Text> 허용 · <Text color='red'>n</Text> 거부 · <Text color='cyan'>d</Text> 미리보기 · <Text color='gray'>Esc</Text> 취소
        </Text>
      </Box>
    )
  }

  // CNF-02: confirm_bash
  if (mode === 'confirm_bash') {
    const command = (payload['command'] as string) ?? ''
    const danger = classifyCommand(command)
    return (
      <Box flexDirection='column' borderStyle='round' borderColor={danger === 'dangerous' ? 'red' : 'yellow'} paddingX={1}>
        <Text color={danger === 'dangerous' ? 'red' : 'yellow'}>
          쉘 실행 확인 {danger === 'dangerous' ? '[위험]' : '[일반]'}
        </Text>
        <Text>커맨드: <Text bold>{command}</Text></Text>
        <Text dimColor>
          <Text color='green'>y</Text> 허용 · <Text color='red'>n</Text> 거부 · <Text color='gray'>Esc</Text> 취소
        </Text>
      </Box>
    )
  }

  // CNF-05: cplan_confirm — confirm_write 와 동일한 프레임
  if (mode === 'cplan_confirm') {
    const task = (payload['task'] as string) ?? ''
    return (
      <Box flexDirection='column' borderStyle='round' borderColor='cyan' paddingX={1}>
        <Text color='cyan'>계획 확인</Text>
        <Text>작업: <Text bold>{task}</Text></Text>
        <Text dimColor>
          <Text color='green'>y</Text> 허용 · <Text color='red'>n</Text> 거부 · <Text color='gray'>Esc</Text> 취소
        </Text>
      </Box>
    )
  }

  return null
}

// CNF-04: 관전자 전용 뷰 — 내용만 보여주고 입력은 받지 않는다
interface ReadOnlyProps {
  mode: Exclude<import('../store/confirm.js').ConfirmMode, 'none'>
  payload: Record<string, unknown>
}

function ConfirmReadOnlyView({mode, payload}: ReadOnlyProps): React.ReactElement {
  const label =
    mode === 'confirm_write' ? '파일 쓰기 대기 중' :
    mode === 'confirm_bash'  ? '쉘 실행 대기 중' :
                               '계획 확인 대기 중'
  const detail =
    mode === 'confirm_write' ? (payload['path'] as string | undefined) ?? '' :
    mode === 'confirm_bash'  ? (payload['command'] as string | undefined) ?? '' :
                               (payload['task'] as string | undefined) ?? ''
  return (
    <Box flexDirection='column' borderStyle='round' borderColor='gray' paddingX={1}>
      <Text color='gray'>{label} (관전 중 — 응답 불가)</Text>
      <Text dimColor>{detail}</Text>
    </Box>
  )
}
```

**핵심 구현 포인트:**
1. `useShallow` 필수 — CLAUDE.md 금지 사항 (`const s = useStore()` 금지) 준수
2. `useInput` 는 `activeIsSelf=true` 일 때만 등록되도록 **조건부 반환** 뒤에 둔다 (관전자는 키 입력을 가로채면 안 됨)
3. sticky-deny 자동 체크는 `useEffect` 에서 mode 변경 시 1회만 수행
4. `.js` 임포트 확장자 (TypeScript → ESM 빌드 관례, 프로젝트 기존 규칙)
5. danger 분류는 `classifyCommand` 로 export — D-4 테스트에서 단위 검증 가능하게
6. Esc 는 deny 와 동일 처리 (요청 스펙 일치)
  </action>

  <verify>
    <automated>cd ui-ink && bun run typecheck 2>&1 | grep -E "(ConfirmDialog|error)" || true</automated>
    <automated>cd ui-ink && bun run lint src/components/ConfirmDialog.tsx 2>&1 || true</automated>
  </verify>

  <acceptance_criteria>
    - 파일 `ui-ink/src/components/ConfirmDialog.tsx` 생성됨
    - `ConfirmDialog` 및 `classifyCommand` named export 존재
    - `useShallow` 사용, 전체 store selector 없음 (`const s = useConfirmStore()` 형태 금지)
    - `.js` 확장자 임포트 사용 (TypeScript ESM)
    - `<div>` / `<span>` / `console.log` / `process.stdout.write` 없음
    - `useInput` 이 `!activeIsSelf` 분기 뒤에 위치 (관전자는 키 비활성)
    - CNF-01/02/05 세 모드 모두 분기 존재
    - sticky-deny 체크가 `useEffect` 로 mode 변경 시 자동 수행
    - Esc / 'n' 시 `addDenied` 호출
    - typecheck 및 lint 통과
  </acceptance_criteria>
  <done>ConfirmDialog 컴포넌트가 타입 에러 없이 컴파일되고, 네 가지 뷰 (write/bash/cplan/read-only) 가 모두 render 분기로 존재한다.</done>
</task>

<task type="auto">
  <name>D-2: DiffPreview.tsx — Phase 2 placeholder (RND-07)</name>
  <files>ui-ink/src/components/DiffPreview.tsx</files>

  <read_first>
    - `.planning/phases/02-core-ux/02-CONTEXT.md` — RND-07 Phase 2 scope 확인 (old_content 미수신)
    - `.planning/REQUIREMENTS.md` — PEXT-02 (Phase 3 에서 old_content 추가) 확인
    - `ui-ink/src/protocol.ts` — `ConfirmWriteMsg` 의 현재 필드는 `path` 만
  </read_first>

  <action>
**파일 전체를 새로 생성한다.** Phase 3 에서 diff@9 `structuredPatch` 로 교체될 placeholder.

```tsx
// DiffPreview — RND-07 Phase 2 placeholder
// Phase 2: 경로 헤더 + 새 내용 처음 10줄만 표시 (old_content 미수신)
// Phase 3 (PEXT-02): old_content 필드 추가 후 diff@9 structuredPatch 연동 예정
import React from 'react'
import {Box, Text} from 'ink'

interface DiffPreviewProps {
  path: string
  newContent?: string
}

const PREVIEW_LINE_LIMIT = 10

export function DiffPreview({path, newContent}: DiffPreviewProps): React.ReactElement {
  const lines = (newContent ?? '').split('\n').slice(0, PREVIEW_LINE_LIMIT)
  const total = (newContent ?? '').split('\n').length
  const truncated = total > PREVIEW_LINE_LIMIT

  return (
    <Box flexDirection='column' marginTop={1} marginBottom={1} borderStyle='single' borderColor='gray' paddingX={1}>
      <Text color='gray'>미리보기 — {path}</Text>
      {newContent === undefined ? (
        <Text dimColor>(새 내용 미수신 — Phase 3 에서 diff 표시 예정)</Text>
      ) : (
        <Box flexDirection='column'>
          {lines.map((ln, i) => (
            <Text key={`preview-${path}-${i}-${ln.slice(0, 16)}`} color='green'>+ {ln}</Text>
          ))}
          {truncated && <Text dimColor>... ({total - PREVIEW_LINE_LIMIT}줄 더)</Text>}
        </Box>
      )}
    </Box>
  )
}
```

**핵심 구현 포인트:**
1. `newContent` 는 optional — 서버가 현재 `path` 만 보내므로 undefined 가 기본
2. React key 에 index 단독 사용 금지 (CLAUDE.md) — `path + i + 내용 앞부분` 조합
3. Phase 3 교체 신호: `old_content` prop 이 추가되면 `diff@9` import + `structuredPatch` 로 변경
4. 배열 splice/mutate 없이 순수 `slice` 만 사용 (Zustand store 영향 없음)
  </action>

  <verify>
    <automated>cd ui-ink && bun run typecheck 2>&1 | grep -E "(DiffPreview|error)" || true</automated>
  </verify>

  <acceptance_criteria>
    - 파일 `ui-ink/src/components/DiffPreview.tsx` 생성됨
    - `DiffPreview` named export 존재, `path: string`, `newContent?: string` props
    - `diff` 패키지 import 없음 (Phase 3 에서 추가)
    - React key 에 index 단독 사용 없음
    - `<div>` / `<span>` / `console.log` / `process.stdout.write` 없음
    - typecheck 통과
  </acceptance_criteria>
  <done>DiffPreview 가 `newContent` 유무에 따라 placeholder 또는 10줄 미리보기 중 하나를 렌더링한다.</done>
</task>

<task type="auto">
  <name>D-3: ToolCard.tsx — TOOL_META 1줄 요약 + 상세 토글 (RND-08)</name>
  <files>ui-ink/src/components/ToolCard.tsx</files>

  <read_first>
    - Plan A SUMMARY — `ToolInvocation` 타입의 확정 필드 이름 (status / result / args 가 맞는지)
    - `ui-ink/src/store/session.ts` — tool_start/tool_end 가 저장되는 구조
    - `ui-ink/src/protocol.ts` — `ToolStartMsg` (name, args), `ToolEndMsg` (name, result)
  </read_first>

  <action>
**파일 전체를 새로 생성한다.**

```tsx
// ToolCard — RND-08 툴 호출 카드
// - 1줄 요약 기본 (TOOL_META 매핑)
// - Space/Enter 로 상세 펼침 (로컬 useState, store 불필요 — Claude 판단)
// - 상태 색상: pending(yellow), ok(green), err(red)
import React, {useState} from 'react'
import {Box, Text, useInput, useFocus} from 'ink'

export interface ToolInvocationView {
  id: string
  name: string
  args: Record<string, unknown>
  result?: string
  status: 'pending' | 'ok' | 'err'
}

type SummaryFn = (args: Record<string, unknown>, result: string) => string

// 주요 툴별 1줄 요약 규칙
const TOOL_META: Record<string, SummaryFn> = {
  read_file: (_args, result) => `read ${result.split('\n').length} lines`,
  write_file: (args) => `write ${String(args['path'] ?? '?')}`,
  run_command: (_args, result) => {
    const match = result.match(/exit (\d+)/)
    return match ? `exit ${match[1]}` : 'ran'
  },
  list_directory: (_args, result) => `ls ${result.split('\n').length} entries`,
  search_files: (_args, result) => `found ${result.split('\n').filter(Boolean).length} results`,
}

function summarize(inv: ToolInvocationView): string {
  if (inv.status === 'pending') return '...'
  const fn = TOOL_META[inv.name]
  const result = inv.result ?? ''
  if (fn) return fn(inv.args, result)
  // fallback: 앞 60자
  return result.length > 60 ? `${result.slice(0, 60)}...` : result
}

interface ToolCardProps {
  invocation: ToolInvocationView
}

export function ToolCard({invocation}: ToolCardProps): React.ReactElement {
  const [expanded, setExpanded] = useState(false)
  const {isFocused} = useFocus({autoFocus: false})

  // Ink useInput — space 는 ch === ' ', Enter 는 key.return 으로 전달된다
  // 포커스된 카드에만 토글 적용 (여러 카드 동시에 토글되지 않도록 isActive 로 제한)
  useInput(
    (ch, key) => {
      if (ch === ' ' || key.return) {
        setExpanded((v) => !v)
      }
    },
    {isActive: isFocused}
  )

  const statusColor =
    invocation.status === 'pending' ? 'yellow' :
    invocation.status === 'ok'      ? 'green'  :
                                       'red'
  const marker =
    invocation.status === 'pending' ? '·' :
    invocation.status === 'ok'      ? '✓' :
                                       '✗'

  return (
    <Box flexDirection='column' borderStyle={isFocused ? 'round' : 'single'} borderColor={statusColor} paddingX={1}>
      <Box>
        <Text color={statusColor}>{marker} </Text>
        <Text bold>{invocation.name}</Text>
        <Text> — </Text>
        <Text dimColor>{summarize(invocation)}</Text>
      </Box>
      {expanded && invocation.result !== undefined && (
        <Box flexDirection='column' marginTop={1}>
          <Text dimColor>────────</Text>
          <Text>{invocation.result}</Text>
        </Box>
      )}
      {isFocused && (
        <Text dimColor>
          <Text color='cyan'>Space/Enter</Text> {expanded ? '접기' : '펼치기'}
        </Text>
      )}
    </Box>
  )
}
```

**핵심 구현 포인트:**
1. `useFocus({autoFocus: false})` — 여러 ToolCard 가 동시에 키 입력 가로채지 않도록 포커스된 카드만 토글
2. Space 는 Ink 에서 `ch === ' '` 로 들어옴 (key.space 없음 — 기존 `useInput` 레퍼런스 확인)
3. TOOL_META 에 없는 툴은 result 앞 60자 fallback
4. 컴포넌트는 **읽기 전용** — store 에서 invocation 을 prop 으로 받고, 로컬 expanded 만 관리
5. `useInput` 호출은 정확히 **1개** — space/Enter 토글만 처리, 포커스 없을 때는 isActive=false 로 이벤트 자체가 차단됨

**작성 시 주의 — `useInput` 은 하나만 둘 것. grep 으로 중복 검증:**
```bash
grep -c 'useInput' ui-ink/src/components/ToolCard.tsx   # 정확히 1
```
  </action>

  <verify>
    <automated>cd ui-ink && bun run typecheck 2>&1 | grep -E "(ToolCard|error)" || true</automated>
    <automated>cd ui-ink && grep -c "useInput" src/components/ToolCard.tsx</automated>
  </verify>

  <acceptance_criteria>
    - 파일 `ui-ink/src/components/ToolCard.tsx` 생성됨
    - `ToolCard`, `ToolInvocationView` named export 존재
    - `useInput` 호출이 **정확히 1개** (grep 결과 === 1)
    - `TOOL_META` 에 최소 5개 툴 (`read_file`, `write_file`, `run_command`, `list_directory`, `search_files`) 포함
    - 상태별 색상 3종 (pending/ok/err) 구분
    - `<div>` / `<span>` / `console.log` 없음
    - typecheck 통과
  </acceptance_criteria>
  <done>ToolCard 가 tool invocation prop 을 받아 1줄 요약을 렌더하고, 포커스 시 Space/Enter 로 상세 result 를 토글한다.</done>
</task>

<task type="auto" tdd="true">
  <name>D-4: vitest — ConfirmDialog 통합 테스트</name>
  <files>ui-ink/src/__tests__/components.confirm.test.tsx</files>

  <behavior>
    - Test 1: `classifyCommand('ls -la')` → `'safe'`
    - Test 2: `classifyCommand('rm -rf /')` → `'dangerous'` (`\brm\b` 매칭)
    - Test 3: `classifyCommand('echo $(whoami)')` → `'dangerous'` (`\$\(` 매칭)
    - Test 4: `confirm_write` 모드에서 경로 텍스트와 `y`/`n`/`d`/`Esc` 힌트가 렌더됨
    - Test 5: `confirm_bash` 모드에서 커맨드 텍스트와 위험도 라벨이 렌더됨 (dangerous 입력 시 `[위험]` 포함)
    - Test 6: `activeIsSelf=false` 일 때 read-only 뷰 ("응답 불가") 렌더, 입력 힌트 없음
    - Test 7: `cplan_confirm` 모드에서 task 텍스트와 힌트 렌더 (CNF-05)
  </behavior>

  <read_first>
    - Plan A SUMMARY — confirm store reset 방법 (`clearConfirm` + `clearDenied`)
    - Plan A SUMMARY — `useRoomStore` 에서 `activeIsSelf` 를 setter 로 제어하는지 (없으면 테스트에서 직접 `useRoomStore.setState({activeIsSelf: false})` 사용)
    - `ui-ink/package.json` — `ink-testing-library`, `vitest` 존재 확인
    - 기존 vitest 테스트 파일이 있으면 style 참고 (`ui-ink/src/__tests__/*.test.ts(x)`)
  </read_first>

  <action>
**파일 전체를 새로 생성한다.**

```tsx
// ConfirmDialog 통합 테스트 — CNF-01/02/04/05 동작 검증
import {describe, it, expect, beforeEach} from 'vitest'
import React from 'react'
import {render} from 'ink-testing-library'
import {ConfirmDialog, classifyCommand} from '../components/ConfirmDialog.js'
import {useConfirmStore} from '../store/confirm.js'
import {useRoomStore} from '../store/room.js'

// 각 테스트 간 store 초기화
beforeEach(() => {
  useConfirmStore.getState().clearConfirm()
  useConfirmStore.getState().clearDenied()
  useRoomStore.setState({activeIsSelf: true})
})

describe('classifyCommand (CNF-02)', () => {
  it('평문 명령은 safe 로 판정한다', () => {
    expect(classifyCommand('ls -la')).toBe('safe')
    expect(classifyCommand('echo hello')).toBe('safe')
  })
  it('rm / sudo / chmod 는 dangerous', () => {
    expect(classifyCommand('rm -rf /')).toBe('dangerous')
    expect(classifyCommand('sudo apt update')).toBe('dangerous')
    expect(classifyCommand('chmod 777 file')).toBe('dangerous')
  })
  it('쉘 메타 문자 및 command substitution 은 dangerous', () => {
    expect(classifyCommand('ls | grep foo')).toBe('dangerous')
    expect(classifyCommand('echo $(whoami)')).toBe('dangerous')
    expect(classifyCommand('cat a > b')).toBe('dangerous')
  })
})

describe('ConfirmDialog rendering', () => {
  it('confirm_write 모드: 경로와 y/n/d/Esc 힌트를 표시한다 (CNF-01)', () => {
    // setConfirm 은 2-인자 (mode, payload) — resolve 는 store 필드
    useConfirmStore.getState().setConfirm(
      'confirm_write',
      {path: '/tmp/foo.txt'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('/tmp/foo.txt')
    expect(frame).toContain('y')
    expect(frame).toContain('n')
    expect(frame).toContain('d')
    expect(frame).toContain('Esc')
  })

  it('confirm_bash 모드: 커맨드와 위험 라벨을 표시한다 (CNF-02)', () => {
    useConfirmStore.getState().setConfirm(
      'confirm_bash',
      {command: 'rm -rf /'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('rm -rf /')
    expect(frame).toContain('[위험]')
  })

  it('confirm_bash 안전 커맨드: [일반] 라벨', () => {
    useConfirmStore.getState().setConfirm(
      'confirm_bash',
      {command: 'ls -la'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    expect(lastFrame() ?? '').toContain('[일반]')
  })

  it('cplan_confirm 모드: task 와 힌트를 표시한다 (CNF-05)', () => {
    useConfirmStore.getState().setConfirm(
      'cplan_confirm',
      {task: 'refactor auth flow'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('refactor auth flow')
    expect(frame).toContain('y')
    expect(frame).toContain('n')
  })

  it('activeIsSelf=false: read-only 뷰를 렌더한다 (CNF-04)', () => {
    useRoomStore.setState({activeIsSelf: false})
    useConfirmStore.getState().setConfirm(
      'confirm_write',
      {path: '/tmp/foo.txt'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('응답 불가')
    expect(frame).toContain('/tmp/foo.txt')
    // y/n 힌트는 나오면 안 됨 (read-only)
    expect(frame).not.toMatch(/y\s.*허용/)
  })

  it('mode=none 일 때 null 을 반환한다', () => {
    useConfirmStore.getState().clearConfirm()
    const {lastFrame} = render(<ConfirmDialog />)
    expect((lastFrame() ?? '').trim()).toBe('')
  })
})
```

**핵심 구현 포인트:**
1. `beforeEach` 로 두 store 모두 초기화 — 테스트 독립성 필수
2. `setConfirm(mode, payload, resolve)` 호출 시 resolve 는 `() => {}` 스텁
3. `useRoomStore.setState({activeIsSelf: false})` 로 관전자 상태 재현
4. read-only 뷰에서 "응답 불가" 문자열이 Korean 인지 ConfirmDialog.tsx 와 정확히 일치하는지 확인
5. `lastFrame()` 이 undefined 가능하므로 `?? ''` fallback
6. `ink-testing-library` 의 `render` 는 동기이므로 `act()` 래핑 불필요 (기존 Ink 테스트 관례)

**Plan A 결정 확인:** `setConfirm(mode, payload)` 은 2-인자이며, `resolve(accept)` 는 store 메서드로 별도 존재한다 (Plan A A-3). ConfirmDialog 는 `useConfirmStore` 에서 `resolve` 를 그대로 꺼내 사용하고, `setConfirm` 호출 시 resolve 를 주입하지 않는다. 테스트에서도 `setConfirm(mode, payload)` 2-인자 호출 후 `resolve` 는 이미 store 에 바인딩된 것을 사용 (별도 주입 불필요).
  </action>

  <verify>
    <automated>cd ui-ink && bun run test -- components.confirm 2>&1 | tail -30</automated>
  </verify>

  <acceptance_criteria>
    - 파일 `ui-ink/src/__tests__/components.confirm.test.tsx` 생성됨
    - `classifyCommand` 관련 3개 테스트 + `ConfirmDialog` 관련 6개 테스트 = 총 9개 test case 이상
    - `bun run test -- components.confirm` 실행 시 모두 pass (green)
    - 기존 vitest suite 회귀 없음 (별도로 `bun run test` 전체 실행해 확인)
  </acceptance_criteria>
  <done>새 테스트 파일의 모든 케이스가 green 이고, 전체 ui-ink vitest suite 가 여전히 green 이다.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| 서버 → UI (WS confirm_* 이벤트) | 서버가 보낸 `path` / `command` / `task` 가 untrusted 문자열로 UI 에 진입 |
| UI → 사용자 (ConfirmDialog) | 사용자가 y/n 키로 결정을 내려 서버로 accept=bool 만 전송 |
| UI 로컬 store (sticky-deny) | `deniedPaths` / `deniedCmds` Set 는 메모리 내부, 세션 종료 시 휘발 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02D-01 | Spoofing | ConfirmDialog 관전자 모드 | mitigate | CNF-04: `!activeIsSelf` 분기에서 `useInput` 미등록 → 관전자가 결정을 내릴 수 없음 (ConfirmReadOnlyView 가 키 입력을 받지 않음) |
| T-02D-02 | Tampering | payload 내 `path` / `command` | accept | 서버가 신뢰된 프로세스(harness_server.py)에서 직접 생성한 값이며, 같은 머신의 같은 사용자 권한. UI 는 표시만 담당 |
| T-02D-03 | Repudiation | 사용자 결정 기록 부재 | accept | Phase 2 스코프 외 — 감사 로그는 Phase 4 (Testing+Beta) 에서 재검토. 현재는 STATE.md / 서버 로그에 의존 |
| T-02D-04 | Information Disclosure | DiffPreview 가 파일 내용 노출 | accept | 같은 Room 내 사용자는 이미 상호 신뢰 관계. Phase 3 PEXT-02 에서 diff 연결 시 재평가 |
| T-02D-05 | Denial of Service | sticky-deny Set 무한 증가 | mitigate | `agentEnd` 시 `clearDenied()` 호출 (Plan B 가 dispatch 에 심음). 본 Plan 은 호출 경로를 신뢰하고 컴포넌트만 렌더 |
| T-02D-06 | Elevation of Privilege | 위험 커맨드 미탐지 → 사용자가 무심코 y | mitigate | CNF-02 `classifyCommand` 의 `DANGEROUS_PATTERNS` 로 `[위험]` 라벨 + 빨간 테두리 시각 경고. 패턴 목록은 테스트로 고정 (D-4) |
| T-02D-07 | Elevation of Privilege | sticky-deny 우회 (같은 파일 대소문자 다르게) | accept | sticky-deny 는 **편의 기능** 이지 보안 경계 아님. 서버 측 권한 검사는 harness_core 의 책임. UI 는 정확한 key 매칭만 수행 |
| T-02D-08 | Information Disclosure | ToolCard result 에 비밀정보 노출 | accept | Phase 2 범위 밖 — secret redaction 은 Phase 3/4 검토 (REQUIREMENTS.md 에 별도 항목 없음) |

**Mitigation summary:** CNF-02 의 danger 분류는 **클라이언트 힌트** 로 명시 — 서버 권한 검사를 대체하지 않음. 모든 confirm 이벤트는 서버가 최종 accept bool 을 처리.
</threat_model>

<verification>
- `bun run typecheck` → 에러 없음
- `bun run lint src/components/` → ConfirmDialog / DiffPreview / ToolCard 에 대한 경고 없음
- `bun run test -- components.confirm` → 9개 이상 test case all green
- `bun run test` 전체 → Wave 1 (Plan A/B) 테스트 포함 전부 green
- 수동 확인: `grep -rn "process.stdout.write\|console.log\|<div>\|<span>" ui-ink/src/components/ConfirmDialog.tsx ui-ink/src/components/DiffPreview.tsx ui-ink/src/components/ToolCard.tsx` → 결과 0건
- 수동 확인: `grep -n "useInput" ui-ink/src/components/ToolCard.tsx | wc -l` → 1
- Python 백엔드 회귀: `.venv/bin/python -m pytest --tb=short -q` → 199건 이상 통과 (ui-ink 컴포넌트 변경이 Python 백엔드에 영향 없음 확인)
</verification>

<must_haves>
  truths:
    - "사용자가 confirm_write 이벤트를 받으면 경로와 y/n/d/Esc 힌트가 화면에 나타난다"
    - "사용자가 confirm_bash 이벤트를 받으면 커맨드와 위험도 라벨(`[위험]`/`[일반]`)이 화면에 나타난다"
    - "사용자가 cplan_confirm 이벤트를 받으면 task 문자열과 y/n/Esc 힌트가 confirm_write 와 동일한 프레임 구조로 나타난다"
    - "활성 턴이 자기 자신이 아닐 때(관전자) ConfirmDialog 는 read-only 뷰로 렌더되고 키 입력을 받지 않는다"
    - "사용자가 n 또는 Esc 를 누르면 sticky-deny 가 등록되어 다음 동일 요청이 자동 거부된다"
    - "ToolCard 는 tool invocation 당 1줄 요약을 표시하고, 포커스 상태에서 Space/Enter 로 상세 result 를 토글한다"
    - "DiffPreview 는 path 와 새 내용 처음 10줄을 placeholder 로 표시한다 (Phase 3 에서 diff 로 교체 가능)"
  artifacts:
    - path: "ui-ink/src/components/ConfirmDialog.tsx"
      provides: "ConfirmDialog + classifyCommand"
      min_lines: 110
      exports: ["ConfirmDialog", "classifyCommand"]
    - path: "ui-ink/src/components/DiffPreview.tsx"
      provides: "DiffPreview placeholder"
      min_lines: 25
      exports: ["DiffPreview"]
    - path: "ui-ink/src/components/ToolCard.tsx"
      provides: "ToolCard with TOOL_META summary"
      min_lines: 60
      exports: ["ToolCard", "ToolInvocationView"]
    - path: "ui-ink/src/__tests__/components.confirm.test.tsx"
      provides: "ConfirmDialog + classifyCommand vitest suite"
      min_lines: 80
      contains: "describe('classifyCommand"
  key_links:
    - from: "ui-ink/src/components/ConfirmDialog.tsx"
      to: "ui-ink/src/store/confirm.ts"
      via: "useConfirmStore(useShallow(...))"
      pattern: "useConfirmStore\\(\\s*useShallow"
    - from: "ui-ink/src/components/ConfirmDialog.tsx"
      to: "ui-ink/src/store/room.ts"
      via: "useRoomStore(s => s.activeIsSelf)"
      pattern: "useRoomStore\\(\\(s\\)\\s*=>\\s*s\\.activeIsSelf\\)"
    - from: "ui-ink/src/components/ConfirmDialog.tsx"
      to: "ui-ink/src/components/DiffPreview.tsx"
      via: "import + showDiff branch"
      pattern: "import\\s*\\{\\s*DiffPreview\\s*\\}"
    - from: "ui-ink/src/components/ConfirmDialog.tsx"
      to: "sticky-deny store"
      via: "addDenied on deny path"
      pattern: "addDenied\\("
    - from: "ui-ink/src/__tests__/components.confirm.test.tsx"
      to: "ui-ink/src/components/ConfirmDialog.tsx"
      via: "ink-testing-library render"
      pattern: "render\\(<ConfirmDialog"
</must_haves>

<success_criteria>
- 세 컴포넌트 (`ConfirmDialog`, `DiffPreview`, `ToolCard`) + 테스트 파일 총 4개 신규 생성
- `bun run typecheck` + `bun run lint` 에러 0
- `bun run test` 전체 green (기존 suite 회귀 없음 + 새 9+ case 통과)
- Absolute prohibitions 위반 0건 (grep 확인)
- `useInput` 호출이 ToolCard 내 정확히 1개
- `useShallow` 가 ConfirmDialog 에서 사용됨 (전체 store selector 없음)
- CNF-01/02/04/05 + RND-07/08 시각적 동작을 테스트가 커버
- Plan E (App.tsx 치환 지점) 에서 `<ConfirmDialog />` import 만 하면 즉시 동작할 수 있는 상태
</success_criteria>

<output>
After completion, create `.planning/phases/02-core-ux/02-PLAN-D-SUMMARY.md` documenting:
- 네 파일의 실제 라인 수 및 export 목록
- `classifyCommand` 의 최종 DANGEROUS_PATTERNS (Plan A/B 통합 시 참고용)
- `TOOL_META` 에 포함된 툴 목록
- Plan E (App.tsx 치환) 가 참조해야 할 import path 및 컴포넌트 시그니처
- Phase 3 PEXT-02 수신 시 DiffPreview 에서 교체해야 할 지점 (newContent → old/new diff)
- vitest 실행 결과 (pass 개수)
</output>
