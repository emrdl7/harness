# Phase 4: Testing + Docs + External Beta — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 5 (new/modified)
**Analogs found:** 4 / 5 (CI yml 은 레포 내 analog 없음 — 외부 패턴 사용)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `ui-ink/src/__tests__/integration.*.test.ts` | test | request-response + event-driven | `ui-ink/src/__tests__/ws-backoff.test.ts` | exact |
| `.github/workflows/ci.yml` | config | batch | 없음 (신규) | no-analog |
| `CLIENT_SETUP.md` | config (doc) | — | 현재 `CLIENT_SETUP.md` (재작성 대상) | rewrite |
| `PROTOCOL.md` | config (doc) | — | `ui-ink/src/protocol.ts` (타입 소스) | partial |
| `PITFALLS 체크리스트` | config (doc) | — | `.planning/research/PITFALLS.md` | partial |

---

## Pattern Assignments

### `ui-ink/src/__tests__/integration.*.test.ts` (test, event-driven + request-response)

**Primary analog:** `ui-ink/src/__tests__/ws-backoff.test.ts`

**특이사항:** 통합 테스트는 `vi.mock('ws', ...)` 대신 실제 `ws` 라이브러리로 in-process WS 서버를 기동한다 (D-01). 아래 구조 패턴을 따르되 mock 전략만 교체.

**Import + describe 패턴** (`ws-backoff.test.ts` lines 1-3):
```typescript
// integration.<시나리오명>.test.ts — <REQ-ID> 통합 검증
import {describe, it, expect, beforeAll, afterAll, beforeEach} from 'vitest'
import WebSocket from 'ws'
import {WebSocketServer} from 'ws'
import {HarnessClient} from '../ws/client.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'
```

**Fake WS 서버 lifecycle 패턴** (D-01, D-03 — ws-backoff.test.ts 의 beforeEach 패턴을 beforeAll 로 격상):
```typescript
// 랜덤 포트 Fake WS 서버 — D-03: 포트 고정 없음
let fakeServer: WebSocketServer
let serverUrl: string

beforeAll(async () => {
  fakeServer = new WebSocketServer({port: 0})  // port:0 → OS가 빈 포트 할당
  const port = (fakeServer.address() as {port: number}).port
  serverUrl = `ws://127.0.0.1:${port}`
})

afterAll(async () => {
  await new Promise<void>((resolve) => fakeServer.close(() => resolve()))
})
```

**Store reset 패턴** (`dispatch.test.ts` lines 11-15, `ws-backoff.test.ts` lines 96-100):
```typescript
beforeEach(() => {
  // 각 테스트 전 모든 store 초기화
  useMessagesStore.setState({completedMessages: [], activeMessage: null})
  useStatusStore.setState({busy: false, connected: false})
  useRoomStore.setState({
    roomName: '', members: [], activeInputFrom: null, activeIsSelf: true,
    busy: false, wsState: 'connected', reconnectAttempt: 0, lastEventId: null,
  })
  useConfirmStore.setState({mode: 'none', payload: {}})
})
```

**서버→클라 메시지 주입 패턴** (Fake 서버가 JSON 전송, 클라 dispatch 결과를 store에서 검증):
```typescript
it('시나리오 설명 (REQ-ID)', async () => {
  // 1) 서버 측: 연결 수신 대기
  const connectionP = new Promise<WebSocket>((resolve) => {
    fakeServer.once('connection', (ws) => resolve(ws))
  })
  // 2) 클라이언트 연결
  const client = new HarnessClient({url: serverUrl, token: 'test-token'})
  client.connect()
  const serverWs = await connectionP
  // 3) 서버가 메시지 주입
  serverWs.send(JSON.stringify({type: 'agent_start', from_self: true}))
  // 4) 비동기 dispatch 완료 대기 — setImmediate 또는 짧은 await
  await new Promise<void>((resolve) => setTimeout(resolve, 10))
  // 5) store 상태 검증
  expect(useStatusStore.getState().busy).toBe(true)
  // 6) 정리
  client.close()
})
```

**CR-01 버그 자동 발견 시나리오 패턴** (CONTEXT.md §Specific Ideas):
```typescript
it('confirm_write accept 응답 — CR-01: accept 필드가 서버에 도달해야 한다', async () => {
  // ... 연결 수립 ...
  // 서버 → 클라: confirm_write 트리거
  serverWs.send(JSON.stringify({type: 'confirm_write', path: '/tmp/test.txt'}))
  await new Promise<void>((r) => setTimeout(r, 10))
  // 클라 → 서버: y 입력 시 accept:true 전송 검증
  const received = await new Promise<string>((resolve) => {
    serverWs.once('message', (data) => resolve(data.toString()))
    // useConfirmStore 의 resolve 호출로 응답 전송
    useConfirmStore.getState().resolve(true)
  })
  const msg = JSON.parse(received)
  // CR-01: 서버는 'accept' 필드 기대 — 'result' 가 아님
  expect(msg.accept).toBe(true)
  expect(msg.result).toBeUndefined()  // 이 테스트는 CR-01 수정 전 실패해야 정상
})
```

**스냅샷 테스트 패턴** (`store.messages.snapshot.test.ts` 스타일, TST-03):
```typescript
// snapshot.test.ts 패턴 — ink-testing-library render() 출력 기반
import {render} from 'ink-testing-library'
import React from 'react'

