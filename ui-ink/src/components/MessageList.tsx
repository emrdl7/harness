// MessageList — alternate screen 모드에서 단순 Ink 렌더 (RND-01, RND-02)
// Banner 는 App.tsx 가 최상단에 배치, MessageList 는 메시지만 담당 (아래 정렬됨)
import React from 'react'
import {Static} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {Message} from './Message.js'

export const MessageList: React.FC = () => {
  const completed = useMessagesStore((s) => s.completedMessages)
  const active = useMessagesStore(useShallow((s) => s.activeMessage))
  // 진행 중 tool — Static 의 in-place 업데이트 한계 회피용 (assistant active 와 동일 패턴)
  const activeTool = useMessagesStore(useShallow((s) => s.activeToolMessage))

  return (
    <>
      {/* 완료된 메시지도 터미널 히스토리로 밀어냄 */}
      <Static items={completed}>
        {(m) => <Message key={m.id} message={m} isStatic/>}
      </Static>
      {/* 진행 중 tool 카드 (tool_end 시 completedMessages 로 이동) */}
      {activeTool ? <Message message={activeTool}/> : null}
      {/* 현재 입력 중이거나 생성 중인 메시지만 하단에 렌더링 */}
      {active ? <Message message={active}/> : null}
    </>
  )
}
