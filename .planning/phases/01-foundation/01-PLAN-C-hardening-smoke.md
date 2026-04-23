---
phase: 01-foundation
plan: C
type: execute
wave: 2
depends_on: [A, B]
files_modified:
  - ui-ink/src/index.tsx
  - ui-ink/src/App.tsx
  - ui-ink/harness.sh
  - ui-ink/src/__tests__/protocol.test.ts
  - ui-ink/src/__tests__/store.test.ts
  - ui-ink/src/__tests__/dispatch.test.ts
  - ui-ink/src/__tests__/tty-guard.test.ts
autonomous: true
requirements:
  - FND-12
  - FND-13
  - FND-14
  - FND-15
  - FND-16

must_haves:
  truths:
    - "bun start 이후 HARNESS_URL+HARNESS_TOKEN 환경변수가 있으면 WS 연결 시도, 없으면 연결 없음 메시지 출력"
    - "echo 'x' | bun run src/index.tsx 가 crash 없이 one-shot 경로(TTY 아님)로 분기해 종료된다"
    - "uncaughtException / unhandledRejection / SIGHUP / SIGINT / SIGTERM 에서 setRawMode(false) + 커서 복원 + stdin.pause() 수행"
    - "render(<App/>, {patchConsole: false}) 로 Ink console 가로채기가 비활성화된다"
    - "harness.sh 에 trap 'stty sane' EXIT 가 포함된다"
    - "vitest 단위 테스트(parseServerMsg, store reducers, dispatch exhaustive, TTY 가드) 전부 통과"
    - "tsc --noEmit 이 green 이다"
  artifacts:
    - path: "ui-ink/src/index.tsx"
      provides: "TTY 가드, 시그널 핸들러, render() 진입점"
      contains: "patchConsole: false"
    - path: "ui-ink/harness.sh"
      provides: "쉘 안전망"
      contains: "trap 'stty sane' EXIT"
    - path: "ui-ink/src/__tests__/protocol.test.ts"
      provides: "parseServerMsg 단위 테스트"
    - path: "ui-ink/src/__tests__/store.test.ts"
      provides: "store reducer 단위 테스트"
    - path: "ui-ink/src/__tests__/dispatch.test.ts"
      provides: "dispatch exhaustive switch 단위 테스트"
    - path: "ui-ink/src/__tests__/tty-guard.test.ts"
      provides: "TTY 가드 단위 테스트"
  key_links:
    - from: "ui-ink/src/index.tsx"
      to: "ui-ink/src/App.tsx"
      via: "render(<App/>, {patchConsole: false})"
      pattern: "patchConsole"
    - from: "ui-ink/harness.sh"
      to: "ui-ink/src/index.tsx"
      via: "bun run src/index.tsx"
      pattern: "stty sane"
---

<objective>
하드닝(TTY 가드, 시그널 핸들러, Ink 옵션, 쉘 안전망)을 완성하고, Plan A/B 에서 구축한 의존성+아키텍처를 App.tsx 에 연결해 end-to-end 스모크가 통과하는 상태를 만든다.

Purpose: 크래시 시 터미널 raw mode 가 복원되지 않으면 외부 사용자가 "망가진 도구" 로 인식한다. 이 plan 은 그 위험을 전부 봉쇄하고, Phase 2+ 빌드가 시작될 수 있는 green 상태를 확인한다.
Output: 하드닝된 index.tsx, 리팩터된 App.tsx, harness.sh, vitest 단위 테스트 4종
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/johyeonchang/harness/.planning/PROJECT.md
@/Users/johyeonchang/harness/.planning/ROADMAP.md
@/Users/johyeonchang/harness/.planning/research/PITFALLS.md
@/Users/johyeonchang/harness/CLAUDE.md

<interfaces>
<!-- Plan B 에서 생성된 타입/함수들 — 이 plan 에서 임포트 기준 -->
from src/protocol.ts:
  export type ServerMsg
  export type ClientMsg
  export function assertNever(x: never): never

from src/store/index.ts:
  export {useMessagesStore} from './messages.js'
  export {useInputStore} from './input.js'
  export {useStatusStore} from './status.js'
  export {useRoomStore} from './room.js'
  export {useConfirmStore} from './confirm.js'

