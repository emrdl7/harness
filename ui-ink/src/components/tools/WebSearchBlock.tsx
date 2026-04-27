// AR-01: search_web 결과 렌더 (V1 Feature T6)
//
// 백엔드 tools/web.py search_web 반환:
//   {ok, results: [{title, url, snippet}], summary, error?}
//   query 는 args.query 로 가져옴
//
// 표시:
//   ⚙ search_web "Qwen3.6 27B 성능"   3개 결과
//   ╭─ results ─────
//   1. Qwen3 시리즈 발표
//      https://example.com/qwen3
//      Qwen3.6 27B 는 ...
//   2. 벤치마크 비교
//      ...
//   ╰────────────────
import React from 'react'
import {Box, Text} from 'ink'
import {DefaultToolBlock} from './DefaultToolBlock.js'
import type {ToolBlockProps} from './types.js'

interface WebResult {
  title?: string
  url?: string
  snippet?: string
}

interface WebSearchPayload {
  ok?: boolean
  error?: string
  results?: WebResult[]
  summary?: string
}

const MAX_RESULTS = 8
const SNIPPET_LEN = 160

function isWebSearchPayload(v: unknown): v is WebSearchPayload {
  return typeof v === 'object' && v !== null
}

export const WebSearchBlock: React.FC<ToolBlockProps> = (props) => {
  const {name, args, payload, streaming, fallbackContent} = props

  if (streaming || !isWebSearchPayload(payload)) {
    return <DefaultToolBlock {...props} fallbackContent={fallbackContent} />
  }

  const query = typeof args?.['query'] === 'string' ? args['query'] : ''
  const error = typeof payload.error === 'string' ? payload.error : null

  if (error) {
    return (
      <Box flexDirection='column' marginY={0}>
        <Box>
          <Text color='red'>  ⚙ </Text>
          <Text bold>{name} </Text>
          {query && <Text color='cyan'>&quot;{query}&quot;</Text>}
          <Text color='red' dimColor>  실패</Text>
        </Box>
        <Box paddingLeft={4}>
          <Text color='red' wrap='wrap'>{error}</Text>
        </Box>
      </Box>
    )
  }

  const results = Array.isArray(payload.results) ? payload.results : []
  if (results.length === 0) {
    return (
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        {query && <Text color='cyan'>&quot;{query}&quot;</Text>}
        <Text dimColor>  결과 없음</Text>
      </Box>
    )
  }

  const shown = results.slice(0, MAX_RESULTS)
  const hidden = results.length - shown.length

  return (
    <Box flexDirection='column' marginY={0}>
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        {query && <Text color='cyan'>&quot;{query}&quot;</Text>}
        <Text dimColor>   </Text>
        <Text>{results.length}개 결과</Text>
      </Box>
      <Box flexDirection='column' paddingLeft={2}>
        <Text dimColor>╭─ results ─────</Text>
        {shown.map((r, i) => {
          const title = typeof r.title === 'string' ? r.title : ''
          const url = typeof r.url === 'string' ? r.url : ''
          const snippetRaw = typeof r.snippet === 'string' ? r.snippet : ''
          const snippet = snippetRaw.length > SNIPPET_LEN
            ? snippetRaw.slice(0, SNIPPET_LEN) + '…'
            : snippetRaw
          return (
            <Box key={`r${i}`} flexDirection='column' marginBottom={i < shown.length - 1 ? 0 : 0}>
              <Box>
                <Text color='yellow'>{i + 1}. </Text>
                <Text bold wrap='truncate-end'>{title || '(제목 없음)'}</Text>
              </Box>
              {url && (
                <Box paddingLeft={3}>
                  <Text color='cyan' dimColor wrap='truncate-end'>{url}</Text>
                </Box>
              )}
              {snippet && (
                <Box paddingLeft={3}>
                  <Text dimColor wrap='wrap'>{snippet}</Text>
                </Box>
              )}
            </Box>
          )
        })}
        {hidden > 0 && <Text dimColor>… +{hidden}개 결과 더</Text>}
        <Text dimColor>╰────────────────</Text>
      </Box>
    </Box>
  )
}
