// HarnessClient — WS 연결 · send · heartbeat (FND-05)
// WSR-01: jitter exponential backoff + resume_from 헤더 (Phase 3)
import WebSocket from 'ws'
import {parseServerMsg} from './parse.js'
import {dispatch} from './dispatch.js'
import {useStatusStore} from '../store/status.js'
import {useMessagesStore} from '../store/messages.js'
import {useRoomStore} from '../store/room.js'
import type {ClientMsg} from '../protocol.js'
import {bindConfirmClient} from '../store/confirm.js'

export interface ConnectOptions {
  url: string
  token: string
  room?: string
  resumeSession?: string  // --resume <id> 세션 ID (SES-02)
}

export class HarnessClient {
  private ws: WebSocket | null = null
  private opts: ConnectOptions
  private pingInterval: ReturnType<typeof setInterval> | null = null
  // WSR-01: jitter exponential backoff 상태
  private backoff = {
    attempts: 0,
    stableTimer: null as ReturnType<typeof setTimeout> | null,
  }
  private _closed = false  // close() 명시적 호출 시 재연결 방지

  constructor(opts: ConnectOptions) {
    this.opts = opts
  }

  connect(): void {
    const headers: Record<string, string> = {
      'x-harness-token': this.opts.token,
    }
    if (this.opts.room) headers['x-harness-room'] = this.opts.room
    // WSR-03: delta replay 요청 — lastEventId가 있으면 resume_from 헤더 추가
    const lastEventId = useRoomStore.getState().lastEventId
    if (lastEventId != null) headers['x-resume-from'] = String(lastEventId)
    // SES-02: 세션 resume 헤더
    if (this.opts.resumeSession) headers['x-resume-session'] = this.opts.resumeSession

    this.ws = new WebSocket(this.opts.url, {headers})

    this.ws.on('open', () => {
      useStatusStore.getState().setConnected(true)
      useRoomStore.getState().setWsState('connected')
      // confirm 응답 전송용 client 바인딩 (CNF-03)
      bindConfirmClient(this)
      // RPC-07: 연결 직후 클라 cwd 를 서버에 동기화 — LLM 의 args.path 가 사용자 PC 기준 경로가 되도록.
      // process.cwd() 가 절대경로 보장 (ui-ink 가 사용자가 띄운 위치).
      this.send({type: 'client_hello', cwd: process.cwd()})
      // WSR-01: 30초 안정 후 attempts 리셋
      this._onConnectedStable()
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
      // stableTimer 취소 (연결 안정화 전에 끊김)
      if (this.backoff.stableTimer) {
        clearTimeout(this.backoff.stableTimer)
        this.backoff.stableTimer = null
      }
      // WSR-01: 명시적 close()가 아닌 경우에만 재연결
      if (!this._closed) {
        this._scheduleReconnect()
      }
    })

    this.ws.on('error', (err) => {
      useMessagesStore.getState().appendSystemMessage(`ws 오류: ${(err as Error).message}`)
    })
  }

  send(msg: ClientMsg): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  close(): void {
    this._closed = true  // 재연결 방지
    this._clearPing()
    if (this.backoff.stableTimer) clearTimeout(this.backoff.stableTimer)
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

  // WSR-01: jitter exponential backoff 재연결 스케줄러
  // 공식: delay = min(base * 2^n * (0.5 + rand*0.5), cap)
  private _scheduleReconnect(): void {
    const {attempts} = this.backoff
    if (attempts >= 10) {
      // 10회 실패 → failed 상태로 고정 (T-03-05-01)
      useRoomStore.getState().setWsState('failed')
      return
    }
    const base = 1000
    const cap = 30_000
    const delay = Math.min(
      base * Math.pow(2, attempts) * (0.5 + Math.random() * 0.5),
      cap,
    )
    this.backoff.attempts++
    useRoomStore.getState().setReconnectAttempt(this.backoff.attempts)
    useRoomStore.getState().setWsState('reconnecting')
    setTimeout(() => {
      if (!this._closed) this.connect()
    }, delay)
  }

  // WSR-01: 연결 안정화 후 30초 경과 시 attempts 리셋 (thundering herd 방지)
  private _onConnectedStable(): void {
    if (this.backoff.stableTimer) clearTimeout(this.backoff.stableTimer)
    this.backoff.stableTimer = setTimeout(() => {
      this.backoff.attempts = 0
      this.backoff.stableTimer = null
    }, 30_000)
  }
}
