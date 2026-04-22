'''harness_core — 1차 추출된 슬래시 핸들러.'''
import os

import pytest

from harness_core import SlashState, SlashResult, SlashContext, dispatch
from harness_core.router import parse, KNOWN_COMMANDS
from harness_core import handlers as h

# 테스트용 빈 컨텍스트 — 핸들러 시그니처 호환
_CTX = SlashContext()


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
        result = h.slash_clear(state, _CTX)
        assert result.handled
        assert result.state.messages == []
        assert result.level == 'info'

    def test_does_not_mutate_input(self):
        state = SlashState(messages=[{'role': 'user', 'content': 'u'}])
        before = list(state.messages)
        _ = h.slash_clear(state, _CTX)
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
        result = h.slash_undo(state, _CTX)
        assert result.handled
        assert len(result.state.messages) == 3
        assert result.state.messages[0]['role'] == 'system'
        assert result.state.messages[-1]['content'] == 'a1'
        assert result.state.undo_count == 1

    def test_noop_when_nothing_to_undo(self):
        state = SlashState(messages=[{'role': 'system', 'content': 's'}])
        result = h.slash_undo(state, _CTX)
        assert result.handled
        assert len(result.state.messages) == 1
        assert result.state.undo_count == 0
        assert '취소할 내용이 없습니다' in result.notice

    def test_removes_tool_messages_in_turn(self):
        '''CONCERNS.md §1.18 회귀 방지: user 이후 assistant + tool 여러 개가
        섞인 경우에도 orphan 없이 모두 제거되어야 한다.'''
        state = SlashState(messages=[
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'a1'},
            {'role': 'user', 'content': 'q2'},
            {'role': 'assistant', 'content': 'calling tool'},
            {'role': 'tool', 'content': '{"ok": true}'},
            {'role': 'tool', 'content': '{"ok": true}'},
            {'role': 'assistant', 'content': 'a2'},
        ])
        result = h.slash_undo(state, _CTX)
        # q2부터 끝까지 전부 제거 → system, q1, a1만 남음
        assert len(result.state.messages) == 3
        roles = [m['role'] for m in result.state.messages]
        assert roles == ['system', 'user', 'assistant']
        assert result.state.messages[-1]['content'] == 'a1'
        assert result.state.undo_count == 1

    def test_undo_twice_clears_to_system(self):
        '''/undo 두 번이면 system만 남아야 함.'''
        state = SlashState(messages=[
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'a1'},
        ])
        r1 = h.slash_undo(state, _CTX)
        r2 = h.slash_undo(r1.state, _CTX)
        assert len(r2.state.messages) == 1
        assert r2.state.messages[0]['role'] == 'system'
        # 두 번째는 noop (undo_count는 r1과 동일)
        assert r2.state.undo_count == r1.state.undo_count


# ── slash_cd ─────────────────────────────────────────────────────────
class TestCd:
    def test_changes_dir(self, tmp_path, monkeypatch):
        # profile.load는 working_dir 안의 .harness.toml + ~/.harness.toml을 본다.
        # 둘 다 없으면 defaults만 반환되므로 안전.
        monkeypatch.setenv('HOME', str(tmp_path / 'home'))
        (tmp_path / 'home').mkdir()

        state = SlashState(working_dir='/tmp', messages=[{'role': 'user', 'content': 'x'}])
        result = h.slash_cd(state, _CTX, str(tmp_path))
        assert result.handled
        assert result.level == 'ok'
        assert result.state.working_dir == str(tmp_path)
        # 디렉토리 변경 시 세션도 초기화되어야 함 (다른 프로젝트 컨텍스트)
        assert result.state.messages == []
        # profile은 새 dir 기준으로 다시 로드됨
        assert isinstance(result.state.profile, dict)

    def test_missing_arg(self, tmp_path):
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_cd(state, _CTX,'')
        assert result.level == 'warn'
        assert '사용법' in result.notice
        # 상태는 그대로
        assert result.state is state

    def test_nonexistent_path(self, tmp_path):
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_cd(state, _CTX, str(tmp_path / 'no_such'))
        assert result.level == 'error'
        assert result.state is state

    def test_expands_user(self, monkeypatch, tmp_path):
        '''~/foo 같은 경로는 expanduser 적용.'''
        home = tmp_path / 'home'
        home.mkdir()
        monkeypatch.setenv('HOME', str(home))
        state = SlashState(working_dir='/tmp')
        result = h.slash_cd(state, _CTX,'~')
        assert result.handled
        # /tmp가 아닌 home으로 바뀜
        assert os.path.realpath(result.state.working_dir) == os.path.realpath(str(home))


# ── slash_init ───────────────────────────────────────────────────────
class TestInit:
    def test_creates_template(self, tmp_path):
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_init(state, _CTX)
        assert result.handled
        assert result.level == 'ok'
        assert (tmp_path / '.harness.toml').exists()

    def test_does_not_overwrite(self, tmp_path):
        (tmp_path / '.harness.toml').write_text('# 기존 내용')
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_init(state, _CTX)
        assert result.level == 'warn'
        assert '이미 존재' in result.notice
        # 원본 보존
        assert (tmp_path / '.harness.toml').read_text() == '# 기존 내용'


# ── slash_save / resume / sessions ───────────────────────────────────
@pytest.fixture
def isolated_session_dir(monkeypatch, tmp_path):
    '''~/.harness/sessions 격리 — 실제 사용자 세션과 충돌 방지.'''
    import session.store as store
    sessions_dir = tmp_path / 'sessions'
    monkeypatch.setattr(store, 'SESSION_DIR', str(sessions_dir))
    return sessions_dir


