// MessageList + Message 컴포넌트 테스트 — Claude Code 식: 완료는 stdout flush, in-flight/active만 Ink 렌더
import React from 'react'
import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'
import {render} from 'ink-testing-library'
import {MessageList} from '../components/MessageList.js'
import {Message} from '../components/Message.js'
import {useMessagesStore} from '../store/messages.js'
import type {Message as MessageType} from '../store/messages.js'

// inkBridge mock — stdout 캡처 (real stdout 오염 방지 + 검증용)
const writeAboveCalls: string[] = []
vi.mock('../inkBridge.js', () => ({
  inkWriteAbove: (data: string) => { writeAboveCalls.push(data) },
  inkClearScreen: () => {},
}))

describe('MessageList + Message', () => {
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null, snapshotKey: 0})
    writeAboveCalls.length = 0
  })

  it('Test 1: 완료 메시지는 inkWriteAbove 로 flush — frame 에는 없음', () => {
    useMessagesStore.setState({
      completedMessages: [
        {id: 'u1', role: 'user', content: '안녕하세요'},
        {id: 'a1', role: 'assistant', content: '안녕하세요! 도움이 필요하신가요?'},
      ],
      activeMessage: null,
    })
    const {lastFrame, unmount} = render(<MessageList/>)
    const frame = lastFrame() ?? ''
    // 완료 메시지는 stdout 으로 flush 됐으므로 Ink frame 에는 없음
    expect(frame).not.toContain('안녕하세요')
    // 대신 inkWriteAbove 로 출력됨 (cli-highlight 등으로 ANSI 포함)
    const written = writeAboveCalls.join('')
    expect(written).toContain('안녕하세요')
    expect(written).toContain('❯')
    unmount()
  })

  it('Test 2: active assistant 토큰은 inkWriteAbove 로 stream — frame 에는 없음', () => {
    useMessagesStore.setState({
      completedMessages: [],
      activeMessage: {id: 'a1', role: 'assistant', content: '스트리밍 중...', streaming: true},
    })
    const {lastFrame, unmount} = render(<MessageList/>)
    const frame = lastFrame() ?? ''
    // active 도 Ink 가 아닌 stdout 으로 stream
    expect(frame).not.toContain('스트리밍 중...')
    expect(writeAboveCalls.join('')).toContain('스트리밍 중...')
    unmount()
  })

  it('Test 3: 완료(user) + active(assistant) 모두 stdout 으로 흐름 — frame 비어있음', () => {
    useMessagesStore.setState({
      completedMessages: [
        {id: 'u1', role: 'user', content: '질문입니다'},
      ],
      activeMessage: {id: 'a1', role: 'assistant', content: '답변 중...', streaming: true},
    })
    const {lastFrame, unmount} = render(<MessageList/>)
    const frame = lastFrame() ?? ''
    expect(frame).not.toContain('질문입니다')
    expect(frame).not.toContain('답변 중...')
    const written = writeAboveCalls.join('')
    expect(written).toContain('질문입니다')
    expect(written).toContain('답변 중...')
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

  it('Test 5: Message role=tool — prefix \'✓ \' 포함', () => {
    const msg: MessageType = {id: 't1', role: 'tool', content: '[read_file] 완료', toolName: 'read_file'}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('✓')
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
