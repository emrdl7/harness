# Phase 01: rpc-skeleton — Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 9 (신규 3 TS + 수정 3 TS + 수정 2 Python + 신규 1 vitest)
**Analogs found:** 9 / 9

## File Classification

| 신규/수정 파일 | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `ui-ink/src/tools/registry.ts` (신규) | tool-runtime registry | request-response (RPC dispatch) | `ui-ink/src/components/tools/index.ts` (TOOL_REGISTRY dict-lookup) | role-match (실행 vs 렌더 — 같은 dict 패턴, 다른 목적) |
| `ui-ink/src/tools/fs.ts` (신규) | client-side tool impl | file-I/O (async) | `tools/fs.py:read_file` (line 55-79) | exact (Python → TS 동등 변환) |
| `ui-ink/src/protocol.ts` (수정) | message type schema | request-response (discriminated union 추가) | 본인 — 기존 `ConfirmWriteMsg`/`ConfirmWriteResponse` 페어 (line 17, 70) | exact (자기 자신의 기존 RPC 스타일 페어) |
| `ui-ink/src/ws/dispatch.ts` (수정) | WS message router | event-driven (switch routing) | 본인 — 기존 `case 'confirm_write'` (line 112-115), `case 'tool_start'` (line 65-69) | exact |
| `ui-ink/src/App.tsx` (수정 — tool runtime 배선) | client init/wiring | event-driven (lifecycle) | 본인 — 기존 `bindConfirmClient` 패턴 (line 75-80) | exact |
| `harness_server.py` (수정 — pending_calls + tool_result handler + rpc_call 콜백 주입) | WS dispatch + thread→async bridge | request-response | `harness_server.py:confirm_write` 클로저 (line 274-290) + `_dispatch_loop` `confirm_write_response` case (line 830-837) | exact (D-09 가 명시 — confirm bridge 그대로 응용) |
| `agent.py` (수정 — `CLIENT_SIDE_TOOLS` 분기) | tool dispatch | request-response | `agent.py:564` `fn = TOOL_MAP.get(fn_name)` 직전 가드 블록 (line 501-512: `confirm_write` 분기) | exact (같은 위치 같은 패턴) |
| `tools/fs.py:read_file` (삭제 only — Phase 1 끝) | — | — | — | N/A (deletion) |
| `tests/test_fs.py` read_file 케이스 (삭제 — Phase 1 끝) | — | — | — | N/A (deletion) |
| `ui-ink/test/tools-fs.test.ts` (신규 vitest) | unit test | file-I/O fixture | `tests/test_fs.py:TestReadWriteEdit` (line 56-83) — 동등 변환 + `ui-ink/src/__tests__/protocol.test.ts` 의 vitest 스타일 | role-match (pytest → vitest) |

---

## Pattern Assignments

### `harness_server.py` (수정) — `pending_calls` + `tool_result` 핸들러 + `rpc_call` 콜백

**Analog:** `harness_server.py` 자기 자신의 confirm bridge — D-09 가 명시한 reference.

**Imports / 클래스 필드 추가** — `Session` (line 160-178) 또는 `Room` (line 199-215) 에 한 필드. CONTEXT D-05 = ws 객체 scope 가 베스트 (BB-2 폐기 후에도 그대로). Phase 1 에선 `Session` 또는 새 `ws_state` dict 권장. 패턴 reference (Session 의 `_confirm_event` 필드):

```python
# harness_server.py:172-173 (현재 confirm 패턴)
self._confirm_event: asyncio.Event | None = None
self._confirm_result: bool = False
```

추가할 필드 (Phase 1 이 새로 도입 — ws scope 권장):

```python
# 신규: pending_calls — call_id → Future. 동일 ws 내 동시 호출 다중 가능 (D-07)
# ws scope (1ws=1session, BB-2 폐기 후에도 변경 0)
ws._pending_calls: dict[str, asyncio.Future] = {}  # WebSocket 객체에 attribute 부여
```

**Thread→async bridge 패턴** (line 274-290 — D-09 이 ground truth):

```python
def confirm_write(path: str, content: str | None = None) -> bool:
    event = asyncio.Event()
    state._confirm_event = event
    state._confirm_result = False
    asyncio.run_coroutine_threadsafe(
        send(ws, type='confirm_write', path=path,
             old_content=_read_existing_file(path)), loop  # PEXT-02
    )
    # 최대 60초 대기 (스레드에서 asyncio Event를 기다리는 우회)
    future = asyncio.run_coroutine_threadsafe(
        asyncio.wait_for(event.wait(), timeout=60), loop
    )
    try:
        future.result(timeout=61)
    except Exception:
        pass
    return state._confirm_result
```

