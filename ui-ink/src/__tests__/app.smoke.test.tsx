// App smoke — 전체 트리 렌더 + 금지 패턴 런타임 검증
import React from 'react'
import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'
import {render} from 'ink-testing-library'
import {App} from '../App.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useConfirmStore} from '../store/confirm.js'
import {useInputStore} from '../store/input.js'

describe('App smoke', () => {
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null})
    useStatusStore.setState({
      connected: true, busy: false,
      workingDir: '/tmp', model: 'm', mode: 'agent',
      turns: 0, ctxTokens: 0,
    })
    useConfirmStore.setState({mode: 'none', payload: {}})
    useInputStore.setState({buffer: '', history: [], historyIndex: -1, slashOpen: false})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders without error (empty state)', () => {
    delete process.env['HARNESS_URL']
    const {lastFrame, unmount} = render(<App/>)
    expect(lastFrame()).toBeTruthy()
    // 레이아웃 필수 요소 존재
    expect(lastFrame()).toContain('─')          // Divider
    expect(lastFrame()).toContain('❯')          // InputArea prefix
    unmount()
  })

  it('renders completed + active messages', () => {
    delete process.env['HARNESS_URL']
    useMessagesStore.setState({
      completedMessages: [
        {id: '1', role: 'user', content: 'hello'},
      ],
      activeMessage: {id: '2', role: 'assistant', content: 'stream…', streaming: true},
    })
    const {lastFrame, unmount} = render(<App/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('hello')
    expect(frame).toContain('stream')
    unmount()
  })

  it('confirm mode shows placeholder instead of input', () => {
    delete process.env['HARNESS_URL']
    useConfirmStore.setState({mode: 'confirm_write', payload: {path: '/foo'}})
    const {lastFrame, unmount} = render(<App/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('/foo')
    unmount()
  })

  it('does NOT emit alternate screen or mouse tracking escapes', () => {
    delete process.env['HARNESS_URL']
    const {lastFrame, unmount} = render(<App/>)
    const frame = lastFrame() ?? ''
    // alternate screen ESC[?104x 및 mouse tracking ESC[?100x 계열 없음 확인
    // eslint-disable-next-line no-control-regex
    expect(frame).not.toMatch(/\x1b\[\?1049[hl]/)
    // eslint-disable-next-line no-control-regex
    expect(frame).not.toMatch(/\x1b\[\?100[0-3][hl]/)
    unmount()
  })
})
