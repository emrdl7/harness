// MessageList — alternate screen 모드에서 단순 Ink 렌더 (RND-01, RND-02)
// Banner 는 App.tsx 가 최상단에 배치, MessageList 는 메시지만 담당 (아래 정렬됨)
import React from 'react'
import {Box} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {Message} from './Message.js'

export const MessageList: React.FC = () => {
  const completed = useMessagesStore((s) => s.completedMessages)
  const active = useMessagesStore(useShallow((s) => s.activeMessage))

  return (
    <Box flexDirection='column'>
      {completed.map((m) => (
        <Message key={m.id} message={m}/>
      ))}
      {active ? <Message message={active}/> : null}
    </Box>
  )
}