from src/ws/client.ts:
  export class HarnessClient
  export interface ConnectOptions { url: string; token: string; room?: string }

from src/ws/parse.ts:
  export function parseServerMsg(raw: string): ServerMsg | null

from src/ws/dispatch.ts:
  export function dispatch(msg: ServerMsg): void

<!-- 현재 스켈레톤 (교체 대상) -->
기존 src/index.tsx — render(<App />) 만 있음, TTY 가드 없음
기존 src/App.tsx — ink@5 + ink-text-input + useState<WebSocket> + index key(key={i}) 패턴
기존 src/store.ts — 단일 파일, Plan B 로 분리됨 → App.tsx 교체 후 삭제
기존 src/ws.ts — on_token/on_tool 패턴 → Plan B 로 교체됨 → 삭제 대상
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task C-1: index.tsx 하드닝 + App.tsx 리팩터 (구 store.ts/ws.ts 삭제)</name>
  <files>
    ui-ink/src/index.tsx,
    ui-ink/src/App.tsx,
    ui-ink/harness.sh
  </files>
  <read_first>
    - /Users/johyeonchang/harness/ui-ink/src/index.tsx (현재 내용 — 교체 대상)
    - /Users/johyeonchang/harness/ui-ink/src/App.tsx (현재 내용 — 교체 대상: ink-text-input, useState<WebSocket>, index key 제거)
    - /Users/johyeonchang/harness/ui-ink/src/store.ts (현재 내용 — 삭제 대상 확인)
    - /Users/johyeonchang/harness/ui-ink/src/ws.ts (현재 내용 — 삭제 대상 확인)
    - /Users/johyeonchang/harness/.planning/research/PITFALLS.md (Pitfall 1, 3, 19 — 하드닝 처방 확인)
  </read_first>
  <action>
세 파일을 생성/교체하고, 기존 store.ts / ws.ts 를 삭제한다.

---

**1) ui-ink/src/index.tsx** — TTY 가드 + 시그널 핸들러 + render 진입점:

```tsx
// harness ui-ink 진입점 (FND-12, FND-13, FND-14)
// TTY 가드, 시그널 핸들러, patchConsole: false
import React from 'react'
import {render} from 'ink'
import {App} from './App.js'

// TTY 가드 — non-TTY 환경(파이프, CI)이거나 argv 에 질문이 있으면 one-shot 분기 (FND-12)
const isInteractive =
  process.stdin.isTTY === true &&
  typeof process.stdin.setRawMode === 'function'

// 시그널/예외 클린업 헬퍼 (FND-13)
function cleanup(code = 1): never {
  try {
    // 커서 복원
    process.stdout.write('\x1b[?25h')
    // raw mode 해제
    if (typeof process.stdin.setRawMode === 'function') {
      process.stdin.setRawMode(false)
    }
    // stdin 일시 정지
    process.stdin.pause()
  } catch {
    // cleanup 자체의 에러는 무시 — 진단 루프 방지
  }
  process.exit(code)
}

process.on('uncaughtException', (err) => {
  process.stderr.write(`[harness] uncaughtException: ${err.message}\n`)
  cleanup(1)
})

process.on('unhandledRejection', (reason) => {
  process.stderr.write(`[harness] unhandledRejection: ${reason}\n`)
  cleanup(1)
})

process.on('SIGHUP',  () => cleanup(0))
process.on('SIGTERM', () => cleanup(0))
// SIGINT: Ink 가 기본 처리하므로 추가 핸들러는 등록하지 않음
// (등록 시 이중 핸들러로 종료 안 되는 케이스 발생)

if (!isInteractive) {
  // One-shot 경로 (FND-12) — Phase 3 에서 실제 WS 연결 + stdout 출력으로 확장
  const query = process.argv[2]
  if (query) {
    process.stdout.write(`[one-shot] ${query}\n`)
  } else {
    process.stderr.write('[harness] non-TTY 환경. HARNESS_URL / HARNESS_TOKEN 으로 연결하세요.\n')
  }
  process.exit(0)
}

// Ink render — patchConsole: false (FND-14)
// alternate screen 비활성: 별도 옵션 없이 기본 Ink 는 inline 렌더
render(<App />, {patchConsole: false})
```

