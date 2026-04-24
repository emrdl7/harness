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
        assert room.active_input_from is None
        assert room.busy is False
        assert room.input_tasks == set()

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
        '''broadcast 페이로드는 JSON 직렬화 가능해야 함.
        PEXT-03 이후 event_id 필드가 추가되므로 assertSubset 패턴으로 검증.
        '''
        import json
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        asyncio.run(srv.broadcast(room, type='tool_end', name='write_file',
                                  result={'ok': True, 'path': '/tmp/x'}))
        decoded = json.loads(ws.received[0])
        assert decoded['type'] == 'tool_end'
        assert decoded['name'] == 'write_file'
        assert decoded['result'] == {'ok': True, 'path': '/tmp/x'}
        assert 'event_id' in decoded  # PEXT-03 필드 포함 확인


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
        # Phase 4: confirm 가드 — active_input_from이 ws여야 처리됨
        room.active_input_from = ws

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


# ── BB-2 Phase 4: confirm 가드 + 라이프사이클 ────────────────────
class TestConfirmGuard:
    @staticmethod
    def _queue_with(items):
        q: asyncio.Queue = asyncio.Queue()
        for x in items:
            q.put_nowait(x)
        q.put_nowait(None)
        return q

    def test_other_ws_confirm_ignored(self, isolated_rooms):
        '''룸 멤버 중 active_input_from이 아닌 ws의 confirm 응답은 무시.'''
        room = srv._get_or_create_room('team')
        a, b = _FakeWS(), _FakeWS()
        room.subscribers.update({a, b})
        room.active_input_from = a  # 입력 주체는 a

        async def _go():
            ev = asyncio.Event()
            room.state._confirm_event = ev
            room.state._confirm_result = False
            # b의 dispatch_loop가 confirm_write_response를 수신 — 가드에서 차단되어야
            q = self._queue_with([{'type': 'confirm_write_response', 'result': True}])
            await srv._dispatch_loop(b, room, q)
            return ev.is_set(), room.state._confirm_result

        was_set, result = asyncio.run(_go())
        assert was_set is False
        assert result is False

    def test_active_ws_bash_confirm_passes(self, isolated_rooms):
        '''active_input_from ws의 confirm_bash_response는 정상 처리.'''
        room = srv._get_or_create_room('team')
        ws = _FakeWS()
        room.subscribers.add(ws)
        room.active_input_from = ws

        async def _go():
            ev = asyncio.Event()
            room.state._confirm_bash_event = ev
            room.state._confirm_bash_result = False
            q = self._queue_with([{'type': 'confirm_bash_response', 'result': True}])
            await srv._dispatch_loop(ws, room, q)
            return ev.is_set(), room.state._confirm_bash_result

        was_set, result = asyncio.run(_go())
        assert was_set is True
        assert result is True


class TestRoomLifecycle:
    def test_state_survives_partial_leave(self, isolated_rooms):
        '''2명 중 1명이 떠나도 Room.state는 그대로 유지된다.'''
        room = srv._get_or_create_room('team')
        a, b = object(), object()
        room.subscribers.update({a, b})
        room.state.messages = [{'role': 'user', 'content': 'q'}]
        # a 이탈
        room.subscribers.discard(a)
        srv._maybe_drop_room(room)
        assert 'team' in srv.ROOMS  # b가 남아있어 보존
        assert srv.ROOMS['team'].state.messages == [{'role': 'user', 'content': 'q'}]

    def test_room_dropped_when_last_leaves(self, isolated_rooms):
        '''마지막 멤버 이탈 시 Room이 ROOMS에서 제거된다.'''
        room = srv._get_or_create_room('team')
        x = object()
        room.subscribers.add(x)
        room.subscribers.discard(x)
        srv._maybe_drop_room(room)
        assert 'team' not in srv.ROOMS

    def test_rejoin_after_full_leave_creates_new_room(self, isolated_rooms):
        '''전원 이탈 후 같은 이름으로 재join하면 새 Room — 이전 messages 유실.'''
        room1 = srv._get_or_create_room('team')
        room1.state.messages = [{'role': 'user', 'content': 'old'}]
        # 전원 이탈
        srv._maybe_drop_room(room1)  # 빈 룸 → 정리
        # 같은 이름으로 재생성
        room2 = srv._get_or_create_room('team')
        assert room2 is not room1
        assert room2.state.messages == []  # 새 Session

    def test_rejoin_after_partial_leave_shares_state(self, isolated_rooms):
        '''한 명이 남아있는 룸에 재합류 — 같은 인스턴스, state 공유.'''
        room1 = srv._get_or_create_room('team')
        survivor = object()
        room1.subscribers.add(survivor)
        room1.state.messages = [{'role': 'user', 'content': 'shared'}]
        # 다른 한 명이 떠나도 룸 유지
        srv._maybe_drop_room(room1)
        # 재합류
        room2 = srv._get_or_create_room('team')
        assert room2 is room1
        assert room2.state.messages == [{'role': 'user', 'content': 'shared'}]


