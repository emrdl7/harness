'''main.handle_slash — slash 디스패치 동작.

핵심: /plan, /retry 등 agent 실행이 필요한 슬래시는 nested `_run_agent`를
참조하면 NameError가 난다. DI(`run_agent` 인자)로 처리해야 한다.
'''
from unittest.mock import MagicMock

import main


class TestAgents:
    '''/agents — 외부 AI 레지스트리 목록.'''

    def test_runs_without_crash(self):
        new_msgs, wd, undo = main.handle_slash('/agents', [], '/tmp', {}, 0)
        assert new_msgs == []
        assert wd == '/tmp'

    def test_shows_claude_by_default(self, monkeypatch):
        '''Claude가 기본 등록되어 있으므로 /agents 분기가 빈 목록 브랜치로
        빠지지 않음. 실제 Rich 출력은 캡쳐 없이 크래시만 검증.'''
        new_msgs, wd, undo = main.handle_slash('/agents', [], '/tmp', {}, 0)
        # registry는 모듈 import 시점에 등록됨 — 최소 1개는 있음
        from tools import external_ai
        assert len(external_ai.list_all()) >= 1


class TestThink:
    '''/think — 마지막 assistant 메시지의 _thinking 필드 펼치기.'''

    def test_no_thinking_message_soft_fail(self):
        '''_thinking 필드 없으면 경고만 출력하고 정상 반환.'''
        msgs = [
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q'},
            {'role': 'assistant', 'content': 'a'},
        ]
        new_msgs, wd, undo = main.handle_slash('/think', msgs, '/tmp', {}, 0)
        assert new_msgs == msgs  # 세션 변경 없음
        assert wd == '/tmp'

    def test_no_assistant_message_soft_fail(self):
        '''assistant 메시지 자체가 없을 때도 크래시 없음.'''
        msgs = [{'role': 'system', 'content': 's'}]
        new_msgs, wd, undo = main.handle_slash('/think', msgs, '/tmp', {}, 0)
        assert new_msgs == msgs

    def test_finds_latest_thinking(self):
        '''여러 assistant 메시지 중 마지막 것의 _thinking 을 본다.'''
        msgs = [
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'a1',
             '_thinking': {'text': '오래된 사고', 'duration': 1.0, 'tokens': 10}},
            {'role': 'user', 'content': 'q2'},
            {'role': 'assistant', 'content': 'a2',
             '_thinking': {'text': '최근 사고', 'duration': 2.5, 'tokens': 20}},
        ]
        # 크래시 없이 통과. 실제 출력은 Rich라 캡쳐 안 함 — 렌더 로직만 검증.
        new_msgs, wd, undo = main.handle_slash('/think', msgs, '/tmp', {}, 0)
        assert new_msgs == msgs


def test_clear_returns_empty_session():
    msgs = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'u'}]
    new_msgs, wd, undo = main.handle_slash('/clear', msgs, '/tmp', {}, 0)
    assert new_msgs == []
    assert wd == '/tmp'
    assert undo == 0


def test_undo_removes_last_exchange():
    msgs = [
        {'role': 'system', 'content': 's'},
        {'role': 'user', 'content': 'q1'},
        {'role': 'assistant', 'content': 'a1'},
        {'role': 'user', 'content': 'q2'},
        {'role': 'assistant', 'content': 'a2'},
    ]
    new_msgs, wd, undo = main.handle_slash('/undo', msgs, '/tmp', {}, 0)
    # system 유지 + 마지막 user/assistant 쌍 제거
    assert len(new_msgs) == 3
    assert new_msgs[0]['role'] == 'system'
    assert new_msgs[-1]['content'] == 'a1'
    assert undo == 1


def test_undo_empty_session_noop():
    msgs = [{'role': 'system', 'content': 's'}]
    new_msgs, wd, undo = main.handle_slash('/undo', msgs, '/tmp', {}, 0)
    assert len(new_msgs) == 1
    assert undo == 0


def test_plan_without_query_shows_usage():
    '''인자 없으면 그냥 usage 출력 후 리턴 (agent 호출 없음).'''
    msgs = [{'role': 'system', 'content': 's'}]
    new_msgs, wd, undo = main.handle_slash('/plan', msgs, '/tmp', {}, 0)
    # 그대로 반환
    assert new_msgs == msgs


def test_plan_with_query_invokes_run_agent_via_DI(monkeypatch):
    '''/plan에 인자 주면 run_agent 콜백을 통해 agent 실행되어야 함.

    수정 전에는 nested `_run_agent`를 참조해 NameError 발생.
    수정 후에는 handle_slash(..., run_agent=fn) 인자로 주입받아 호출.
    '''
    # context 스니펫 검색 우회 (인덱싱된 게 없을 수 있음)
    monkeypatch.setattr(main, 'get_context_snippets', lambda q, wd, p: '')

    fake_run = MagicMock()
    msgs = [{'role': 'system', 'content': 's'}]
    new_msgs, wd, undo = main.handle_slash(
        '/plan 테스트 작업', msgs, '/tmp', {}, 0,
        run_agent=fake_run,
    )
    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    # 첫 인자는 query
    assert '테스트 작업' in (args[0] if args else kwargs.get('user_input', ''))
    assert kwargs.get('plan_mode') is True


