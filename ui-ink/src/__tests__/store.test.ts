// store reducer 단위 테스트 (FND-06, FND-07, FND-08)
import {describe, it, expect, beforeEach} from 'vitest'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'

describe('useMessagesStore', () => {
  // 각 테스트 전 store 초기 상태로 리셋 — 상태 오염 방지
  beforeEach(() => {
    useMessagesStore.setState({messages: []})
    useStatusStore.setState({busy: false, connected: false})
  })

  it('agentStart() 호출 시 streaming:true 인 assistant 메시지 추가', () => {
    useMessagesStore.getState().agentStart()
    const {messages} = useMessagesStore.getState()
    expect(messages).toHaveLength(1)
    expect(messages[0].role).toBe('assistant')
    expect(messages[0].streaming).toBe(true)
    expect(messages[0].content).toBe('')
  })

  it('appendToken 두 번 호출 → 메시지 1개, content 누적 (in-place update)', () => {
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendToken('hello')
    useMessagesStore.getState().appendToken(' world')
    const {messages} = useMessagesStore.getState()
    // 새 메시지 push 가 아닌 in-place update — 메시지 1개여야 함
    expect(messages).toHaveLength(1)
    expect(messages[0].content).toBe('hello world')
    expect(messages[0].streaming).toBe(true)
  })

  it('agentEnd() 호출 시 마지막 assistant 메시지 streaming:false 로 변경', () => {
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendToken('done')
    useMessagesStore.getState().agentEnd()
    const {messages} = useMessagesStore.getState()
    expect(messages).toHaveLength(1)
    expect(messages[0].streaming).toBe(false)
    expect(messages[0].content).toBe('done')
  })

  it('각 메시지에 id 필드가 string 타입이며 중복 없음', () => {
    useMessagesStore.getState().appendUserMessage('msg1')
    useMessagesStore.getState().agentStart()
    useMessagesStore.getState().appendSystemMessage('sys')
    const {messages} = useMessagesStore.getState()
    expect(messages).toHaveLength(3)
    const ids = messages.map((m) => m.id)
    // 모두 string
    ids.forEach((id) => expect(typeof id).toBe('string'))
    // 중복 없음
    const uniqueIds = new Set(ids)
    expect(uniqueIds.size).toBe(3)
  })

  it('appendUserMessage 호출 시 role:user 메시지 추가', () => {
    useMessagesStore.getState().appendUserMessage('안녕하세요')
    const {messages} = useMessagesStore.getState()
    expect(messages).toHaveLength(1)
    expect(messages[0].role).toBe('user')
    expect(messages[0].content).toBe('안녕하세요')
  })

  it('agentStart 없이 appendToken 호출 시 방어 처리 (새 메시지 생성)', () => {
    // agentStart 없이 token 이 오는 경우 크래시 없이 처리
    useMessagesStore.getState().appendToken('orphan token')
    const {messages} = useMessagesStore.getState()
    expect(messages).toHaveLength(1)
    expect(messages[0].role).toBe('assistant')
    expect(messages[0].content).toBe('orphan token')
  })
})