**RPC 적용 변환** (이 패턴 그대로 응용):

```python
# run_agent 내부 클로저로 정의 (confirm_write 와 같은 layer — line 274 부근)
def rpc_call(name: str, args: dict, timeout: float = 30.0) -> dict:
    '''agent (sync 스레드) 가 호출. ws 로 tool_request 송신 후 tool_result 까지 wait.

    confirm_write 와 동일 패턴 — Event 대신 Future 사용 (결과값 같이 운반).
    '''
    call_id = uuid.uuid4().hex
    future: asyncio.Future = loop.create_future()
    ws._pending_calls[call_id] = future
    try:
        asyncio.run_coroutine_threadsafe(
            send(ws, type='tool_request', call_id=call_id, name=name, args=args), loop
        )
        wait_future = asyncio.run_coroutine_threadsafe(
            asyncio.wait_for(asyncio.shield(future), timeout=timeout), loop
        )
        return wait_future.result(timeout=timeout + 1)
    except asyncio.TimeoutError:
        return {'ok': False, 'error': f'tool_call timeout ({timeout}s)'}
    except asyncio.CancelledError:
        return {'ok': False, 'error': 'tool_call aborted (disconnect)'}
    finally:
        ws._pending_calls.pop(call_id, None)
```

**`_dispatch_loop` 에 `tool_result` case 추가** (analog: line 830-837 의 `confirm_write_response`):

```python
elif t == 'confirm_write_response':
    # DQ2: 입력 주체(active_input_from) ws만 confirm 가능.
    if ws is not room.active_input_from:
        continue
    state._confirm_result = msg.get('accept', msg.get('result', False))
    if state._confirm_event:
        state._confirm_event.set()
```

→ 적용:

```python
elif t == 'tool_result':
    # RPC-01: 클라가 보낸 도구 실행 결과를 pending future 에 주입
    call_id = msg.get('call_id')
    if not call_id:
        continue
    future = ws._pending_calls.get(call_id)
    if future is None or future.done():
        continue  # late/duplicate 은 silent drop
    if msg.get('ok'):
        future.set_result({'ok': True, **(msg.get('result') or {})})
    else:
        err = msg.get('error') or {'kind': 'unknown', 'message': 'no error payload'}
        future.set_result({'ok': False, 'error': err.get('message') if isinstance(err, dict) else str(err)})
```

**Disconnect cleanup** (D-12) — analog: `_run_session` finally 블록 (line ~990 부근, `room.subscribers.discard(ws)` 직후). pattern:

```python
# 신규: ws disconnect 시 pending 일괄 cancel
for call_id, fut in list(getattr(ws, '_pending_calls', {}).items()):
    if not fut.done():
        fut.cancel()
ws._pending_calls = {}
```

**`run_agent` 의 콜백 주입** (line 347-374 — `_run` 클로저):

```python
# 현재 (line 362-374)
_, state.messages = agent.run(
    user_input,
    session_messages=state.messages,
    working_dir=state.working_dir,
    profile=state.profile,
    ...
    on_tool=on_tool,
    confirm_write=confirm_write if state.profile.get('confirm_writes', True) else None,
    confirm_bash=confirm_bash if state.profile.get('confirm_bash', True) else None,
    hooks=state.profile.get('hooks', {}),
)
```

→ 적용 (`rpc_call=rpc_call` 추가):

```python
_, state.messages = agent.run(
    user_input,
    ...
    on_tool=on_tool,
    confirm_write=confirm_write if ... else None,
    confirm_bash=confirm_bash if ... else None,
    hooks=state.profile.get('hooks', {}),
    rpc_call=rpc_call,  # 신규: 클라 위임 도구의 진입점
)
```

---

### `agent.py` (수정) — `CLIENT_SIDE_TOOLS` 분기

**Analog:** `agent.py:501-512` — `fn_name in ('write_file', 'edit_file')` 가드 블록. 같은 위치, 같은 if-fallthrough 패턴.

**Existing pattern** (line 491-512):

```python
for tc in tool_calls:
    fn_name = tc['function']['name']
    args = tc['function'].get('arguments', {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}

    # 파일 쓰기/수정 확인
    if fn_name in ('write_file', 'edit_file') and confirm_write:
        _cw_content = args.get('content') if fn_name == 'write_file' else None
        if not confirm_write(args.get('path', '?'), _cw_content):
            denied_in_turn = True
            result = {'ok': False, 'error': '사용자가 취소했습니다'}
            if on_tool:
                on_tool(fn_name, args, result)
            session_messages.append({
                'role': 'tool',
                'content': json.dumps(result, ensure_ascii=False),
            })
            continue
```

