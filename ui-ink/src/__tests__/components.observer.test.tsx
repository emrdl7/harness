// ReconnectOverlay + ObserverOverlay 컴포넌트 테스트 (WSR-02, REM-04, DIFF-01)
// ReconnectOverlay: 재연결 중 yellow, 실패 red
// ObserverOverlay: username 색 + 'N 입력 중...' dimColor italic
import React from 'react'
import {describe, it, expect, beforeEach} from 'vitest'
import {render} from 'ink-testing-library'
import {ReconnectOverlay} from '../components/ReconnectOverlay.js'
import {ObserverOverlay} from '../components/ObserverOverlay.js'

describe('ReconnectOverlay', () => {
  it('Test R1: attempt=3 → "(attempt 3/10)" 텍스트 포함', () => {
    const {lastFrame, unmount} = render(<ReconnectOverlay attempt={3} />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('(attempt 3/10)')
    unmount()
  })

  it('Test R2: attempt prop → "reconnecting" 텍스트 포함', () => {
    const {lastFrame, unmount} = render(<ReconnectOverlay attempt={1} />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('reconnecting')
    unmount()
  })

  it('Test R3: failed=true → "reconnect failed" 텍스트 포함', () => {
    const {lastFrame, unmount} = render(<ReconnectOverlay failed={true} />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('reconnect failed')
    unmount()
  })
})

describe('ObserverOverlay', () => {
  beforeEach(() => {
    delete process.env['HARNESS_TOKEN']
  })

  it('Test O1: username="alice" → "입력 중..." 텍스트 포함', () => {
    const {lastFrame, unmount} = render(<ObserverOverlay username='alice' />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('입력 중...')
    unmount()
  })

  it('Test O2: username=null → "상대방" + "입력 중..." 렌더 (null 안전)', () => {
    const {lastFrame, unmount} = render(<ObserverOverlay username={null} />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('상대방')
    expect(frame).toContain('입력 중...')
    unmount()
  })

  it('Test O3: username 있을 때 displayName 포함 + "입력 중..." 렌더', () => {
    const {lastFrame, unmount} = render(<ObserverOverlay username='bob' />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('bob')
    expect(frame).toContain('입력 중...')
    unmount()
  })
})