def test_plan_without_run_agent_shows_internal_error():
    '''run_agent 미주입 시: NameError 대신 명확한 내부 오류 메시지로 fail-safe.'''
    msgs = [{'role': 'system', 'content': 's'}]
    new_msgs, wd, undo = main.handle_slash(
        '/plan 어떤 작업', msgs, '/tmp', {}, 0,
        run_agent=None,  # 명시적으로 미주입
    )
    # 크래시하지 않고 그대로 반환되어야 함
    assert new_msgs == msgs


# ── harness_core 위임 회귀 테스트 ─────────────────────────────────────
class TestCoreDelegation:
    '''/clear /undo /cd /init이 harness_core.dispatch로 위임되는지 검증.

    main.py의 _CORE_DELEGATED_SLASHES 화이트리스트 회귀 방지.
    위임이 깨지면 deleted된 dead block이 없으니 명령이 silently 사라진다.
    '''
    def test_cd_via_core(self, tmp_path, monkeypatch):
        # HOME 격리 (~/.harness.toml 간섭 차단)
        monkeypatch.setenv('HOME', str(tmp_path / 'home'))
        (tmp_path / 'home').mkdir()
        msgs = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'x'}]
        new_msgs, wd, undo = main.handle_slash(
            f'/cd {tmp_path}', msgs, '/tmp', {}, 0,
        )
        # 코어 핸들러: working_dir 변경 + 메시지 비움
        assert wd == str(tmp_path)
        assert new_msgs == []

    def test_init_via_core(self, tmp_path):
        msgs = [{'role': 'system', 'content': 's'}]
        new_msgs, wd, undo = main.handle_slash(
            '/init', msgs, str(tmp_path), {}, 0,
        )
        assert (tmp_path / '.harness.toml').exists()
        # 메시지/wd 변경 없음
        assert new_msgs == msgs
        assert wd == str(tmp_path)

    def test_init_does_not_overwrite_via_core(self, tmp_path):
        (tmp_path / '.harness.toml').write_text('# 기존')
        msgs = [{'role': 'system', 'content': 's'}]
        new_msgs, wd, undo = main.handle_slash(
            '/init', msgs, str(tmp_path), {}, 0,
        )
        # 보존
        assert (tmp_path / '.harness.toml').read_text() == '# 기존'

    def test_save_via_core(self, tmp_path, monkeypatch):
        '''/save도 코어 화이트리스트에 포함 — 디스크에 파일 생성.'''
        import session.store as store
        sessions_dir = tmp_path / 'sessions'
        monkeypatch.setattr(store, 'SESSION_DIR', str(sessions_dir))
        msgs = [
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q'},
        ]
        new_msgs, wd, undo = main.handle_slash(
            '/save', msgs, str(tmp_path), {}, 0,
        )
        # 메시지/wd 변경 없음
        assert new_msgs == msgs
        assert wd == str(tmp_path)
        # 디스크 검증
        assert sessions_dir.exists()
        assert any(p.suffix == '.json' for p in sessions_dir.iterdir())

    def test_resume_via_core(self, tmp_path, monkeypatch):
        '''/save → /resume 라운드트립.'''
        import session.store as store
        sessions_dir = tmp_path / 'sessions'
        monkeypatch.setattr(store, 'SESSION_DIR', str(sessions_dir))
        original = [
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'a1'},
        ]
        # save
        main.handle_slash('/save', original, '/tmp/wd', {}, 0)
        # 빈 세션에서 resume
        new_msgs, wd, undo = main.handle_slash(
            '/resume', [], '/tmp/wd', {}, 0,
        )
        assert len(new_msgs) == 3
        assert wd == '/tmp/wd'

    def test_sessions_via_core(self, tmp_path, monkeypatch):
        '''/sessions는 Table 렌더라 결과 검증은 어려움 — 크래시만 안 나면 OK.'''
        import session.store as store
        monkeypatch.setattr(store, 'SESSION_DIR', str(tmp_path / 'sessions'))
        new_msgs, wd, undo = main.handle_slash(
            '/sessions', [], '/tmp', {}, 0,
        )
        # 메시지/wd 변경 없음, 크래시 없이 반환
        assert new_msgs == []
        assert wd == '/tmp'

    def test_files_via_core(self, tmp_path):
        '''/files는 Rich Tree 렌더 — 크래시 없이 반환되면 통합 OK.'''
        (tmp_path / 'a.py').write_text('x')
        (tmp_path / 'sub').mkdir()
        new_msgs, wd, undo = main.handle_slash(
            '/files', [], str(tmp_path), {}, 0,
        )
        assert new_msgs == []
        assert wd == str(tmp_path)
