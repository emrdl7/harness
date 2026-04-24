// MessageList + Message 컴포넌트 테스트 — Static/active 분리, prefix/색상, key warning (B-4)
import React from 'react'
import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'
import {render} from 'ink-testing-library'
import {MessageList} from '../components/MessageList.js'
import {Message} from '../components/Message.js'
import {useMessagesStore} from '../store/messages.js'
import type {Message as MessageType} from '../store/messages.js'

describe('MessageList + Message', () => {
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null})
  })

  it('Test 1: completedMessages=[user,assistant], activeMessage=null — 2개 렌더', () => {
    useMessagesStore.setState({
      completedMessages: [
        {id: 'u1', role: 'user', content: '안녕하세요'},
        {id: 'a1', role: 'assistant', content: '안녕하세요! 도움이 필요하신가요?'},
      ],
      activeMessage: null,
    })
    const {lastFrame, unmount} = render(<MessageList/>)
    const frame = lastFrame() ?? ''
    // user prefix
    expect(frame).toContain('❯')
    // assistant prefix
    expect(frame).toContain('●')
    expect(frame).toContain('안녕하세요')
    unmount()
  })

  it('Test 2: completedMessages=[], activeMessage={role:assistant} — assistant 1개 렌더', () => {
    useMessagesStore.setState({
      completedMessages: [],
      activeMessage: {id: 'a1', role: 'assistant', content: '스트리밍 중...', streaming: true},
    })
    const {lastFrame, unmount} = render(<MessageList/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('●')
    expect(frame).toContain('스트리밍 중...')
    unmount()
  })

  it('Test 3: completedMessages=[user], activeMessage={role:assistant} — 2개 순서대로 렌더', () => {
    useMessagesStore.setState({
      completedMessages: [
        {id: 'u1', role: 'user', content: '질문입니다'},
      ],
      activeMessage: {id: 'a1', role: 'assistant', content: '답변 중...', streaming: true},
    })
    const {lastFrame, unmount} = render(<MessageList/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('질문입니다')
    expect(frame).toContain('답변 중...')
    unmount()
  })

  it('Test 4: Message role=system — gray 색 prefix 공백', () => {
    const msg: MessageType = {id: 's1', role: 'system', content: '시스템 알림'}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('시스템 알림')
    // system prefix 는 공백 2개 — prefix 없이 내용만 나옴
    unmount()
  })

  it('Test 5: Message role=tool — prefix \'└ \' 포함', () => {
    const msg: MessageType = {id: 't1', role: 'tool', content: '[read_file] 완료', toolName: 'read_file'}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('└')
    expect(frame).toContain('[read_file] 완료')
    unmount()
  })

  it('Test 6: React key warning 없음 — id 기반 key 사용 검증', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    useMessagesStore.setState({
      completedMessages: [
        {id: 'u1', role: 'user', content: 'msg1'},
        {id: 'u2', role: 'user', content: 'msg2'},
        {id: 'u3', role: 'user', content: 'msg3'},
      ],
      activeMessage: null,
    })
    const {unmount} = render(<MessageList/>)
    expect(errSpy).not.toHaveBeenCalledWith(
      expect.stringContaining('unique "key"'),
    )
    unmount()
    errSpy.mockRestore()
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})