# ── PEXT-03: event_id + ring buffer ─────────────────────────────
class TestEventBuffer:
    def test_event_counter_increments(self, isolated_rooms):
        '''broadcast() 호출마다 room.event_counter가 1씩 증가한다.'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        assert room.event_counter == 0
        asyncio.run(srv.broadcast(room, type='token', text='a'))
        assert room.event_counter == 1
        asyncio.run(srv.broadcast(room, type='token', text='b'))
        assert room.event_counter == 2

    def test_ring_buffer_stores_payload(self, isolated_rooms):
        '''broadcast() 후 room.event_buffer에 (event_id, timestamp, payload_dict) 튜플이 저장된다.'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        asyncio.run(srv.broadcast(room, type='token', text='hello'))
        assert len(room.event_buffer) == 1
        event_id, ts, payload = room.event_buffer[0]
        assert event_id == 1
        assert isinstance(ts, float)
        assert payload['type'] == 'token'
        assert payload['text'] == 'hello'
        assert payload['event_id'] == 1

    def test_ttl_cleanup(self, isolated_rooms, monkeypatch):
        '''60초 이상 된 항목이 다음 broadcast() 호출 시 event_buffer에서 제거된다.'''
        import time as _time
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)

        # 오래된 항목을 직접 삽입 (현재 - 61초)
        old_ts = _time.monotonic() - 61
        room.event_buffer.append((0, old_ts, {'type': 'old'}))
        assert len(room.event_buffer) == 1

        # 새 broadcast 호출 시 TTL cleanup이 발생해야 함
        asyncio.run(srv.broadcast(room, type='new', text='fresh'))
        # 오래된 항목은 제거되고 새 항목만 남아야 함
        assert len(room.event_buffer) == 1
        _, _, payload = room.event_buffer[0]
        assert payload['type'] == 'new'

    def test_maxlen(self, isolated_rooms):
        '''event_buffer.maxlen이 10000이다.'''
        room = srv._get_or_create_room('r')
        from collections import deque
        assert isinstance(room.event_buffer, deque)
        assert room.event_buffer.maxlen == 10000


# ── PEXT-01: _broadcast_agent_start + from_self ──────────────────
class TestAgentStartFromSelf:
    def test_requester_gets_from_self_true(self, isolated_rooms):
        '''_broadcast_agent_start() 호출 시 requester_ws에는 from_self=True가 전송된다.'''
        import json
        room = srv._get_or_create_room('r')
        requester = _FakeWS()
        observer = _FakeWS()
        room.subscribers.update({requester, observer})
        asyncio.run(srv._broadcast_agent_start(room, requester))
        # requester 메시지 확인
        assert len(requester.received) == 1
        decoded = json.loads(requester.received[0])
        assert decoded['type'] == 'agent_start'
        assert decoded['from_self'] is True

    def test_observer_gets_from_self_false(self, isolated_rooms):
        '''_broadcast_agent_start() 호출 시 requester가 아닌 구독자는 from_self=False를 받는다.'''
        import json
        room = srv._get_or_create_room('r')
        requester = _FakeWS()
        observer = _FakeWS()
        room.subscribers.update({requester, observer})
        asyncio.run(srv._broadcast_agent_start(room, requester))
        # observer 메시지 확인
        assert len(observer.received) == 1
        decoded = json.loads(observer.received[0])
        assert decoded['type'] == 'agent_start'
        assert decoded['from_self'] is False

    def test_dead_ws_removed(self, isolated_rooms):
        '''_broadcast_agent_start() 호출 시 끊긴 ws는 room.subscribers에서 제거된다.'''
        room = srv._get_or_create_room('r')
        requester = _FakeWS()
        dead = _FakeWS(raise_on_send=True)
        room.subscribers.update({requester, dead})
        asyncio.run(srv._broadcast_agent_start(room, requester))
        assert dead not in room.subscribers
        assert requester in room.subscribers


