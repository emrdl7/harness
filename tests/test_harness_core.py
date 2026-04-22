'''harness_core — 1차 추출된 슬래시 핸들러.'''
import os

import pytest

from harness_core import SlashState, SlashResult, dispatch
from harness_core.router import parse, KNOWN_COMMANDS
from harness_core import handlers as h


# ── parse ────────────────────────────────────────────────────────────
class TestParse:
    def test_no_arg(self):
        assert parse('/clear') == ('/clear', '')

    def test_with_arg(self):
        assert parse('/cd /tmp/foo') == ('/cd', '/tmp/foo')

    def test_arg_with_spaces(self):
        '''첫 공백 한 번만 split — 인자에 공백 포함 가능.'''
        assert parse('/plan 첫 번째 작업') == ('/plan', '첫 번째 작업')

    def test_strips_whitespace(self):
        assert parse('  /clear  ') == ('/clear', '')

    def test_empty_string(self):
        assert parse('') == ('', '')


# ── slash_clear ──────────────────────────────────────────────────────
class TestClear:
    def test_empties_messages(self):
        state = SlashState(messages=[
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'u'},
        ])
        result = h.slash_clear(state)
        assert result.handled
        assert result.state.messages == []
        assert result.level == 'info'

    def test_does_not_mutate_input(self):
        state = SlashState(messages=[{'role': 'user', 'content': 'u'}])
        before = list(state.messages)
        _ = h.slash_clear(state)
        assert state.messages == before


# ── slash_undo ───────────────────────────────────────────────────────
class TestUndo:
    def test_removes_last_pair(self):
        state = SlashState(messages=[
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'a1'},
            {'role': 'user', 'content': 'q2'},
            {'role': 'assistant', 'content': 'a2'},
        ])
        result = h.slash_undo(state)
        assert result.handled
        assert len(result.state.messages) == 3
        assert result.state.messages[0]['role'] == 'system'
        assert result.state.messages[-1]['content'] == 'a1'
        assert result.state.undo_count == 1

    def test_noop_when_nothing_to_undo(self):
        state = SlashState(messages=[{'role': 'system', 'content': 's'}])
        result = h.slash_undo(state)
        assert result.handled
        assert len(result.state.messages) == 1
        assert result.state.undo_count == 0
        assert '취소할 내용이 없습니다' in result.notice


# ── slash_cd ─────────────────────────────────────────────────────────
class TestCd:
    def test_changes_dir(self, tmp_path, monkeypatch):
        # profile.load는 working_dir 안의 .harness.toml + ~/.harness.toml을 본다.
        # 둘 다 없으면 defaults만 반환되므로 안전.
        monkeypatch.setenv('HOME', str(tmp_path / 'home'))
        (tmp_path / 'home').mkdir()

        state = SlashState(working_dir='/tmp', messages=[{'role': 'user', 'content': 'x'}])
        result = h.slash_cd(state, str(tmp_path))
        assert result.handled
        assert result.level == 'ok'
        assert result.state.working_dir == str(tmp_path)
        # 디렉토리 변경 시 세션도 초기화되어야 함 (다른 프로젝트 컨텍스트)
        assert result.state.messages == []
        # profile은 새 dir 기준으로 다시 로드됨
        assert isinstance(result.state.profile, dict)

    def test_missing_arg(self, tmp_path):
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_cd(state, '')
        assert result.level == 'warn'
        assert '사용법' in result.notice
        # 상태는 그대로
        assert result.state is state

    def test_nonexistent_path(self, tmp_path):
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_cd(state, str(tmp_path / 'no_such'))
        assert result.level == 'error'
        assert result.state is state

    def test_expands_user(self, monkeypatch, tmp_path):
        '''~/foo 같은 경로는 expanduser 적용.'''
        home = tmp_path / 'home'
        home.mkdir()
        monkeypatch.setenv('HOME', str(home))
        state = SlashState(working_dir='/tmp')
        result = h.slash_cd(state, '~')
        assert result.handled
        # /tmp가 아닌 home으로 바뀜
        assert os.path.realpath(result.state.working_dir) == os.path.realpath(str(home))


# ── slash_init ───────────────────────────────────────────────────────
class TestInit:
    def test_creates_template(self, tmp_path):
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_init(state)
        assert result.handled
        assert result.level == 'ok'
        assert (tmp_path / '.harness.toml').exists()

    def test_does_not_overwrite(self, tmp_path):
        (tmp_path / '.harness.toml').write_text('# 기존 내용')
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_init(state)
        assert result.level == 'warn'
        assert '이미 존재' in result.notice
        # 원본 보존
        assert (tmp_path / '.harness.toml').read_text() == '# 기존 내용'


# ── slash_help ───────────────────────────────────────────────────────
class TestHelp:
    def test_returns_text(self):
        result = h.slash_help(SlashState())
        assert result.handled
        assert '/clear' in result.notice
        assert '/cd' in result.notice
        # 상태 변경 없음
        assert result.state.messages == []


# ── dispatch (router) ────────────────────────────────────────────────
class TestDispatch:
    def test_known_command_no_arg(self):
        state = SlashState(messages=[{'role': 'user', 'content': 'x'}])
        result = dispatch('/clear', state)
        assert result.handled
        assert result.state.messages == []

    def test_known_command_with_arg(self, tmp_path, monkeypatch):
        monkeypatch.setenv('HOME', str(tmp_path / 'home'))
        (tmp_path / 'home').mkdir()
        state = SlashState(working_dir='/tmp')
        result = dispatch(f'/cd {tmp_path}', state)
        assert result.handled
        assert result.state.working_dir == str(tmp_path)

    def test_unknown_command(self):
        state = SlashState()
        result = dispatch('/wat', state)
        assert result.handled is False
        assert result.level == 'warn'
        assert '/wat' in result.notice

    def test_known_commands_registry_complete(self):
        '''라우터에 등록된 명령은 모두 호출 가능해야 함 (콜러블 + 시그니처 확인).'''
        for name, (fn, needs_arg) in KNOWN_COMMANDS.items():
            assert callable(fn), f'{name} 핸들러가 콜러블이 아님'
            assert isinstance(needs_arg, bool)
