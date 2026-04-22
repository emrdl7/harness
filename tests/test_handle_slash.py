'''main.handle_slash — slash 디스패치 동작.

핵심: /plan, /retry 등 agent 실행이 필요한 슬래시는 nested `_run_agent`를
참조하면 NameError가 난다. DI(`run_agent` 인자)로 처리해야 한다.
'''
from unittest.mock import MagicMock

import main


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
