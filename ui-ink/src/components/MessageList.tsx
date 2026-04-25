// MessageList — completedMessages 는 <Static>, activeMessage 는 일반 Box (RND-01, RND-02)
// <Static>: append-only 로 이미 렌더된 프레임을 재렌더하지 않음 → scrollback 안정
// active: in-place 업데이트로 매 토큰마다 리렌더 가능
// Static position:'absolute' 기본값 → content 폭으로 크기 결정 → 터미널 폭 초과 시 커서 추적 오차
// style.width 를 명시적으로 지정해 Static box 가 터미널 전체 폭을 차지하도록 강제
import React from 'react'
import {Box, Static, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {Message} from './Message.js'

export const MessageList: React.FC = () => {
  const {completedMessages: completed, snapshotKey} = useMessagesStore(useShallow((s) => ({
    completedMessages: s.completedMessages,
    snapshotKey: s.snapshotKey,
  })))
  const active = useMessagesStore(useShallow((s) => s.activeMessage))
  const {stdout} = useStdout()
  const columns = stdout?.columns ?? 80

  return (
    <Box flexDirection='column' width={columns}>
      {/* REM-03: snapshotKey를 Static key로 사용 — snapshot 로드 시 Static 강제 remount */}
      {/* style.width=columns: Static box 가 터미널 전체 폭을 차지해야 텍스트가 올바른 폭에서 wrapping */}
      <Static key={snapshotKey} items={completed} style={{width: columns}}>
        {(m) => <Message key={m.id} message={m} columns={columns}/>}
      </Static>
      {active ? (
        <Box flexDirection='column' width={columns}>
          <Message message={active} columns={columns}/>
        </Box>
      ) : null}
    </Box>
  )
}