---

**2) ui-ink/src/App.tsx** — Plan B 슬라이스 임포트 + 구 패턴 제거:

```tsx
// App 컴포넌트 — Phase 1 스모크용 최소 구현
// ink-text-input 제거 / useState<WebSocket> 제거 / index key 제거 (CLAUDE.md)
import React, {useEffect, useRef} from 'react'
import {Box, Text, useApp, useInput} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from './store/messages.js'
import {useStatusStore} from './store/status.js'
import {useInputStore} from './store/input.js'
import {HarnessClient} from './ws/client.js'

// 스피너 프레임 (busy 상태 표시용 — Phase 2 에서 ink-spinner 로 교체)
const SPIN = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

export const App: React.FC = () => {
  const {exit} = useApp()

  // 슬라이스 선택자 — useShallow 로 필요한 필드만 구독 (FND-06, CLAUDE.md)
  const messages = useMessagesStore(useShallow((s) => s.messages))
  const {buffer, setBuffer, clearBuffer} = useInputStore(useShallow((s) => ({
    buffer: s.buffer,
    setBuffer: s.setBuffer,
    clearBuffer: s.clearBuffer,
  })))
  const {connected, busy} = useStatusStore(useShallow((s) => ({
    connected: s.connected,
    busy: s.busy,
  })))

  // WS 클라이언트 ref (useState 아님 — 전체 리렌더 방지)
  const clientRef = useRef<HarnessClient | null>(null)
  const spinRef = useRef(0)

  // WS 연결 초기화
  useEffect(() => {
    const url = process.env['HARNESS_URL']
    const token = process.env['HARNESS_TOKEN']
    if (url && token) {
      const client = new HarnessClient({
        url,
        token,
        room: process.env['HARNESS_ROOM'],
      })
      client.connect()
      clientRef.current = client
      return () => {
        client.close()
        clientRef.current = null
      }
    }
  }, [])

  // 입력 처리 — useInput 으로 키 이벤트 구독
  useInput((ch, key) => {
    if (key.ctrl && ch === 'c') {
      exit()
      return
    }
    if (key.return) {
      const text = buffer.trim()
      clearBuffer()
      if (!text) return
      useMessagesStore.getState().appendUserMessage(text)
      const client = clientRef.current
      if (client) {
        client.send({type: 'input', text})
      } else {
        useMessagesStore.getState().appendSystemMessage(
          '(연결 안 됨 — HARNESS_URL / HARNESS_TOKEN 필요)'
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

  // 스피너 프레임 회전 (단순 카운터 — Phase 2 에서 ink-spinner 로 교체)
  const spinFrame = busy ? SPIN[spinRef.current++ % SPIN.length] : ' '

  return (
    <Box flexDirection='column'>
      {/* 메시지 목록 — id 를 React key 로 사용 (FND-08, CLAUDE.md index key 금지) */}
      <Box flexDirection='column'>
        {messages.map((m) => (
          <Box key={m.id} marginBottom={0}>
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
          </Box>
        ))}
      </Box>

      {/* 구분선 */}
      <Text dimColor>{'─'.repeat(40)}</Text>

      {/* 입력 행 — ink-text-input 제거, 자체 buffer (FND-01 ink-text-input 제거) */}
      <Box>
        <Text color='cyan' bold>❯ </Text>
        <Text>{buffer}</Text>
        <Text color='cyan'>▌</Text>
      </Box>

      {/* 구분선 */}
      <Text dimColor>{'─'.repeat(40)}</Text>

      {/* 상태 표시줄 */}
      <Box>
        {busy && <Text color='cyan'>{spinFrame + ' '}</Text>}
        <Text color={connected ? 'green' : 'red'}>
          {connected ? '● connected' : '○ disconnected'}
        </Text>
      </Box>
    </Box>
  )
}
```

주의:
- `import TextInput from 'ink-text-input'` 없음 (FND-01)
- `useState<WebSocket>` 없음 → `useRef<HarnessClient>` 사용
- `messages.map((m, i) => key={i})` 패턴 없음 → `key={m.id}` 사용 (FND-08)
- `useStore()` 전체 구독 없음 → `useShallow` + 슬라이스별 구독 (CLAUDE.md)
- `<div>` / `<span>` JSX 없음 (CLAUDE.md)
- `process.stdout.write` / `console.log` 없음 (CLAUDE.md)

