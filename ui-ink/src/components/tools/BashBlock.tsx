// AR-01: run_command / run_python 결과 렌더
// 백엔드 tools/shell.py 반환: {ok, stdout, stderr, returncode}
//
// 표시:
//   ╭─ $ npm install ──── ✓ 0 ─╮
//   │ stdout (white)              │
//   ├─────────────────────────────┤
//   │ ⚠ stderr (yellow)          │
//   ╰─────────────────────────────╯
import React from 'react'
import {Box, Text} from 'ink'
import {DefaultToolBlock} from './DefaultToolBlock.js'
import type {ToolBlockProps} from './types.js'

interface BashPayload {
  ok?: boolean
  stdout?: string
  stderr?: string
  returncode?: number
  error?: string
}

const MAX_LINES = 30

function clampLines(text: string): {lines: string[]; hidden: number} {
  const all = text.split('\n')
  if (all[all.length - 1] === '') all.pop()
  if (all.length <= MAX_LINES) return {lines: all, hidden: 0}
  return {lines: all.slice(all.length - MAX_LINES), hidden: all.length - MAX_LINES}
}

function isBashPayload(v: unknown): v is BashPayload {
  return typeof v === 'object' && v !== null
}

export const BashBlock: React.FC<ToolBlockProps> = (props) => {
  const {args, payload, streaming, fallbackContent} = props

  // 진행 중이거나 payload 가 dict 가 아니면 fallback 동작
  if (streaming || !isBashPayload(payload)) {
    return <DefaultToolBlock {...props} fallbackContent={fallbackContent} />
  }

  const cmd = typeof args?.['command'] === 'string'
    ? args['command']
    : typeof args?.['code'] === 'string'
      ? args['code']
      : ''
  const stdout = typeof payload.stdout === 'string' ? payload.stdout : ''
  const stderr = typeof payload.stderr === 'string' ? payload.stderr : ''
  const rc = typeof payload.returncode === 'number' ? payload.returncode : null
  const errorMsg = typeof payload.error === 'string' ? payload.error : null

  const ok = payload.ok !== false && (rc === null || rc === 0)
  const badgeColor = ok ? 'green' : 'red'
  const badge = ok ? `✓ ${rc ?? 0}` : `✗ ${rc ?? '?'}`
  const cmdShort = cmd.length > 60 ? `${cmd.slice(0, 60)}…` : cmd

  const stdoutClamp = stdout ? clampLines(stdout) : null
  const stderrClamp = stderr ? clampLines(stderr) : null

  return (
    <Box flexDirection='column' marginY={0}>
      <Box>
        <Text color='cyan'>  $ </Text>
        <Text bold>{cmdShort}</Text>
        <Text> </Text>
        <Text color={badgeColor}>{badge}</Text>
      </Box>

      {errorMsg && (
        <Box paddingLeft={4}>
          <Text color='red' wrap='wrap'>{errorMsg}</Text>
        </Box>
      )}

      {stdoutClamp && (
        <Box flexDirection='column' paddingLeft={4}>
          {stdoutClamp.hidden > 0 && (
            <Text dimColor>… +{stdoutClamp.hidden}줄 (앞부분)</Text>
          )}
          <Text wrap='wrap'>{stdoutClamp.lines.join('\n')}</Text>
        </Box>
      )}

      {stderrClamp && (
        <Box flexDirection='column' paddingLeft={4}>
          {stderrClamp.hidden > 0 && (
            <Text color='yellow' dimColor>… +{stderrClamp.hidden}줄 (앞부분)</Text>
          )}
          <Text color='yellow' wrap='wrap'>{stderrClamp.lines.join('\n')}</Text>
        </Box>
      )}
    </Box>
  )
}
