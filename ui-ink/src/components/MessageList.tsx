// MessageList — completedMessages 는 <Static>, activeMessage 는 일반 Box (RND-01, RND-02)
// <Static>: append-only 로 이미 렌더된 프레임을 재렌더하지 않음 → scrollback 안정
// active: in-place 업데이트로 매 토큰마다 리렌더 가능
import React from 'react'
import {Box, Static} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {Message} from './Message.js'

export const MessageList: React.FC = () => {
  const {completedMessages: completed, snapshotKey} = useMessagesStore(useShallow((s) => ({
    completedMessages: s.completedMessages,
    snapshotKey: s.snapshotKey,
  })))
  const active = useMessagesStore(useShallow((s) => s.activeMessage))

  return (
    <Box flexDirection='column'>
      {/* REM-03: snapshotKey를 Static key로 사용 — snapshot 로드 시 Static 강제 remount */}
      <Static key={snapshotKey} items={completed}>
        {(m) => <Message key={m.id} message={m}/>}
      </Static>
      {active ? (
        <Box flexDirection='column'>
          <Message message={active}/>
        </Box>
      ) : null}
    </Box>
  )
}
