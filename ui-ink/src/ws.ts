/* harness_server.py 와의 WebSocket 연결 (레거시 — Plan C 에서 ws/client.ts 로 교체 예정).
 *
 * 프로토콜 (교정된 이름):
 *   · 서버 → 클라: ready / state_snapshot / token / tool_start / tool_end /
 *                   confirm_write / confirm_bash / error / agent_start /
 *                   agent_end / room_* / queue / queue_ready
 *   · 클라 → 서버: input / confirm_write_response / confirm_bash_response /
 *                   slash
 *
 * 현 스켈레톤은 연결 + 기본 메시지 라우팅만. 상세 구현은 ws/dispatch.ts 참조.
 */
import WebSocket from 'ws';
import {useStore, Message} from './store.js';

export interface ConnectOptions {
  url: string;
  token: string;
  room?: string;
}

export function connect({url, token, room}: ConnectOptions): WebSocket {
  const headers: Record<string, string> = {
    'x-harness-token': token,
  };
  if (room) headers['x-harness-room'] = room;

  const ws = new WebSocket(url, {headers});

  ws.on('open', () => {
    useStore.getState().setStatus([
      {label: 'connected', color: 'green'},
    ]);
  });

  ws.on('message', (raw) => {
    let msg: any;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }
    const {appendMessage, setBusy} = useStore.getState();
    switch (msg.type) {
      case 'ready':
        // TODO: 초기화 처리
        break;
      case 'token':
        appendMessage({role: 'assistant', content: String(msg.text ?? '')});
        break;
      case 'tool_start':
        appendMessage({
          role: 'tool',
          content: `[${msg.name}] ${JSON.stringify(msg.args ?? {})}`,
        });
        break;
      case 'tool_end':
        appendMessage({
          role: 'tool',
          content: `[${msg.name}] ${msg.result ?? ''}`,
          meta: {result: msg.result},
        });
        break;
      case 'agent_start':
        setBusy(true);
        break;
      case 'agent_end':
        setBusy(false);
        break;
      case 'error':
        appendMessage({role: 'system', content: `오류: ${msg.text}`});
        break;
      // TODO: confirm_write / confirm_bash / room_* / state_snapshot
    }
  });

  ws.on('close', () => {
    useStore.getState().setStatus([
      {label: 'disconnected', color: 'red'},
    ]);
  });

  ws.on('error', (err) => {
    const m: Message = {role: 'system', content: `ws error: ${err.message}`};
    useStore.getState().appendMessage(m);
  });

  return ws;
}

export function sendInput(ws: WebSocket, text: string) {
  ws.send(JSON.stringify({type: 'input', text}));
}
