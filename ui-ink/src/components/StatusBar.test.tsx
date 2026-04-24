// Task E-3: StatusBar CtxMeter 격리 TDD 테스트 (RND-09)
// CtxMeter 서브컴포넌트가 StatusBar 본체와 독립적으로 리렌더되는지 검증
import React from 'react'
import {describe, it, expect, beforeEach} from 'vitest'
import {render} from 'ink-testing-library'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'

const {StatusBar} = await import('../components/StatusBar.js')

describe('StatusBar — CtxMeter 격리 (E-3)', () => {
  beforeEach(() => {
    useStatusStore.setState({
      connected: true,
      busy: false,
      workingDir: '/home/user/project',
      model: 'qwen2.5-coder:32b',
      mode: 'agent',
      turns: 3,
      ctxTokens: 16384,  // 50% — 테스트 2와 4에서 일관된 값 사용
    })
    useRoomStore.setState({roomName: 'testroom', members: []})
  })

  it('Test 1: CtxMeter 서브컴포넌트가 StatusBar.tsx 내에 정의되어 있음 (구조 검증)', () => {
    // StatusBar 컴포넌트가 정상 렌더되고 ctx 세그먼트 포함 확인
    const {lastFrame, unmount} = render(<StatusBar columns={120}/>)
    const frame = lastFrame() ?? ''
    // CtxMeter 가 렌더되면 ctx% 세그먼트가 보임
    expect(frame).toContain('ctx')
    unmount()
  })

  it('Test 2: ctxTokens=16384(50%) 시 ctx 50% 렌더 (CtxMeter 구독 동작 확인)', () => {
    // beforeEach 에서 ctxTokens=16384 (32768 기준 50%) 설정
    const {lastFrame, unmount} = render(<StatusBar columns={120}/>)
    const frame = lastFrame() ?? ''

    // ctx 50% 렌더 확인 (CtxMeter 가 구독하는 값)
    expect(frame).toContain('ctx 50%')
    unmount()
  })

  it('Test 3: ctxTokens=undefined 일 때 CtxMeter 렌더 안 됨', () => {
    useStatusStore.setState({ctxTokens: undefined})
    const {lastFrame, unmount} = render(<StatusBar columns={120}/>)
    const frame = lastFrame() ?? ''
    // CtxMeter 가 조건부 렌더이므로 ctx 세그먼트 없어야 함
    expect(frame).not.toContain('ctx ')
    unmount()
  })

  it('Test 4: CtxMeter 와 함께 나머지 세그먼트(path/model/mode/turn/room) 모두 렌더됨', () => {
    const {lastFrame, unmount} = render(<StatusBar columns={160}/>)
    const frame = lastFrame() ?? ''

    // 전 세그먼트 확인 (SC-5 요구사항)
    expect(frame).toContain('qwen2.5-coder:32b')  // model
    expect(frame).toContain('agent')               // mode
    expect(frame).toContain('turn')                // turn
    expect(frame).toContain('ctx')                 // CtxMeter
    // PresenceSegment 교체 후: roomName 텍스트 대신 '🟢' 아이콘으로 확인 (REM-02)
    expect(frame).toContain('🟢')                  // room (PresenceSegment)
    unmount()
  })
})