it('500 토큰 스트리밍 스냅샷', () => {
  // 500 토큰 상태 세팅
  useMessagesStore.setState({
    completedMessages: [],
    activeMessage: {id: 'a1', role: 'assistant', content: 'x'.repeat(500), streaming: true},
  })
  const {lastFrame, unmount} = render(<App />)
  expect(lastFrame()).toMatchSnapshot()
  unmount()
})
```

---

### `.github/workflows/ci.yml` (config, batch)

**Analog:** 없음 (레포 내 기존 CI 파일 없음)

**No-analog 이유:** 레포에 `.github/` 디렉토리 자체가 없음. `ui-ink/scripts/ci-no-escape.sh` 와 `ui-ink/scripts/guard-forbidden.sh` 가 실제로 실행할 명령 소스다.

**`ui-ink/package.json` scripts (lines 6-13) — CI yml 에서 호출할 커맨드 소스:**
```json
{
  "typecheck": "tsc --noEmit",
  "lint": "eslint src --max-warnings=0",
  "test": "vitest run",
  "ci:no-escape": "bash scripts/ci-no-escape.sh",
  "guard": "bash scripts/guard-forbidden.sh",
  "ci": "bun run typecheck && bun run test && bun run guard"
}
```

**D-04/D-05 matrix 구조 (외부 GitHub Actions 표준 패턴):**
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ui-ink:
    name: ui-ink (${{ matrix.os }} / ${{ matrix.runtime }})
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        runtime: [bun, node]
    steps:
      - uses: actions/checkout@v4
      - name: Setup Bun
        if: matrix.runtime == 'bun'
        uses: oven-sh/setup-bun@v2
        with:
          bun-version: latest
      - name: Setup Node 22
        if: matrix.runtime == 'node'
        uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Install deps (bun)
        if: matrix.runtime == 'bun'
        run: cd ui-ink && bun install --frozen-lockfile
      - name: Install deps (node)
        if: matrix.runtime == 'node'
        run: cd ui-ink && npm ci
      - name: typecheck
        run: cd ui-ink && bun run typecheck      # bun runtime에서만 tsc 실행
        if: matrix.runtime == 'bun'
      - name: vitest
        run: cd ui-ink && bun run test
        if: matrix.runtime == 'bun'
      - name: guard
        run: cd ui-ink && bun run guard
        if: matrix.runtime == 'bun'
      - name: ci:no-escape
        run: cd ui-ink && bun run ci:no-escape
        if: matrix.runtime == 'bun'

  python:
    name: Python pytest (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      - name: Install Python deps
        run: pip install -e ".[dev]" || pip install -r requirements.txt
      - name: pytest
        run: .venv/bin/python -m pytest -x --tb=short || python -m pytest -x --tb=short
```

**ci-no-escape.sh 핵심 패턴** (`ui-ink/scripts/ci-no-escape.sh` lines 10-24):
```bash
# alternate screen / mouse tracking escape 코드 grep 가드
RESULT=$(grep -rn $'\x1b\[\?1049\|\x1b\[\?1000\|\x1b\[\?1002\|\x1b\[\?1003\|\x1b\[\?1006' "$SRC_DIR" 2>/dev/null || true)
if [ -n "$RESULT" ]; then
  echo "오류: alternate screen 또는 mouse tracking escape 코드 발견"
  exit 1
fi
```

