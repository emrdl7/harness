// dispatch exhaustive switch 단위 테스트 (FND-04, FND-05)
import {describe, it, expect, beforeEach, vi} from 'vitest'
import {dispatch, flushPendingTokens} from '../ws/dispatch.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'

// RPC-01: dispatch 핸드오프 회귀용 — runClientTool 이 호출됐는지 검증한다.
// vi.mock 은 호이스팅되므로 import 위치와 무관하게 실제 호출이 mock 으로 대체된다.
vi.mock('../tools/registry.js', () => ({
  runClientTool: vi.fn(() => Promise.resolve()),
  bindToolClient: vi.fn(),
}))

describe('dispatch', () => {
  // 각 테스트 전 모든 store 초기화
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null})
    useStatusStore.setState({busy: false, connected: false})
    useRoomStore.setState({roomName: '', members: [], activeInputFrom: null, activeIsSelf: true, busy: false})
    useConfirmStore.setState({mode: 'none', payload: {}})
  })

  it('token → 메시지에 token text 포함 (AR-02 coalesce — flush 후 검증)', () => {
    dispatch({type: 'token', text: 'hi'})
    flushPendingTokens()   // AR-02: 16ms 대기 회피, 즉시 flush
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    // token 은 activeMessage 에 누적됨
    const content = activeMessage?.content ?? completedMessages[completedMessages.length - 1]?.content ?? ''
    expect(content).toContain('hi')
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

  it('error → completedMessages 에 "오류: fail" 포함', () => {
    dispatch({type: 'error', text: 'fail'})
    const {completedMessages} = useMessagesStore.getState()
    const found = completedMessages.some((m) => m.content.includes('오류: fail'))
    expect(found).toBe(true)
  })

  it('info → completedMessages 에 text 포함', () => {
    dispatch({type: 'info', text: '정보 메시지'})
    const {completedMessages} = useMessagesStore.getState()
    const found = completedMessages.some((m) => m.content.includes('정보 메시지'))
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
    const {completedMessages} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(0)
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

  it('claude_token → completedMessages 또는 activeMessage 에 token text 포함 (AR-02 coalesce)', () => {
    dispatch({type: 'claude_token', text: 'claude says hi'})
    flushPendingTokens()   // AR-02
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    const content = activeMessage?.content ?? completedMessages[completedMessages.length - 1]?.content ?? ''
    expect(content).toContain('claude says hi')
  })

  it('queue → completedMessages 에 큐 대기 메시지 포함', () => {
    dispatch({type: 'queue', position: 3})
    const {completedMessages} = useMessagesStore.getState()
    const found = completedMessages.some((m) => m.content.includes('3'))
    expect(found).toBe(true)
  })

  // slash_result cmd 별 분기 테스트 (A-5)
  it('slash_result cmd=clear → completedMessages=[], activeMessage=null', () => {
    useMessagesStore.getState().appendUserMessage('삭제될 메시지')
    dispatch({type: 'slash_result', cmd: 'clear'})
    const {completedMessages, activeMessage} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(0)
    expect(activeMessage).toBeNull()
  })

  it('slash_result cmd=cd path="/tmp" → status.workingDir === "/tmp"', () => {
    dispatch({type: 'slash_result', cmd: 'cd', path: '/tmp'})
    expect(useStatusStore.getState().workingDir).toBe('/tmp')
  })

  it('slash_result cmd=model model="qwen2.5-coder:32b" → status.model 업데이트', () => {
    dispatch({type: 'slash_result', cmd: 'model', model: 'qwen2.5-coder:32b'})
    expect(useStatusStore.getState().model).toBe('qwen2.5-coder:32b')
  })

  it('slash_result cmd=mode mode="plan" → status.mode 업데이트', () => {
    dispatch({type: 'slash_result', cmd: 'mode', mode: 'plan'})
    expect(useStatusStore.getState().mode).toBe('plan')
  })

  it('slash_result cmd=unknown → appendSystemMessage fallback', () => {
    dispatch({type: 'slash_result', cmd: 'unknown_cmd'})
    const {completedMessages} = useMessagesStore.getState()
    const found = completedMessages.some((m) => m.content.includes('unknown_cmd'))
    expect(found).toBe(true)
  })

  it('slash_result cmd=help → completedMessages 에 help 텍스트 포함', () => {
    dispatch({type: 'slash_result', cmd: 'help', help_text: '사용 가능한 명령어 목록'})
    const {completedMessages} = useMessagesStore.getState()
    const found = completedMessages.some((m) => m.content.includes('사용 가능한 명령어 목록'))
    expect(found).toBe(true)
  })

  // RPC-01: tool_request 위임 회귀
  it('tool_request 가 runClientTool(call_id, name, args) 로 위임된다', async () => {
    const {runClientTool} = await import('../tools/registry.js')
    ;(runClientTool as ReturnType<typeof vi.fn>).mockClear()
    dispatch({type: 'tool_request', call_id: 'X1', name: 'read_file', args: {path: '/tmp/a'}})
    expect(runClientTool).toHaveBeenCalledWith('X1', 'read_file', {path: '/tmp/a'})
  })
})
