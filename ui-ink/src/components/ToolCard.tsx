// ToolCard — RND-08 툴 호출 카드
// - 1줄 요약 기본 (TOOL_META 매핑)
// - Space/Enter 로 상세 펼침 (로컬 useState, store 불필요 — Claude 판단)
// - 상태 색상: pending(yellow), ok(green), err(red)
import React, {useState} from 'react'
import {Box, Text, useInput, useFocus} from 'ink'

export interface ToolInvocationView {
  id: string
  name: string
  args: Record<string, unknown>
  result?: string
  status: 'pending' | 'ok' | 'err'
}

type SummaryFn = (args: Record<string, unknown>, result: string) => string

// 주요 툴별 1줄 요약 규칙
const TOOL_META: Record<string, SummaryFn> = {
  read_file: (_args, result) => `read ${result.split('\n').length} lines`,
  write_file: (args) => `write ${String(args['path'] ?? '?')}`,
  run_command: (_args, result) => {
    const match = result.match(/exit (\d+)/)
    return match ? `exit ${match[1]}` : 'ran'
  },
  list_directory: (_args, result) => `ls ${result.split('\n').length} entries`,
  search_files: (_args, result) => `found ${result.split('\n').filter(Boolean).length} results`,
}

function summarize(inv: ToolInvocationView): string {
  if (inv.status === 'pending') return '...'
  const fn = TOOL_META[inv.name]
  const result = inv.result ?? ''
  if (fn) return fn(inv.args, result)
  // fallback: 앞 60자
  return result.length > 60 ? `${result.slice(0, 60)}...` : result
}

interface ToolCardProps {
  invocation: ToolInvocationView
}

export function ToolCard({invocation}: ToolCardProps): React.ReactElement {
  const [expanded, setExpanded] = useState(false)
  const {isFocused} = useFocus({autoFocus: false})

  // Ink useInput — space 는 ch === ' ', Enter 는 key.return 으로 전달된다
  // 포커스된 카드에만 토글 적용 (여러 카드 동시에 토글되지 않도록 isActive 로 제한)
  useInput(
    (ch, key) => {
      if (ch === ' ' || key.return) {
        setExpanded((v) => !v)
      }
    },
    {isActive: isFocused}
  )

  const statusColor =
    invocation.status === 'pending' ? 'yellow' :
    invocation.status === 'ok'      ? 'green'  :
                                       'red'
  const marker =
    invocation.status === 'pending' ? '·' :
    invocation.status === 'ok'      ? '✓' :
                                       '✗'

  return (
    <Box flexDirection='column' borderStyle={isFocused ? 'round' : 'single'} borderColor={statusColor} paddingX={1}>
      <Box>
        <Text color={statusColor}>{marker} </Text>
        <Text bold>{invocation.name}</Text>
        <Text> — </Text>
        <Text dimColor>{summarize(invocation)}</Text>
      </Box>
      {expanded && invocation.result !== undefined && (
        <Box flexDirection='column' marginTop={1}>
          <Text dimColor>────────</Text>
          <Text>{invocation.result}</Text>
        </Box>
      )}
      {isFocused && (
        <Text dimColor>
          <Text color='cyan'>Space/Enter</Text> {expanded ? '접기' : '펼치기'}
        </Text>
      )}
    </Box>
  )
}
