// ReconnectOverlay — WS 재연결 중 InputArea 치환 컴포넌트 (WSR-02)
// ConfirmReadOnlyView와 동일한 InputArea 치환 패턴
// 03-UI-SPEC.md §재연결 오버레이
import React from 'react'
import {Box, Text} from 'ink'

interface ReconnectOverlayProps {
  attempt?: number   // 재연결 시도 횟수 (1 기준)
  failed?: boolean   // 10회 실패 후
}

export function ReconnectOverlay({attempt, failed}: ReconnectOverlayProps): React.ReactElement {
  if (failed) {
    return (
      <Box>
        <Text color='red'>disconnected — reconnect failed. Ctrl+C to exit.</Text>
      </Box>
    )
  }

  return (
    <Box>
      <Text color='yellow'>
        {`disconnected — reconnecting... (attempt ${attempt ?? 1}/10)`}
      </Text>
    </Box>
  )
}
