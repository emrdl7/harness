// Phase 3 loadSnapshot + dispatch 확장 테스트 (REM-02~05, PEXT-01/05, DIFF-01/03)
// + Phase 4 회귀 스냅샷 4종 (TST-03)
// TDD RED: 구현 전 실패 테스트
import React from 'react'
import {describe, it, expect, beforeEach} from 'vitest'
import {render} from 'ink-testing-library'
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
    delete process.env['HARNESS_URL']
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

  it('한국어+emoji 메시지 렌더 스냅샷 (TST-03)', () => {
    // 한국어 문장 + emoji 포함 메시지 렌더 — ink-testing-library columns 옵션 미지원
    // 기본 폭에서 한국어+emoji 문자가 올바르게 렌더됨을 스냅샷으로 고정
    useMessagesStore.setState({
      completedMessages: [
        {
          id: 'ko-01',
          role: 'assistant',
          content: '안녕하세요! 🎉 이것은 한국어 메시지입니다. emoji 포함 wrap 검증.',
          streaming: false,
        },
      ],
      activeMessage: null,
    })
    const {lastFrame, unmount} = render(<App />)
    const frame = lastFrame()
    // 한국어 콘텐츠가 렌더됨을 확인
    expect(frame).toContain('안녕하세요')
    expect(frame).toMatchSnapshot()
    unmount()
  })

  it('/undo + 새 메시지 순서 스냅샷 (TST-03)', () => {
    // /undo 후 남은 메시지 1개 + 새 메시지 1개 — 순서 고정
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
    // 순서 검증: 첫 번째 메시지가 두 번째보다 앞에 렌더됨
    const pos1 = frame?.indexOf('첫 번째 메시지') ?? -1
    const pos2 = frame?.indexOf('새로운 응답') ?? -1
    expect(pos1).toBeGreaterThanOrEqual(0)
    expect(pos2).toBeGreaterThanOrEqual(0)
    expect(pos1).toBeLessThan(pos2)
    unmount()
  })

  it('Static 오염 0 — spinner 프레임 잔재 없음 (TST-03)', () => {
    // 완결 메시지(streaming:false)에 spinner 문자가 잔재하면 안 됨
    useMessagesStore.setState({
      completedMessages: [
        {id: 'done-01', role: 'assistant', content: '완료된 메시지', streaming: false},
      ],
      activeMessage: null,
    })
    const {lastFrame, unmount} = render(<App />)
    const frame = lastFrame() ?? ''
    // spinner 프레임 문자 (Braille dots) 가 포함되면 Static 오염
    expect(frame).not.toMatch(/[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]/)
    expect(frame).toMatchSnapshot()
    unmount()
  })
})
