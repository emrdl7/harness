// App — D-01..D-04 레이아웃 + D-07..D-08 Ctrl+C/D (INPT-07)
import React, {useCallback, useEffect, useRef, useState} from 'react'
import {Box, useApp, useInput, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from './store/messages.js'
import {useStatusStore} from './store/status.js'
import {useInputStore} from './store/input.js'
import {useConfirmStore, bindConfirmClient} from './store/confirm.js'
import {useRoomStore} from './store/room.js'
import {HarnessClient} from './ws/client.js'
import {bindExit} from './ws/dispatch.js'
import {loadConfig, type HarnessConfig} from './config.js'
import {MessageList} from './components/MessageList.js'
import {StatusBar} from './components/StatusBar.js'
import {InputArea} from './components/InputArea.js'
import {ConfirmDialog} from './components/ConfirmDialog.js'
import {ReconnectOverlay} from './components/ReconnectOverlay.js'
import {ObserverOverlay} from './components/ObserverOverlay.js'
import {SetupWizard} from './components/SetupWizard.js'
import {NickPrompt} from './components/NickPrompt.js'

// env var 우선 → config 파일 fallback
function resolveConfig(): HarnessConfig | null {
  const url = process.env['HARNESS_URL']
  const token = process.env['HARNESS_TOKEN']
  const room = process.env['HARNESS_ROOM']
  const nick = process.env['HARNESS_NICK']
  if (url && token) return {url, token, room, nick}
  const fileCfg = loadConfig()
  if (!fileCfg) return null
  // argv --room / --nick 이 env var 로 들어오면 config 파일 값 덮어씀
  return {
    ...fileCfg,
    ...(room ? {room} : {}),
    ...(nick ? {nick} : {}),
  }
}

export const App: React.FC = () => {
  const {exit} = useApp()
  const {stdout} = useStdout()

  const [cfg, setCfg] = useState<HarnessConfig | null>(resolveConfig)

  const {buffer} = useInputStore(useShallow((s) => ({buffer: s.buffer})))
  const busy = useStatusStore(useShallow((s) => s.busy))
  const confirmMode = useConfirmStore(useShallow((s) => s.mode))
  // Phase 3: wsState/activeIsSelf/activeInputFrom 구독 (WSR-02, REM-04)
  const wsState = useRoomStore((s) => s.wsState)
  const reconnectAttempt = useRoomStore((s) => s.reconnectAttempt)
  const activeIsSelf = useRoomStore((s) => s.activeIsSelf)
  const activeInputFrom = useRoomStore((s) => s.activeInputFrom)

  const clientRef = useRef<HarnessClient | null>(null)
  const lastCtrlCRef = useRef<number>(0)

  // WS 연결 + confirm store 바인딩 — cfg 확정 후 실행
  useEffect(() => {
    if (!cfg) return
    const client = new HarnessClient({
      url: cfg.url,
      token: cfg.token,
      room: cfg.room ?? process.env['HARNESS_ROOM'],
      resumeSession: process.env['HARNESS_RESUME_SESSION'],  // SES-02: --resume 분기에서 설정
    })
    client.connect()
    clientRef.current = client
    bindConfirmClient(client)
    return () => {
      bindConfirmClient(null)
      client.close()
      clientRef.current = null
    }
  }, [cfg])

  // bindExit 등록 — /exit /quit slash_result 에서 호출됨
  useEffect(() => {
    bindExit(exit)
    return () => bindExit(null)
  }, [exit])

  // history hydration — 마운트 시 1회
  useEffect(() => {
    const {hydrate} = useInputStore.getState()
    if (hydrate) hydrate()
  }, [])

  // D-07/D-08: Ctrl+C (busy → cancel, idle × 2 → exit) / Ctrl+D (idle → exit)
  useInput((ch, key) => {
    if (key.ctrl && ch === 'c') {
      if (busy) {
        clientRef.current?.send({type: 'cancel'})  // WSR-04: cancel 메시지 교정 (stub 제거)
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
    // DIFF-02: room 모드에서만 meta.author 추가 (Message.tsx author prefix 표시용)
    const author = cfg?.room ? (cfg.nick || 'me') : undefined
    useMessagesStore.getState().appendUserMessage(text, {author})
    const client = clientRef.current
    if (client) {
      client.send({type: 'input', text})
    } else {
      useMessagesStore.getState().appendSystemMessage('(연결 안 됨 — HARNESS_URL / HARNESS_TOKEN 필요)')
    }
  }, [])

  const columns = stdout?.columns ?? 80

  // 입력 영역 치환 우선순위 (03-UI-SPEC.md §치환 우선순위)
  // reconnecting > failed > confirm > observer > input
  let inputArea: React.ReactNode
  if (wsState === 'reconnecting') {
    inputArea = <ReconnectOverlay attempt={reconnectAttempt} />
  } else if (wsState === 'failed') {
    inputArea = <ReconnectOverlay failed />
  } else if (confirmMode !== 'none') {
    // ConfirmDialog 내부에서 activeIsSelf 체크 후 ConfirmReadOnlyView 분기 (CNF-04)
    inputArea = <ConfirmDialog />
  } else if (!activeIsSelf) {
    // 관전 모드 — ObserverOverlay (REM-04, DIFF-01)
    inputArea = <ObserverOverlay username={activeInputFrom} />
  } else {
    inputArea = <InputArea onSubmit={handleSubmit} disabled={busy} />
  }

  // 최초 실행 — config 없으면 SetupWizard 표시
  if (!cfg) {
    return <SetupWizard onDone={setCfg} />
  }

  // 룸 모드 + 닉네임 미설정 — NickPrompt 표시
  if (cfg.room && !cfg.nick) {
    return <NickPrompt cfg={cfg} onDone={setCfg} />
  }

  // alt screen 모드: viewport 채우고, MessageList 가 flex-grow + justifyContent='flex-end'
  // → 새 메시지가 아래(InputArea 바로 위)에 쌓이고 오래된 건(Banner 포함) 위로 밀려 clip 됨
  const rows = stdout?.rows ?? 24
  return (
    <Box flexDirection='column' height={rows}>
      <Box flexDirection='column' flexGrow={1} overflow='hidden' justifyContent='flex-end'>
        <MessageList/>
      </Box>
      {inputArea}
      <StatusBar columns={columns}/>
    </Box>
  )
}
