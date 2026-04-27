// AR-02: streaming token 16ms coalescer 동작 검증
// - 다중 token 호출은 16ms 윈도우에 누적
// - 16ms 후 trailing flush 1회만 set
// - tool_start/tool_end/agent_end 등 경계 이벤트는 즉시 flush
import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'
import {dispatch, flushPendingTokens} from '../ws/dispatch.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'

describe('AR-02 — token coalescer', () => {
  beforeEach(() => {
    flushPendingTokens()   // 이전 테스트 잔재 제거
    useMessagesStore.setState({completedMessages: [], activeMessage: null})
    useStatusStore.setState({busy: false, connected: false})
    useRoomStore.setState({roomName: '', members: [], activeInputFrom: null, activeIsSelf: true, busy: false})
    useConfirmStore.setState({mode: 'none', payload: {}})
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('Test 1: 단일 token — 16ms 미만에는 store 미반영, 16ms 후 반영', () => {
    dispatch({type: 'token', text: 'hello'})
    // 즉시 — store 빈 상태
    expect(useMessagesStore.getState().activeMessage).toBeNull()
    // 15ms 진행 — 아직 미flush
    vi.advanceTimersByTime(15)
    expect(useMessagesStore.getState().activeMessage).toBeNull()
    // 16ms 도달 — flush
    vi.advanceTimersByTime(1)
    expect(useMessagesStore.getState().activeMessage?.content).toBe('hello')
  })

  it('Test 2: 다중 token — 16ms 윈도우에 누적 후 1회만 store update', () => {
    let updates = 0
    const unsub = useMessagesStore.subscribe(() => { updates++ })

    dispatch({type: 'token', text: 'a'})
    dispatch({type: 'token', text: 'b'})
    dispatch({type: 'token', text: 'c'})
    dispatch({type: 'token', text: 'd'})
    // 즉시 — store 무변경
    expect(updates).toBe(0)
    vi.advanceTimersByTime(16)
    // flush 후 — appendToken 1회만 호출 → store 1회 update
    expect(updates).toBe(1)
    expect(useMessagesStore.getState().activeMessage?.content).toBe('abcd')

    unsub()
  })

  it('Test 3: tool_start 경계 — 누적된 token 즉시 flush', () => {
    dispatch({type: 'token', text: 'partial'})
    expect(useMessagesStore.getState().activeMessage).toBeNull()
    dispatch({type: 'tool_start', name: 'read_file', args: {path: 'foo'}})
    // 16ms 대기 없이도 token flush 됨
    expect(useMessagesStore.getState().activeMessage?.content).toBe('partial')
  })

  it('Test 4: agent_end 경계 — 누적 token flush 후 turn 종료', () => {
    dispatch({type: 'agent_start'})
    dispatch({type: 'token', text: 'final answer'})
    dispatch({type: 'agent_end'})
    // flush 후 activeMessage → completedMessages 이동
    const {completedMessages, activeMessage} = useMessagesStore.getState()
    expect(activeMessage).toBeNull()
    expect(completedMessages.at(-1)?.content).toBe('final answer')
  })

  it('Test 5: claude_token 경로도 동일 coalesce', () => {
    dispatch({type: 'claude_token', text: 'cl'})
    dispatch({type: 'claude_token', text: 'aude'})
    expect(useMessagesStore.getState().activeMessage).toBeNull()
    vi.advanceTimersByTime(16)
    expect(useMessagesStore.getState().activeMessage?.content).toBe('claude')
  })

  it('Test 6: flushPendingTokens() public — 사용자 호출로 즉시 flush', () => {
    dispatch({type: 'token', text: 'now'})
    expect(useMessagesStore.getState().activeMessage).toBeNull()
    flushPendingTokens()
    expect(useMessagesStore.getState().activeMessage?.content).toBe('now')
  })
})