**Adopt pattern — `CLIENT_SIDE_TOOLS` 분기** (D-08, D-10):

모듈 상단에 추가 (`MAX_TOOL_RESULT_CHARS` 부근):

```python
# RPC-02: 클라이언트 측에서 실행되는 도구 — Phase 1 = read_file 만
CLIENT_SIDE_TOOLS = {'read_file'}
```

`run()` signature 에 `rpc_call=None` 추가 (line 416-431 — `confirm_write/confirm_bash` 와 같은 layer):

```python
def run(
    user_input: str,
    session_messages: list = None,
    ...
    confirm_write=None,
    confirm_bash=None,
    on_unknown_tool=None,
    on_thought=None,
    on_thought_end=None,
    hooks: dict = None,
    rpc_call=None,  # RPC-02: 신규 — 클라 위임 진입점 (callable[(name, args, timeout?), dict])
) -> tuple[str, list]:
```

`fn = TOOL_MAP.get(fn_name)` (line 564) 직전에 분기 추가:

```python
# 기존 (line 560-569)
# shell 툴은 working_dir를 cwd로 자동 주입
if fn_name in ('run_command', 'run_python') and 'cwd' not in args:
    args = {**args, 'cwd': working_dir}

fn = TOOL_MAP.get(fn_name)
if fn:
    try:
        result = fn(**args)
    except TypeError as e:
        result = {'ok': False, 'error': f'인자 오류: {e}'}
```

→ 적용 (분기 삽입):

```python
# shell 툴은 working_dir를 cwd로 자동 주입
if fn_name in ('run_command', 'run_python') and 'cwd' not in args:
    args = {**args, 'cwd': working_dir}

# RPC-02: 클라 위임 도구 — rpc_call 콜백으로 ws→client→ws 라운드트립
if fn_name in CLIENT_SIDE_TOOLS:
    if rpc_call is None:
        result = {'ok': False, 'error': f'rpc_call 콜백 없음 — {fn_name} 은 클라 측 도구'}
    else:
        # path | file_path alias 정규화 (D-16)
        if fn_name == 'read_file' and 'path' not in args and 'file_path' in args:
            args = {**args, 'path': args.pop('file_path')}
        result = rpc_call(fn_name, args)
else:
    fn = TOOL_MAP.get(fn_name)
    if fn:
        try:
            result = fn(**args)
        except TypeError as e:
            result = {'ok': False, 'error': f'인자 오류: {e}'}
    else:
        result = {
            'ok': False,
            'error': f'툴 "{fn_name}"은 존재하지 않습니다. ...',
            '_unknown_tool': fn_name,
        }
        unknown_tool_count += 1
        if on_unknown_tool:
            on_unknown_tool(fn_name, args)
```

**Important:** `tools/__init__.py:TOOL_MAP['read_file']` 항목은 Phase 1 끝에서 `tools/fs.py:read_file` deletion 과 함께 제거 (D-18). Deletion 전까지 dual-stack — `CLIENT_SIDE_TOOLS` 분기가 먼저 잡혀서 클라 위임이 우선.

---

### `ui-ink/src/protocol.ts` (수정) — RPC 메시지 타입 추가

**Analog:** 자기 자신 — 기존 `ConfirmWriteMsg` (서버→클라, line 17) + `ConfirmWriteResponse` (클라→서버, line 70) 페어 패턴.

**Existing pattern** (line 17-18, 70-71):

```typescript
// 서버 → 클라 (line 17)
export interface ConfirmWriteMsg { type: 'confirm_write';       path: string; old_content?: string }
export interface ConfirmBashMsg  { type: 'confirm_bash';        command: string }
...
// 클라 → 서버 (line 70-71)
export interface ConfirmWriteResponse { type: 'confirm_write_response'; accept: boolean }
export interface ConfirmBashResponse  { type: 'confirm_bash_response';  accept: boolean }
```

**Adopt pattern** — D-01/D-02 schema:

```typescript
// 서버 → 클라 (RPC-01) — ConfirmWriteMsg 와 같은 layer 에 추가
export interface ToolRequestMsg {
  type: 'tool_request'
  call_id: string                       // uuid v4 (correlation)
  name: string                           // 'read_file' (Phase 1)
  args: Record<string, unknown>          // {path, offset?, limit?}
}

// 클라 → 서버 (RPC-01) — ConfirmWriteResponse 와 같은 layer 에 추가
export interface ToolResultMsg {
  type: 'tool_result'
  call_id: string
  ok: boolean
  result?: Record<string, unknown>       // ok=true 시
  error?: { kind: string; message: string }  // ok=false 시 (D-02)
}
```

**Discriminated union 갱신** (line 54-65, 77-79):

