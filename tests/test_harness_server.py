'''harness_server.py — 코어 결합 헬퍼 단위 테스트.

서버 본체(async + WebSocket + Session)는 통합 테스트가 까다로워서
순수 함수 헬퍼만 다룬다. UI 호환성 회귀 방지가 목적.
'''
from harness_core import SlashState, SlashResult
import harness_server as srv


def _make_session(messages=None, working_dir='/tmp', profile=None, undo_count=0):
    '''Session 객체를 직접 생성하지 않고 minimal stub로 대체 — Session.__init__가
    HARNESS_CWD/profile 로드 등 부수효과를 가지므로 테스트용 stub.'''
    class _Stub:
        pass
    s = _Stub()
    s.messages = messages if messages is not None else []
    s.working_dir = working_dir
    s.profile = profile if profile is not None else {}
    s.undo_count = undo_count
    return s


class TestToCoreState:
    def test_round_trip_fields(self):
        sess = _make_session(
            messages=[{'role': 'user', 'content': 'x'}],
            working_dir='/foo',
            profile={'language': 'korean'},
            undo_count=3,
        )
        cs = srv._to_core_state(sess)
        assert isinstance(cs, SlashState)
        assert cs.messages == [{'role': 'user', 'content': 'x'}]
        assert cs.working_dir == '/foo'
        assert cs.profile == {'language': 'korean'}
        assert cs.undo_count == 3


class TestApplyCoreResult:
    def test_writes_back_all_fields(self):
        sess = _make_session(messages=[], working_dir='/old', profile={}, undo_count=0)
        new_state = SlashState(
            messages=[{'role': 'system', 'content': 's'}],
            working_dir='/new',
            profile={'model': 'X'},
            undo_count=5,
        )
        result = SlashResult.ok(new_state, '바뀜')
        srv._apply_core_result(sess, result)
        assert sess.messages == [{'role': 'system', 'content': 's'}]
        assert sess.working_dir == '/new'
        assert sess.profile == {'model': 'X'}
        assert sess.undo_count == 5

    def test_round_trip_via_dispatch(self, tmp_path, monkeypatch):
        '''_to_core_state → dispatch('/clear') → _apply_core_result 라운드트립.'''
        from harness_core import dispatch
        sess = _make_session(
            messages=[{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'u'}],
            working_dir=str(tmp_path),
        )
        result = dispatch('/clear', srv._to_core_state(sess))
        srv._apply_core_result(sess, result)
        assert sess.messages == []
        assert sess.working_dir == str(tmp_path)  # 변경 없음
