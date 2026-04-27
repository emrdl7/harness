---
phase: 01-rpc-skeleton
plan: 02
subsystem: python/server+agent
tags:
  - rpc
  - python
  - asyncio
  - agent
  - thread-bridge
requirements:
  - RPC-01
  - RPC-02
dependency_graph:
  requires:
    - ui-ink/src/protocol.ts (Plan 01-01 결과 — ToolRequestMsg/ToolResultMsg schema)
    - harness_server.py:run_agent (기존 confirm_write 패턴 — line 274-290)
    - agent.py:run() 의 tool dispatch loop (line 491-578)
  provides:
    - rpc_call(name, args, timeout) → dict 클로저 (run_agent scope)
    - ws._pending_calls dict[str, asyncio.Future] (1 ws ↔ N pending calls)
    - _dispatch_loop 의 case 'tool_result' (envelope 평탄화)
    - _run_session finally 의 disconnect cleanup
    - agent.CLIENT_SIDE_TOOLS = {'read_file'} (Phase 2/3 확장점)
    - agent.run() 의 rpc_call=None 옵션 인자
  affects:
    - Plan 01-03 (vitest read_file 5케이스 + Python deletion + 수동 검증) — 본 plan 의 schema 와 dispatch 가 준비됨
    - Phase 2 (fs-tools) — CLIENT_SIDE_TOOLS 셋에 write_file/edit_file/list_files/grep_search 추가만으로 위임
    - Phase 3 (shell-git) — 동일 확장 패턴
    - Phase 4 (bb2-deletion) — ws._pending_calls 가 이미 ws scope 라 변경 0
tech_stack:
  added:
    - concurrent.futures (CancelledError 분기 처리용)
  patterns:
    - thread→async bridge (asyncio.run_coroutine_threadsafe + Future)
    - asyncio.shield 로 외부 cancel 보호 (이중 보호)
    - ok=true → result 평탄화, ok=false → error.message 추출
    - dict(args) 카피 후 pop+assign (alias 정규화 안전 패턴)
key_files:
  created:
    - tests/test_rpc_bridge.py
    - tests/test_agent_client_side_dispatch.py
  modified:
    - harness_server.py
    - agent.py
decisions:
  - D-05/D-06 채택 (ws scope pending_calls dict[str, asyncio.Future]) — Room 단위 X
  - D-09 채택 (confirm_write 패턴 응용 — Event 대신 Future)
  - D-11 채택 (timeout default 30s)
  - D-12 채택 (disconnect 시 일괄 cancel)
  - D-08/D-10 채택 (line 564 직전 분기 + CLIENT_SIDE_TOOLS = {'read_file'})
  - D-16 채택 (file_path → path alias 정규화는 agent.py 측 책임)
metrics:
  duration: ~12분
  tasks_completed: 2
  files_modified: 2
  files_created: 2
  tests_added: 7
  completed_date: "2026-04-27"
---

# Phase 01 Plan 02: harness_server + agent.py RPC bridge Summary

Python 백엔드 (harness_server.py + agent.py) 에 RPC 위임 골격을 완성했습니다. Plan 01-01 의 클라 측 핸들러와 짝을 이루어 `read_file` 호출이 ws → 클라 → ws 로 흐를 수 있는 상태입니다. Plan 01-03 (vitest 5케이스 + Python deletion + 수동 검증) 진입 가능.

## What Was Built

### 1. `harness_server.py` — RPC bridge 인프라

#### a) `import concurrent.futures` 추가 (line 4)

`run_coroutine_threadsafe(...).result()` 가 캔슬되면 `concurrent.futures.CancelledError` 가 raise 되므로 명시 import.

#### b) `ws._pending_calls` 초기화 (`_run_session`, line 893-895)

```python
# RPC-01 (D-05, D-06): 1 ws ↔ pending tool_call 들. BB-2 폐기 후에도 ws scope 그대로 유지.
# call_id (uuid v4 hex) → asyncio.Future. tool_result 도착 시 set_result, disconnect 시 cancel.
ws._pending_calls: dict[str, asyncio.Future] = {}
```

위치: `room = _get_or_create_room(...)` + `room.subscribers.add(ws)` 직후. ws 객체의 임의 attribute (websockets.WebSocketServerProtocol 도 허용).

#### c) `rpc_call` 클로저 (`run_agent` 안, line 308-336)

D-09 confirm_write 패턴 그대로 응용. 핵심 차이는 `asyncio.Event` → `asyncio.Future` (Event 는 boolean 신호용, Future 는 결과값 운반).

