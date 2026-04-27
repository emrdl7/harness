'''agent.py 의 CLIENT_SIDE_TOOLS 분기 + rpc_call 위임 + alias 정규화 회귀.

본 파일은 agent.run 의 main loop 까지 통과 — confirm/cwd 주입/sticky_deny 분기와의
회귀도 같이 검증. _stream_response 만 patch.object 로 주입.
'''
import json
from unittest.mock import MagicMock, patch

import agent


def test_client_side_tools_constant():
    '''Phase 1 = read_file 만 클라 위임.'''
    assert agent.CLIENT_SIDE_TOOLS == {'read_file'}


def test_read_file_uses_rpc_call_when_provided():
    '''rpc_call 주입 시 read_file 이 위임됨 — TOOL_MAP 의 fs.read_file 호출 안 됨.'''
    rpc_call = MagicMock(return_value={'ok': True, 'content': '   1\thi\n',
                                       'total_lines': 1, 'start_line': 1, 'end_line': 1})
    # 한 turn = tool_call → 다음 응답에서 final answer
    tool_call_msg = {
        'role': 'assistant',
        'content': '',
        'tool_calls': [{'function': {'name': 'read_file',
                                     'arguments': json.dumps({'path': '/tmp/x.txt'})}}],
    }
    final_msg = {'role': 'assistant', 'content': '읽었습니다'}
    with patch.object(agent, '_stream_response', side_effect=[tool_call_msg, final_msg]):
        _, msgs = agent.run('읽어줘', session_messages=[], rpc_call=rpc_call)
    rpc_call.assert_called_once_with('read_file', {'path': '/tmp/x.txt'})
    tool_msgs = [m for m in msgs if m.get('role') == 'tool']
    assert len(tool_msgs) == 1
    parsed = json.loads(tool_msgs[0]['content'])
    assert parsed['ok'] is True
    assert parsed['total_lines'] == 1


def test_read_file_alias_file_path_normalized():
    '''D-16: file_path 만 있고 path 없으면 path 로 alias 정규화.'''
    rpc_call = MagicMock(return_value={'ok': True})
    tool_call_msg = {
        'role': 'assistant',
        'content': '',
        'tool_calls': [{'function': {'name': 'read_file',
                                     'arguments': json.dumps({'file_path': '/tmp/y.txt'})}}],
    }
    final_msg = {'role': 'assistant', 'content': 'done'}
    with patch.object(agent, '_stream_response', side_effect=[tool_call_msg, final_msg]):
        agent.run('x', session_messages=[], rpc_call=rpc_call)
    name, args = rpc_call.call_args[0]
    assert name == 'read_file'
    assert args.get('path') == '/tmp/y.txt'
    assert 'file_path' not in args


def test_read_file_fallback_when_rpc_call_missing():
    '''rpc_call=None 일 때 ok=false + 명시 에러 메시지 (단독 CLI 호환성).'''
    tool_call_msg = {
        'role': 'assistant',
        'content': '',
        'tool_calls': [{'function': {'name': 'read_file',
                                     'arguments': json.dumps({'path': '/tmp/z.txt'})}}],
    }
    final_msg = {'role': 'assistant', 'content': 'done'}
    with patch.object(agent, '_stream_response', side_effect=[tool_call_msg, final_msg]):
        _, msgs = agent.run('x', session_messages=[], rpc_call=None)
    tool_msgs = [m for m in msgs if m.get('role') == 'tool']
    parsed = json.loads(tool_msgs[0]['content'])
    assert parsed['ok'] is False
    assert 'rpc_call' in parsed['error']
