// PresenceSegment — StatusBar 서브컴포넌트 (REM-02, DIFF-04)
// CtxMeter 격리 패턴 동일 — roomName 없으면 null
// 03-UI-SPEC.md §Presence 세그먼트
import React from 'react'
import {Text} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useRoomStore} from '../store/room.js'
import {userColor} from '../utils/userColor.js'

export function PresenceSegment(): React.ReactElement | null {
  const {roomName, members} = useRoomStore(useShallow((s) => ({
    roomName: s.roomName,
    members: s.members,
  })))

  // solo 모드(roomName 없음): CtxMeter의 null 반환과 동일 패턴
  if (!roomName) return null

  const count = members.length

  return (
    <Text>
      {'🟢 '}
      <Text color='green'>{count}명</Text>
      {' ['}
      {members.map((m, i) => (
        <React.Fragment key={m}>
          {i > 0 && <Text color='gray'>{' · '}</Text>}
          <Text color={userColor(m)} bold>{m === process.env['HARNESS_TOKEN'] ? 'me' : m}</Text>
        </React.Fragment>
      ))}
      {']'}
    </Text>
  )
}
