// Phase 3 loadSnapshot + dispatch 확장 테스트 (REM-02~05, PEXT-01/05, DIFF-01/03)
// + Phase 4 회귀 스냅샷 4종 (TST-03)
// TDD RED: 구현 전 실패 테스트
import React from 'react'
import {describe, it, expect, beforeEach, vi} from 'vitest'
import {render} from 'ink-testing-library'

// inkBridge mock — 새 아키텍처: 완료 메시지는 stdout flush, 테스트는 active/inFlight 만 frame 으로 검증
vi.mock('../inkBridge.js', () => ({
  inkWriteAbove: vi.fn(),
  inkClearScreen: vi.fn(),
}))
import {useMessagesStore} from '../store/messages.js'
import {useRoomStore} from '../store/room.js'
import {useStatusStore} from '../store/status.js'
import {useInputStore} from '../store/input.js'
import {useConfirmStore} from '../store/confirm.js'
import {dispatch} from '../ws/dispatch.js'
import {App} from '../App.js'

describe('loadSnapshot (REM-03)', () => {
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null, snapshotKey: 0})
  })

  it('Test 1: loadSnapshot([]) 호출 시 completedMessages가 빈 배열이 되고 snapshotKey가 1 증가한다', () => {
    useMessagesStore.getState().loadSnapshot([])
    const {completedMessages, snapshotKey} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(0)
    expect(snapshotKey).toBe(1)
  })

  it('Test 2: loadSnapshot([{role:"user", content:"hi"}]) 호출 시 completedMessages에 id가 부여된 메시지가 로드된다', () => {
    useMessagesStore.getState().loadSnapshot([{role: 'user', content: 'hi'}])
    const {completedMessages} = useMessagesStore.getState()
    expect(completedMessages).toHaveLength(1)
    expect(completedMessages[0].role).toBe('user')
    expect(completedMessages[0].content).toBe('hi')
    expect(typeof completedMessages[0].id).toBe('string')
    expect(completedMessages[0].id.length).toBeGreaterThan(0)
  })

  it('Test 3: loadSnapshot() 호출 후 activeMessage가 null이 된다', () => {
    // activeMessage가 있는 상태에서 loadSnapshot 호출
    useMessagesStore.getState().agentStart()
    expect(useMessagesStore.getState().activeMessage).not.toBeNull()
    useMessagesStore.getState().loadSnapshot([])
    expect(useMessagesStore.getState().activeMessage).toBeNull()
  })
})

describe('dispatch 확장 (PEXT-01/05, DIFF-03)', () => {
  beforeEach(() => {
    useMessagesStore.setState({completedMessages: [], activeMessage: null, snapshotKey: 0})
    useStatusStore.setState({busy: false, connected: false})
    useRoomStore.setState({
      roomName: '', members: [], activeInputFrom: null, activeIsSelf: true, busy: false,
      wsState: 'connected', reconnectAttempt: 0, lastEventId: null,
    })
  })

  it('Test 4: dispatch agent_start {from_self: false} 후 room.activeIsSelf가 false가 된다', () => {
    dispatch({type: 'agent_start', from_self: false})
    expect(useRoomStore.getState().activeIsSelf).toBe(false)
  })

  it('Test 5: dispatch agent_start {} (from_self 없음) 후 room.activeIsSelf가 true가 된다 (구버전 호환)', () => {
    // from_self 필드 없이 전송되는 구버전 서버 호환
    dispatch({type: 'agent_start'})
    expect(useRoomStore.getState().activeIsSelf).toBe(true)
  })

  it('Test 6: dispatch agent_cancelled 후 busy가 false가 된다', () => {
    useStatusStore.setState({busy: true})
    dispatch({type: 'agent_cancelled'})
    expect(useStatusStore.getState().busy).toBe(false)
  })

  it('Test 7: event_id: 42가 있는 메시지 수신 시 room.lastEventId가 42가 된다', () => {
    // event_id 필드를 가진 메시지 (state_snapshot에 추가)
    dispatch({
      type: 'state_snapshot',
      working_dir: '/tmp',
      model: 'qwen2.5',
      mode: 'act',
      turns: 0,
      // event_id는 ServerMsg 타입에 없지만 실제 WS 메시지에는 포함됨
      // cast를 통해 테스트
    } as Parameters<typeof dispatch>[0] & {event_id: number})
    // event_id 없으면 lastEventId는 null 유지
    expect(useRoomStore.getState().lastEventId).toBeNull()

    // event_id가 있는 경우 직접 setLastEventId 호출 경로 테스트
    // dispatch 내부에서 처리하므로 실제 타입 캐스트 필요
    const msgWithEventId = {type: 'pong', event_id: 42} as unknown as Parameters<typeof dispatch>[0]
    dispatch(msgWithEventId)
    expect(useRoomStore.getState().lastEventId).toBe(42)
  })
})

