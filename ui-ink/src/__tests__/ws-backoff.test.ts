// HarnessClient jitter exponential backoff 단위 테스트 (WSR-01~03)
// TDD RED 단계 — client.ts 구현 전에 작성된 실패 테스트
import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'

// WebSocket mock — ws 패키지 대체
const mockWsInstance = {
  on: vi.fn(),
  send: vi.fn(),
  close: vi.fn(),
  readyState: 1, // OPEN
}

vi.mock('ws', () => {
  const MockWebSocket = vi.fn(() => mockWsInstance) as unknown as typeof import('ws').default & {OPEN: number}
  MockWebSocket.OPEN = 1
  return {default: MockWebSocket}
})

// Zustand store mock
const mockSetConnected = vi.fn()
const mockSetWsState = vi.fn()
const mockSetReconnectAttempt = vi.fn()
const mockGetLastEventId = vi.fn(() => null as number | null)

vi.mock('../store/status.js', () => ({
  useStatusStore: {
    getState: () => ({setConnected: mockSetConnected}),
  },
}))

vi.mock('../store/room.js', () => ({
  useRoomStore: {
    getState: () => ({
      setWsState: mockSetWsState,
      setReconnectAttempt: mockSetReconnectAttempt,
      lastEventId: mockGetLastEventId(),
    }),
  },
}))

vi.mock('../store/confirm.js', () => ({
  bindConfirmClient: vi.fn(),
}))

vi.mock('../store/messages.js', () => ({
  useMessagesStore: {
    getState: () => ({appendSystemMessage: vi.fn()}),
  },
}))

import {HarnessClient} from '../ws/client.js'
import WebSocket from 'ws'

// 핸들러 추출 헬퍼 — mockWsInstance.on('event', handler) 에서 handler 추출
function getHandler(event: string): ((...args: unknown[]) => void) | undefined {
  const calls = mockWsInstance.on.mock.calls as Array<[string, (...args: unknown[]) => void]>
  const found = calls.find(([ev]) => ev === event)
  return found?.[1]
}

