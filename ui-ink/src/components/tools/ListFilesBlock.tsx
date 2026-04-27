// AR-01: list_files 결과 렌더 (V1 Feature T3 - 단순 list 버전)
//
// 백엔드 tools/fs.py list_files 반환:
//   {ok, files: ['/abs/path/a.ts', '/abs/path/b.ts', ...], error?}
//   pattern 은 args.pattern 으로 가져옴 (results 에 없음)
//
// 표시:
//   ⚙ list_files  "**/index.html"   N개 파일
//   (공통 prefix 가 있으면) base: /Users/johyeonchang/harness/
//   ╭─ files ─────
//   src/components/App.tsx
//   src/store/messages.ts
//   ...
//   ╰─────────────
import React from 'react'
import {Box, Text} from 'ink'
import {DefaultToolBlock} from './DefaultToolBlock.js'
import type {ToolBlockProps} from './types.js'

interface ListFilesPayload {
  ok?: boolean
  files?: string[]
  error?: string
}

const MAX_FILES = 30

function isListFilesPayload(v: unknown): v is ListFilesPayload {
  return typeof v === 'object' && v !== null
}

// 공통 디렉토리 prefix 추출 — 모든 path 에 공통되는 가장 긴 디렉토리.
// 결과 prefix 는 `/` 로 끝남(또는 빈 문자열).
function commonDirPrefix(paths: string[]): string {
  if (paths.length === 0) return ''
  if (paths.length === 1) {
    const idx = paths[0]!.lastIndexOf('/')
    return idx >= 0 ? paths[0]!.slice(0, idx + 1) : ''
  }
  let prefix = paths[0]!
  for (const p of paths.slice(1)) {
    let i = 0
    while (i < prefix.length && i < p.length && prefix[i] === p[i]) i++
    prefix = prefix.slice(0, i)
    if (!prefix) return ''
  }
  // 마지막 `/` 이후는 파일명 일부일 수 있어 잘라냄 — 디렉토리 단위까지만 prefix
  const idx = prefix.lastIndexOf('/')
  return idx >= 0 ? prefix.slice(0, idx + 1) : ''
}

export const ListFilesBlock: React.FC<ToolBlockProps> = (props) => {
  const {name, args, payload, streaming, fallbackContent} = props

  if (streaming || !isListFilesPayload(payload)) {
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

  const files = Array.isArray(payload.files) ? payload.files.filter((f): f is string => typeof f === 'string') : []
  const total = files.length

  if (total === 0) {
    return (
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        {pattern && <Text color='cyan'>&quot;{pattern}&quot;</Text>}
        <Text dimColor>  매치 없음</Text>
      </Box>
    )
  }

  // 정렬은 백엔드(fs.py) 가 이미 sorted 로 반환하지만 방어적으로 한 번 더
  const sorted = [...files].sort()
  // 공통 디렉토리 prefix 추출 — 동일 프로젝트 내 검색 결과 가독성↑
  const prefix = commonDirPrefix(sorted)
  const shown = sorted.slice(0, MAX_FILES)
  const hidden = total - shown.length

  return (
    <Box flexDirection='column' marginY={0}>
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        {pattern && <Text color='cyan'>&quot;{pattern}&quot;</Text>}
        <Text dimColor>   </Text>
        <Text>{total}개 파일</Text>
      </Box>
      {prefix && (
        <Box paddingLeft={2}>
          <Text dimColor>base: </Text>
          <Text color='cyan' dimColor>{prefix}</Text>
        </Box>
      )}
      <Box flexDirection='column' paddingLeft={2}>
        <Text dimColor>╭─ files ─────</Text>
        {shown.map((path, i) => {
          // prefix 가 있으면 그 부분 제거해서 상대경로로 표시
          const display = prefix && path.startsWith(prefix) ? path.slice(prefix.length) : path
          return <Text key={`f${i}`}>{display}</Text>
        })}
        {hidden > 0 && <Text dimColor>… +{hidden}개 더</Text>}
        <Text dimColor>╰─────────────</Text>
      </Box>
    </Box>
  )
}
