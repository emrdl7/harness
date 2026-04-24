// App — D-01..D-04 레이아웃 + D-07..D-08 Ctrl+C/D (INPT-07)
// MultilineInput / SlashPopup / ConfirmDialog 는 Wave 2 에서 교체됨 — 이 파일의 입력 영역은 placeholder.
import React, {useEffect, useRef, useState} from 'react'
import {Box, Text, useApp, useInput, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from './store/messages.js'
import {useStatusStore} from './store/status.js'
import {useInputStore} from './store/input.js'
import {useConfirmStore, bindConfirmClient} from './store/confirm.js'
import {HarnessClient} from './ws/client.js'
import {MessageList} from './components/MessageList.js'
import {StatusBar} from './components/StatusBar.js'
import {Divider} from './components/Divider.js'
import {theme} from './theme.js'

export const App: React.FC = () => {
  const {exit} = useApp()
  const {stdout} = useStdout()

  const {buffer, setBuffer, clearBuffer, pushHistory, historyUp, historyDown} = useInputStore(
    useShallow((s) => ({
      buffer: s.buffer,
      setBuffer: s.setBuffer,
      clearBuffer: s.clearBuffer,
      pushHistory: s.pushHistory,
      historyUp: s.historyUp,
      historyDown: s.historyDown,
    })),
  )

  const busy = useStatusStore(useShallow((s) => s.busy))
  const confirmMode = useConfirmStore(useShallow((s) => s.mode))

  const clientRef = useRef<HarnessClient | null>(null)
  const lastCtrlCRef = useRef<number>(0)

  // WS 연결 + confirm store 바인딩
  useEffect(() => {
    const url = process.env['HARNESS_URL']
    const token = process.env['HARNESS_TOKEN']
    if (!url || !token) return
    const client = new HarnessClient({
      url,
      token,
      room: process.env['HARNESS_ROOM'],
    })
    client.connect()
    clientRef.current = client
    bindConfirmClient(client)
    return () => {
      bindConfirmClient(null)
      client.close()
      clientRef.current = null
    }
  }, [])

  // history 파일 hydration — 마운트 시 1회
  useEffect(() => {
    const {hydrate} = useInputStore.getState()
    if (hydrate) hydrate()
  }, [])

  // RND-04: resize 강제 clear — ED2+ED3+Home escape (Python 경험: ED3 필수)
  // SIGWINCH 시 Ink 가 재렌더하지만, ED3(scrollback clear)까지 발행해야 stale line 잔재가 사라짐
  const [_resizeCount, setResizeCount] = useState(0)
  useEffect(() => {
    const handleResize = () => {
      // ED2(\x1b[2J 화면 클리어) + ED3(\x1b[3J scrollback 클리어) + Home(\x1b[H 커서 원점)
      stdout.write('\x1b[2J\x1b[3J\x1b[H')
      setResizeCount((c) => c + 1)  // Ink 재렌더 trigger 용 더미 state
    }
    stdout.on('resize', handleResize)
    return () => {
      stdout.off('resize', handleResize)
    }
  }, [stdout])

  // 입력 처리 — confirm 모드일 때는 본 useInput 이 처리하지 않음 (ConfirmDialog 가 처리; Wave 2)
  // 현재는 confirm 모드에서도 placeholder 로 ConfirmDialog 미구현 상태 → 이 useInput 이 y/n 만 최소 처리
  useInput((ch, key) => {
    // D-07, D-08: Ctrl+C
    if (key.ctrl && ch === 'c') {
      if (busy) {
        // busy 시 — cancel 전송 + 안내
        const client = clientRef.current
        if (client) {
          client.send({type: 'input', text: '/cancel'})
        }
        useMessagesStore.getState().appendSystemMessage('취소 요청 중…')
        lastCtrlCRef.current = Date.now()
        return
      }
      // idle 시 — 2초 내 2회 반복 → exit
      const now = Date.now()
      if (now - lastCtrlCRef.current < 2000) {
        exit()
        return
      }
      lastCtrlCRef.current = now
      useMessagesStore.getState().appendSystemMessage('다시 Ctrl+C 를 누르면 종료됩니다')
      return
    }

    // Ctrl+D — idle 일 때 즉시 exit (관용)
    if (key.ctrl && ch === 'd') {
      if (!buffer && !busy) {
        exit()
        return
      }
    }

    // confirm 모드에서는 최소한의 y/n 처리만 (Wave 2 의 ConfirmDialog 에서 본격 처리)
    if (confirmMode !== 'none') {
      if (ch === 'y' || ch === 'Y') {
        useConfirmStore.getState().resolve(true)
        return
      }
      if (ch === 'n' || ch === 'N' || key.escape) {
        useConfirmStore.getState().resolve(false)
        return
      }
      return
    }

    // history 순회
    if (key.upArrow) {
      historyUp()
      return
    }
    if (key.downArrow) {
      historyDown()
      return
    }

    if (key.return) {
      const text = buffer.trim()
      clearBuffer()
      if (!text) return
      pushHistory(text)
      useMessagesStore.getState().appendUserMessage(text)
      const client = clientRef.current
      if (client) {
        client.send({type: 'input', text})
      } else {
        useMessagesStore.getState().appendSystemMessage(
          '(연결 안 됨 — HARNESS_URL / HARNESS_TOKEN 필요)',
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

  const columns = stdout?.columns ?? 80

  // D-01 레이아웃: [MessageList(Static + active)] → [Divider] → [InputArea | ConfirmDialog] → [Divider] → [StatusBar]
  return (
    <Box flexDirection='column'>
      <MessageList/>

      <Divider columns={columns}/>

      {confirmMode !== 'none' ? (
        // ConfirmDialog placeholder (Wave 2 에서 교체) — D-03 동일 위치 규칙만 지킴
        <Box>
          <Text color={theme.status.busy} bold>[confirm {confirmMode}] y/n · esc</Text>
        </Box>
      ) : (
        // InputArea placeholder (Wave 2 의 MultilineInput 로 교체)
        <Box>
          <Text color={theme.role.user} bold>❯ </Text>
          <Text>{buffer}</Text>
          <Text color={theme.role.user}>▌</Text>
        </Box>
      )}

      <Divider columns={columns}/>

      <StatusBar columns={columns}/>
    </Box>
  )
}
