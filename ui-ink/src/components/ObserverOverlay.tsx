// ObserverOverlay — 관전자 시 InputArea 치환 컴포넌트 (REM-04, DIFF-01)
// "A 입력 중..." — 입력 주체 아닌 관전자에게만 표시
// 03-UI-SPEC.md §"A 입력 중" 오버레이
import React from 'react'
import {Box, Text} from 'ink'
import {userColor} from '../utils/userColor.js'

interface ObserverOverlayProps {
  username: string | null  // activeInputFrom (null 안전)
}

export function ObserverOverlay({username}: ObserverOverlayProps): React.ReactElement {
  const displayName = username ?? '상대방'
  return (
    <Box>
      <Text color={userColor(username ?? '')} bold>{displayName}</Text>
      <Text dimColor italic>{' 입력 중...'}</Text>
    </Box>
  )
}
