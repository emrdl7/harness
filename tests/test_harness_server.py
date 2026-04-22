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


# ── BB-2 Phase 2: broadcast / broadcast_state ────────────────────
class _FakeWS:
    '''ws.send(payload)만 흉내내는 stub. raise=True면 BrokenPipeError 시뮬.'''
    def __init__(self, raise_on_send=False):
        self.received: list[str] = []
        self.raise_on_send = raise_on_send

    async def send(self, payload):
        if self.raise_on_send:
            raise BrokenPipeError('simulated dead ws')
        self.received.append(payload)


class TestBroadcast:
    def test_single_subscriber_receives(self, isolated_rooms):
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        asyncio.run(srv.broadcast(room, type='token', text='hi'))
        assert len(ws.received) == 1
        assert '"text": "hi"' in ws.received[0]
        assert '"type": "token"' in ws.received[0]

    def test_multiple_subscribers_get_same_payload(self, isolated_rooms):
        room = srv._get_or_create_room('r')
        a, b, c = _FakeWS(), _FakeWS(), _FakeWS()
        room.subscribers.update({a, b, c})
        asyncio.run(srv.broadcast(room, type='agent_end'))
        assert a.received == b.received == c.received
        assert len(a.received) == 1

    def test_dead_subscribers_are_pruned(self, isolated_rooms):
        '''send에서 예외 던지는 ws는 broadcast 후 subscribers에서 제거된다.'''
        room = srv._get_or_create_room('r')
        alive = _FakeWS()
        dead = _FakeWS(raise_on_send=True)
        room.subscribers.update({alive, dead})
        asyncio.run(srv.broadcast(room, type='ping'))
        assert alive in room.subscribers
        assert dead not in room.subscribers
        assert len(alive.received) == 1

    def test_empty_room_is_noop(self, isolated_rooms):
        '''subscribers가 비어있어도 예외 없이 통과.'''
        room = srv._get_or_create_room('r')
        room.subscribers.clear()
        asyncio.run(srv.broadcast(room, type='whatever'))  # 예외 안 나면 통과

    def test_payload_is_valid_json(self, isolated_rooms):
        '''broadcast 페이로드는 JSON 직렬화 가능해야 함.'''
        import json
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        asyncio.run(srv.broadcast(room, type='tool_end', name='write_file',
                                  result={'ok': True, 'path': '/tmp/x'}))
        decoded = json.loads(ws.received[0])
        assert decoded == {'type': 'tool_end', 'name': 'write_file',
                           'result': {'ok': True, 'path': '/tmp/x'}}


class TestBroadcastState:
    def test_state_payload_reaches_all_subscribers(self, isolated_rooms):
        import json
        room = srv._get_or_create_room('r')
        room.state.messages = [
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'user', 'content': 'q2'},
        ]
        a, b = _FakeWS(), _FakeWS()
        room.subscribers.update({a, b})
        asyncio.run(srv.broadcast_state(room))
        assert len(a.received) == 1 and len(b.received) == 1
        decoded = json.loads(a.received[0])
        assert decoded['type'] == 'state'
        assert decoded['turns'] == 2  # user 메시지만 셈
        assert decoded['working_dir'] == room.state.working_dir
        assert 'compact_count' in decoded
        assert 'claude_available' in decoded


# ── BB-2 Phase 2.5: reader/dispatch + busy turn-taking ──────────
class TestRoomBusyDefaults:
    def test_initial_state(self, isolated_rooms):
        '''신규 Room은 busy/active_input_from 미설정, input_tasks 비어있음.'''
        room = srv._get_or_create_room('r')
        assert room.busy is False
        assert room.active_input_from is None
        assert room.input_tasks == set()


class TestSpawnInputTask:
    def test_task_kept_in_set_until_done(self, isolated_rooms):
        '''create_task GC 회피 — input_tasks에 추가되고 완료 후 자동 제거.'''
        room = srv._get_or_create_room('r')

        async def _payload():
            return 'done'

        async def _go():
            t = srv._spawn_input_task(room, _payload())
            assert t in room.input_tasks
            await t
            return t

        task = asyncio.run(_go())
        # done callback이 즉시 실행됐는지 확인 — asyncio.run 종료 후 자연스럽게 비어있음
        assert task.done()