class TestSave:
    def test_save_creates_file(self, isolated_session_dir):
        state = SlashState(
            messages=[
                {'role': 'system', 'content': 's'},
                {'role': 'user', 'content': 'hello'},
            ],
            working_dir='/tmp',
        )
        result = h.slash_save(state, _CTX)
        assert result.handled
        assert result.level == 'ok'
        assert 'filename' in result.data
        # 디스크에 실제 생성됨
        assert (isolated_session_dir / result.data['filename']).exists()


class TestResume:
    def test_no_sessions_returns_info(self, isolated_session_dir):
        state = SlashState(working_dir='/tmp')
        result = h.slash_resume(state, _CTX)
        assert result.handled
        assert result.level == 'info'
        assert '불러올 세션이 없습니다' in result.notice
        # 상태 변경 없음
        assert result.state.messages == []

    def test_resume_latest(self, isolated_session_dir):
        # 먼저 세션 저장
        from harness_core import handlers as hh
        save_state = SlashState(
            messages=[
                {'role': 'system', 'content': 's'},
                {'role': 'user', 'content': 'q1'},
                {'role': 'assistant', 'content': 'a1'},
            ],
            working_dir='/tmp/foo',
        )
        save_result = hh.slash_save(save_state, _CTX)
        # 비어있는 세션에서 resume
        empty_state = SlashState(working_dir='/tmp/foo')
        result = hh.slash_resume(empty_state, _CTX)
        assert result.handled
        assert result.level == 'ok'
        assert result.data['turns'] == 1
        assert len(result.state.messages) == 3
        assert result.state.working_dir == '/tmp/foo'

    def test_resume_by_filename(self, isolated_session_dir):
        from harness_core import handlers as hh
        save_state = SlashState(
            messages=[{'role': 'user', 'content': 'q'}],
            working_dir='/tmp/bar',
        )
        save_result = hh.slash_save(save_state, _CTX)
        fn = save_result.data['filename']
        # 다른 working_dir에서 명시적으로 파일명 지정해 복원
        empty_state = SlashState(working_dir='/tmp/elsewhere')
        result = hh.slash_resume(empty_state, _CTX, fn)
        assert result.handled
        # working_dir도 저장된 값으로 복원
        assert result.state.working_dir == '/tmp/bar'


class TestSessions:
    def test_empty_returns_info(self, isolated_session_dir):
        state = SlashState()
        result = h.slash_sessions(state, _CTX)
        assert result.handled
        assert result.level == 'info'
        assert result.data['sessions'] == []

    def test_lists_saved(self, isolated_session_dir):
        from harness_core import handlers as hh
        s1 = SlashState(messages=[{'role': 'user', 'content': 'first'}], working_dir='/tmp/a')
        s2 = SlashState(messages=[{'role': 'user', 'content': 'second'}], working_dir='/tmp/b')
        hh.slash_save(s1, _CTX)
        hh.slash_save(s2, _CTX)
        result = h.slash_sessions(SlashState(), _CTX)
        assert result.level == 'ok'
        assert len(result.data['sessions']) == 2
        # 각 세션은 dict (filename, working_dir, turns, preview)
        for sess in result.data['sessions']:
            assert 'filename' in sess
            assert 'working_dir' in sess


# ── slash_files ──────────────────────────────────────────────────────
class TestFiles:
    def test_returns_tree_dict(self, tmp_path):
        # 디렉토리 구조: a.txt, sub/b.txt
        (tmp_path / 'a.txt').write_text('x')
        (tmp_path / 'sub').mkdir()
        (tmp_path / 'sub' / 'b.txt').write_text('y')
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_files(state, _CTX)
        assert result.handled
        assert result.level == 'ok'
        tree = result.data['tree']
        assert tree['name'] == tmp_path.name
        # children에 a.txt + sub 두 개
        names = {c['name'] for c in tree['children']}
        assert 'a.txt' in names
        assert 'sub' in names
        # sub는 children 키 보유 (디렉토리 마커)
        sub_node = next(c for c in tree['children'] if c['name'] == 'sub')
        assert 'children' in sub_node

    def test_ignores_common_dirs(self, tmp_path):
        (tmp_path / 'a.txt').write_text('x')
        (tmp_path / '.git').mkdir()
        (tmp_path / '.git' / 'config').write_text('x')
        (tmp_path / '__pycache__').mkdir()
        (tmp_path / 'node_modules').mkdir()
        state = SlashState(working_dir=str(tmp_path))
        result = h.slash_files(state, _CTX)
        names = {c['name'] for c in result.data['tree']['children']}
        assert '.git' not in names
        assert '__pycache__' not in names
        assert 'node_modules' not in names

    def test_max_depth_respected(self, tmp_path):
        # 깊이 5의 nested 디렉토리. _walk(path, 1)로 시작이라
        # max_depth=3이면 root → l1(d=2) → l2(d=3)까지만 나옴.
        deep = tmp_path / 'l1' / 'l2' / 'l3' / 'l4' / 'l5'
        deep.mkdir(parents=True)
        (deep / 'leaf.txt').write_text('x')
        result = h.slash_files(SlashState(working_dir=str(tmp_path)), _CTX)
        l1 = result.data['tree']['children'][0]
        assert l1['name'] == 'l1'
        l2 = l1['children'][0]
        assert l2['name'] == 'l2'
        # l3은 depth=4가 되어 None 반환 → l2.children에 안 들어감
        assert l2['children'] == []


# ── slash_help ───────────────────────────────────────────────────────
class TestHelp:
    def test_returns_text(self):
        result = h.slash_help(SlashState(), _CTX)
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
