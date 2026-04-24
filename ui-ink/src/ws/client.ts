// HarnessClient — WS 연결 · send · heartbeat (FND-05)
// reconnect / backoff 는 Phase 3 (WSR-01) 에서 완성
import WebSocket from 'ws'
import {parseServerMsg} from './parse.js'
import {dispatch} from './dispatch.js'
import {useStatusStore} from '../store/status.js'
import {useMessagesStore} from '../store/messages.js'
import type {ClientMsg} from '../protocol.js'
import {bindConfirmClient} from '../store/confirm.js'

export interface ConnectOptions {
  url: string
  token: string
  room?: string
}

export class HarnessClient {
  private ws: WebSocket | null = null
  private opts: ConnectOptions
  private pingInterval: ReturnType<typeof setInterval> | null = null

  constructor(opts: ConnectOptions) {
    this.opts = opts
  }

  connect(): void {
    const headers: Record<string, string> = {
      'x-harness-token': this.opts.token,
    }
    if (this.opts.room) headers['x-harness-room'] = this.opts.room

    this.ws = new WebSocket(this.opts.url, {headers})

    this.ws.on('open', () => {
      useStatusStore.getState().setConnected(true)
      // confirm 응답 전송용 client 바인딩 (CNF-03)
      bindConfirmClient(this)
      // heartbeat
      this.pingInterval = setInterval(() => {
        this.send({type: 'ping'})
      }, 30_000)
    })

    this.ws.on('message', (raw) => {
      const msg = parseServerMsg(raw.toString())
      if (msg) dispatch(msg)
    })

    this.ws.on('close', () => {
      useStatusStore.getState().setConnected(false)
      this._clearPing()
      // Phase 3 에서 jitter backoff reconnect 추가
    })

    this.ws.on('error', (err) => {
      useMessagesStore.getState().appendSystemMessage(`ws 오류: ${err.message}`)
    })
  }

  send(msg: ClientMsg): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  close(): void {
    this._clearPing()
    this.ws?.close()
    this.ws = null
    // confirm 바인딩 해제
    bindConfirmClient(null)
  }

  private _clearPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }
}
