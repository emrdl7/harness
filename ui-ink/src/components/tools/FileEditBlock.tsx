// AR-01: write_file / edit_file 결과 렌더 (V1 Feature A — 파일 변경 diff 표시)
//
// 백엔드 tools/fs.py 반환:
//   write_file(신규):  {ok, path, is_new_file: true, new_content}
//   write_file(덮어쓰기): {ok, path, file_diff}
//   edit_file:         {ok, path, replaced, file_diff}
//   실패:               {ok: false, error}
//
// 표시:
//   ⚙ edit_file  src/foo.ts   +3 -1
//   ╭─ diff ─────────
//   @@ -10,3 +10,4 @@
//    context
//   -removed
//   +added1
//   +added2
//   ╰────────────────
import React from 'react'
import {Box, Text} from 'ink'
import {highlight} from 'cli-highlight'
import {DefaultToolBlock} from './DefaultToolBlock.js'
import type {ToolBlockProps} from './types.js'

interface FileEditPayload {
  ok?: boolean
  path?: string
  error?: string
  // edit/write(덮어쓰기)
  file_diff?: string
  replaced?: number
  // write 신규
  is_new_file?: boolean
  new_content?: string
}

// 신규 내용 / diff 미리보기 라인 캡 (Feature C 의 30줄 정책과 동일)
const MAX_LINES = 30

function isFileEditPayload(v: unknown): v is FileEditPayload {
  return typeof v === 'object' && v !== null
}

function langFromPath(path: string): string | undefined {
  const m = path.match(/\.([a-zA-Z0-9]+)$/)
  if (!m) return undefined
  const ext = m[1]!.toLowerCase()
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    py: 'python', rs: 'rust', go: 'go', java: 'java', kt: 'kotlin',
    rb: 'ruby', sh: 'bash', md: 'markdown', json: 'json', yaml: 'yaml', yml: 'yaml',
    toml: 'toml', html: 'html', css: 'css', scss: 'scss',
  }
  return map[ext]
}

function safeHighlight(code: string, lang: string): string {
  try {
    return highlight(code, {language: lang, ignoreIllegals: true})
  } catch {
    return code
  }
}

function diffStats(diff: string): {add: number; del: number} {
  let add = 0
  let del = 0
  for (const line of diff.split('\n')) {
    // unified diff 헤더(+++/---) 는 제외 — 추가/삭제 통계와 무관
    if (line.startsWith('+++') || line.startsWith('---')) continue
    if (line.startsWith('+')) add++
    else if (line.startsWith('-')) del++
  }
  return {add, del}
}

function clampLines(text: string, max: number): {text: string; hidden: number} {
  const lines = text.split('\n')
  // 마지막 빈 라인은 split 부산물 — 제거하여 라인 수 정확히
  if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop()
  if (lines.length <= max) return {text: lines.join('\n'), hidden: 0}
  return {text: lines.slice(0, max).join('\n'), hidden: lines.length - max}
}

export const FileEditBlock: React.FC<ToolBlockProps> = (props) => {
  const {name, args, payload, streaming, fallbackContent} = props

  // 스트리밍 중 또는 dict 가 아닌 결과는 fallback (snapshot 호환 포함)
  if (streaming || !isFileEditPayload(payload)) {
    return <DefaultToolBlock {...props} fallbackContent={fallbackContent} />
  }

  const path = typeof payload.path === 'string'
    ? payload.path
    : typeof args?.['path'] === 'string' ? args['path'] : '?'
  const error = typeof payload.error === 'string' ? payload.error : null

  // 실패
  if (error) {
    return (
      <Box flexDirection='column' marginY={0}>
        <Box>
          <Text color='red'>  ⚙ </Text>
          <Text bold>{name} </Text>
          <Text color='cyan'>{path}</Text>
          <Text color='red' dimColor>  실패</Text>
        </Box>
        <Box paddingLeft={4}>
          <Text color='red' wrap='wrap'>{error}</Text>
        </Box>
      </Box>
    )
  }

  // 신규 파일 — 전체 내용 (라인 캡 적용)
  if (payload.is_new_file && typeof payload.new_content === 'string') {
    const {text, hidden} = clampLines(payload.new_content, MAX_LINES)
    const totalLines = payload.new_content.split('\n').filter(Boolean).length
    const lang = langFromPath(path)
    const highlighted = safeHighlight(text, lang || 'plaintext')
    return (
      <Box flexDirection='column' marginY={0}>
        <Box>
          <Text color='green'>  ⚙ </Text>
          <Text bold>{name} </Text>
          <Text color='cyan'>{path}</Text>
          <Text color='green' dimColor>  +{totalLines}줄 신규</Text>
        </Box>
        <Box flexDirection='column' paddingLeft={2}>
          <Text dimColor>{lang ? `╭─ ${lang} ───────` : '╭───────────────'}</Text>
          <Text wrap='wrap'>{highlighted}</Text>
          {hidden > 0 && <Text dimColor>… +{hidden}줄</Text>}
          <Text dimColor>╰───────────────</Text>
        </Box>
      </Box>
    )
  }

  // 편집/덮어쓰기 — unified diff
  const diff = typeof payload.file_diff === 'string' ? payload.file_diff : ''
  if (!diff) {
    // file_diff='' — 동일 내용 덮어쓰기 또는 diff 생성 불가
    return (
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        <Text color='cyan'>{path}</Text>
        <Text dimColor>  (변경 없음)</Text>
      </Box>
    )
  }
  const {add, del} = diffStats(diff)
  // diff 는 헤더 라인(+++/---/@@) 포함이라 본문 30줄 + 여유 5
  const {text, hidden} = clampLines(diff, MAX_LINES + 5)
  const highlighted = safeHighlight(text, 'diff')

  return (
    <Box flexDirection='column' marginY={0}>
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>{name} </Text>
        <Text color='cyan'>{path}</Text>
        <Text dimColor>   </Text>
        <Text color='green'>+{add}</Text>
        <Text dimColor> </Text>
        <Text color='red'>-{del}</Text>
      </Box>
      <Box flexDirection='column' paddingLeft={2}>
        <Text dimColor>╭─ diff ─────────</Text>
        <Text wrap='wrap'>{highlighted}</Text>
        {hidden > 0 && <Text dimColor>… +{hidden}줄</Text>}
        <Text dimColor>╰───────────────</Text>
      </Box>
    </Box>
  )
}