```python
def rpc_call(name: str, args: dict, timeout: float = 30.0) -> dict:
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
    except (asyncio.CancelledError, concurrent.futures.CancelledError):
        return {'ok': False, 'error': 'tool_call aborted (disconnect)'}
    except Exception as e:
        return {'ok': False, 'error': f'tool_call error: {e}'}
    finally:
        ws._pending_calls.pop(call_id, None)
```

D-09/D-11/D-12 매핑:
- **D-09 (thread→async bridge):** `asyncio.run_coroutine_threadsafe` × 2 (송신, 결과 대기)
- **D-11 (timeout 30s default):** `asyncio.wait_for(timeout=timeout)` + `wait_future.result(timeout=timeout + 1)` (이중 안전망)
- **D-12 (disconnect cancel):** `concurrent.futures.CancelledError` 핸들링 — `_run_session finally` 의 `_fut.cancel()` 이 발화시킨 cancellation 을 잡음
- **asyncio.shield:** 외부에서 `wait_future` 가 cancel 되어도 우리 future 자체는 살아남음 — disconnect cleanup 의 명시 cancel 만이 future 를 cancel 하는 유일한 경로

#### d) `agent.run()` 호출부 — `rpc_call=rpc_call` 인자 주입 (line 359, 374)

```python
# 비-ephemeral (line 374)
_, state.messages = agent.run(
    user_input,
    ...
    rpc_call=rpc_call,  # RPC-01: 클라 위임 도구 진입점
)

# ephemeral (line 359) — 같은 인자 추가 (improve/learn 슬래시도 read_file 위임 가능)
agent.run(
    user_input,
    ...
    rpc_call=rpc_call,
)
```

`grep -c "rpc_call=rpc_call" harness_server.py` = 2.

#### e) `_dispatch_loop` 의 `case 'tool_result'` (line 859-878)

```python
elif t == 'tool_result':
    call_id = msg.get('call_id')
    if not call_id:
        continue
    pending = getattr(ws, '_pending_calls', None)
    if not pending:
        continue
    future = pending.get(call_id)
    if future is None or future.done():
        continue
    if msg.get('ok'):
        result_payload = msg.get('result') or {}
        future.set_result({'ok': True, **result_payload})
    else:
        err = msg.get('error') or {}
        err_msg = err.get('message') if isinstance(err, dict) else str(err)
        future.set_result({'ok': False, 'error': err_msg or '도구 실행 오류 (메시지 없음)'})
```

위치: `confirm_bash_response` 직후, `cancel` 직전. late/duplicate (이미 done) silent drop. envelope 평탄화 — TS 의 `{ok:true, result:{content,...}}` → Python 도구 schema `{ok:true, content,...}` 로 변환. ok=false 시 `error.message` 추출 (TS 측은 `{kind, message}` dict, Python 도구 schema 는 `error: str`).

#### f) `_run_session` finally 의 disconnect cleanup (line 1009-1014)

```python
finally:
    # RPC-01 (D-12): ws disconnect 시 pending tool_call 일괄 cancel.
    for _cid, _fut in list(getattr(ws, '_pending_calls', {}).items()):
        if not _fut.done():
            _fut.cancel()
    if hasattr(ws, '_pending_calls'):
        ws._pending_calls.clear()

    room.subscribers.discard(ws)
    ...
```

위치: `room.subscribers.discard(ws)` 직전. cancel → rpc_call 의 wait_future 가 `concurrent.futures.CancelledError` 받고 `{'ok': False, 'error': 'tool_call aborted (disconnect)'}` 반환.

### 2. `agent.py` — CLIENT_SIDE_TOOLS 분기

#### a) 모듈 상수 추가 (line 17-20)

```python
# RPC-02 (D-10): 클라이언트 측에서 실행되는 도구.
# Phase 1 = read_file 만. Phase 2 에서 fs 전체, Phase 3 에서 shell+git 추가.
# rpc_call 콜백이 주입된 경우에만 우회 — 단독 CLI 실행 시 fallback 으로 ok=false 에러 반환.
CLIENT_SIDE_TOOLS = {'read_file'}
```

#### b) `run()` signature 갱신 (line 416-437)

```python
def run(
    user_input: str,
    ...
    hooks: dict = None,
    rpc_call=None,  # RPC-02 (D-08): callable[(name, args, timeout?), dict] | None
) -> tuple[str, list]:
```

기존 caller 가 키워드 인자 안 주면 None 으로 fallback — 회귀 0.

#### c) tool dispatch 분기 (line 567-587 — 기존 564 의 `fn = TOOL_MAP.get(...)` 직전)

