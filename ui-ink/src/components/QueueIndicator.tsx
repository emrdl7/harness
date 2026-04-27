// AR-04: 큐잉된 입력 표시 인디케이터
// busy=true 동안 사용자가 추가 입력을 enqueue 하면 아래 형태로 표시:
//   ▸ 1 queued: "다음 메시지..."
//   ▸ 3 queued (다음: "첫번째...")
import React from 'react'
import {Box, Text} from 'ink'
import {useInputQueueStore} from '../store/inputQueue.js'

const PREVIEW_LEN = 40

export const QueueIndicator: React.FC = () => {
  const queue = useInputQueueStore((s) => s.queue)
  if (queue.length === 0) return null

  const next = queue[0]!
  const previewRaw = next.text.replace(/\n+/g, ' ').trim()
  const preview = previewRaw.length > PREVIEW_LEN
    ? `${previewRaw.slice(0, PREVIEW_LEN)}…`
    : previewRaw

  return (
    <Box paddingX={2}>
      <Text color='magenta'>▸ </Text>
      <Text color='magenta' bold>{queue.length} queued</Text>
      <Text dimColor>: </Text>
      <Text color='magenta' dimColor>"{preview}"</Text>
    </Box>
  )
}
