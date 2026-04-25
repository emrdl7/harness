// App smoke — 전체 트리 렌더 + 금지 패턴 런타임 검증
import React from 'react'
import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'
import {render} from 'ink-testing-library'
import {App} from '../App.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useConfirmStore} from '../store/confirm.js'
import {useInputStore} from '../store/input.js'

// inkBridge mock — stdout 캡처 (real stdout 오염 방지)
vi.mock('../inkBridge.js', () => ({
  inkWriteAbove: vi.fn(),
  inkClearScreen: vi.fn(),
}))

describe('App smoke', () => {
  beforeEach(() => {
    // 더미 env var — SetupWizard 를 건너뛰고 main 레이아웃 렌더
    process.env['HARNESS_URL'] = 'ws://localhost:0'
    process.env['HARNESS_TOKEN'] = 'test-token'
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
    delete process.env['HARNESS_URL']
    delete process.env['HARNESS_TOKEN']
    vi.restoreAllMocks()
  })

  it('renders without error (empty state)', () => {
    const {lastFrame, unmount} = render(<App/>)
    expect(lastFrame()).toBeTruthy()
    // 레이아웃 필수 요소 — Divider 제거됨, InputArea prefix 만 검증
    expect(lastFrame()).toContain('❯')
    unmount()
  })

  it('renders active message in frame (completed flushed via inkBridge mock)', () => {
    useMessagesStore.setState({
      completedMessages: [
        {id: '1', role: 'user', content: 'hello'},
      ],
      activeMessage: {id: '2', role: 'assistant', content: 'stream…', streaming: true},
    })
    const {lastFrame, unmount} = render(<App/>)
    const frame = lastFrame() ?? ''
    // 완료 메시지(hello)는 stdout 으로 flush — frame 에 없음
    // active(stream)는 Ink frame 에 있음
    expect(frame).toContain('stream')
    unmount()
  })

  it('confirm mode shows placeholder instead of input', () => {
    useConfirmStore.setState({mode: 'confirm_write', payload: {path: '/foo'}})
    const {lastFrame, unmount} = render(<App/>)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('/foo')
    unmount()
  })

  it('does NOT emit alternate screen or mouse tracking escapes', () => {
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
