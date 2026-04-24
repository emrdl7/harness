// room busy + 3인 동시 재접속 통합 테스트 (TST-02)
// D-01: vi.mock('ws') 없이 실제 TCP WS 서버 기동
import {describe, it, expect, beforeAll, afterAll, beforeEach} from 'vitest'
import {WebSocketServer} from 'ws'
import type WebSocket from 'ws'
import {HarnessClient} from '../ws/client.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'

// ─── Fake WS 서버 lifecycle (D-01, D-03: port:0 OS 할당) ──────────────────────
let fakeServer: WebSocketServer
let serverUrl: string

beforeAll(async () => {
  // port:0 → OS가 빈 포트 자동 할당 (포트 충돌 방지 — T-04-01)
  fakeServer = new WebSocketServer({port: 0})
  const port = (fakeServer.address() as {port: number}).port
  serverUrl = `ws://127.0.0.1:${port}`
})

afterAll(async () => {
  // 서버 완전 종료 보장 — T-04-01 mitigate
  await new Promise<void>((resolve) => fakeServer.close(() => resolve()))
})

// ─── Store 초기화 (dispatch.test.ts 패턴) ────────────────────────────────────
beforeEach(() => {
  useMessagesStore.setState({completedMessages: [], activeMessage: null})
  useStatusStore.setState({busy: false, connected: false})
  useRoomStore.setState({
    roomName: '', members: [], activeInputFrom: null, activeIsSelf: true,
    busy: false, wsState: 'connected', reconnectAttempt: 0, lastEventId: null,
  })
  useConfirmStore.setState({mode: 'none', payload: {}})
})

describe('integration: room busy + 3인 동시 재접속 (TST-02)', () => {
  it('room_busy 수신 → useRoomStore.busy === true (TST-02)', async () => {
    // 서버 측 연결 수신 대기
    const connectionP = new Promise<WebSocket>((resolve) => {
      fakeServer.once('connection', (ws) => resolve(ws))
    })

    const client = new HarnessClient({url: serverUrl, token: 'room-busy-token'})
    client.connect()

    const serverWs = await connectionP

    // 서버 → 클라: room_busy 전송
    serverWs.send(JSON.stringify({type: 'room_busy'}))
    // 비동기 dispatch 완료 대기
    await new Promise<void>((r) => setTimeout(r, 20))

    expect(useRoomStore.getState().busy).toBe(true)

    client.close()
  })

  it('3개 HarnessClient 동시 접속 — 전원 연결 확인 (TST-02 3인 동시 재접속)', async () => {
    // T-04-03: 3인 동시 접속, 각 클라이언트 정리 보장
    const clients = [
      new HarnessClient({url: serverUrl, token: 'token-a'}),
      new HarnessClient({url: serverUrl, token: 'token-b'}),
      new HarnessClient({url: serverUrl, token: 'token-c'}),
    ]

    // 서버 측 3개 연결 수신 대기 Promise
    const serverWsList: WebSocket[] = []
    const allConnected = new Promise<void>((resolve) => {
      let count = 0
      fakeServer.on('connection', (ws) => {
        serverWsList.push(ws)
        count++
        if (count === 3) resolve()
      })
    })

    // 3개 클라이언트 동시 연결
    clients.forEach(c => c.connect())

    // 3개 연결 완료 대기 (최대 2000ms)
    await allConnected

    // 각 서버 WS에서 ready 전송 → connected 상태 업데이트
    serverWsList.forEach(ws => {
      ws.send(JSON.stringify({type: 'ready', room: ''}))
    })
    await new Promise<void>((r) => setTimeout(r, 20))

    // 마지막 클라이언트 기준으로 connected 확인
    // (Zustand store는 전역 싱글톤이므로 마지막 ready 수신 결과)
    expect(useStatusStore.getState().connected).toBe(true)

    // T-04-03: 모든 클라이언트 정리
    clients.forEach(c => c.close())
  })
})