```typescript
// ServerMsg 에 ToolRequestMsg 추가
export type ServerMsg =
  | TokenMsg | ToolStartMsg | ToolEndMsg
  | ToolRequestMsg                       // RPC-01 추가
  | AgentStartMsg | AgentEndMsg | AgentCancelledMsg
  ...

// ClientMsg 에 ToolResultMsg 추가
export type ClientMsg =
  | InputMsg | ConfirmWriteResponse | ConfirmBashResponse | SlashMsg | PingMsg | CancelMsg
  | FileListRequestMsg
  | ToolResultMsg                        // RPC-01 추가
```

**Constraint:** discriminated union 의 모든 멤버는 `type` literal 을 가지고, dispatch.ts 가 `assertNever` exhaustive 가드 (line 252-254). 새 case 안 잡으면 컴파일 에러 — 누락 차단 메커니즘.

---

### `ui-ink/src/ws/dispatch.ts` (수정) — `tool_request` 핸들러

**Analog:** 자기 자신 — `case 'tool_start'` (line 65-69) 또는 `case 'confirm_write'` (line 112-115) 의 dict-lookup + side-effect 패턴.

**Existing pattern** — `case 'confirm_write'` (line 112-115):

```typescript
case 'confirm_write':
  // PEXT-02: old_content 전달 (diff 기반 UX용)
  confirm.setConfirm('confirm_write', {path: msg.path, oldContent: msg.old_content})
  break
```

**Adopt pattern** — `case 'tool_request'` 추가 (switch 본체에, `case 'tool_end'` 직후 권장):

```typescript
case 'tool_request': {
  // RPC-01: 서버가 클라 측 도구 실행 요청. registry 에서 핸들러 조회 → 실행 → tool_result 송신.
  // 동기 분기는 하지 않음 — async 라 dispatch() 자체는 Promise 무시 (fire-and-forget).
  // boundClient 는 store/confirm 의 bindConfirmClient 와 동일 런타임 주입 패턴.
  void runClientTool(msg.call_id, msg.name, msg.args)
  break
}
```

**런타임 주입 패턴** (analog: `bindConfirmClient` line 9-13 of `store/confirm.ts`):

```typescript
// store/confirm.ts:9-13
let boundClient: HarnessClient | null = null
export function bindConfirmClient(client: HarnessClient | null): void {
  boundClient = client
}
```

→ tool runtime 도 동일 패턴 — `tools/registry.ts` 가 `boundClient` 를 갖고, `App.tsx` 가 `bindToolClient(client)` 호출. dispatch.ts 는 `runClientTool` 만 import.

**Constraint:** `dispatch()` 는 async 가 아님 (synchronous return). Promise 는 `void` 캐스팅으로 명시 fire-and-forget — exhaustive switch 에 영향 없음.

---

### `ui-ink/src/tools/registry.ts` (신규) — tool runtime registry

**Analog:** `ui-ink/src/components/tools/index.ts` (TOOL_REGISTRY dict-lookup, line 20-30). 같은 dict + getter 패턴, 다만 *렌더 컴포넌트* 가 아닌 *실행 함수*.

**Existing pattern** (TOOL_REGISTRY):

```typescript
// ui-ink/src/components/tools/index.ts:20-34
export const TOOL_REGISTRY: Record<string, ToolBlockComponent> = {
  run_command: BashBlock,
  run_python:  BashBlock,
  read_file:   ReadFileBlock,
  write_file:  FileEditBlock,
  ...
}

export function getToolRenderer(name: string): ToolBlockComponent {
  return TOOL_REGISTRY[name] ?? DefaultToolBlock
}
```

**Adopt pattern** — 실행 registry:

