import React, {useEffect, useState} from 'react';
import {Box, Text, useApp, useInput, useStdout} from 'ink';
import TextInput from 'ink-text-input';
import {useStore} from './store.js';
import {connect, sendInput} from './ws.js';
import type WebSocket from 'ws';

const SPIN = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

/* Claude Code 스타일 레이아웃:
 *   Message List (flexGrow=1)
 *   top rule (────)
 *   input row ( ❯ ...)
 *   bottom rule (────)
 *   status bar
 *
 * Ink + Yoga flex 라 resize/wrap 은 엔진이 처리. scrollback 도 유지.
 */
export const App: React.FC = () => {
  const {exit} = useApp();
  const {stdout} = useStdout();
  const cols = stdout.columns ?? 80;

  const messages = useStore((s) => s.messages);
  const input = useStore((s) => s.input);
  const setInput = useStore((s) => s.setInput);
  const appendMessage = useStore((s) => s.appendMessage);
  const status = useStore((s) => s.status);
  const busy = useStore((s) => s.busy);

  const [ws, setWs] = useState<WebSocket | null>(null);
  const [spinIdx, setSpinIdx] = useState(0);

  // WS 연결 (환경변수 기반). 없으면 로컬 데모 모드.
  useEffect(() => {
    const url = process.env.HARNESS_URL;
    const token = process.env.HARNESS_TOKEN;
    if (url && token) {
      const socket = connect({
        url,
        token,
        room: process.env.HARNESS_ROOM,
      });
      setWs(socket);
      return () => socket.close();
    }
  }, []);

  // 스피너 프레임 회전
  useEffect(() => {
    if (!busy) return;
    const id = setInterval(() => setSpinIdx((i) => (i + 1) % SPIN.length), 100);
    return () => clearInterval(id);
  }, [busy]);

  // 전역 키 — Ctrl+C 종료
  useInput((_ch, key) => {
    if (key.ctrl && _ch === 'c') exit();
  });

  const onSubmit = (text: string) => {
    const t = text.trim();
    setInput('');
    if (!t) return;
    appendMessage({role: 'user', content: t});
    if (ws && ws.readyState === 1) {
      sendInput(ws, t);
    } else {
      appendMessage({
        role: 'system',
        content: '(연결 안 됨 — HARNESS_URL / HARNESS_TOKEN 필요)',
      });
    }
  };

  return (
    <Box flexDirection="column">
      {/* Message List */}
      <Box flexDirection="column">
        {messages.map((m, i) => (
          <Box key={i} marginBottom={0}>
            <Text color={m.role === 'user' ? 'cyan' : m.role === 'assistant' ? 'yellow' : 'gray'} bold={m.role !== 'system'}>
              {m.role === 'user' ? '❯ ' : m.role === 'assistant' ? '● ' : m.role === 'tool' ? '└ ' : '  '}
            </Text>
            <Text wrap="wrap">{m.content}</Text>
          </Box>
        ))}
      </Box>

      {/* top rule */}
      <Text dimColor>{'─'.repeat(Math.max(10, cols))}</Text>

      {/* input row */}
      <Box>
        <Text color="cyan" bold>
          ❯{' '}
        </Text>
        <TextInput value={input} onChange={setInput} onSubmit={onSubmit} />
      </Box>

      {/* bottom rule */}
      <Text dimColor>{'─'.repeat(Math.max(10, cols))}</Text>

      {/* status bar */}
      <Box>
        {busy && (
          <Text color="cyan">
            {' ' + SPIN[spinIdx] + ' '}
          </Text>
        )}
        {status.map((seg, i) => (
          <Text key={i} color={seg.color ?? 'gray'}>
            {(i === 0 ? '  ' : '    ') + seg.label}
          </Text>
        ))}
      </Box>
    </Box>
  );
};
