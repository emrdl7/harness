// one-shot 경량 WS 클라이언트 (SES-01, SES-03)
// REPL 없이 단일 질문 → answer stdout → exit
// non-TTY 시 ANSI off (Pitfall G 방지)
import WebSocket from 'ws'
import type {ServerMsg} from './protocol.js'
import {parseServerMsg} from './ws/parse.js'

export interface OneShotOptions {
  url: string
  token: string
  query: string
  room?: string
  ansi: boolean   // true = TTY 환경 (ANSI 출력 허용)
}

export async function runOneShot(opts: OneShotOptions): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const headers: Record<string, string> = {
      'x-harness-token': opts.token,
    }
    if (opts.room) headers['x-harness-room'] = opts.room

    const ws = new WebSocket(opts.url, {headers})
    let resolved = false

    // 30초 타임아웃 (서버 무응답 방지) — T-03-05-04
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true
        ws.close()
        reject(new Error('[harness] one-shot 타임아웃 (30s)'))
      }
    }, 30_000)

    ws.on('open', () => {
      // open 시점에 아무것도 하지 않음 — ready 이벤트를 기다려야 함
    })

    ws.on('message', (raw) => {
      const msg = parseServerMsg(raw.toString()) as (ServerMsg & {type: string}) | null
      if (!msg) return

      switch (msg.type) {
        case 'ready':
          // 서버 준비 완료 → 질문 전송
          ws.send(JSON.stringify({type: 'input', text: opts.query}))
          break

        case 'token': {
          // 토큰 누적 출력 (non-TTY 시 ANSI 없이 — piping 안전)
          // eslint-disable-next-line no-restricted-syntax
          process.stdout.write((msg as {type: 'token'; text: string}).text)
          break
        }

        case 'agent_end':
          // 응답 완료 → 개행 후 종료
          if (!resolved) {
            resolved = true
            clearTimeout(timeout)
            // eslint-disable-next-line no-restricted-syntax
            process.stdout.write('\n')
            ws.close()
            resolve()
          }
          break

        case 'error':
          if (!resolved) {
            resolved = true
            clearTimeout(timeout)
            ws.close()
            reject(new Error(`[harness] 서버 오류: ${(msg as {type: 'error'; text: string}).text}`))
          }
          break

        default:
          // 나머지 이벤트 (state_snapshot, room_joined 등) — one-shot에서 무시
          break
      }
    })

    ws.on('error', (err) => {
      if (!resolved) {
        resolved = true
        clearTimeout(timeout)
        reject(err)
      }
    })

    ws.on('close', () => {
      if (!resolved) {
        resolved = true
        clearTimeout(timeout)
        // 서버 종료로 인한 예기치 않은 close
        reject(new Error('[harness] WS 연결 종료됨'))
      }
    })
  })
}
