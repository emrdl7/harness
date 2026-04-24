// store reducer 단위 테스트 (FND-06, FND-07, FND-08)
// completedMessages/activeMessage 분리 계약 기준으로 업데이트
import {describe, it, expect, beforeEach} from 'vitest'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'

describe('useMessagesStore', () => {
  // 각 테스트 전 store 초기 상태로 리셋 — 상태 오염 방지
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null})
    useStatusStore.setState({busy: false, connected: false})
  })

  it('agentStart() 호출 시 activeMessage 에 streaming:true 인 assistant 메시지 배치', () => {
    useMessagesStore.getState().agentStart()
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    expect(activeMessage).not.toBeNull()
    expect(activeMessage?.role).toBe('assistant')
    expect(activeMessage?.streaming).toBe(true)
    expect(activeMessage?.content).toBe('')
    expect(completedMessages).toHaveLength(0) // completedMessages 는 불변
  })

  it('appendToken 두 번 호출 → activeMessage.content 누적 (in-place update)', () => {
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendToken('hello')
    useMessagesStore.getState().appendToken(' world')
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    // in-place update — activeMessage 1개만 존재, completedMessages 는 비어있음
    expect(activeMessage?.content).toBe('hello world')
    expect(activeMessage?.streaming).toBe(true)
    expect(completedMessages).toHaveLength(0)
  })

  it('agentEnd() 호출 시 activeMessage→completedMessages 이동, streaming:false', () => {
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendToken('done')
    useMessagesStore.getState().agentEnd()
    const {activeMessage, completedMessages} = useMessagesStore.getState()
    expect(activeMessage).toBeNull()
    expect(completedMessages).toHaveLength(1)
    expect(completedMessages[0].streaming).toBe(false)
    expect(completedMessages[0].content).toBe('done')
  })

  it('각 메시지에 id 필드가 string 타입이며 중복 없음', () => {
    useMessagesStore.getState().appendUserMessage('msg1')
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendSystemMessage('sys')
    const {completedMessages, activeMessage} = useMessagesStore.getState()
    const all = [...completedMessages, ...(activeMessage ? [activeMessage] : [])]
    expect(all).toHaveLength(3)
    const ids = all.map((m) => m.id)
    // 모두 string
    ids.forEach((id) => expect(typeof id).toBe('string'))
    // 중복 없음
    const uniqueIds = new Set(ids)
    expect(uniqueIds.size).toBe(3)
  })

  it('appendUserMessage 호출 시 completedMessages 에 role:user 메시지 즉시 추가', () => {
    useMessagesStore.getState().appendUserMessage('안녕하세요')
    const {completedMessages} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(1)
    expect(completedMessages[0].role).toBe('user')
    expect(completedMessages[0].content).toBe('안녕하세요')
  })

  it('agentStart 없이 appendToken 호출 시 방어 처리 (activeMessage 새로 생성)', () => {
    // agentStart 없이 token 이 오는 경우 크래시 없이 처리
    useMessagesStore.getState().appendToken('orphan token')
    const {activeMessage} = useMessagesStore.getState()
    expect(activeMessage).not.toBeNull()
    expect(activeMessage?.role).toBe('assistant')
    expect(activeMessage?.content).toBe('orphan token')
  })
})