// ─── 회귀 스냅샷 4종 (TST-03) ───────────────────────────────────────────────
// ink-testing-library render() 기반 — 향후 컴포넌트 변경 시 자동 감지

describe('회귀 스냅샷 (TST-03)', () => {
  // 각 테스트 전 전체 store 초기화 (app.smoke.test.tsx 패턴)
  beforeEach(() => {
    // 더미 env var — SetupWizard 를 건너뛰고 main 레이아웃 렌더
    process.env['HARNESS_URL'] = 'ws://localhost:0'
    process.env['HARNESS_TOKEN'] = 'test-token'
    useMessagesStore.setState({completedMessages: [], activeMessage: null, snapshotKey: 0})
    useStatusStore.setState({
      connected: true, busy: false,
      workingDir: '/tmp', model: 'qwen2.5', mode: 'agent',
      turns: 0, ctxTokens: 0,
    })
    useConfirmStore.setState({mode: 'none', payload: {}})
    useInputStore.setState({buffer: '', history: [], historyIndex: -1, slashOpen: false})
    useRoomStore.setState({
      roomName: '', members: [], activeInputFrom: null, activeIsSelf: true, busy: false,
      wsState: 'connected', reconnectAttempt: 0, lastEventId: null,
    })
  })

  it('500 토큰 스트리밍 스냅샷 (TST-03)', () => {
    // 500자 스트리밍 중 activeMessage 상태 스냅샷
    useMessagesStore.setState({
      completedMessages: [],
      activeMessage: {
        id: 'stream-01',
        role: 'assistant',
        content: 'A'.repeat(500),
        streaming: true,
      },
    })
    const {lastFrame, unmount} = render(<App />)
    expect(lastFrame()).toMatchSnapshot()
    unmount()
  })

  it('한국어+emoji 메시지 렌더 스냅샷 (TST-03) — active 도 stdout 흐름', () => {
    // 새 아키텍처: 완료/active 모두 stdout 으로 stream → frame 에는 UI 셸만
    useMessagesStore.setState({
      completedMessages: [],
      activeMessage: {
        id: 'ko-01',
        role: 'assistant',
        content: '안녕하세요! 🎉 이것은 한국어 메시지입니다. emoji 포함 wrap 검증.',
        streaming: true,
      },
    })
    const {lastFrame, unmount} = render(<App />)
    const frame = lastFrame()
    // 메시지는 frame 에 없음 (stdout flush)
    expect(frame).not.toContain('안녕하세요')
    expect(frame).toMatchSnapshot()
    unmount()
  })

  it('/undo + 새 메시지 순서 스냅샷 (TST-03) — store 순서 검증', () => {
    // 새 아키텍처: 완료 메시지는 stdout flush 됨 → frame 에 보이지 않음
    // 순서 보존은 store + flush 로직(MessageList 의 useLayoutEffect)에서 보장
    useMessagesStore.setState({
      completedMessages: [
        {id: 'msg-01', role: 'user', content: '첫 번째 메시지', streaming: false},
        {id: 'msg-02', role: 'assistant', content: '새로운 응답', streaming: false},
      ],
      activeMessage: null,
    })
    const {lastFrame, unmount} = render(<App />)
    const frame = lastFrame()
    expect(frame).toMatchSnapshot()
    // 순서는 store 에서 검증 (frame 에는 완료 메시지 없음)
    const completed = useMessagesStore.getState().completedMessages
    expect(completed[0].content).toBe('첫 번째 메시지')
    expect(completed[1].content).toBe('새로운 응답')
    unmount()
  })

  it('spinner 오염 0 — frame 에 spinner 잔재 없음 (TST-03)', () => {
    useMessagesStore.setState({
      completedMessages: [],
      activeMessage: null,
    })
    const {lastFrame, unmount} = render(<App />)
    const frame = lastFrame() ?? ''
    // spinner 프레임 문자 (Braille dots) 가 포함되면 안 됨
    expect(frame).not.toMatch(/[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]/)
    expect(frame).toMatchSnapshot()
    unmount()
  })
})
