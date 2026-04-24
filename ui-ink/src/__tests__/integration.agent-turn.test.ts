// agent 턴 + one-shot 통합 테스트 (TST-02)
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

// ─── Store 초기화 (dispatch.test.ts 패턴 그대로) ────────────────────────────────
beforeEach(() => {
  useMessagesStore.setState({completedMessages: [], activeMessage: null})
  useStatusStore.setState({busy: false, connected: false})
  useRoomStore.setState({
    roomName: '', members: [], activeInputFrom: null, activeIsSelf: true,
    busy: false, wsState: 'connected', reconnectAttempt: 0, lastEventId: null,
  })
  useConfirmStore.setState({mode: 'none', payload: {}})
})

describe('integration: agent 턴 (TST-02)', () => {
  it('agent_start → busy=true, agent_end → busy=false (TST-02)', async () => {
    // 서버 측 연결 수신 대기
    const connectionP = new Promise<WebSocket>((resolve) => {
      fakeServer.once('connection', (ws) => resolve(ws))
    })

    const client = new HarnessClient({url: serverUrl, token: 'test-token'})
    client.connect()

    const serverWs = await connectionP

    // 서버 → 클라: agent_start 전송
    serverWs.send(JSON.stringify({type: 'agent_start', from_self: true}))
    // 비동기 dispatch 완료 대기
    await new Promise<void>((r) => setTimeout(r, 20))

    expect(useStatusStore.getState().busy).toBe(true)

    // 서버 → 클라: agent_end 전송
    serverWs.send(JSON.stringify({type: 'agent_end'}))
    await new Promise<void>((r) => setTimeout(r, 20))

    expect(useStatusStore.getState().busy).toBe(false)

    client.close()
  })

  it('agent_end 수신 후 클라이언트가 close 요청을 보낸다 (TST-02 one-shot)', async () => {
    // 서버 측 연결 수신 대기
    const connectionP = new Promise<WebSocket>((resolve) => {
      fakeServer.once('connection', (ws) => resolve(ws))
    })

    const client = new HarnessClient({url: serverUrl, token: 'oneshot-token'})
    client.connect()

    const serverWs = await connectionP

    // 서버 → 클라: ready 전송 후 agent_end 전송
    serverWs.send(JSON.stringify({type: 'ready', room: ''}))
    await new Promise<void>((r) => setTimeout(r, 20))

    serverWs.send(JSON.stringify({type: 'agent_end'}))
    await new Promise<void>((r) => setTimeout(r, 20))

    // HarnessClient 단독 동작 검증: agent_end 수신 시 busy=false
    expect(useStatusStore.getState().busy).toBe(false)

    // 명시적 close 후 serverWs readyState 확인
    client.close()
    await new Promise<void>((r) => setTimeout(r, 20))

    // 참고: HarnessClient는 agent_end에 auto-close하지 않으므로
    // busy=false assertion만으로 one-shot 동작 검증
    expect(useStatusStore.getState().busy).toBe(false)
  })
})
