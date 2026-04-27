// AR-01: read_file 결과 렌더
// 백엔드 tools/fs.py read_file 반환: {ok, content, path}
//
// 표시:
//   ⚙ read_file  src/foo.ts  (124 줄, 3.2 KB)
//   ╭─ ts ──────────────╮
//   │   1  │ import ... │  ← 처음 N 줄만 (cli-highlight)
//   │  ...              │
//   ╰────────────────────╯
import React from 'react'
import {Box, Text} from 'ink'
import {highlight} from 'cli-highlight'
import {DefaultToolBlock} from './DefaultToolBlock.js'
import type {ToolBlockProps} from './types.js'

interface ReadFilePayload {
  ok?: boolean
  content?: string
  path?: string
  error?: string
}

const MAX_PREVIEW_LINES = 20

function isReadFilePayload(v: unknown): v is ReadFilePayload {
  return typeof v === 'object' && v !== null
}

// 파일 확장자 → cli-highlight 언어 힌트
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

function safeHighlight(code: string, lang?: string): string {
  try {
    return highlight(code, {language: lang, ignoreIllegals: true})
  } catch {
    return code
  }
}

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export const ReadFileBlock: React.FC<ToolBlockProps> = (props) => {
  const {args, payload, streaming, fallbackContent} = props

  if (streaming || !isReadFilePayload(payload)) {
    return <DefaultToolBlock {...props} fallbackContent={fallbackContent} />
  }

  const path = typeof payload.path === 'string'
    ? payload.path
    : typeof args?.['path'] === 'string' ? args['path'] : '?'
  const content = typeof payload.content === 'string' ? payload.content : ''
  const errorMsg = typeof payload.error === 'string' ? payload.error : null
  const allLines = content.split('\n')
  if (allLines[allLines.length - 1] === '') allLines.pop()
  const lineCount = allLines.length
  const byteSize = Buffer.byteLength(content, 'utf8')
  const lang = langFromPath(path)

  const previewLines = allLines.slice(0, MAX_PREVIEW_LINES)
  const hidden = Math.max(0, lineCount - MAX_PREVIEW_LINES)
  const numW = String(Math.min(lineCount, MAX_PREVIEW_LINES)).length
  const highlighted = safeHighlight(previewLines.join('\n'), lang)

  const DIM = '\x1b[2m'
  const UND = '\x1b[22m'
  const body = highlighted.split('\n').map((line, i) =>
    `${DIM}${String(i + 1).padStart(numW)}  │ ${UND}${line}`
  ).join('\n')

  return (
    <Box flexDirection='column' marginY={0}>
      <Box>
        <Text color='cyan'>  ⚙ </Text>
        <Text bold>read_file </Text>
        <Text color='cyan'>{path}</Text>
        <Text dimColor>  ({lineCount}줄, {humanBytes(byteSize)})</Text>
      </Box>

      {errorMsg && (
        <Box paddingLeft={4}>
          <Text color='red' wrap='wrap'>{errorMsg}</Text>
        </Box>
      )}

      {previewLines.length > 0 && (
        <Box flexDirection='column' paddingLeft={2} marginY={0}>
          <Text dimColor>{lang ? `╭─ ${lang} ───────` : '╭───────────────'}</Text>
          <Text wrap='wrap'>{body}</Text>
          {hidden > 0 && <Text dimColor>… +{hidden}줄</Text>}
          <Text dimColor>╰───────────────</Text>
        </Box>
      )}
    </Box>
  )
}