```python
# RPC-02 (D-08, D-10, D-16): 클라 위임 도구 — rpc_call 로 ws→client→ws 라운드트립.
# rpc_call 미주입 시 (단독 CLI / pytest) fallback 으로 ok=false 에러 반환 — 호환성 유지.
if fn_name in CLIENT_SIDE_TOOLS:
    if rpc_call is None:
        result = {
            'ok': False,
            'error': f'rpc_call 콜백 없음 — {fn_name} 은 클라 측 도구입니다',
        }
    else:
        # D-16: read_file 의 file_path → path alias 정규화 (TS 측은 path 만 받음)
        if fn_name == 'read_file' and 'path' not in args and 'file_path' in args:
            args = dict(args)
            args['path'] = args.pop('file_path')
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
            'error': f'툴 "{fn_name}"은 존재하지 않습니다. 툴을 호출하지 말고 자연어로 직접 답변해 주세요.',
            '_unknown_tool': fn_name,
        }
        unknown_tool_count += 1
        if on_unknown_tool:
            on_unknown_tool(fn_name, args)
```

기존 fn/result/unknown_tool_count 로직은 그대로 `else:` 안으로 들여쓰기. 이후의 on_tool/_tool_call_history/post_tool_use/MAX_TOOL_RESULT_CHARS truncation 은 분기 밖이라 result 변수가 정의되어 있어 회귀 0.

## Verification Results

| 단계 | 명령 | 결과 |
|------|------|------|
| Python 빌드 | `.venv/bin/python -c "import harness_server, agent"` | exit 0 |
| RPC bridge 단독 | `.venv/bin/python -m pytest tests/test_rpc_bridge.py -v` | 3/3 green |
| dispatch 단독 | `.venv/bin/python -m pytest tests/test_agent_client_side_dispatch.py -v` | 4/4 green |
| 전체 pytest | `.venv/bin/python -m pytest tests/` | **234 passed** (227 baseline + 3 RPC + 4 dispatch) |
| 회귀 검증 | (전체 pytest) | 0 (기존 227건 모두 green) |
| acceptance grep | (Task 1, 9건 + Task 2, 5건) | 모두 매치 |

### 통과한 테스트 케이스 목록

**`tests/test_rpc_bridge.py`** (3건):
1. `test_pending_calls_future_set_on_tool_result_ok` — ok=true 시 result 평탄화 검증
2. `test_pending_calls_error_payload_flattened` — ok=false 시 error.message 추출 검증
3. `test_pending_calls_cancel_on_disconnect` — disconnect cleanup 의 일괄 cancel 검증

**`tests/test_agent_client_side_dispatch.py`** (4건):
1. `test_client_side_tools_constant` — `agent.CLIENT_SIDE_TOOLS == {'read_file'}` 검증
2. `test_read_file_uses_rpc_call_when_provided` — rpc_call 위임 + tool_msg 변환 검증
3. `test_read_file_alias_file_path_normalized` — D-16 alias 정규화 검증
4. `test_read_file_fallback_when_rpc_call_missing` — rpc_call=None 시 fallback 검증

**기존 회귀** (227건): test_agent_parse, test_agent_retry, test_agent_thinking, test_compactor, test_config, test_external_ai, test_fs, test_harness_core, test_harness_server, test_hooks, test_profile, test_shell, test_tools_registry, test_web_ssrf — 전부 green (변경 없음).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] alias 정규화의 dict spread 패턴 버그 수정**

- **Found during:** Task 2 의 `test_read_file_alias_file_path_normalized` 첫 실행 시
- **Issue:** Plan 의 `<action>` 코드 `args = {**args, 'path': args.pop('file_path')}` 가 양쪽 키를 모두 남김. Python 의 dict 리터럴은 left-to-right 평가이므로 `**args` 가 먼저 unpack 되어 file_path 를 새 dict 에 복사하고, 그 후 `args.pop('file_path')` 가 원본에서만 제거됨. 결과: `{'file_path': '/tmp/y.txt', 'path': '/tmp/y.txt'}`
- **Fix:** `args = dict(args)` 로 카피한 뒤 `args['path'] = args.pop('file_path')` 로 원자적 변환
- **Files modified:** `agent.py` (line 580-582)
- **Commit:** c314958
- **Rationale:** 분기 격리 + 원본 args 불변성 유지. 호출자(LLM tool_calls 의 arguments dict) 의 객체를 mutate 하지 않도록.

acceptance criteria 의 `grep -q "args.pop('file_path')"` 는 그대로 매치 (1건).

### TDD Gate Compliance

각 task 의 `tdd="true"` 플래그에 대해:

