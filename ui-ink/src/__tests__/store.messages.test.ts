// messages 슬라이스 단위 테스트 — completedMessages/activeMessage 분리 (RND-01, RND-02)
import {describe, it, expect, beforeEach} from 'vitest'
import {useMessagesStore} from '../store/messages.js'

describe('useMessagesStore (completedMessages / activeMessage 분리)', () => {
  // 각 테스트 전 초기화
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null})
  })

  it('Test 1: agentStart → activeMessage !== null, completedMessages 길이 불변', () => {
    useMessagesStore.getState().agentStart()
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    expect(activeMessage).not.toBeNull()
    expect(activeMessage?.role).toBe('assistant')
    expect(activeMessage?.streaming).toBe(true)
    expect(completedMessages).toHaveLength(0) // 불변
  })

  it('Test 2: appendToken 2회 → activeMessage.content 누적 (in-place)', () => {
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendToken('토큰1')
    useMessagesStore.getState().appendToken('토큰2')
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    expect(activeMessage?.content).toBe('토큰1토큰2')
    expect(completedMessages).toHaveLength(0) // 스트리밍 중에는 completed 불변
  })

  it('Test 3: agentEnd 후 activeMessage===null, completedMessages 마지막 원소 streaming=false', () => {
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendToken('완료 메시지')
    useMessagesStore.getState().agentEnd()
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    expect(activeMessage).toBeNull()
    expect(completedMessages).toHaveLength(1)
    expect(completedMessages[0].streaming).toBe(false)
    expect(completedMessages[0].role).toBe('assistant')
    expect(completedMessages[0].content).toBe('완료 메시지')
  })

  it('Test 4: appendUserMessage → completedMessages 즉시 push (activeMessage 무관)', () => {
    useMessagesStore.getState().appendUserMessage('안녕하세요')
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(1)
    expect(completedMessages[0].role).toBe('user')
    expect(completedMessages[0].content).toBe('안녕하세요')
    expect(activeMessage).toBeNull()
  })

  it('Test 5: appendToolStart/appendToolEnd → completedMessages 에서 in-place 업데이트', () => {
    useMessagesStore.getState().appendToolStart('read_file', {path: '/tmp/foo'})
    const afterStart = useMessagesStore.getState()
    expect(afterStart.completedMessages).toHaveLength(1)
    expect(afterStart.completedMessages[0].role).toBe('tool')
    expect(afterStart.completedMessages[0].streaming).toBe(true)

    useMessagesStore.getState().appendToolEnd('read_file', '파일 내용')
    const afterEnd = useMessagesStore.getState()
    expect(afterEnd.completedMessages).toHaveLength(1) // push 없음, in-place
    expect(afterEnd.completedMessages[0].streaming).toBe(false)
    expect(afterEnd.completedMessages[0].content).toContain('파일 내용')
  })

  it('Test 6: clearMessages → completedMessages=[], activeMessage=null', () => {
    useMessagesStore.getState().appendUserMessage('삭제될 메시지')
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().clearMessages()
    const {completedMessages, activeMessage} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(0)
    expect(activeMessage).toBeNull()
  })

  it('Test 7: appendSystemMessage → completedMessages 즉시 push', () => {
    useMessagesStore.getState().appendSystemMessage('시스템 알림')
    const {completedMessages, activeMessage} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(1)
    expect(completedMessages[0].role).toBe('system')
    expect(completedMessages[0].content).toBe('시스템 알림')
    expect(activeMessage).toBeNull()
  })
})
