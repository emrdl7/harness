// AR-01: git_log 결과 렌더 (V1 Feature T5)
//
// 백엔드 tools/git.py git_log 반환:
//   {ok, commits: [{hash, short, author, date, subject}], stdout, stderr}
//   - hash: 풀 SHA · short: 7자 SHA · date: 'N minutes/hours/days ago'
//
// 표시:
//   ⚙ git_log   N개 커밋
//   ╭─ commits ─────
//   ● abc1234  feat: 새 기능 추가
//     johyeon  2 hours ago
//   ● def5678  fix: 버그 수정
//     johyeon  1 day ago
//   ╰────────────────
import React from 'react'
import {Box, Text} from 'ink'
import {DefaultToolBlock} from './DefaultToolBlock.js'
import type {ToolBlockProps} from './types.js'

interface Commit {
  hash?: string
  short?: string
  author?: string
  date?: string
  subject?: string
}

interface GitLogPayload {
  ok?: boolean
  commits?: Commit[]
  stdout?: string
  stderr?: string
}

const MAX_COMMITS = 30

function isGitLogPayload(v: unknown): v is GitLogPayload {
  return typeof v === 'object' && v !== null
}

export const GitLogBlock: React.FC<ToolBlockProps> = (props) => {
  const {name, payload, streaming, fallbackContent} = props

  if (streaming || !isGitLogPayload(payload)) {
    return <DefaultToolBlock {...props} fallbackContent={fallbackContent} />
  }

  const stderr = typeof payload.stderr === 'string' ? payload.stderr : ''
  // _git 실패 시 ok=false → stderr 표시
  if (payload.ok === false || (stderr && (!Array.isArray(payload.commits) || payload.commits.length === 0))) {
    return (
      <Box flexDirection='column' marginY={0}>
        <Box>
          <Text color='red'>  ⚙ </Text>
          <Text bold>{name} </Text>
          <Text color='red' dimColor>실패</Text>
        </Box>
        {stderr && (
          <Box paddingLeft={4}>
            <Text color='red' wrap='wrap'>{stderr}</Text>
          </Box>
        )}
      </Box>
    )
  }

  const commits = Array.isArray(payload.commits) ? payload.commits : []
  if (commits.length === 0) {
    return (
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        <Text dimColor>  커밋 없음</Text>
      </Box>
    )
  }

  const shown = commits.slice(0, MAX_COMMITS)
  const hidden = commits.length - shown.length

  return (
    <Box flexDirection='column' marginY={0}>
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        <Text dimColor>   </Text>
        <Text>{commits.length}개 커밋</Text>
      </Box>
      <Box flexDirection='column' paddingLeft={2}>
        <Text dimColor>╭─ commits ─────</Text>
        {shown.map((c, i) => (
          <Box key={`c${i}`} flexDirection='column'>
            <Box>
              <Text color='yellow'>● </Text>
              <Text color='cyan'>{c.short ?? '???????'}</Text>
              <Text>  </Text>
              <Text wrap='truncate-end'>{c.subject ?? ''}</Text>
            </Box>
            {(c.author || c.date) && (
              <Box paddingLeft={2}>
                {c.author && <Text dimColor>{c.author}</Text>}
                {c.author && c.date && <Text dimColor>  </Text>}
                {c.date && <Text dimColor>{c.date}</Text>}
              </Box>
            )}
          </Box>
        ))}
        {hidden > 0 && <Text dimColor>… +{hidden}개 더</Text>}
        <Text dimColor>╰────────────────</Text>
      </Box>
    </Box>
  )
}