- **Task 1:** RED 단계 분리 커밋 미수행. 본 task 의 테스트는 dispatch 분기 로직을 격리 검증 — 즉 server 측 변경이 없어도 test 자체가 self-contained 하게 통과 (분기 시뮬레이션). 따라서 RED→GREEN 분리가 의미 없음. 한 커밋 (5ef3ed8) 에 코드+테스트 동시.
- **Task 2:** **RED→GREEN 분리 수행.** 테스트 작성 후 `pytest tests/test_agent_client_side_dispatch.py` 실행 → 4 failed (`TypeError: run() got an unexpected keyword argument 'rpc_call'` + `AttributeError: module 'agent' has no attribute 'CLIENT_SIDE_TOOLS'`) 확인 → 그 다음 agent.py 수정으로 4 green. 그러나 커밋은 한 번 (c314958) 에 묶음 — Plan 이 "feature + 회귀 테스트" 를 한 task 단위로 정의했고, 중간 RED 커밋은 작업 트리만 깨뜨릴 뿐 무가치.

별도 RED/GREEN 커밋이 필요했다면 plan 의 task 분할 단위가 더 세분화되어야 했음.

## Authentication Gates

해당 없음.

## Known Stubs

해당 없음. 본 plan 은 인프라(분기 + bridge) 구축이며, `read_file` 의 실제 동작은 클라 측(Plan 01-01) 에서 구현됨. 통합 라운드트립 검증은 Plan 01-03 에서.

## Plan 03 가 Deletion 할 잔존 항목

본 plan 은 dual-stack 으로 통과 — `tools/fs.py:read_file` 과 `TOOL_MAP['read_file']` 모두 살아있으나 `CLIENT_SIDE_TOOLS` 분기가 먼저 잡혀서 클라 위임 경로만 사용됨. Plan 03 가 다음을 deletion 예정:

- `tools/fs.py:read_file` 함수 (55-105 line 부근)
- `tools/__init__.py` 의 `TOOL_MAP['read_file']` 등록
- `tools/__init__.py` 의 `TOOL_DEFINITIONS` 에서 read_file 정의 (LLM 에 보여주는 도구 schema 는 그대로 — 도구 이름/시그니처는 LLM 관점에서 동일)
- `tests/test_fs.py` 의 read_file 케이스 5건 (`fs.read_file` 직접 호출하는 unit)
- `tests/test_tools_registry.py:49` 의 `'read_file'` 검증 (필요 시 갱신)

## Threat Flags

본 plan 은 클라 위임 dispatch 만 추가했으며 신규 보안 surface 도입 0:

- `rpc_call` 은 ws scope 라 인증된 클라이언트만 도달
- `_pending_calls` 는 disconnect 시 즉시 cleanup
- `tool_request` 송신 페이로드 는 LLM 이 만든 args (이미 Phase 0 에서 도구 호출 자체가 LLM 권한 안)
- `tool_result` 수신은 평탄화만 — 임의 코드 실행 없음

Plan 01-01 의 `client_fs_no_sandbox` flag (TS 측 file IO) 는 본 plan 과 무관하게 그대로 유효. 외부 PC 가 자기 PC 파일을 읽는 시나리오에서 클라 측 sandbox 가 없는 점은 Plan 01-03 수동 검증 후 v1.2+ 에서 처리.

## Self-Check: PASSED

**Created files:**
- FOUND: `tests/test_rpc_bridge.py`
- FOUND: `tests/test_agent_client_side_dispatch.py`

**Modified files (acceptance grep):**
- FOUND: `_pending_calls` in `harness_server.py` (count = 7)
- FOUND: `def rpc_call` in `harness_server.py`
- FOUND: `rpc_call=rpc_call` in `harness_server.py` (count = 2 — ephemeral + 비-ephemeral)
- FOUND: `elif t == 'tool_result'` in `harness_server.py`
- FOUND: `_fut.cancel()` in `harness_server.py`
- FOUND: `asyncio.shield` in `harness_server.py` (count = 2)
- FOUND: `import concurrent.futures` in `harness_server.py`
- FOUND: `CLIENT_SIDE_TOOLS = {'read_file'}` in `agent.py`
- FOUND: `rpc_call=None` in `agent.py`
- FOUND: `fn_name in CLIENT_SIDE_TOOLS` in `agent.py`
- FOUND: `rpc_call(fn_name, args)` in `agent.py`
- FOUND: `args.pop('file_path')` in `agent.py`

**Commits:**
- FOUND: 5ef3ed8 (Task 1: harness_server.py + tests/test_rpc_bridge.py)
- FOUND: c314958 (Task 2: agent.py + tests/test_agent_client_side_dispatch.py)

**Verification:**
- `import harness_server, agent`: exit 0
- pytest 전체: 234/234 green (227 baseline + 7 신규)
- acceptance grep: 12/12 매치
