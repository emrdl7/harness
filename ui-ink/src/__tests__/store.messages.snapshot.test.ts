// Phase 3 loadSnapshot + dispatch 확장 테스트 (REM-02~05, PEXT-01/05, DIFF-01/03)
// TDD RED: 구현 전 실패 테스트
import {describe, it, expect, beforeEach} from 'vitest'
import {useMessagesStore} from '../store/messages.js'
import {useRoomStore} from '../store/room.js'
import {useStatusStore} from '../store/status.js'
import {dispatch} from '../ws/dispatch.js'

describe('loadSnapshot (REM-03)', () => {
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null, snapshotKey: 0})
  })

  it('Test 1: loadSnapshot([]) 호출 시 completedMessages가 빈 배열이 되고 snapshotKey가 1 증가한다', () => {
    useMessagesStore.getState().loadSnapshot([])
    const {completedMessages, snapshotKey} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(0)
    expect(snapshotKey).toBe(1)
  })

  it('Test 2: loadSnapshot([{role:"user", content:"hi"}]) 호출 시 completedMessages에 id가 부여된 메시지가 로드된다', () => {
    useMessagesStore.getState().loadSnapshot([{role: 'user', content: 'hi'}])
    const {completedMessages} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(1)
    expect(completedMessages[0].role).toBe('user')
    expect(completedMessages[0].content).toBe('hi')
    expect(typeof completedMessages[0].id).toBe('string')
    expect(completedMessages[0].id.length).toBeGreaterThan(0)
  })

  it('Test 3: loadSnapshot() 호출 후 activeMessage가 null이 된다', () => {
    // activeMessage가 있는 상태에서 loadSnapshot 호출
    useMessagesStore.getState().agentStart()
    expect(useMessagesStore.getState().activeMessage).not.toBeNull()
    useMessagesStore.getState().loadSnapshot([])
    expect(useMessagesStore.getState().activeMessage).toBeNull()
  })
})

describe('dispatch 확장 (PEXT-01/05, DIFF-03)', () => {
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null, snapshotKey: 0})
    useStatusStore.setState({busy: false, connected: false})
    useRoomStore.setState({
      roomName: '', members: [], activeInputFrom: null, activeIsSelf: true, busy: false,
      wsState: 'connected', reconnectAttempt: 0, lastEventId: null,
    })
  })

  it('Test 4: dispatch agent_start {from_self: false} 후 room.activeIsSelf가 false가 된다', () => {
    dispatch({type: 'agent_start', from_self: false})
    expect(useRoomStore.getState().activeIsSelf).toBe(false)
  })

  it('Test 5: dispatch agent_start {} (from_self 없음) 후 room.activeIsSelf가 true가 된다 (구버전 호환)', () => {
    // from_self 필드 없이 전송되는 구버전 서버 호환
    dispatch({type: 'agent_start'})
    expect(useRoomStore.getState().activeIsSelf).toBe(true)
  })

  it('Test 6: dispatch agent_cancelled 후 busy가 false가 된다', () => {
    useStatusStore.setState({busy: true})
    dispatch({type: 'agent_cancelled'})
    expect(useStatusStore.getState().busy).toBe(false)
  })

  it('Test 7: event_id: 42가 있는 메시지 수신 시 room.lastEventId가 42가 된다', () => {
    // event_id 필드를 가진 메시지 (state_snapshot에 추가)
    dispatch({
      type: 'state_snapshot',
      working_dir: '/tmp',
      model: 'qwen2.5',
      mode: 'act',
      turns: 0,
      // event_id는 ServerMsg 타입에 없지만 실제 WS 메시지에는 포함됨
      // cast를 통해 테스트
    } as Parameters<typeof dispatch>[0] & {event_id: number})
    // event_id 없으면 lastEventId는 null 유지
    expect(useRoomStore.getState().lastEventId).toBeNull()

    // event_id가 있는 경우 직접 setLastEventId 호출 경로 테스트
    // dispatch 내부에서 처리하므로 실제 타입 캐스트 필요
    const msgWithEventId = {type: 'pong', event_id: 42} as unknown as Parameters<typeof dispatch>[0]
    dispatch(msgWithEventId)
    expect(useRoomStore.getState().lastEventId).toBe(42)
  })
})