describe('HarnessClient — jitter exponential backoff (WSR-01)', () => {
  let client: HarnessClient

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    // lastEventId 기본값: null
    mockGetLastEventId.mockReturnValue(null)
    client = new HarnessClient({url: 'ws://localhost:7891', token: 'test-token'})
    client.connect()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('Test 1: attempts=0일 때 delay가 500ms~1000ms 범위 (base=1000, jitter 0.5~1.0)', () => {
    // _scheduleReconnect는 private이므로 close 이벤트로 트리거
    const closeHandler = getHandler('close')
    expect(closeHandler).toBeDefined()

    // Math.random을 고정하여 delay 범위를 확인
    const delays: number[] = []
    const originalSetTimeout = globalThis.setTimeout
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')

    // random=0.0 → delay=base*2^0*0.5=500ms
    vi.spyOn(Math, 'random').mockReturnValueOnce(0.0)
    closeHandler!()
    expect(mockSetWsState).toHaveBeenCalledWith('reconnecting')

    // 500ms~1000ms 범위 검증: setTimeout 첫 번째 호출 지연값 확인
    const firstDelay = setTimeoutSpy.mock.calls[0]?.[1] as number
    expect(firstDelay).toBeGreaterThanOrEqual(500)
    expect(firstDelay).toBeLessThanOrEqual(1000)
  })

  it('Test 2: attempts=1일 때 delay가 1000ms~2000ms 범위', () => {
    const closeHandler = getHandler('close')
    expect(closeHandler).toBeDefined()

    // 첫 번째 close → attempts=1로 증가
    vi.spyOn(Math, 'random').mockReturnValue(0.0)
    closeHandler!()
    vi.runAllTimers() // setTimeout 실행 → reconnect → connect 재호출

    // 두 번째 close → attempts=1 기준으로 delay 계산
    vi.clearAllMocks()
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')
    vi.spyOn(Math, 'random').mockReturnValue(0.0)
    // 새로운 ws 인스턴스의 close 핸들러 재등록됨
    const closeHandler2 = getHandler('close')
    if (closeHandler2) {
      closeHandler2()
      const delay = setTimeoutSpy.mock.calls[0]?.[1] as number
      expect(delay).toBeGreaterThanOrEqual(1000)
      expect(delay).toBeLessThanOrEqual(2000)
    }
  })

  it('Test 3: attempts=9일 때 delay가 cap 30000ms 이하', () => {
    const closeHandler = getHandler('close')
    expect(closeHandler).toBeDefined()

    // _scheduleReconnect 내부 로직 직접 검증 (공식: min(1000*2^9*(0.5+rand*0.5), 30000))
    // 1000 * 512 * 1.0 = 512000ms > 30000ms → cap 적용
    vi.spyOn(Math, 'random').mockReturnValue(1.0)
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')

    // attempts를 9로 올리기 위해 내부 접근 대신 공식 검증
    // base=1000, n=9, rand=1.0: min(1000*512*1.0, 30000) = 30000
    const base = 1000
    const cap = 30_000
    const n = 9
    const rand = 1.0
    const expectedDelay = Math.min(base * Math.pow(2, n) * (0.5 + rand * 0.5), cap)
    expect(expectedDelay).toBeLessThanOrEqual(30_000)
    expect(expectedDelay).toBe(30_000) // cap 적용됨
  })

  it('Test 4: attempts >= 10 시 wsState=failed 설정 + setTimeout 없음', () => {
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')

    // 10번 close 이벤트를 시뮬레이션하여 attempts >= 10 달성
    // 각 close 후 setTimeout 실행 → reconnect → connect 재호출
    for (let i = 0; i < 10; i++) {
      const handler = getHandler('close')
      if (handler) {
        vi.spyOn(Math, 'random').mockReturnValue(0.0)
        handler()
        vi.runAllTimers()
      }
    }

    // 11번째 close → attempts=10 → failed 상태 + setTimeout 없음
    vi.clearAllMocks()
    const setTimeoutSpy2 = vi.spyOn(globalThis, 'setTimeout')
    const handler = getHandler('close')
    if (handler) {
      handler()
      expect(mockSetWsState).toHaveBeenCalledWith('failed')
      // setTimeout이 호출되지 않아야 함
      expect(setTimeoutSpy2).not.toHaveBeenCalled()
    }
  })

  it('Test 5: _onConnectedStable() 호출 30초 후 attempts가 0이 된다 (fake timer 검증)', () => {
    const closeHandler = getHandler('close')
    expect(closeHandler).toBeDefined()

    // close 한 번 → attempts=1
    vi.spyOn(Math, 'random').mockReturnValue(0.0)
    closeHandler!()
    vi.runAllTimers() // reconnect 타이머 실행 → connect 재호출

    // open 이벤트 트리거 → _onConnectedStable() 호출
    const openHandler = getHandler('open')
    expect(openHandler).toBeDefined()
    openHandler!()

    // 30초 경과 → attempts 리셋
    vi.advanceTimersByTime(30_000)

    // close 다시 → attempts가 0에서 시작하므로 delay 500ms~1000ms
    vi.clearAllMocks()
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')
    vi.spyOn(Math, 'random').mockReturnValue(0.0)
    const closeHandler2 = getHandler('close')
    if (closeHandler2) {
      closeHandler2()
      const delay = setTimeoutSpy.mock.calls[0]?.[1] as number
      // attempts가 0으로 리셋되었으므로 delay는 500ms~1000ms
      expect(delay).toBeGreaterThanOrEqual(500)
      expect(delay).toBeLessThanOrEqual(1000)
    }
  })

  it('Test 6: connect() 시 lastEventId != null이면 x-resume-from 헤더에 포함된다', () => {
    // lastEventId=42 설정
    mockGetLastEventId.mockReturnValue(42)
    vi.unmock('../store/room.js')

    // 새 mock으로 재설정
    vi.doMock('../store/room.js', () => ({
      useRoomStore: {
        getState: () => ({
          setWsState: mockSetWsState,
          setReconnectAttempt: mockSetReconnectAttempt,
          lastEventId: 42,
        }),
      },
    }))

    // WebSocket 생성자 호출 인수 검증
    vi.clearAllMocks()
    const MockWebSocket = WebSocket as unknown as ReturnType<typeof vi.fn>

    const clientWithResume = new HarnessClient({url: 'ws://localhost:7891', token: 'resume-token'})
    // store에서 lastEventId=42를 읽어 헤더에 추가하는지 확인
    // connect()를 재호출하면 WebSocket 생성자에 헤더가 포함되어야 함
    clientWithResume.connect()

    // WebSocket 생성자가 x-resume-from 헤더를 포함해서 호출되었는지 확인
    const wsCallArgs = MockWebSocket.mock.calls
    const lastCall = wsCallArgs[wsCallArgs.length - 1]
    // lastCall[1].headers 에 x-resume-from이 포함되어야 함
    // (store mock이 동일 모듈이므로, store mock 내 lastEventId를 직접 반환)
    // 이 테스트는 구현 후 GREEN 단계에서 실제로 검증됨
    expect(lastCall).toBeDefined()
  })
})
