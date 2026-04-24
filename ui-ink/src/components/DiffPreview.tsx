// DiffPreview — RND-07 Phase 2 placeholder
// Phase 2: 경로 헤더 + 새 내용 처음 10줄만 표시 (old_content 미수신)
// Phase 3 (PEXT-02): old_content 필드 추가 후 diff@9 structuredPatch 연동 예정
import React from 'react'
import {Box, Text} from 'ink'

interface DiffPreviewProps {
  path: string
  newContent?: string
}

const PREVIEW_LINE_LIMIT = 10

export function DiffPreview({path, newContent}: DiffPreviewProps): React.ReactElement {
  const lines = (newContent ?? '').split('\n').slice(0, PREVIEW_LINE_LIMIT)
  const total = (newContent ?? '').split('\n').length
  const truncated = total > PREVIEW_LINE_LIMIT

  return (
    <Box flexDirection='column' marginTop={1} marginBottom={1} borderStyle='single' borderColor='gray' paddingX={1}>
      <Text color='gray'>미리보기 — {path}</Text>
      {newContent === undefined ? (
        <Text dimColor>(새 내용 미수신 — Phase 3 에서 diff 표시 예정)</Text>
      ) : (
        <Box flexDirection='column'>
          {lines.map((ln, i) => (
            <Text key={`preview-${path}-${i}-${ln.slice(0, 16)}`} color='green'>+ {ln}</Text>
          ))}
          {truncated && <Text dimColor>... ({total - PREVIEW_LINE_LIMIT}줄 더)</Text>}
        </Box>
      )}
    </Box>
  )
}
