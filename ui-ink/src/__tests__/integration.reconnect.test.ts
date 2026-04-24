// reconnect delta (x-resume-from 헤더) + 로컬-원격 동등성 통합 테스트 (TST-02, REM-06)
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
// 열린 소켓 추적 — afterAll에서 완전 종료 보장
const openSockets: Set<WebSocket> = new Set()

beforeAll(async () => {
  // port:0 → OS가 빈 포트 자동 할당 (포트 충돌 방지 — T-04-01)
  fakeServer = new WebSocketServer({port: 0})
  const port = (fakeServer.address() as {port: number}).port
  serverUrl = `ws://127.0.0.1:${port}`

  // 모든 연결 소켓 추적 (afterAll 종료 시 강제 닫기)
  fakeServer.on('connection', (ws) => {
    openSockets.add(ws)
    ws.on('close', () => openSockets.delete(ws))
  })
})

afterAll(async () => {
  // 열린 소켓 강제 종료 후 서버 닫기 — T-04-01 mitigate (타임아웃 방지)
  openSockets.forEach(ws => ws.terminate())
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

describe('integration: reconnect delta x-resume-from 헤더 (TST-02, REM-06)', () => {
  it('재연결 시 x-resume-from 헤더에 lastEventId 포함 (TST-02 reconnect delta, REM-06)', async () => {
    // 서버에서 연결 수신 + 요청 헤더 캡처
    const headerCaptures: Array<Record<string, string>> = []
    const connectionP = new Promise<void>((resolve) => {
      fakeServer.once('connection', (_ws: WebSocket, req) => {
        // 요청 헤더 저장
        headerCaptures.push(req.headers as Record<string, string>)
        resolve()
      })
    })

    // WSR-03: lastEventId=42 사전 설정 — 재연결 시 헤더에 포함되어야 함
    useRoomStore.setState({
      roomName: '', members: [], activeInputFrom: null, activeIsSelf: true,
      busy: false, wsState: 'connected', reconnectAttempt: 0, lastEventId: 42,
    })

    const client = new HarnessClient({url: serverUrl, token: 'delta-token'})
    client.connect()

    // 연결 완료 대기
    await connectionP

    // x-resume-from 헤더 검증 (WSR-03)
    const headers = headerCaptures[headerCaptures.length - 1]
    expect(headers?.['x-resume-from']).toBe('42')

    client.close()
  })

  it('로컬-원격 동등성 — 동일 시나리오가 127.0.0.1 Fake 서버에서 green (TST-02, REM-06)', async () => {
    // REM-06: 이 시나리오는 원격 ws://external-host:7891에서도 동일하게 동작해야 함
    // serverUrl = ws://127.0.0.1:{port} — 로컬과 원격의 동일한 플로우 검증

    // 서버 측 연결 대기 — Promise로 serverWs 직접 획득
    const connectionP = new Promise<WebSocket>((resolve) => {
      fakeServer.once('connection', (ws) => resolve(ws))
    })

    const client = new HarnessClient({url: serverUrl, token: 'local-token'})
    client.connect()

    const serverWs = await connectionP

    // 서버 → 클라: ready 전송 → connected 상태 업데이트
    serverWs.send(JSON.stringify({type: 'ready', room: 'testroom'}))
    await new Promise<void>((r) => setTimeout(r, 20))

    expect(useStatusStore.getState().connected).toBe(true)

    // 서버 → 클라: agent_start 전송 → busy=true
    serverWs.send(JSON.stringify({type: 'agent_start', from_self: true}))
    await new Promise<void>((r) => setTimeout(r, 20))

    expect(useStatusStore.getState().busy).toBe(true)

    // 서버 → 클라: agent_end 전송 → busy=false
    serverWs.send(JSON.stringify({type: 'agent_end'}))
    await new Promise<void>((r) => setTimeout(r, 20))

    expect(useStatusStore.getState().busy).toBe(false)

    client.close()
  })
})
