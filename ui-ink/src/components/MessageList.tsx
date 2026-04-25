// MessageList — Claude Code 식 아키텍처
// 완료 메시지는 stdout 직접 출력 (터미널 자연 스크롤백 → resize 안전)
// Ink 는 in-flight(streaming) 메시지 + active(streaming assistant) 만 관리
import React, {useLayoutEffect, useRef, useState} from 'react'
import {Box} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {useRoomStore} from '../store/room.js'
import {Message} from './Message.js'
import {formatMessage} from '../utils/formatMessage.js'
import {inkWriteAbove, inkClearScreen} from '../inkBridge.js'

export const MessageList: React.FC = () => {
  const {completedMessages: completed, snapshotKey} = useMessagesStore(useShallow((s) => ({
    completedMessages: s.completedMessages,
    snapshotKey: s.snapshotKey,
  })))
  const active = useMessagesStore(useShallow((s) => s.activeMessage))
  const roomName = useRoomStore((s) => s.roomName)

  const [flushedCount, setFlushedCount] = useState(0)
  const lastSnapshotKeyRef = useRef(snapshotKey)

  useLayoutEffect(() => {
    // 스냅샷 reload (REM-03) — 화면 클리어 + flushedCount 리셋
    if (snapshotKey !== lastSnapshotKeyRef.current) {
      lastSnapshotKeyRef.current = snapshotKey
      inkClearScreen()
      setFlushedCount(0)
      return  // 다음 effect 사이클에서 새 스냅샷을 flush
    }

    // 순서대로 flush, 첫 streaming 메시지에서 멈춤
    let i = flushedCount
    const toFlush = []
    while (i < completed.length) {
      const m = completed[i]
      if (m.streaming) break  // tool 등 in-flight 면 대기
      toFlush.push(m)
      i++
    }
    if (toFlush.length === 0) return

    const text = toFlush.map((m) => formatMessage(m, {roomName})).join('')
    inkWriteAbove(text)
    setFlushedCount(i)
  }, [completed, snapshotKey, roomName, flushedCount])

  // Ink 에는 아직 flush 안 된 in-flight(streaming tool 등) + active(streaming assistant) 만 렌더
  const inFlight = completed.slice(flushedCount)

  return (
    <Box flexDirection='column'>
      {inFlight.map((m) => (
        <Message key={m.id} message={m}/>
      ))}
      {active ? <Message message={active}/> : null}
    </Box>
  )
}
