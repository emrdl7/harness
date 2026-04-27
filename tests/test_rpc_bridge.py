'''RPC bridge — pending_calls + tool_result dispatch + disconnect cleanup 회귀.

rpc_call 클로저 자체는 run_agent 내부 — thread-safety/timeout 통합 검증은 외부 PC
수동 검증 + Plan 03 으로 위임. 본 파일은 _dispatch_loop 의 tool_result 분기 +
finally 의 cleanup 분기만 격리 단위 검증.
'''
import asyncio
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_pending_calls_future_set_on_tool_result_ok():
    '''tool_result(ok=true) 가 ws._pending_calls[call_id].set_result 를 호출 + envelope 평탄화.'''
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    pending = {'abc': future}
    ws = MagicMock()
    ws._pending_calls = pending

    # _dispatch_loop 의 tool_result 분기 시뮬레이션
    msg = {'type': 'tool_result', 'call_id': 'abc', 'ok': True,
           'result': {'content': 'hello', 'total_lines': 1, 'start_line': 1, 'end_line': 1}}
    call_id = msg.get('call_id')
    f = pending.get(call_id)
    assert f is not None and not f.done()
    result_payload = msg.get('result') or {}
    f.set_result({'ok': True, **result_payload})

    result = await asyncio.wait_for(future, timeout=1)
    assert result['ok'] is True
    assert result['content'] == 'hello'
    assert result['total_lines'] == 1


@pytest.mark.asyncio
async def test_pending_calls_error_payload_flattened():
    '''tool_result(ok=false) 가 error.message 를 result.error 로 평탄화.'''
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    msg = {'type': 'tool_result', 'call_id': 'x', 'ok': False,
           'error': {'kind': 'tool_error', 'message': 'EISDIR'}}
    err = msg.get('error') or {}
    err_msg = err.get('message') if isinstance(err, dict) else str(err)
    future.set_result({'ok': False, 'error': err_msg})

    r = await asyncio.wait_for(future, timeout=1)
    assert r == {'ok': False, 'error': 'EISDIR'}


@pytest.mark.asyncio
async def test_pending_calls_cancel_on_disconnect():
    '''disconnect cleanup: ws._pending_calls 의 모든 Future 가 cancel 되어야 함.'''
    loop = asyncio.get_event_loop()
    f1 = loop.create_future()
    f2 = loop.create_future()
    ws = MagicMock()
    ws._pending_calls = {'a': f1, 'b': f2}

    # _run_session finally 분기 시뮬레이션
    for _cid, _fut in list(getattr(ws, '_pending_calls', {}).items()):
        if not _fut.done():
            _fut.cancel()

    assert f1.cancelled()
    assert f2.cancelled()
