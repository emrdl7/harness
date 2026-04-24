// DiffPreview — PEXT-02 활성화: old_content 있으면 structuredPatch, 없으면 신규 파일 표시
// Phase 2 placeholder → Phase 3 실제 diff (W1)
import React from 'react'
import {Box, Text} from 'ink'
import {structuredPatch} from 'diff'

interface DiffPreviewProps {
  path: string
  newContent?: string
  oldContent?: string  // W1: optional — 기존 파일이면 서버가 전송, 신규 파일이면 undefined
}

export function DiffPreview({path, newContent, oldContent}: DiffPreviewProps): React.ReactElement {
  // 신규 파일 — old_content 없음
  if (!oldContent) {
    return (
      <Box flexDirection='column' marginTop={1} marginBottom={1} borderStyle='single' borderColor='green' paddingX={1}>
        <Text color='green'>+ (신규 파일) {path}</Text>
        {newContent === undefined ? (
          <Text dimColor>(내용 미수신)</Text>
        ) : (
          <Text color='green' wrap='wrap'>{newContent.slice(0, 500)}</Text>
        )}
      </Box>
    )
  }

  // 기존 파일 — structuredPatch 로 실제 diff 표시
  const patch = structuredPatch(path, path, oldContent, newContent ?? '')
  const lines: Array<{text: string; color: string | undefined}> = []

  for (const hunk of patch.hunks) {
    lines.push({
      text: `@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@`,
      color: 'cyan',
    })
    for (const line of hunk.lines) {
      const color = line.startsWith('+') ? 'green' : line.startsWith('-') ? 'red' : undefined
      lines.push({text: line, color})
    }
  }

  if (lines.length === 0) {
    return (
      <Box flexDirection='column' marginTop={1} marginBottom={1} borderStyle='single' borderColor='gray' paddingX={1}>
        <Text color='gray'>미리보기 — {path}</Text>
        <Text dimColor>(변경 없음)</Text>
      </Box>
    )
  }

  return (
    <Box flexDirection='column' marginTop={1} marginBottom={1} borderStyle='single' borderColor='gray' paddingX={1}>
      <Text color='gray'>미리보기 — {path}</Text>
      {lines.map((l, i) => (
        // diff 렌더링은 단방향 정적 리스트 — index 기반 key 예외 허용
        <Text key={`diff-${String(i)}`} color={l.color}>{l.text}</Text>
      ))}
    </Box>
  )
}
