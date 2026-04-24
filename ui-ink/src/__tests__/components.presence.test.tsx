// PresenceSegment 컴포넌트 테스트 (REM-02, DIFF-04)
// solo 모드 null 반환, room 모드 '🟢 N명 [...]' 렌더 검증
import React from 'react'
import {describe, it, expect, beforeEach} from 'vitest'
import {render} from 'ink-testing-library'
import {PresenceSegment} from '../components/PresenceSegment.js'
import {useRoomStore} from '../store/room.js'

describe('PresenceSegment', () => {
  beforeEach(() => {
    useRoomStore.setState({roomName: '', members: []})
    delete process.env['HARNESS_TOKEN']
  })

  it('Test P1: roomName="" → null 반환 (미렌더)', () => {
    useRoomStore.setState({roomName: '', members: []})
    const {lastFrame, unmount} = render(<PresenceSegment />)
    const frame = lastFrame() ?? ''
    expect(frame.trim()).toBe('')
    unmount()
  })

  it('Test P2: roomName 있고 members 2명 → "🟢 2명" 텍스트 포함', () => {
    useRoomStore.setState({roomName: 'team', members: ['alice', 'me']})
    const {lastFrame, unmount} = render(<PresenceSegment />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('🟢')
    expect(frame).toContain('2명')
    unmount()
  })

  it('Test P3: members 사이에 "·" 구분자 있음', () => {
    useRoomStore.setState({roomName: 'room1', members: ['alice', 'bob']})
    const {lastFrame, unmount} = render(<PresenceSegment />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('·')
    unmount()
  })
})