class TestDispatchLoop:
    @staticmethod
    def _make_queue(items):
        '''미리 준비한 메시지 리스트를 담은 asyncio.Queue 반환 (None 종료 포함).'''
        q: asyncio.Queue = asyncio.Queue()
        for item in items:
            q.put_nowait(item)
        q.put_nowait(None)
        return q

    def test_ping_returns_pong(self, isolated_rooms):
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        q = self._make_queue([{'type': 'ping'}])
        asyncio.run(srv._dispatch_loop(ws, room, q))
        assert any('"type": "pong"' in p for p in ws.received)

    def test_confirm_response_sets_event_and_result(self, isolated_rooms):
        '''confirm_*_response가 즉시 처리되어 state.event를 set한다 (deadlock 회피 핵심).'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)

        async def _go():
            ev = asyncio.Event()
            room.state._confirm_event = ev
            room.state._confirm_result = False
            q = self._make_queue([
                {'type': 'confirm_write_response', 'result': True},
            ])
            await srv._dispatch_loop(ws, room, q)
            return ev.is_set(), room.state._confirm_result

        was_set, result = asyncio.run(_go())
        assert was_set is True
        assert result is True

    def test_input_busy_rejects_second(self, isolated_rooms, monkeypatch):
        '''두 번째 input이 들어오면 room_busy로 거부 (DQ3).

        첫 번째 input은 spawn되어 busy=True 상태로 진행 중. 두 번째는
        busy 체크에서 broadcast로 거부.
        '''
        import json as _json

        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)

        # _handle_input을 잠시 멈추는 fake로 교체 — 첫 task가 진짜 busy 상태로 머물게.
        slow_started = asyncio.Event()
        slow_release = asyncio.Event()

        async def _slow(ws_, room_, text_):
            try:
                slow_started.set()
                await slow_release.wait()
            finally:
                room_.busy = False
                room_.active_input_from = None

        monkeypatch.setattr(srv, '_handle_input', _slow)

        async def _go():
            q: asyncio.Queue = asyncio.Queue()
            q.put_nowait({'type': 'input', 'text': 'first'})
            # dispatch_loop를 background에서 돌리고, 첫 task가 busy=True 잡을 시간을 줌
            dispatch_task = asyncio.create_task(srv._dispatch_loop(ws, room, q))
            await slow_started.wait()
            assert room.busy is True
            assert room.active_input_from is ws
            # 두 번째 input — busy라 거부되어야
            q.put_nowait({'type': 'input', 'text': 'second'})
            # 거부 메시지 broadcast가 돌도록 잠시 양보
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            # spawn된 첫 task 풀어주고 dispatch 종료
            slow_release.set()
            q.put_nowait(None)
            await dispatch_task

        asyncio.run(_go())
        decoded = [_json.loads(p) for p in ws.received]
        # room_busy가 한 번 도달해야 함
        assert any(d.get('type') == 'room_busy' for d in decoded)

    def test_empty_input_ignored(self, isolated_rooms):
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        q = self._make_queue([{'type': 'input', 'text': '   '}])
        asyncio.run(srv._dispatch_loop(ws, room, q))
        # busy 변화 없음, ws에 아무것도 안 보냄
        assert room.busy is False
        assert ws.received == []

    def test_cplan_execute_busy_check(self, isolated_rooms, monkeypatch):
        '''cplan_execute도 busy 시 거부된다.'''
        import json as _json
        room = srv._get_or_create_room('r')
        room.busy = True  # 미리 busy 상태
        ws = _FakeWS()
        room.subscribers.add(ws)
        q = self._make_queue([{'type': 'cplan_execute', 'task': 'do something'}])
        asyncio.run(srv._dispatch_loop(ws, room, q))
        decoded = [_json.loads(p) for p in ws.received]
        assert any(d.get('type') == 'room_busy' for d in decoded)


class TestReaderLoop:
    def test_invalid_json_skipped_then_none(self, isolated_rooms):
        '''JSON 파싱 실패는 무시, ws 종료 시 None.'''
        from websockets.exceptions import ConnectionClosed

        class _ClosingWS:
            '''몇 개 메시지를 yield 후 ConnectionClosed 발생.'''
            def __init__(self, items):
                self.items = items

            def __aiter__(self):
                self._iter = iter(self.items)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise ConnectionClosed(None, None)

        async def _go():
            ws = _ClosingWS(['not json', '{"type":"ping"}'])
            q: asyncio.Queue = asyncio.Queue()
            await srv._reader_loop(ws, q)
            collected = []
            while not q.empty():
                collected.append(await q.get())
            return collected

        items = asyncio.run(_go())
        # 잘못된 JSON은 스킵, 유효한 메시지만 + 종료 None
        assert items == [{'type': 'ping'}, None]


# ── BB-2 Phase 3: /who + room_joined ────────────────────────────
class TestSlashWho:
    @staticmethod
    def _decode(ws):
        import json
        return [json.loads(p) for p in ws.received]

    def test_who_returns_member_count(self, isolated_rooms):
        '''/who는 subscribers 카운트 + members 배열을 반환한다.'''
        room = srv._get_or_create_room('team')
        a, b = _FakeWS(), _FakeWS()
        room.subscribers.update({a, b})
        asyncio.run(srv.handle_slash(a, room, '/who'))
        msgs = self._decode(a)
        who = next(m for m in msgs if m.get('type') == 'slash_result' and m.get('cmd') == 'who')
        assert who['count'] == 2
        assert who['shared'] is True
        assert who['busy'] is False
        assert len(who['members']) == 2
        # 자기 자신은 self=True인 멤버 정확히 1개
        selfs = [m for m in who['members'] if m['self']]
        assert len(selfs) == 1

    def test_who_marks_solo_room(self, isolated_rooms):
        '''솔로 룸(_solo_ 접두)은 shared=false.'''
        room = srv._get_or_create_room('_solo_abc')
        ws = _FakeWS()
        room.subscribers.add(ws)
        asyncio.run(srv.handle_slash(ws, room, '/who'))
        who = next(m for m in self._decode(ws)
                   if m.get('type') == 'slash_result' and m.get('cmd') == 'who')
        assert who['shared'] is False
        assert who['count'] == 1

    def test_who_active_marker(self, isolated_rooms):
        '''active_input_from으로 지정된 ws는 active=True.'''
        room = srv._get_or_create_room('team')
        a, b = _FakeWS(), _FakeWS()
        room.subscribers.update({a, b})
        room.active_input_from = b
        room.busy = True
        asyncio.run(srv.handle_slash(a, room, '/who'))
        who = next(m for m in self._decode(a)
                   if m.get('type') == 'slash_result' and m.get('cmd') == 'who')
        assert who['busy'] is True
        # 활성 멤버는 b 1명만
        actives = [m for m in who['members'] if m['active']]
        assert len(actives) == 1


class TestRoomJoinedShape:
    '''_run_session 직접 통합은 복잡 — room_joined 페이로드 형태만 단위 검증.

    실제 송신 경로는 _run_session 내부에 인라인이라 함수 추출 X. 페이로드의
    JSON 직렬화 가능성과 필드 셋만 확인.
    '''
    def test_payload_serializable(self, isolated_rooms):
        import json
        room = srv._get_or_create_room('team')
        room.busy = False
        # _run_session이 보내는 것과 동일한 형태
        payload = dict(type='room_joined', room=room.name, shared=True,
                       subscribers=1, busy=room.busy)
        s = json.dumps(payload)
        decoded = json.loads(s)
        assert decoded['type'] == 'room_joined'
        assert decoded['shared'] is True
        assert 'subscribers' in decoded
        assert 'busy' in decoded

    def test_state_snapshot_carries_messages(self, isolated_rooms):
        import json
        room = srv._get_or_create_room('team')
        room.state.messages = [
            {'role': 'system', 'content': 's'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'a1'},
        ]
        # _run_session에서 송신하는 형태
        turns = len([m for m in room.state.messages if m['role'] == 'user'])
        payload = dict(type='state_snapshot', turns=turns, messages=room.state.messages)
        decoded = json.loads(json.dumps(payload))
        assert decoded['turns'] == 1
        assert len(decoded['messages']) == 3