---

### `CLIENT_SETUP.md` (config/doc — 재작성)

**Analog:** 현재 `CLIENT_SETUP.md` (재작성 대상)

**현재 파일의 문제점** (lines 14-99 참조):
- Node.js / `npm install` / `ui/` 기준 구버전 명령어 — `bun` / `ui-ink/` 로 교체 필요
- 환경변수가 `HARNESS_HOST` + `HARNESS_PORT` 분리 — 신규는 `HARNESS_URL` 단일 변수
- 설명이 너무 많음 — D-08: 명령어만, "why" 생략

**D-08 준수 목표 구조 (명령어 위주, 설명 최소화):**
```markdown
# CLIENT_SETUP

## 사전 준비

서버 담당자로부터 받아야 하는 값:
- `HARNESS_URL` (예: `ws://123.45.67.89:7891`)
- `HARNESS_TOKEN`
- `HARNESS_ROOM` (선택)

## 설치

```bash
git clone https://github.com/emrdl7/harness
cd harness/ui-ink
bun install --frozen-lockfile
```

## 실행

```bash
HARNESS_URL=ws://서버IP:7891 \
HARNESS_TOKEN=토큰문자열 \
HARNESS_ROOM=팀룸이름 \
bun start
```

## 업데이트

```bash
git pull
cd ui-ink && bun install --frozen-lockfile
```
```

---

### `PROTOCOL.md` (config/doc — 신규)

**Analog (타입 소스):** `ui-ink/src/protocol.ts`

**D-09 준수 요건:** AI 에이전트 친화적, TypeScript interface 수준 타입 정의 + 필드 설명, 시퀀스 다이어그램 없음, 데이터 형상 중심.

**ServerMsg 타입 소스** (`ui-ink/src/protocol.ts` lines 1-78 — 26종 전체):

서버→클라 메시지 (lines 6-59):
```typescript
// 스트리밍
{ type: 'token';         text: string }
{ type: 'claude_token';  text: string }
// 에이전트 라이프사이클
{ type: 'agent_start';   from_self?: boolean }  // PEXT-01
{ type: 'agent_end' }
{ type: 'agent_cancelled' }                      // PEXT-05
{ type: 'claude_start' }
{ type: 'claude_end' }
// 툴
{ type: 'tool_start';    name: string; args: Record<string, unknown> }
{ type: 'tool_end';      name: string; result: string }
// 상태
{ type: 'error';         text: string }          // .text 사용, .message 아님
{ type: 'info';          text: string }
{ type: 'ready';         room: string }
{ type: 'state_snapshot'; working_dir: string; model: string; mode: string; turns: number; ctx_tokens?: number; messages?: unknown[] }
{ type: 'state';          working_dir: string; model: string; mode: string; turns: number; ctx_tokens?: number }
// Room
{ type: 'room_joined';   room: string; shared: boolean; subscribers: number; busy: boolean; members?: string[] }
{ type: 'room_member_joined'; user: string }
{ type: 'room_member_left';   user: string }
{ type: 'room_busy' }
// Confirm
{ type: 'confirm_write'; path: string; old_content?: string }
{ type: 'confirm_bash';  command: string }
{ type: 'cplan_confirm'; task: string }
// 기타
{ type: 'slash_result';  cmd: string; [key: string]: unknown }
{ type: 'queue';         position: number }
{ type: 'queue_ready' }
{ type: 'pong' }
{ type: 'quit' }
```

클라→서버 메시지 (lines 63-71):
```typescript
{ type: 'input';                  text: string }
{ type: 'confirm_write_response'; accept: boolean }  // CR-01: 'accept' 필드 (서버는 이를 expect)
{ type: 'confirm_bash_response';  accept: boolean }
{ type: 'slash';                  name: string; args?: string }
{ type: 'ping' }
{ type: 'cancel' }
```

**WS 연결 헤더 패턴** (`ui-ink/src/ws/client.ts` lines 34-44):
```typescript
// 연결 시 헤더
headers = {
  'x-harness-token': token,        // 필수
  'x-harness-room': room,          // 선택 — 공유 룸
  'x-resume-from': String(lastEventId),  // WSR-03: delta replay (lastEventId != null 시)
  'x-resume-session': resumeSession,     // SES-02: 세션 resume
}
```

---

### PITFALLS 체크리스트 (config/doc — 신규)

**Analog (내용 소스):** `.planning/research/PITFALLS.md` (17항목)

**TST-05 Claude 재량** (CONTEXT.md): 별도 파일 vs VERIFICATION.md 통합은 Claude 판단. 권장: Phase 4 VERIFICATION.md 에 "수동 체크리스트" 섹션으로 통합 (별도 파일 대신). 이유: 에이전트가 참조할 파일 수를 최소화.

**PITFALLS.md 17항목 식별** (`.planning/research/PITFALLS.md` 구조):
- Pitfall 1: Alternate screen 모드 실수로 활성화 (H)
- Pitfall 2: Terminal resize 시 stale line 잔존 (H)
- Pitfall 3: Raw mode 미복원으로 터미널 먹통 (H)
- Pitfall 4: Ink 재렌더가 전체 트리를 훑어 스트리밍 토큰에서 플리커 (H)
- Pitfall 5: stdout 에 직접 write 하는 코드와 Ink 의 이중 렌더 (H)
- Pitfall 6: `<Static>` 오용으로 과거 메시지 사라짐 / 영원히 사라지지 않음 (M)
- (이하 11항목 — PITFALLS.md offset 140+ 에서 확인 필요)

**체크리스트 항목 포맷 패턴** (구조 가이드):
```markdown
## 수동 체크리스트 (PITFALLS 17항목)

