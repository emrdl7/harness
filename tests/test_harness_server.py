'''harness_server.py — 코어 결합 헬퍼 단위 테스트.

서버 본체(async + WebSocket + Session)는 통합 테스트가 까다로워서
순수 함수 헬퍼만 다룬다. UI 호환성 회귀 방지가 목적.
'''
import asyncio

import pytest

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


# ── BB-2 Phase 1: Room/ROOMS 헬퍼 ────────────────────────────────
@pytest.fixture
def isolated_rooms(tmp_path, monkeypatch):
    '''ROOMS 전역을 격리하고, Session 생성이 깨끗한 임시 디렉토리에서 일어나도록.'''
    monkeypatch.setenv('HARNESS_CWD', str(tmp_path))
    saved = dict(srv.ROOMS)
    srv.ROOMS.clear()
    yield
    srv.ROOMS.clear()
    srv.ROOMS.update(saved)


class TestRoom:
    def test_dataclass_defaults(self, isolated_rooms):
        room = srv.Room(name='r1', state=srv.Session())
        assert room.name == 'r1'
        assert isinstance(room.state, srv.Session)
        assert room.subscribers == set()
        assert isinstance(room.input_lock, asyncio.Lock)
        assert room.active_input_from is None

    def test_get_or_create_returns_same_instance_for_same_name(self, isolated_rooms):
        a = srv._get_or_create_room('team')
        b = srv._get_or_create_room('team')
        assert a is b
        assert a.state is b.state  # Session 공유 — 핵심

    def test_get_or_create_isolates_different_names(self, isolated_rooms):
        a = srv._get_or_create_room('alpha')
        b = srv._get_or_create_room('beta')
        assert a is not b
        assert a.state is not b.state

    def test_solo_uuid_rooms_are_unique(self, isolated_rooms):
        '''솔로 모드(헤더 없음)는 매 연결마다 다른 UUID 룸을 받아 격리된다.'''
        import uuid as _u
        n1 = f'_solo_{_u.uuid4().hex}'
        n2 = f'_solo_{_u.uuid4().hex}'
        r1 = srv._get_or_create_room(n1)
        r2 = srv._get_or_create_room(n2)
        assert r1 is not r2
        assert r1.state is not r2.state

    def test_maybe_drop_removes_empty_room(self, isolated_rooms):
        room = srv._get_or_create_room('temp')
        assert 'temp' in srv.ROOMS
        srv._maybe_drop_room(room)
        assert 'temp' not in srv.ROOMS

    def test_maybe_drop_keeps_room_with_subscribers(self, isolated_rooms):
        room = srv._get_or_create_room('keep')
        room.subscribers.add(object())  # 가짜 ws
        srv._maybe_drop_room(room)
        assert 'keep' in srv.ROOMS

    def test_maybe_drop_no_op_when_room_already_gone(self, isolated_rooms):
        '''경합 시 다른 finally가 먼저 정리한 경우 — KeyError 안 나야 함.'''
        room = srv.Room(name='ghost', state=srv.Session())
        # ROOMS에 등록 안 된 상태 — _maybe_drop_room이 아무것도 하지 않아야 함
        srv._maybe_drop_room(room)  # raises 없으면 통과
        assert 'ghost' not in srv.ROOMS

    def test_maybe_drop_does_not_remove_replacement_room(self, isolated_rooms):
        '''같은 이름이지만 다른 인스턴스가 ROOMS에 있을 때 (재생성 케이스) 보호.'''
        old = srv.Room(name='dup', state=srv.Session())
        new = srv._get_or_create_room('dup')  # ROOMS['dup'] = new
        assert srv.ROOMS['dup'] is new
        srv._maybe_drop_room(old)  # old는 ROOMS에 없으므로 no-op
        assert srv.ROOMS.get('dup') is new
