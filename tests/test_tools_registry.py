'''tools/__init__.py — TOOL_DEFINITIONS / TOOL_MAP 무결성.'''
import pytest

import tools


class TestToolDefinitions:
    def test_has_definitions(self):
        assert hasattr(tools, 'TOOL_DEFINITIONS')
        assert isinstance(tools.TOOL_DEFINITIONS, list)
        assert len(tools.TOOL_DEFINITIONS) > 0

    def test_each_definition_has_required_keys(self):
        for tool_def in tools.TOOL_DEFINITIONS:
            assert 'name' in tool_def
            assert 'description' in tool_def
            assert 'parameters' in tool_def
            assert isinstance(tool_def['name'], str)
            assert tool_def['name']  # not empty

    def test_parameter_schema_valid(self):
        for tool_def in tools.TOOL_DEFINITIONS:
            params = tool_def['parameters']
            assert params['type'] == 'object'
            assert 'properties' in params
            assert isinstance(params['properties'], dict)

    def test_no_duplicate_names(self):
        names = [t['name'] for t in tools.TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), f'중복 툴: {names}'


class TestToolMap:
    def test_has_map(self):
        assert hasattr(tools, 'TOOL_MAP')
        assert isinstance(tools.TOOL_MAP, dict)
        assert len(tools.TOOL_MAP) > 0

    def test_definitions_match_map(self):
        '''모든 등록 정의에 대해 TOOL_MAP에 콜러블이 있어야 함 (단, CLIENT_SIDE_TOOLS 는 클라 위임이므로 TOOL_MAP 부재가 정상).'''
        from agent import CLIENT_SIDE_TOOLS
        for tool_def in tools.TOOL_DEFINITIONS:
            name = tool_def['name']
            if name in CLIENT_SIDE_TOOLS:
                assert name not in tools.TOOL_MAP, f'클라 위임 도구가 서버 TOOL_MAP 에 잔존: {name}'
                continue
            assert name in tools.TOOL_MAP, f'TOOL_MAP에 누락: {name}'
            assert callable(tools.TOOL_MAP[name]), f'{name} 콜러블 아님'

    def test_core_tools_present(self):
        '''핵심 툴들이 빠지지 않았는지.'''
        names = {t['name'] for t in tools.TOOL_DEFINITIONS}
        for required in ['read_file', 'write_file', 'edit_file', 'list_files',
                         'grep_search', 'run_command', 'run_python']:
            assert required in names, f'핵심 툴 누락: {required}'
