// AR-01: grep_search 결과 렌더 (V1 Feature T2)
//
// 백엔드 tools/fs.py grep_search 반환:
//   {ok, results: [{file, lines: ['>  12: matched', '   13: context', '---', ...]}], total_matches}
//   라인 prefix: '>' = 매치, ' ' = 컨텍스트, '---' = 매치 그룹 분리자
//   pattern 자체는 results 에 없음 — args.pattern 으로 가져옴
//
// 표시:
//   ⚙ grep_search  "useState"   3개 파일 · 7개 매치
//   ╭─ matches ─────
//   src/App.tsx
//   >  12: import { useState } from 'react'
//   src/hooks/use.ts
//   >   3: const [v, setV] = useState(0)
//   ╰───────────────
import React from 'react'
import {Box, Text} from 'ink'
import {DefaultToolBlock} from './DefaultToolBlock.js'
import type {ToolBlockProps} from './types.js'

interface GrepResult {
  file?: string
  lines?: string[]
}

interface GrepPayload {
  ok?: boolean
  error?: string
  results?: GrepResult[]
  total_matches?: number
}

// 출력 라인 캡 — Feature C 의 30줄 정책과 동일
const MAX_LINES = 30

function isGrepPayload(v: unknown): v is GrepPayload {
  return typeof v === 'object' && v !== null
}

type FlatItem = {kind: 'file'; text: string} | {kind: 'line'; text: string}

export const GrepResultBlock: React.FC<ToolBlockProps> = (props) => {
  const {name, args, payload, streaming, fallbackContent} = props

  if (streaming || !isGrepPayload(payload)) {
    return <DefaultToolBlock {...props} fallbackContent={fallbackContent} />
  }

  const pattern = typeof args?.['pattern'] === 'string' ? args['pattern'] : ''
  const error = typeof payload.error === 'string' ? payload.error : null

  if (error) {
    return (
      <Box flexDirection='column' marginY={0}>
        <Box>
          <Text color='red'>  ⚙ </Text>
          <Text bold>{name} </Text>
          {pattern && <Text color='cyan'>&quot;{pattern}&quot;</Text>}
          <Text color='red' dimColor>  실패</Text>
        </Box>
        <Box paddingLeft={4}>
          <Text color='red' wrap='wrap'>{error}</Text>
        </Box>
      </Box>
    )
  }

  const results = Array.isArray(payload.results) ? payload.results : []
  const totalMatches = typeof payload.total_matches === 'number' ? payload.total_matches : 0
  const fileCount = results.length

  if (totalMatches === 0) {
    return (
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        {pattern && <Text color='cyan'>&quot;{pattern}&quot;</Text>}
        <Text dimColor>  매치 없음</Text>
      </Box>
    )
  }

  // 파일 단위로 라인 적재 (파일 헤더 + 매치/컨텍스트/분리자). MAX_LINES 도달 시 중단.
  const flat: FlatItem[] = []
  let truncated = false
  let shownMatches = 0
  outer: for (const r of results) {
    if (typeof r.file !== 'string') continue
    flat.push({kind: 'file', text: r.file})
    if (flat.length >= MAX_LINES) { truncated = true; break }
    if (Array.isArray(r.lines)) {
      for (const line of r.lines) {
        if (typeof line !== 'string') continue
        flat.push({kind: 'line', text: line})
        if (line.startsWith('>')) shownMatches++
        if (flat.length >= MAX_LINES) { truncated = true; break outer }
      }
    }
  }
  const hiddenMatches = Math.max(0, totalMatches - shownMatches)

  return (
    <Box flexDirection='column' marginY={0}>
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        {pattern && <Text color='cyan'>&quot;{pattern}&quot;</Text>}
        <Text dimColor>   </Text>
        <Text>{fileCount}개 파일</Text>
        <Text dimColor> · </Text>
        <Text>{totalMatches}개 매치</Text>
      </Box>
      <Box flexDirection='column' paddingLeft={2}>
        <Text dimColor>╭─ matches ─────</Text>
        {flat.map((it, i) => {
          if (it.kind === 'file') {
            return <Text key={`f${i}`} color='cyan'>{it.text}</Text>
          }
          if (it.text === '---') {
            return <Text key={`s${i}`} dimColor>  ---</Text>
          }
          // 매치 라인('>' prefix) 은 일반, 컨텍스트(' ' prefix) 는 dim
          if (it.text.startsWith('>')) {
            return <Text key={`m${i}`}>{it.text}</Text>
          }
          return <Text key={`c${i}`} dimColor>{it.text}</Text>
        })}
        {truncated && hiddenMatches > 0 && (
          <Text dimColor>… +{hiddenMatches}개 매치 더</Text>
        )}
        <Text dimColor>╰───────────────</Text>
      </Box>
    </Box>
  )
}
