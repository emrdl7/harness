// dispatch exhaustive switch 단위 테스트 (FND-04, FND-05)
import {describe, it, expect, beforeEach} from 'vitest'
import {dispatch} from '../ws/dispatch.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'

describe('dispatch', () => {
  // 각 테스트 전 모든 store 초기화
  beforeEach(() => {
    useMessagesStore.setState({messages: []})
    useStatusStore.setState({busy: false, connected: false})
    useRoomStore.setState({roomName: '', members: [], activeInputFrom: null, activeIsSelf: true, busy: false})
    useConfirmStore.setState({mode: 'none', payload: {}})
  })

  it('token → 메시지에 token text 포함', () => {
    dispatch({type: 'token', text: 'hi'})
    const {messages} = useMessagesStore.getState()
    expect(messages.length).toBeGreaterThan(0)
    expect(messages[messages.length - 1].content).toContain('hi')
  })

  it('agent_start → status.busy === true', () => {
    dispatch({type: 'agent_start'})
    expect(useStatusStore.getState().busy).toBe(true)
  })

  it('agent_end → status.busy === false', () => {
    // 먼저 busy 상태로 설정
    useStatusStore.setState({busy: true})
    dispatch({type: 'agent_end'})
    expect(useStatusStore.getState().busy).toBe(false)
  })

  it('error → messages 에 "오류: fail" 포함', () => {
    dispatch({type: 'error', text: 'fail'})
    const {messages} = useMessagesStore.getState()
    const found = messages.some((m) => m.content.includes('오류: fail'))
    expect(found).toBe(true)
  })

  it('info → messages 에 text 포함', () => {
    dispatch({type: 'info', text: '정보 메시지'})
    const {messages} = useMessagesStore.getState()
    const found = messages.some((m) => m.content.includes('정보 메시지'))
    expect(found).toBe(true)
  })

  it('ready → status.connected === true', () => {
    dispatch({type: 'ready', room: 'test-room'})
    expect(useStatusStore.getState().connected).toBe(true)
  })

  it('confirm_write → confirm store 에 mode:confirm_write 설정', () => {
    dispatch({type: 'confirm_write', path: '/tmp/test.txt'})
    const confirmState = useConfirmStore.getState()
    expect(confirmState.mode).toBe('confirm_write')
  })

  it('confirm_bash → confirm store 에 mode:confirm_bash 설정', () => {
    dispatch({type: 'confirm_bash', command: 'rm -rf /'})
    const confirmState = useConfirmStore.getState()
    expect(confirmState.mode).toBe('confirm_bash')
  })

  it('pong → 메시지나 상태 변화 없음 (heartbeat 무시)', () => {
    dispatch({type: 'pong'})
    const {messages} = useMessagesStore.getState()
    expect(messages).toHaveLength(0)
  })

  it('claude_start → status.busy === true', () => {
    dispatch({type: 'claude_start'})
    expect(useStatusStore.getState().busy).toBe(true)
  })

  it('claude_end → status.busy === false', () => {
    useStatusStore.setState({busy: true})
    dispatch({type: 'claude_end'})
    expect(useStatusStore.getState().busy).toBe(false)
  })

  it('claude_token → messages 에 token text 포함', () => {
    dispatch({type: 'claude_token', text: 'claude says hi'})
    const {messages} = useMessagesStore.getState()
    expect(messages.length).toBeGreaterThan(0)
    expect(messages[messages.length - 1].content).toContain('claude says hi')
  })

  it('queue → messages 에 큐 대기 메시지 포함', () => {
    dispatch({type: 'queue', position: 3})
    const {messages} = useMessagesStore.getState()
    const found = messages.some((m) => m.content.includes('3'))
    expect(found).toBe(true)
  })
})