| # | 항목 | 심각도 | 확인 방법 | 상태 |
|---|------|--------|-----------|------|
| P1 | Alternate screen 미발생 | H | `bun run ci:no-escape` 통과 확인 | [ ] |
| P2 | resize 후 잔상 없음 | H | 터미널 폭 200→40→200 수동 조작 | [ ] |
| P3 | Raw mode 복원 | H | Ctrl+C 후 `stty -a` 에 `-icanon` 없음 | [ ] |
...
```

---

## Shared Patterns

### vitest 테스트 파일 공통 구조
**Source:** `ui-ink/src/__tests__/dispatch.test.ts` lines 1-16 + `ws-backoff.test.ts` lines 3-5
**Apply to:** 모든 신규 통합 테스트 파일

```typescript
// <설명> — <REQ-ID> 검증
import {describe, it, expect, beforeAll, afterAll, beforeEach, vi} from 'vitest'
// ... imports ...

describe('<테스트 대상>', () => {
  beforeEach(() => {
    // store 전체 초기화 — dispatch.test.ts 패턴
    useMessagesStore.setState({completedMessages: [], activeMessage: null})
    useStatusStore.setState({busy: false, connected: false})
    useRoomStore.setState({roomName: '', members: [], activeInputFrom: null, activeIsSelf: true, busy: false})
    useConfirmStore.setState({mode: 'none', payload: {}})
  })

  it('<시나리오> (<REQ-ID>)', async () => {
    // ...
  })
})
```

### 코딩 스타일 규칙 (CLAUDE.md)
**Apply to:** 모든 TypeScript 파일
- 들여쓰기: 2 spaces
- 따옴표: single quote
- 세미콜론: 없음
- 주석: 한국어

### CI 금지 패턴 가드
**Source:** `ui-ink/scripts/guard-forbidden.sh` + `ui-ink/scripts/ci-no-escape.sh`
**Apply to:** `.github/workflows/ci.yml`

`bun run guard` 가 검사하는 패턴:
- `process.stdout.write` (테스트 + index.tsx 제외)
- `console.log` (테스트 파일 제외)
- `from 'child_process'`
- `<div>`, `<span>` JSX 태그
- `\x1b[?1049h` (alternate screen)
- `\x1b[?1000h` (mouse tracking)

---

## No Analog Found

| File | Role | Data Flow | 이유 |
|------|------|-----------|------|
| `.github/workflows/ci.yml` | config | batch | 레포 내 GitHub Actions 파일 전무. `ui-ink/package.json` scripts 와 두 guard shell 스크립트가 실행 명령 소스. 외부 GitHub Actions 표준 패턴 사용. |

---

## Metadata

**Analog search scope:** `ui-ink/src/__tests__/`, `ui-ink/scripts/`, `ui-ink/package.json`, `ui-ink/src/protocol.ts`, `ui-ink/src/ws/client.ts`, `CLIENT_SETUP.md`, `.planning/research/PITFALLS.md`
**Files scanned:** 13
**Pattern extraction date:** 2026-04-24