---

**3) ui-ink/harness.sh** — 쉘 진입 스크립트 (FND-15):

```bash
#!/usr/bin/env bash
# harness 쉘 진입 스크립트 — 터미널 raw mode 안전망 (FND-15)
# crash 시 stty sane 으로 터미널 복구

# 쉘 종료 시(정상/비정상 모두) 터미널 상태 복원
trap 'stty sane 2>/dev/null || true' EXIT

# ui-ink 디렉토리가 스크립트 위치 기준
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bun run "$SCRIPT_DIR/src/index.tsx" "$@"
```

스크립트를 실행 가능하게 설정:
```bash
chmod +x /Users/johyeonchang/harness/ui-ink/harness.sh
```

---

**4) 기존 파일 삭제:**

```bash
rm /Users/johyeonchang/harness/ui-ink/src/store.ts
rm /Users/johyeonchang/harness/ui-ink/src/ws.ts
```

새 App.tsx 가 `./store/messages.js` 등 새 경로를 임포트하므로 기존 단일 파일들은 더 이상 필요 없다.
  </action>
  <verify>
    <automated>cd /Users/johyeonchang/harness/ui-ink && grep 'patchConsole: false' src/index.tsx && grep "trap 'stty sane'" harness.sh && ! test -f src/store.ts && ! test -f src/ws.ts && ! grep 'ink-text-input' src/App.tsx && grep 'key={m.id}' src/App.tsx && echo "OK"</automated>
  </verify>
  <acceptance_criteria>
    - src/index.tsx 에 `patchConsole: false` 포함
    - src/index.tsx 에 `process.on('uncaughtException'` 포함
    - src/index.tsx 에 `process.on('SIGHUP'` 포함
    - src/index.tsx 에 `setRawMode(false)` 또는 `setRawMode` 참조 포함
    - src/index.tsx 에 `process.stdin.isTTY` TTY 가드 포함
    - src/App.tsx 에 `ink-text-input` import 없음
    - src/App.tsx 에 `useState<WebSocket>` 없음 (useRef 사용)
    - src/App.tsx 에 `key={m.id}` 패턴 포함 (index key 아님)
    - src/App.tsx 에 `useShallow` 사용
    - src/App.tsx 에 `<div>` `<span>` JSX 없음
    - harness.sh 에 `trap 'stty sane'` 포함
    - harness.sh 에 `EXIT` 트랩 포함
    - src/store.ts 파일 없음 (삭제됨)
    - src/ws.ts 파일 없음 (삭제됨)
  </acceptance_criteria>
  <done>index.tsx 하드닝 완료, App.tsx 리팩터 완료, 구 파일 삭제, harness.sh 생성</done>
</task>