```typescript
// ui-ink/src/tools/registry.ts (신규)
// RPC-02: 클라 측 도구 실행 registry. dispatch.ts 의 'tool_request' 가 진입.
// 새 도구 추가:
//   1. tools/<file>.ts 작성 — async (args) => Promise<ToolResult>
//   2. 아래 TOOL_RUNTIME 에 한 줄 추가
//   3. 끝 (dispatch.ts 변경 불필요)
import {readFile} from './fs.js'
import type {HarnessClient} from '../ws/client.js'
import type {ClientMsg} from '../protocol.js'

export type ToolResult =
  | { ok: true; [k: string]: unknown }
  | { ok: false; error: string }

export type ToolFn = (args: Record<string, unknown>) => Promise<ToolResult>

export const TOOL_RUNTIME: Record<string, ToolFn> = {
  read_file: readFile,
  // Phase 2 에서 write_file/edit_file/list_files/grep_search 추가
}

// store/confirm.ts:bindConfirmClient 와 동일 런타임 주입 패턴 (순환 의존 회피)
let boundClient: HarnessClient | null = null
export function bindToolClient(client: HarnessClient | null): void {
  boundClient = client
}

export async function runClientTool(
  call_id: string,
  name: string,
  args: Record<string, unknown>,
): Promise<void> {
  const fn = TOOL_RUNTIME[name]
  let response: ClientMsg
  if (!fn) {
    response = {
      type: 'tool_result',
      call_id,
      ok: false,
      error: { kind: 'unknown_tool', message: `클라 측 도구 미등록: ${name}` },
    }
  } else {
    try {
      const r = await fn(args)
      if (r.ok) {
        const {ok: _ok, ...rest} = r
        response = { type: 'tool_result', call_id, ok: true, result: rest }
      } else {
        response = {
          type: 'tool_result',
          call_id,
          ok: false,
          error: { kind: 'tool_error', message: r.error },
        }
      }
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e)
      response = {
        type: 'tool_result',
        call_id,
        ok: false,
        error: { kind: 'exception', message: m },
      }
    }
  }
  boundClient?.send(response)
}
```

**Naming:** `TOOL_RUNTIME` (실행) vs 기존 `TOOL_REGISTRY` (렌더) — 충돌 방지.

---

### `ui-ink/src/tools/fs.ts` (신규) — `read_file` (TS 동등)

**Analog:** `tools/fs.py:read_file` (line 55-79) — 시그니처 + 반환 형태 동등 (D-14, D-15, D-16).

**Existing Python pattern** (line 55-79):

```python
def read_file(path: str = None, file_path: str = None, offset: int = 1, limit: int = 0) -> dict:
    path = path or file_path
    '''offset: 시작 줄(1-based), limit: 읽을 줄 수(0=전체)'''
    ok, resolved = _resolve_path(path)
    if not ok:
        return {'ok': False, 'error': resolved}
    try:
        with open(resolved, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        total = len(lines)
        start = max(1, offset) - 1          # 0-based index
        end   = (start + limit) if limit > 0 else total
        end   = min(end, total)
        sliced = lines[start:end]
        # 줄 번호 prefix (cat -n 스타일)
        content = ''.join(f'{start + i + 1:4d}\t{l}' for i, l in enumerate(sliced))
        return {
            'ok': True,
            'content': content,
            'total_lines': total,
            'start_line': start + 1,
            'end_line': start + len(sliced),
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}
```

**Adopt pattern** (TS 동등 — D-15/D-16 alias 는 agent.py 에서 처리하므로 TS 는 `path` 만):

```typescript
// ui-ink/src/tools/fs.ts (신규)
// RPC-03 (Phase 1): read_file — Python tools/fs.py:read_file 와 동등 schema.
// alias 처리 안 함 (D-16: agent.py 가 file_path → path 정규화).
import {promises as fs} from 'node:fs'
import type {ToolResult} from './registry.js'

export interface ReadFileArgs {
  path: string
  offset?: number  // 1-based, 기본 1
  limit?: number   // 기본 0 = 전체
}

export async function readFile(rawArgs: Record<string, unknown>): Promise<ToolResult> {
  const path = typeof rawArgs.path === 'string' ? rawArgs.path : ''
  const offset = typeof rawArgs.offset === 'number' ? rawArgs.offset : 1
  const limit = typeof rawArgs.limit === 'number' ? rawArgs.limit : 0
  if (!path) {
    return { ok: false, error: 'path 누락' }
  }
  try {
    // bun/node — utf-8 읽기. 바이너리는 Phase 2 에서 결정 (CONTEXT specifics).
    const buf = await fs.readFile(path, 'utf-8')
    const lines = buf.split(/(?<=\n)/)  // keepends 동등 — 마지막 줄에 \n 없을 수 있음
    const total = lines.length
    const start = Math.max(1, offset) - 1
    const end = limit > 0 ? Math.min(start + limit, total) : total
    const sliced = lines.slice(start, end)
    // cat -n 스타일 — Python 의 f'{n:4d}\t{l}' 동등
    const content = sliced
      .map((l, i) => `${String(start + i + 1).padStart(4, ' ')}\t${l}`)
      .join('')
    return {
      ok: true,
      content,
      total_lines: total,
      start_line: start + 1,
      end_line: start + sliced.length,
    }
  } catch (e) {
    const m = e instanceof Error ? e.message : String(e)
    return { ok: false, error: m }
  }
}
```

**Schema constraints (D-14/D-15):**
- 성공 = `{ok:true, content, total_lines, start_line, end_line}` — Python 과 동일 키
- 실패 = `{ok:false, error: string}` — `error` 는 string (registry.ts 가 wrap 해서 `{kind, message}` 로 송출)
- 한국어 에러 메시지 (CONTEXT D-discretion: Python 측 한국어와 동일)