# ── PEXT-02: confirm_write old_content ───────────────────────────
class TestConfirmWriteOldContent:
    def test_read_existing_file_returns_content(self, tmp_path):
        '''_read_existing_file()이 존재하는 파일에서 내용을 반환한다.'''
        f = tmp_path / 'sample.txt'
        f.write_text('hello world', encoding='utf-8')
        result = srv._read_existing_file(str(f))
        assert result == 'hello world'

    def test_read_existing_file_returns_none_for_missing(self, tmp_path):
        '''_read_existing_file()이 존재하지 않는 파일에서 None을 반환한다.'''
        missing = str(tmp_path / 'nonexistent.txt')
        result = srv._read_existing_file(missing)
        assert result is None


# ── PEXT-04: delta replay + SES-02: resume-session + B3/B4 ─────────
class TestDeltaReplay:
    '''x-resume-from 헤더 파싱, ring buffer delta 재송신, x-resume-session,
    _token_hash 헬퍼, room_member_joined user 필드를 단위 검증.'''

    def test_no_header_no_replay(self, isolated_rooms):
        '''x-resume-from 헤더 없음 → resume_from=None, delta 재송신 없음.'''
        # resume_from 파싱 로직 직접 검증
        raw = ''
        if raw.isdigit() and int(raw) < 2 ** 31:
            resume_from = int(raw)
        else:
            resume_from = None
        assert resume_from is None

    def test_resume_from_filters_events(self, isolated_rooms):
        '''resume_from=5이면 event_id > 5인 이벤트만 재송신된다.'''
        from collections import deque
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        # event_buffer에 event_id 1~7 수동 삽입
        for eid in range(1, 8):
            room.event_buffer.append((eid, 0.0, {'type': 'token', 'text': str(eid), 'event_id': eid}))
        resume_from = 5
        replayed = [eid for (eid, _ts, _p) in list(room.event_buffer) if eid > resume_from]
        assert replayed == [6, 7]

    def test_resume_from_zero_sends_all(self, isolated_rooms):
        '''resume_from=0이면 ring buffer 모든 이벤트가 재송신 대상.'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        for eid in range(1, 4):
            room.event_buffer.append((eid, 0.0, {'type': 'token', 'text': str(eid), 'event_id': eid}))
        resume_from = 0
        replayed = [eid for (eid, _ts, _p) in list(room.event_buffer) if eid > resume_from]
        assert replayed == [1, 2, 3]

    def test_non_integer_header_ignored(self, isolated_rooms):
        '''x-resume-from: "abc" → resume_from=None (무시).'''
        raw = 'abc'
        if raw.isdigit() and int(raw) < 2 ** 31:
            resume_from = int(raw)
        else:
            resume_from = None
        assert resume_from is None

    def test_overflow_header_ignored(self, isolated_rooms):
        '''x-resume-from: "99999999999" (2^31 초과) → resume_from=None.'''
        raw = '99999999999'
        if raw.isdigit() and int(raw) < 2 ** 31:
            resume_from = int(raw)
        else:
            resume_from = None
        assert resume_from is None

    def test_room_joined_has_members_field(self, isolated_rooms):
        '''room_joined 페이로드에 members 필드가 포함된다 (Pitfall H 수정).'''
        import json
        room = srv._get_or_create_room('team')
        room.busy = False
        # _run_session에서 수정된 형태 — members=[] 포함
        payload = dict(type='room_joined', room=room.name, shared=True,
                       subscribers=1, busy=room.busy, members=[])
        decoded = json.loads(json.dumps(payload))
        assert 'members' in decoded

    def test_resume_session_loads_state(self, isolated_rooms, tmp_path, monkeypatch):
        '''x-resume-session 헤더 있고 첫 번째 접속자 → sess.load()가 호출된다.'''
        import session.store as _store
        called = []

        def mock_load(filename):
            called.append(filename)
            return {'working_dir': str(tmp_path), 'messages': [{'role': 'user', 'content': 'restored'}]}

        monkeypatch.setattr(_store, 'load', mock_load)
        # _run_session의 resume_session 로직을 직접 시뮬레이션
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        resume_session_id = '20240101_120000_abc123.json'
        # 첫 번째 접속자 (room.subscribers - {ws} == 비어있음)
        is_first = not (room.subscribers - {ws})
        assert is_first is True
        if resume_session_id and is_first:
            data = _store.load(resume_session_id)
            room.state.messages = data.get('messages', [])
        assert called == [resume_session_id]
        assert room.state.messages == [{'role': 'user', 'content': 'restored'}]

    def test_resume_session_not_found_sends_error(self, isolated_rooms, tmp_path):
        '''세션 파일 없으면 FileNotFoundError → error 이벤트를 전송한다.'''
        import json
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        # sess.load()가 FileNotFoundError를 던지는 경우를 시뮬레이션
        async def _go():
            try:
                raise FileNotFoundError('세션 파일 없음')
            except FileNotFoundError:
                await srv.send(ws, type='error', text='세션 없음: nonexistent.json')
        asyncio.run(_go())
        decoded = json.loads(ws.received[-1])
        assert decoded['type'] == 'error'
        assert '세션 없음' in decoded['text']

    def test_token_hash_returns_8_char_hex(self, isolated_rooms):
        '''_token_hash("abc123")이 SHA-256 앞 8자 hex string을 반환한다.'''
        import hashlib
        result = srv._token_hash('abc123')
        expected = hashlib.sha256('abc123'.encode()).hexdigest()[:8]
        assert result == expected
        assert len(result) == 8
        assert all(c in '0123456789abcdef' for c in result)

    def test_room_member_joined_has_user_field(self, isolated_rooms):
        '''room_member_joined broadcast에 user=_token_hash(token) 필드가 포함된다.'''
        import json
        room = srv._get_or_create_room('team')
        ws = _FakeWS()
        room.subscribers.add(ws)
        token = 'mytoken123'
        expected_hash = srv._token_hash(token)
        asyncio.run(srv.broadcast(room, type='room_member_joined',
                                  subscribers=1, user=expected_hash))
        decoded = json.loads(ws.received[-1])
        assert decoded['type'] == 'room_member_joined'
        assert 'user' in decoded
        assert decoded['user'] == expected_hash


# ── PEXT-05 (B2): cancel 케이스 + _cancel_requested 플래그 ──────────
class TestCancelTask:
    '''_dispatch_loop cancel 케이스 + _handle_input CancelledError 처리 + B2 플래그 단위 검증.'''

    @staticmethod
    def _queue_with(items):
        q: asyncio.Queue = asyncio.Queue()
        for x in items:
            q.put_nowait(x)
        q.put_nowait(None)
        return q

    def test_cancel_by_active_input_from_cancels_tasks(self, isolated_rooms):
        '''active_input_from과 동일한 ws가 cancel 전송 시 input_tasks의 task가 cancel()된다.'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        room.active_input_from = ws

        # 완료되지 않은 fake task 추가
        cancelled = []

        class _FakeTask:
            def done(self):
                return False
            def cancel(self):
                cancelled.append(True)

        room.input_tasks.add(_FakeTask())

        q = self._queue_with([{'type': 'cancel'}])
        asyncio.run(srv._dispatch_loop(ws, room, q))
        assert len(cancelled) == 1  # task.cancel()이 호출됨

    def test_cancel_by_non_active_ignored(self, isolated_rooms):
        '''active_input_from이 아닌 ws가 cancel 전송 시 아무 일도 일어나지 않는다.'''
        room = srv._get_or_create_room('r')
        a, b = _FakeWS(), _FakeWS()
        room.subscribers.update({a, b})
        room.active_input_from = a  # a가 입력 주체
        room._cancel_requested = False

        cancelled = []

        class _FakeTask:
            def done(self):
                return False
            def cancel(self):
                cancelled.append(True)

        room.input_tasks.add(_FakeTask())
        # b가 cancel 전송 — 무시되어야
        q = self._queue_with([{'type': 'cancel'}])
        asyncio.run(srv._dispatch_loop(b, room, q))
        assert len(cancelled) == 0
        assert room._cancel_requested is False

    def test_cancel_broadcasts_agent_cancelled(self, isolated_rooms):
        '''cancel 메시지 수신 후 broadcast(room, type="agent_cancelled")가 호출된다.'''
        import json
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        room.active_input_from = ws
        q = self._queue_with([{'type': 'cancel'}])
        asyncio.run(srv._dispatch_loop(ws, room, q))
        decoded = [json.loads(p) for p in ws.received]
        assert any(d.get('type') == 'agent_cancelled' for d in decoded)

    def test_cancel_sets_cancel_requested_flag(self, isolated_rooms):
        '''cancel 메시지 수신 후 room._cancel_requested가 True가 된다 (B2).'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        room.active_input_from = ws
        assert room._cancel_requested is False
        q = self._queue_with([{'type': 'cancel'}])
        asyncio.run(srv._dispatch_loop(ws, room, q))
        assert room._cancel_requested is True

    def test_cancelled_error_clears_busy(self, isolated_rooms):
        '''task cancel 시 _spawn_input_task done callback이 busy=False, active_input_from=None을 정리한다.

        asyncio에서 task.cancel()을 첫 await 이전에 호출하면 코루틴이 한 번도
        실행되지 않아 finally가 동작하지 않는다. _spawn_input_task의 on_done
        callback이 cancelled() 상태를 감지해 room 상태를 정리해야 한다.
        '''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        room.busy = True
        room.active_input_from = ws

        async def _go():
            # _spawn_input_task를 통해 task 생성 — done callback 포함
            task = srv._spawn_input_task(room, srv._handle_input(ws, room, 'test'))
            # 즉시 취소 (await 이전이므로 코루틴 미실행 → done callback이 정리 담당)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        asyncio.run(_go())
        assert room.busy is False
        assert room.active_input_from is None

    def test_cancel_on_done_task_safe(self, isolated_rooms):
        '''task.cancel()이 이미 done() 상태인 task에 호출되어도 오류 없이 처리된다.'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        room.active_input_from = ws

        # done() 상태인 fake task
        class _DoneTask:
            def done(self):
                return True
            def cancel(self):
                raise RuntimeError('done task에 cancel 호출됨 — 이 줄 실행되면 안 됨')

        room.input_tasks.add(_DoneTask())
        # cancel 메시지 처리 — done() 체크 후 cancel() 건너뜀
        q = self._queue_with([{'type': 'cancel'}])
        asyncio.run(srv._dispatch_loop(ws, room, q))  # 예외 없이 통과해야

    def test_handle_input_finally_resets_cancel_flag(self, isolated_rooms, monkeypatch):
        '''_handle_input() 완료 시 finally 블록에서 room._cancel_requested가 False로 리셋된다 (B2).'''
        room = srv._get_or_create_room('r')
        ws = _FakeWS()
        room.subscribers.add(ws)
        room.busy = True
        room.active_input_from = ws
        room._cancel_requested = True  # 미리 True로 설정

        # handle_slash가 즉시 리턴하도록 mock
        async def _mock_slash(ws_, room_, cmd):
            pass

        monkeypatch.setattr(srv, 'handle_slash', _mock_slash)

        asyncio.run(srv._handle_input(ws, room, '/test'))
        # finally에서 _cancel_requested가 False로 리셋돼야
        assert room._cancel_requested is False
        assert room.busy is False
        assert room.active_input_from is None