<task type="auto" tdd="true">
  <name>Task C-2: vitest 단위 테스트 4종 작성 + tsc / smoke 검증</name>
  <files>
    ui-ink/src/__tests__/protocol.test.ts,
    ui-ink/src/__tests__/store.test.ts,
    ui-ink/src/__tests__/dispatch.test.ts,
    ui-ink/src/__tests__/tty-guard.test.ts
  </files>
  <read_first>
    - /Users/johyeonchang/harness/ui-ink/src/protocol.ts (parseServerMsg 입력/출력 파악)
    - /Users/johyeonchang/harness/ui-ink/src/ws/parse.ts (parseServerMsg 구현 확인)
    - /Users/johyeonchang/harness/ui-ink/src/ws/dispatch.ts (dispatch 함수 동작 확인)
    - /Users/johyeonchang/harness/ui-ink/src/store/messages.ts (appendToken, agentStart, agentEnd 확인)
    - /Users/johyeonchang/harness/ui-ink/src/index.tsx (TTY 가드 로직 확인)
    - /Users/johyeonchang/harness/.planning/ROADMAP.md (Phase 1 success criteria 확인)
  </read_first>
  <behavior>
    - protocol.test.ts:
      - parseServerMsg('{"type":"token","text":"hello"}') → TokenMsg 객체 반환
      - parseServerMsg('{"type":"agent_end"}') → AgentEndMsg 반환
      - parseServerMsg('{invalid json') → null 반환
      - parseServerMsg('{"type":"error","text":"oops"}') → ErrorMsg { type:'error', text:'oops' } (text 필드)
      - parseServerMsg('{"type":"unknown_future_type"}') → 파싱은 되지만 타입 가드 없이 반환

    - store.test.ts:
      - agentStart() 호출 → messages 에 streaming:true assistant 메시지 추가
      - appendToken('hello') 호출 후 appendToken(' world') → 두 번의 push 아닌 단일 메시지 content='hello world'
      - agentEnd() 호출 → 마지막 assistant 메시지 streaming:false
      - 각 메시지에 id 필드가 string 타입이며 중복 없음

    - dispatch.test.ts:
      - dispatch({type:'token', text:'hi'}) → useMessagesStore messages[0].content === 'hi' 포함
      - dispatch({type:'agent_start'}) → useStatusStore.busy === true
      - dispatch({type:'agent_end'}) → useStatusStore.busy === false
      - dispatch({type:'error', text:'fail'}) → messages 에 '오류: fail' 포함
      - exhaustive switch: ServerMsg 의 모든 타입을 dispatch 가 처리함을 보증 (타입 레벨에서 assertNever 가 컴파일 시 탐지)

    - tty-guard.test.ts:
      - process.stdin.isTTY === undefined 인 경우 isInteractive === false 확인
      - process.stdin.isTTY === false 인 경우 isInteractive === false 확인
      - process.stdin.isTTY === true + setRawMode 함수 존재 → isInteractive === true
  </behavior>
  <action>
`__tests__` 디렉토리를 생성하고 4개 테스트 파일을 작성한다.

**주의사항:**
- vitest@4 import: `import {describe, it, expect, beforeEach, vi} from 'vitest'`
- 각 테스트 beforeEach 에서 store 를 초기 상태로 리셋한다 (Zustand store 상태 오염 방지):
  ```ts
  beforeEach(() => {
    useMessagesStore.setState({messages: []})
    useStatusStore.setState({busy: false, connected: false})
  })
  ```
- `dispatch` 함수는 `useStore.getState()` 를 모듈 레벨에서 호출하므로 vi.mock 없이 실제 store 를 사용해 테스트 가능.
- tty-guard.test.ts 는 index.tsx 의 TTY 가드 로직을 **함수로 추출**해 테스트할 수 없는 경우, 로직 자체를 별도 `src/tty-guard.ts` 유틸로 추출하고 그것을 테스트한다:
  ```ts
  // src/tty-guard.ts
  export function isInteractiveTTY(stdin: NodeJS.ReadStream): boolean {
    return stdin.isTTY === true && typeof stdin.setRawMode === 'function'
  }
  ```
  index.tsx 에서 이 함수를 import 해 사용하도록 변경.
- 테스트 완료 후 반드시 실행:
  ```bash
  cd /Users/johyeonchang/harness/ui-ink && bun run typecheck && bun test
  ```
  (`bun test` 는 vitest 와 다를 수 있으므로 `bun run test` 로도 시도)

**end-to-end smoke 검증 (FND-16):**
```bash
# TTY 가드 one-shot 경로 (non-TTY)
echo 'hello' | bun run /Users/johyeonchang/harness/ui-ink/src/index.tsx
# → crash 없이 종료 (exit code 0 또는 안내 메시지)

# alternate screen escape 없는지 CI 가드
cd /Users/johyeonchang/harness/ui-ink && bash scripts/ci-no-escape.sh
```

