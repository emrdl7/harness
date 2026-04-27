// ToolIndicator — 도구 실행 중 인풋 영역 바로 위에 표시되는 라이브 인디케이터
import React from 'react'
import {Box, Text} from 'ink'
import Spinner from 'ink-spinner'

// 도구 인자에서 사람이 읽기 좋은 한 줄 힌트 추출
function argsPreview(args: Record<string, unknown>): string {
  const priority = ['path', 'file_path', 'command', 'query', 'pattern', 'message', 'branch']
  const key = priority.find((k) => k in args && typeof args[k] === 'string')
  if (!key) return ''
  const val = String(args[key])
  return val.length > 50 ? val.slice(0, 47) + '…' : val
}

interface ToolIndicatorProps {
  tool: string | null
  args: Record<string, unknown> | null
}

export function ToolIndicator({tool, args}: ToolIndicatorProps): React.ReactElement {
  const label = tool ?? '생성 중…'
  const preview = tool && args ? argsPreview(args) : ''
  return (
    <Box paddingLeft={2} marginTop={1}>
      <Text color='yellow'><Spinner type='dots'/>{' '}</Text>
      <Text color='yellow'>{label}</Text>
      {preview ? <Text dimColor>{'  '}{preview}</Text> : null}
    </Box>
  )
}
