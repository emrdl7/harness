// App — D-01..D-04 레이아웃 + D-07..D-08 Ctrl+C/D (INPT-07)
import React, {useCallback, useEffect, useRef, useState} from 'react'
import {Box, useApp, useInput, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from './store/messages.js'
import {useStatusStore} from './store/status.js'
import {useInputStore} from './store/input.js'
import {useConfirmStore, bindConfirmClient} from './store/confirm.js'
import {HarnessClient} from './ws/client.js'
import {MessageList} from './components/MessageList.js'
import {StatusBar} from './components/StatusBar.js'
import {Divider} from './components/Divider.js'
import {InputArea} from './components/InputArea.js'
import {ConfirmDialog} from './components/ConfirmDialog.js'

export const App: React.FC = () => {
  const {exit} = useApp()
  const {stdout} = useStdout()

  const {buffer} = useInputStore(useShallow((s) => ({buffer: s.buffer})))
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

  // D-07/D-08: Ctrl+C (busy → cancel, idle × 2 → exit) / Ctrl+D (idle → exit)
  useInput((ch, key) => {
    if (key.ctrl && ch === 'c') {
      if (busy) {
        clientRef.current?.send({type: 'input', text: '/cancel'})
        useMessagesStore.getState().appendSystemMessage('취소 요청 중…')
        lastCtrlCRef.current = Date.now()
        return
      }
      const now = Date.now()
      if (now - lastCtrlCRef.current < 2000) { exit(); return }
      lastCtrlCRef.current = now
      useMessagesStore.getState().appendSystemMessage('다시 Ctrl+C 를 누르면 종료됩니다')
      return
    }
    if (key.ctrl && ch === 'd' && !buffer && !busy) {
      exit()
    }
  })

  // InputArea 의 onSubmit — WS 전송 + 메시지 표시
  const handleSubmit = useCallback((text: string) => {
    useMessagesStore.getState().appendUserMessage(text)
    const client = clientRef.current
    if (client) {
      client.send({type: 'input', text})
    } else {
      useMessagesStore.getState().appendSystemMessage('(연결 안 됨 — HARNESS_URL / HARNESS_TOKEN 필요)')
    }
  }, [])

  const columns = stdout?.columns ?? 80

  // D-01 레이아웃: [MessageList(Static + active)] → [Divider] → [InputArea | ConfirmDialog] → [Divider] → [StatusBar]
  return (
    <Box flexDirection='column'>
      <MessageList/>

      <Divider columns={columns}/>

      {confirmMode !== 'none' ? (
        <ConfirmDialog />
      ) : (
        <InputArea onSubmit={handleSubmit} disabled={busy} />
      )}

      <Divider columns={columns}/>

      <StatusBar columns={columns}/>
    </Box>
  )
}