HARNESS_URL + HARNESS_TOKEN 환경변수가 없는 환경에서 전체 인터랙티브 스모크 테스트는 사람이 수행해야 하므로 자동화 제외.
  </action>
  <verify>
    <automated>cd /Users/johyeonchang/harness/ui-ink && bun run typecheck && bun run test 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - src/__tests__/ 디렉토리에 protocol.test.ts, store.test.ts, dispatch.test.ts, tty-guard.test.ts 4개 파일 존재
    - `bun run typecheck` (tsc --noEmit) exit code 0
    - `bun run test` vitest 결과 전체 PASS (0 failed)
    - protocol.test.ts 에 parseServerMsg 테스트 케이스 최소 4개 (정상 token, 정상 agent_end, invalid JSON, error.text 필드)
    - store.test.ts 에 appendToken in-place 테스트 (토큰 두 번 → 메시지 1개 content 누적)
    - dispatch.test.ts 에 agent_start → busy:true, agent_end → busy:false 테스트 포함
    - tty-guard.test.ts 에 isTTY:undefined → isInteractive:false 케이스 포함
    - `echo 'x' | bun run src/index.tsx` → exit code 0 (crash 없음)
    - `bash scripts/ci-no-escape.sh` → "OK" 출력
  </acceptance_criteria>
  <done>vitest 4개 테스트 파일 생성, tsc --noEmit green, bun run test PASS, one-shot 경로 동작 확인</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| process.stdin → Ink useInput | raw mode 입력이 앱에 전달되는 경계 — cleanup 필수 |
| 시그널 핸들러 → process.exit | SIGHUP/SIGTERM 수신 시 cleanup 완료 후 종료 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01C-01 | Elevation of Privilege | raw mode 미복원 | mitigate | uncaughtException + SIGHUP + SIGTERM 핸들러에서 setRawMode(false) + stdin.pause(). harness.sh 의 `trap 'stty sane' EXIT` 쉘 레벨 안전망 이중 적용 |
| T-01C-02 | Denial of Service | non-TTY 환경에서 render() 호출 | mitigate | TTY 가드로 isInteractiveTTY false 이면 render() 를 호출하지 않고 종료 (Pitfall 19 방지) |
| T-01C-03 | Information Disclosure | process.stderr.write 로 내부 에러 노출 | accept | 로컬 3인 환경, 디버깅용 메시지. 민감 정보(토큰) 는 메시지에 포함하지 않음 |
| T-01C-04 | Tampering | vitest 테스트 우회 | accept | 테스트는 개발 환경 전용, 배포 경로 없음. CI matrix 는 Phase 4 에서 추가 |
</threat_model>

<verification>
```bash
# 1. patchConsole: false 확인
grep 'patchConsole: false' /Users/johyeonchang/harness/ui-ink/src/index.tsx

# 2. 시그널 핸들러 확인
grep 'uncaughtException\|unhandledRejection\|SIGHUP\|SIGTERM' /Users/johyeonchang/harness/ui-ink/src/index.tsx

# 3. TTY 가드 확인
grep 'isTTY' /Users/johyeonchang/harness/ui-ink/src/index.tsx

# 4. harness.sh 확인
grep "trap 'stty sane'" /Users/johyeonchang/harness/ui-ink/harness.sh

# 5. 구 파일 삭제 확인
! test -f /Users/johyeonchang/harness/ui-ink/src/store.ts
! test -f /Users/johyeonchang/harness/ui-ink/src/ws.ts

# 6. index key 금지 확인
! grep 'key={i}' /Users/johyeonchang/harness/ui-ink/src/App.tsx

# 7. tsc + vitest
cd /Users/johyeonchang/harness/ui-ink && bun run typecheck && bun run test

# 8. non-TTY 경로
echo 'x' | bun run /Users/johyeonchang/harness/ui-ink/src/index.tsx

# 9. CI escape 가드
cd /Users/johyeonchang/harness/ui-ink && bash scripts/ci-no-escape.sh
```
</verification>

<success_criteria>
Phase 1 exit criteria 전부 통과:
1. `bun run typecheck` green — tsc --noEmit exit 0
2. `bun run test` green — vitest PASS (parseServerMsg / store reducers / dispatch / TTY 가드)
3. `bash scripts/ci-no-escape.sh` → "OK" (alternate screen 이스케이프 0건)
4. `echo 'x' | bun run src/index.tsx` → crash 없이 종료 (exit 0)
5. src/App.tsx 에 key={m.id} 사용, ink-text-input 없음, useShallow 적용
6. harness.sh 에 trap 'stty sane' EXIT 포함
7. on_token / on_tool / error.message 가 ui-ink/src/ 전체에서 0건
</success_criteria>

<output>
완료 후 `/Users/johyeonchang/harness/.planning/phases/01-foundation/01-C-SUMMARY.md` 생성.
</output>
