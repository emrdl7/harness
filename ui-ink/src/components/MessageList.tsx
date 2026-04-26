// MessageList — alternate screen 모드에서 단순 Ink 렌더 (RND-01, RND-02)
// alt screen 안이라 resize/scroll 안전 → 모든 메시지를 정상 React 컴포넌트로 그림
// 비어있을 때 환영 배너 표시
import React from 'react'
import {Box} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {Message} from './Message.js'
import {Banner} from './Banner.js'

export const MessageList: React.FC = () => {
  const completed = useMessagesStore((s) => s.completedMessages)
  const active = useMessagesStore(useShallow((s) => s.activeMessage))

  const isEmpty = completed.length === 0 && !active

  return (
    <Box flexDirection='column'>
      {isEmpty ? <Banner/> : null}
      {completed.map((m) => (
        <Message key={m.id} message={m}/>
      ))}
      {active ? <Message message={active}/> : null}
    </Box>
  )
}
