'''agent._parse_text_tool_calls — 텍스트 툴콜 파서 회귀 테스트.

CONCERNS.md §1.5 대응: nested 중괄호를 포함한 arguments도 파싱되어야 함.
'''
import agent


class TestParseTextToolCalls:
    def test_flat_arguments(self):
        text = '{"name": "read_file", "arguments": {"path": "a.py"}}'
        calls = agent._parse_text_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]['function']['name'] == 'read_file'
        assert calls[0]['function']['arguments'] == {'path': 'a.py'}

    def test_nested_arguments(self):
        '''§1.5 회귀 방지: arguments가 중첩 객체여도 파싱.'''
        text = '{"name": "mcp_query", "arguments": {"filter": {"type": "eq", "val": 3}}}'
        calls = agent._parse_text_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]['function']['arguments'] == {
            'filter': {'type': 'eq', 'val': 3}
        }

    def test_multiple_calls_in_text(self):
        text = (
            '사용자 답변: {"name": "read_file", "arguments": {"path": "a"}}\n'
            '이어서 {"name": "edit_file", "arguments": {"path": "b", "old_string": "x", "new_string": "y"}}'
        )
        calls = agent._parse_text_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]['function']['name'] == 'read_file'
        assert calls[1]['function']['name'] == 'edit_file'

    def test_nested_list_argument(self):
        text = '{"name": "multi_read", "arguments": {"paths": ["a", "b", "c"]}}'
        calls = agent._parse_text_tool_calls(text)
        assert calls[0]['function']['arguments']['paths'] == ['a', 'b', 'c']

    def test_xml_format_still_works(self):
        text = '<function=read_file><parameter=path>foo.py</parameter></function>'
        calls = agent._parse_text_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]['function']['name'] == 'read_file'
        assert calls[0]['function']['arguments'] == {'path': 'foo.py'}

    def test_garbage_ignored(self):
        '''툴콜 형식이 아닌 JSON은 무시.'''
        text = '{"some": "unrelated"}'
        calls = agent._parse_text_tool_calls(text)
        assert calls == []
