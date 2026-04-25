// MessageList — Claude Code 식 아키텍처
// 모든 메시지(완료 + 스트리밍 토큰)는 Ink 밖 stdout 으로 직접 출력 → 터미널 자연 스크롤백
// Ink 는 in-flight tool 같은 짧은 임시 항목만 (대부분 빈 박스)
// 활성 어시스턴트 토큰: appendToken 호출마다 delta 만 stdout 에 흘림 (Ink 미렌더)
import React, {useLayoutEffect, useRef, useState} from 'react'
import {Box} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore, type Message as MessageType} from '../store/messages.js'
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
  // 토큰 스트리밍 추적: 같은 active.id 내에서 이미 stdout 에 쓴 길이
  const streamedRef = useRef<{id: string, length: number} | null>(null)
  // agentEnd 후 completed 로 옮겨질 때 중복 flush 방지
  const streamedIdsRef = useRef(new Set<string>())

  useLayoutEffect(() => {
    // 스냅샷 reload (REM-03)
    if (snapshotKey !== lastSnapshotKeyRef.current) {
      lastSnapshotKeyRef.current = snapshotKey
      streamedRef.current = null
      streamedIdsRef.current.clear()
      inkClearScreen()
      setFlushedCount(0)
      return
    }

    // 1) 활성 어시스턴트 토큰 delta → stdout 직접 stream
    if (active && active.role === 'assistant') {
      let cur = streamedRef.current
      if (!cur || cur.id !== active.id) {
        cur = {id: active.id, length: 0}
        streamedRef.current = cur
        streamedIdsRef.current.add(active.id)
        inkWriteAbove('\n')
      }
      const delta = active.content.slice(cur.length)
      if (delta.length > 0) {
        inkWriteAbove(delta)
        cur.length = active.content.length
      }
    } else if (streamedRef.current !== null) {
      // active 가 사라짐 (agentEnd / cancel) — 끝 줄바꿈
      inkWriteAbove('\n')
      streamedRef.current = null
    }

    // 2) 완료 메시지 flush (이미 stream 으로 쓴 assistant 는 skip)
    let i = flushedCount
    const toFlush: MessageType[] = []
    while (i < completed.length) {
      const m = completed[i]
      if (m.streaming) break  // tool in-flight 면 대기
      if (m.role === 'assistant' && streamedIdsRef.current.has(m.id)) {
        // 이미 토큰 스트림으로 출력됨 — index 만 진행
        streamedIdsRef.current.delete(m.id)
      } else {
        toFlush.push(m)
      }
      i++
    }
    if (toFlush.length > 0) {
      const text = toFlush.map((m) => formatMessage(m, {roomName})).join('')
      inkWriteAbove(text)
    }
    if (i !== flushedCount) {
      setFlushedCount(i)
    }
  }, [active, completed, snapshotKey, roomName, flushedCount])

  // Ink 에는 streaming tool 만 (대부분 비어있음). active assistant 는 stdout 에 흘림.
  const inFlight = completed.slice(flushedCount).filter((m) => m.streaming)

  return (
    <Box flexDirection='column'>
      {inFlight.map((m) => (
        <Message key={m.id} message={m}/>
      ))}
    </Box>
  )
}