**Constraint:** 샌드박스 적용 안 함 (Phase 1) — 클라 측 도구는 사용자 자기 PC 라 격리 의미 약함. Phase 2 에서 working_dir 기반 상대 경로 정책 결정.

---

### `ui-ink/src/App.tsx` (수정) — tool runtime 배선

**Analog:** 자기 자신 — `bindConfirmClient(client)` 호출 (line 75-76, 78-79) + cleanup. 같은 lifecycle 패턴.

**Existing pattern** (line 65-83):

```typescript
useEffect(() => {
  if (!cfg) return
  const client = new HarnessClient({
    url: cfg.url,
    token: cfg.token,
    room: cfg.room ?? process.env['HARNESS_ROOM'],
    resumeSession: process.env['HARNESS_RESUME_SESSION'],
  })
  client.connect()
  clientRef.current = client
  bindConfirmClient(client)
  bindFilesClient(client)
  return () => {
    bindConfirmClient(null)
    bindFilesClient(null)
    client.close()
    clientRef.current = null
  }
}, [cfg])
```

**Adopt pattern** — `bindToolClient(client)` 한 줄 추가:

```typescript
import {bindToolClient} from './tools/registry.js'   // 상단 import 에 추가

// useEffect 내부
client.connect()
clientRef.current = client
bindConfirmClient(client)
bindFilesClient(client)
bindToolClient(client)                                // 신규 — RPC-01 송신용
return () => {
  bindConfirmClient(null)
  bindFilesClient(null)
  bindToolClient(null)                                // cleanup
  client.close()
  clientRef.current = null
}
```

---

### `ui-ink/test/tools-fs.test.ts` (신규 vitest)

**Analog 1 (테스트 케이스 매핑):** `tests/test_fs.py:TestReadWriteEdit` (line 56-83) — 5 케이스 동등 변환 (D-17).

**Analog 2 (vitest 스타일):** `ui-ink/src/__tests__/protocol.test.ts` — `describe`/`it`/`expect` 구조.

**Existing pytest pattern** (line 67-83):

```python
def test_read_offset_limit(self, tmp_path):
    path = tmp_path / 'multi.txt'
    path.write_text(''.join(f'line{i}\n' for i in range(10)))
    result = fs.read_file(str(path), offset=3, limit=2)
    assert result['ok'] is True
    assert result['start_line'] == 3
    assert result['end_line'] == 4
    assert 'line2' in result['content']
    assert 'line3' in result['content']
    assert 'line0' not in result['content']

def test_read_accepts_file_path_alias(self, tmp_path):
    '''profile/legacy 호환: file_path 인자도 받아야 함.'''
    path = tmp_path / 'a.txt'
    path.write_text('x')
    result = fs.read_file(file_path=str(path))
    assert result['ok'] is True
```

**Adopt pattern** (vitest + node:fs/promises tmp dir):

```typescript
// ui-ink/test/tools-fs.test.ts (신규) — D-17: 5 케이스
import {describe, it, expect, beforeEach, afterEach} from 'vitest'
import {promises as fs} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {readFile} from '../src/tools/fs.js'

describe('read_file (RPC-03)', () => {
  let dir: string

  beforeEach(async () => {
    dir = await fs.mkdtemp(join(tmpdir(), 'harness-fs-'))
  })
  afterEach(async () => {
    await fs.rm(dir, {recursive: true, force: true})
  })

  it('성공 — 전체 읽기 시 줄 번호 prefix + total_lines 반환', async () => {
    const p = join(dir, 'sample.txt')
    await fs.writeFile(p, 'hello\nworld\n')
    const r = await readFile({path: p})
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.total_lines).toBe(2)
      expect(r.content).toContain('hello')
      expect(r.content).toContain('world')
    }
  })

  it('성공 — offset/limit 분기 (Python test_read_offset_limit 동등)', async () => {
    const p = join(dir, 'multi.txt')
    const lines = Array.from({length: 10}, (_, i) => `line${i}\n`).join('')
    await fs.writeFile(p, lines)
    const r = await readFile({path: p, offset: 3, limit: 2})
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.start_line).toBe(3)
      expect(r.end_line).toBe(4)
      expect(r.content).toContain('line2')
      expect(r.content).toContain('line3')
      expect(r.content).not.toContain('line0')
    }
  })

  it('실패 — 존재하지 않는 파일은 ok=false', async () => {
    const r = await readFile({path: join(dir, 'nope.txt')})
    expect(r.ok).toBe(false)
  })

  it('실패 — 디렉토리는 ok=false (EISDIR)', async () => {
    const r = await readFile({path: dir})
    expect(r.ok).toBe(false)
  })

  it('대용량 offset — 파일 끝 너머 offset 도 안전 (sliced 빈 배열)', async () => {
    const p = join(dir, 'small.txt')
    await fs.writeFile(p, 'a\nb\n')
    const r = await readFile({path: p, offset: 100, limit: 10})
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.content).toBe('')
      expect(r.end_line).toBe(99)  // start_line - 1 (sliced 빈 배열)
    }
  })
})
```

