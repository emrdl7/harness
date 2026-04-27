// messages 슬라이스 단위 테스트 — completedMessages/activeMessage 분리 (RND-01, RND-02)
import {describe, it, expect, beforeEach} from 'vitest'
import {useMessagesStore} from '../store/messages.js'

describe('useMessagesStore (completedMessages / activeMessage 분리)', () => {
  // 각 테스트 전 초기화
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null, activeToolMessage: null})
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

  it('Test 5: appendToolStart → activeToolMessage 슬롯 (Static 격리), appendToolEnd → completedMessages 로 이동', () => {
    useMessagesStore.getState().appendToolStart('read_file', {path: '/tmp/foo'})
    const afterStart = useMessagesStore.getState()
    // Static 의 append-only 회피 — completedMessages 에는 push 안 함
    expect(afterStart.completedMessages).toHaveLength(0)
    expect(afterStart.activeToolMessage).not.toBeNull()
    expect(afterStart.activeToolMessage?.role).toBe('tool')
    expect(afterStart.activeToolMessage?.streaming).toBe(true)
    expect(afterStart.activeToolMessage?.toolName).toBe('read_file')

    useMessagesStore.getState().appendToolEnd('read_file', '파일 내용')
    const afterEnd = useMessagesStore.getState()
    expect(afterEnd.activeToolMessage).toBeNull()                // 슬롯 비움
    expect(afterEnd.completedMessages).toHaveLength(1)           // 완성 카드 push
    expect(afterEnd.completedMessages[0].streaming).toBe(false)
    expect(afterEnd.completedMessages[0].content).toContain('파일 내용')
    expect(afterEnd.completedMessages[0].toolName).toBe('read_file')
  })

  it('Test 5b: appendToolEnd 가 dict payload → toolPayload 로 보존 (AR-01)', () => {
    useMessagesStore.getState().appendToolStart('edit_file', {path: '/tmp/x'})
    useMessagesStore.getState().appendToolEnd('edit_file', {ok: true, file_diff: '--- a\n+++ b\n'})
    const after = useMessagesStore.getState()
    expect(after.completedMessages).toHaveLength(1)
    const m = after.completedMessages[0]
    expect(m.toolPayload).toEqual({ok: true, file_diff: '--- a\n+++ b\n'})
    expect(m.streaming).toBe(false)
  })

  it('Test 5c: tool_start 없이 tool_end 만 도달 (snapshot 등) → fallback 으로 직접 push', () => {
    useMessagesStore.getState().appendToolEnd('grep_search', {ok: true})
    const after = useMessagesStore.getState()
    expect(after.completedMessages).toHaveLength(1)
    expect(after.completedMessages[0].streaming).toBe(false)
    expect(after.completedMessages[0].toolName).toBe('grep_search')
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
