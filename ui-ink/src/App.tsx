// App 컴포넌트 — Phase 1 스모크용 최소 구현
// ink-text-input 제거 / useState<WebSocket> 제거 / index key 제거 (CLAUDE.md)
import React, {useEffect, useRef} from 'react'
import {Box, Text, useApp, useInput} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from './store/messages.js'
import {useStatusStore} from './store/status.js'
import {useInputStore} from './store/input.js'
import {HarnessClient} from './ws/client.js'

// 스피너 프레임 (busy 상태 표시용 — Phase 2 에서 ink-spinner 로 교체)
const SPIN = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

export const App: React.FC = () => {
  const {exit} = useApp()

  // 슬라이스 선택자 — useShallow 로 필요한 필드만 구독 (FND-06, CLAUDE.md)
  const messages = useMessagesStore(useShallow((s) => s.messages))
  const {buffer, setBuffer, clearBuffer} = useInputStore(useShallow((s) => ({
    buffer: s.buffer,
    setBuffer: s.setBuffer,
    clearBuffer: s.clearBuffer,
  })))
  const {connected, busy} = useStatusStore(useShallow((s) => ({
    connected: s.connected,
    busy: s.busy,
  })))

  // WS 클라이언트 ref (useState 아님 — 전체 리렌더 방지)
  const clientRef = useRef<HarnessClient | null>(null)
  const spinRef = useRef(0)

  // WS 연결 초기화
  useEffect(() => {
    const url = process.env['HARNESS_URL']
    const token = process.env['HARNESS_TOKEN']
    if (url && token) {
      const client = new HarnessClient({
        url,
        token,
        room: process.env['HARNESS_ROOM'],
      })
      client.connect()
      clientRef.current = client
      return () => {
        client.close()
        clientRef.current = null
      }
    }
  }, [])

  // 입력 처리 — useInput 으로 키 이벤트 구독
  useInput((ch, key) => {
    if (key.ctrl && ch === 'c') {
      exit()
      return
    }
    if (key.return) {
      const text = buffer.trim()
      clearBuffer()
      if (!text) return
      useMessagesStore.getState().appendUserMessage(text)
      const client = clientRef.current
      if (client) {
        client.send({type: 'input', text})
      } else {
        useMessagesStore.getState().appendSystemMessage(
          '(연결 안 됨 — HARNESS_URL / HARNESS_TOKEN 필요)'
        )
      }
      return
    }
    if (key.backspace || key.delete) {
      setBuffer(buffer.slice(0, -1))
      return
    }
    if (ch && !key.ctrl && !key.meta) {
      setBuffer(buffer + ch)
    }
  })

  // 스피너 프레임 회전 (단순 카운터 — Phase 2 에서 ink-spinner 로 교체)
  const spinFrame = busy ? SPIN[spinRef.current++ % SPIN.length] : ' '

  return (
    <Box flexDirection='column'>
      {/* 메시지 목록 — id 를 React key 로 사용 (FND-08, CLAUDE.md index key 금지) */}
      <Box flexDirection='column'>
        {messages.map((m) => (
          <Box key={m.id} marginBottom={0}>
            <Text
              color={
                m.role === 'user' ? 'cyan'
                  : m.role === 'assistant' ? 'yellow'
                  : m.role === 'tool' ? 'green'
                  : 'gray'
              }
              bold={m.role !== 'system'}
            >
              {m.role === 'user' ? '❯ '
                : m.role === 'assistant' ? '● '
                : m.role === 'tool' ? '└ '
                : '  '}
            </Text>
            <Text wrap='wrap'>{m.content}</Text>
          </Box>
        ))}
      </Box>

      {/* 구분선 */}
      <Text dimColor>{'─'.repeat(40)}</Text>

      {/* 입력 행 — ink-text-input 제거, 자체 buffer (FND-01 ink-text-input 제거) */}
      <Box>
        <Text color='cyan' bold>❯ </Text>
        <Text>{buffer}</Text>
        <Text color='cyan'>▌</Text>
      </Box>

      {/* 구분선 */}
      <Text dimColor>{'─'.repeat(40)}</Text>

      {/* 상태 표시줄 */}
      <Box>
        {busy && <Text color='cyan'>{spinFrame + ' '}</Text>}
        <Text color={connected ? 'green' : 'red'}>
          {connected ? '● connected' : '○ disconnected'}
        </Text>
      </Box>
    </Box>
  )
}