**vitest 패턴 reference** (`ui-ink/src/__tests__/protocol.test.ts:1-12`):

```typescript
import {describe, it, expect} from 'vitest'
import {parseServerMsg} from '../ws/parse.js'

describe('parseServerMsg', () => {
  it('정상 token 메시지를 파싱해 TokenMsg 반환', () => {
    const result = parseServerMsg('{"type":"token","text":"hello"}')
    expect(result).not.toBeNull()
    expect(result?.type).toBe('token')
    expect((result as {type: string; text: string}).text).toBe('hello')
  })
  ...
})
```

**Constraint:** vitest 케이스 5건은 D-17 명시. symbolic link / 대용량 케이스는 mkdtemp 안에서 자유롭게 구성. mocking 전략은 Claude's discretion — 위 예시는 실제 fs 사용 (전형적 e2e-unit). pretest fixture 패턴은 `tests/test_fs.py:reset_sandbox` (autouse=True) 와 동등하게 `beforeEach`/`afterEach` 의 mkdtemp/rm.

---

## Shared Patterns

### Pattern 1: Thread→async bridge (sync agent ↔ async ws)

**Source:** `harness_server.py:274-290` (`confirm_write`), `run_agent` 의 `_run` (line 347-385).

**Apply to:** `harness_server.py` 의 신규 `rpc_call` 클로저.

**Mechanism:** `asyncio.run_coroutine_threadsafe(coro, loop)` + `concurrent.futures.Future.result(timeout)`. Future 자체는 asyncio.Future (loop.create_future()) — 송신/대기 분리.

```python
# 송신
asyncio.run_coroutine_threadsafe(send(ws, type=..., **payload), loop)
# 대기 (timeout)
wait_future = asyncio.run_coroutine_threadsafe(
    asyncio.wait_for(asyncio.shield(future), timeout=timeout), loop
)
result = wait_future.result(timeout=timeout + 1)
```

**Critical:** `asyncio.shield(future)` 로 외부 cancel 이 우리 future 를 직접 cancel 못하게 막고, disconnect cleanup 이 `future.cancel()` 을 명시 호출. (이중 보호 — confirm 패턴에는 shield 가 없는데 RPC 는 disconnect cancel 정책 D-12 가 있어서 추가.)

### Pattern 2: 런타임 클라이언트 주입 (순환 의존 회피)

**Source:** `ui-ink/src/store/confirm.ts:9-13` (`bindConfirmClient`).

**Apply to:** `ui-ink/src/tools/registry.ts` 의 `bindToolClient`.

```typescript
let boundClient: HarnessClient | null = null
export function bindToolClient(client: HarnessClient | null): void {
  boundClient = client
}
```

**Why:** `registry.ts` 가 `HarnessClient` 를 import 하면, `client.ts` → `dispatch.ts` → `registry.ts` → `client.ts` 순환. 런타임 주입으로 type-only import 만 허용.

### Pattern 3: Discriminated union + assertNever exhaustive 가드

**Source:** `ui-ink/src/protocol.ts:83-85` (assertNever) + `dispatch.ts:252-254` (default branch).

**Apply to:** RPC 메시지 추가 시 `ServerMsg`/`ClientMsg` union 갱신 → dispatch.ts 에 `case 'tool_request'` 추가하지 않으면 컴파일 에러로 누락 차단.

```typescript
export function assertNever(x: never): never {
  throw new Error(`Unhandled ServerMsg type: ${(x as { type: string }).type}`)
}
```

### Pattern 4: Tool 결과 schema = `{ok: bool, ...}` / `{ok: false, error}`

**Source:** `tools/fs.py:read_file` 등 모든 Python tool. `agent.py:580-595` 가 `result.get('ok')` 로 분기.

**Apply to:** `ui-ink/src/tools/fs.ts` 의 `readFile` 반환. `ui-ink/src/tools/registry.ts` 의 `ToolResult` 타입.

**Critical (D-14):** 클라 도구 반환 schema 가 Python 과 동일해야 LLM 컨텍스트에 들어가는 `tool_result_str` 이 일관됨. `agent.py:540` 의 `json.dumps(result)` 가 그 결과를 LLM 메시지로 변환.

