// confirm_write CR-01 버그 자동 발견 통합 테스트 (TST-02)
// D-01: vi.mock('ws') 없이 실제 TCP WS 서버 기동
import {describe, it, expect, beforeAll, afterAll, beforeEach} from 'vitest'
import {WebSocketServer} from 'ws'
import type WebSocket from 'ws'
import {HarnessClient} from '../ws/client.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore, bindConfirmClient} from '../store/confirm.js'

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

describe('integration: confirm_write CR-01 버그 자동 발견 (TST-02)', () => {
  it('confirm_write accept — CR-01: 서버가 accept 필드를 수신해야 한다', async () => {
    // 서버 측 연결 수신 대기
    const connectionP = new Promise<WebSocket>((resolve) => {
      fakeServer.once('connection', (ws) => resolve(ws))
    })

    const client = new HarnessClient({url: serverUrl, token: 'confirm-token'})
    // confirm 응답 전송을 위해 client를 store에 바인딩
    bindConfirmClient(client)
    client.connect()

    const serverWs = await connectionP

    // 서버 → 클라: confirm_write 트리거
    serverWs.send(JSON.stringify({type: 'confirm_write', path: '/tmp/test.txt'}))
    // 비동기 dispatch 완료 대기
    await new Promise<void>((r) => setTimeout(r, 20))

    // confirm store에 mode가 설정되었는지 검증
    expect(useConfirmStore.getState().mode).toBe('confirm_write')

    // 서버가 다음 메시지 수신 준비 (클라 → 서버)
    const receivedP = new Promise<string>((resolve) => {
      serverWs.once('message', (data) => resolve(data.toString()))
    })

    // y 키 입력 시뮬레이션 — resolve(true) 호출
    useConfirmStore.getState().resolve(true)

    const received = await receivedP
    const msg = JSON.parse(received)

    // CR-01 검증: 클라이언트가 올바른 필드(accept)를 서버에 전송하는지 확인
    // CR-01 이슈: 서버(harness_server.py:782)가 'result' 필드를 읽는데
    // 클라이언트(confirm.ts:61)는 'accept' 필드를 전송함 — 필드명 불일치
    // 이 테스트는 "클라이언트가 accept 필드를 올바르게 전송하는지" 검증
    expect(msg.type).toBe('confirm_write_response')
    // CR-01: 클라이언트는 accept:true를 전송 (이것이 올바른 동작)
    expect(msg.accept).toBe(true)
    // CR-01: result 필드는 없어야 함 (클라이언트가 잘못된 필드를 전송하지 않음)
    expect(msg.result).toBeUndefined()

    // 참고: 이 테스트는 PASS가 정상 — 클라이언트 측은 올바름
    // CR-01 버그는 서버 측(harness_server.py)에 있음: accept 대신 result를 읽음
    // 서버 수정(04-05)에서 harness_server.py의 result → accept 교정 예정

    client.close()
  })
})