### Pattern 5: 한국어 에러 메시지

**Source:** `tools/fs.py` 전체 (`'경로가 샌드박스 밖입니다: ...'`, `'old_string을 찾을 수 없음'`).

**Apply to:** `ui-ink/src/tools/fs.ts` 의 에러 텍스트, `ui-ink/src/tools/registry.ts` 의 unknown_tool 메시지. (CONTEXT Claude's discretion — 한국어 통일.)

### Pattern 6: dict-lookup registry + getter

**Source:** `tools/__init__.py:310-329` (`TOOL_MAP`) — Python. `ui-ink/src/components/tools/index.ts:20-34` (`TOOL_REGISTRY`) — TS.

**Apply to:** `ui-ink/src/tools/registry.ts` 의 `TOOL_RUNTIME`. 같은 dict 형태, key 가 도구 이름, value 가 실행 함수.

---

## No Analog Found

없음 — Phase 1 의 모든 신규/수정 파일에 1차 reference 존재. RPC 패턴은 confirm bridge 가, dispatch 라우팅은 기존 case 들이, registry 는 `TOOL_REGISTRY` 가, vitest 는 `protocol.test.ts` 가 각각 ground truth.

---

## Metadata

**Analog search scope:**
- `harness_server.py` (line 1-300, 793-870, run_agent 347-401)
- `agent.py` (line 416-600 = run() 본체 + tool dispatch)
- `tools/fs.py` (line 1-130 = read_file/write_file/edit_file)
- `tools/__init__.py` (line 1-50, 300-329 = TOOL_MAP)
- `ui-ink/src/protocol.ts` (전체 86 line)
- `ui-ink/src/ws/dispatch.ts` (전체 257 line)
- `ui-ink/src/ws/client.ts` (전체 138 line)
- `ui-ink/src/store/confirm.ts` (전체 105 line — bindClient 패턴)
- `ui-ink/src/components/tools/index.ts` (전체 38 line)
- `ui-ink/src/App.tsx` (전체 224 line — useEffect lifecycle)
- `ui-ink/src/__tests__/protocol.test.ts` + `dispatch.test.ts` (vitest 스타일 reference)
- `tests/test_fs.py` (line 1-90 = read_file 케이스 매핑)

**Files scanned:** 12

**Pattern extraction date:** 2026-04-27

---

## Quick Reference Index (planner 용)

| 새 파일/수정 | 1줄 액션 |
|---|---|
| `ui-ink/src/tools/registry.ts` | `components/tools/index.ts:20-34` 의 dict 패턴 + `store/confirm.ts:9-13` 의 boundClient 패턴 합성 |
| `ui-ink/src/tools/fs.ts` | `tools/fs.py:55-79 read_file` schema 그대로 TS 변환 (D-14, D-15) |
| `ui-ink/src/protocol.ts` | `ConfirmWriteMsg`/`ConfirmWriteResponse` 페어 (line 17, 70) 와 같은 layer 에 `ToolRequestMsg`/`ToolResultMsg` 추가 + union 갱신 |
| `ui-ink/src/ws/dispatch.ts` | `case 'confirm_write'` (line 112-115) 형태로 `case 'tool_request'` 추가 → `runClientTool` fire-and-forget |
| `ui-ink/src/App.tsx` | line 75-79 의 `bindConfirmClient` 호출 옆에 `bindToolClient(client)` 한 줄 추가 |
| `harness_server.py` | line 274-290 `confirm_write` 패턴으로 `rpc_call` 클로저 작성 (Future + shield + cancel cleanup), line 830-837 `confirm_write_response` 패턴으로 `tool_result` case 추가, line 362-374 `agent.run(...)` 에 `rpc_call=rpc_call` 인자 추가, disconnect cleanup 에 `ws._pending_calls` 일괄 cancel |
| `agent.py` | line 416 signature 에 `rpc_call=None` 추가, line 564 `fn = TOOL_MAP.get(...)` 직전에 `if fn_name in CLIENT_SIDE_TOOLS: result = rpc_call(fn_name, args)` 분기 + alias 정규화 (D-16) |
| `ui-ink/test/tools-fs.test.ts` | `__tests__/protocol.test.ts` 의 `describe`/`it` 스타일 + `tests/test_fs.py:56-83` 5 케이스 동등 변환, mkdtemp 픽스처 |
| (deletion) `tools/fs.py:read_file` + `TOOL_MAP['read_file']` + `tests/test_fs.py:test_read_*` (~5건) | Phase 1 끝 (vitest green + 수동 검증 후) — D-18 |
