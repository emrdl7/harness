// Message — Gemini CLI 스타일 마크다운 렌더 (RND-06, RND-10, RND-11)
// 코드블록: 라인 번호 + 신택스 하이라이트
// 텍스트: **bold**, `inline code`, # 헤더, - / 1. 목록, --- 수평선, R1 표
import React from 'react'
import {Box, Text} from 'ink'
import Link from 'ink-link'
import {useTerminalColumns} from '../hooks/useTerminalColumns.js'
import {highlight} from 'cli-highlight'
import {stringWidth} from '../utils/stringWidth.js'
import type {Message as MessageType} from '../store/messages.js'
import {useRoomStore} from '../store/room.js'
import {userColor} from '../utils/userColor.js'
import {getToolRenderer} from './tools/index.js'

interface MessageProps {
  message: MessageType
  isStatic?: boolean
}

interface TextSegment { type: 'text'; text: string }
interface CodeSegment { type: 'code'; text: string; lang?: string }
// R1: GitHub 스타일 마크다운 표 — | h | h |\n|---|---|\n| v | v |
interface TableSegment { type: 'table'; headers: string[]; rows: string[][] }
// R2: 모델이 자연어 안에 직접 출력한 JSON (object/array)
interface JsonSegment { type: 'json'; text: string }
type ContentSegment = TextSegment | CodeSegment | TableSegment | JsonSegment

function highlightCode(code: string, lang?: string): string {
  try {
    return highlight(code, {language: lang, ignoreIllegals: true})
  } catch {
    return code
  }
}

function splitByCodeFence(content: string, streaming?: boolean): ContentSegment[] {
  const segments: ContentSegment[] = []
  const fenceRe = /```(\w*)\n([\s\S]*?)```/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = fenceRe.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({type: 'text', text: content.slice(lastIndex, match.index)})
    }
    const rawLang = match[1]
    segments.push({type: 'code', text: match[2], lang: rawLang !== '' ? rawLang : undefined})
    lastIndex = fenceRe.lastIndex
  }

  const remaining = content.slice(lastIndex)

  // 스트리밍 중 — 닫는 ``` 없는 열린 펜스도 즉시 CodeBlock 으로 렌더 (높이 점프 방지)
  if (streaming && remaining) {
    const openIdx = remaining.indexOf('```')
    if (openIdx !== -1) {
      if (openIdx > 0) segments.push({type: 'text', text: remaining.slice(0, openIdx)})
      const afterTick = remaining.slice(openIdx + 3)
      const nlIdx = afterTick.indexOf('\n')
      if (nlIdx !== -1) {
        const rawLang = afterTick.slice(0, nlIdx)
        segments.push({
          type: 'code',
          text: afterTick.slice(nlIdx + 1),
          lang: rawLang !== '' ? rawLang : undefined,
        })
      } else {
        // 언어 라인도 미완성 — 텍스트 유지
        segments.push({type: 'text', text: remaining})
      }
      if (segments.length === 0) segments.push({type: 'text', text: content})
      return segments
    }
  }

  if (remaining) segments.push({type: 'text', text: remaining})
  if (segments.length === 0) segments.push({type: 'text', text: content})
  return segments
}

// R1: 마크다운 표 감지/분리. text segment 안에서 다음 패턴을 TableSegment 로 추출.
//   | a | b |
//   |---|---|
//   | 1 | 2 |
function isTableHeaderLine(line: string): boolean {
  const t = line.trim()
  if (!t.startsWith('|') || !t.endsWith('|')) return false
  // 최소 1개 cell — '|x|' 형태도 허용 (split 길이 ≥ 3: '', x, '')
  return t.split('|').length >= 3
}

function isTableSeparatorLine(line: string): boolean {
  const t = line.trim()
  if (!t.startsWith('|') || !t.endsWith('|')) return false
  // 각 셀은 -, :, 공백 으로만 구성하며 최소 1개 - 포함
  const cells = t.slice(1, -1).split('|')
  return cells.length > 0 && cells.every(c => /^[\s\-:]+$/.test(c) && c.includes('-'))
}

function parseTableRow(line: string): string[] {
  return line.trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(s => s.trim())
}

function splitByTable(text: string): ContentSegment[] {
  const lines = text.split('\n')
  const out: ContentSegment[] = []
  let buffer: string[] = []
  const flushBuf = () => {
    if (buffer.length > 0) {
      out.push({type: 'text', text: buffer.join('\n')})
      buffer = []
    }
  }
  let i = 0
  while (i < lines.length) {
    const line = lines[i]!
    // 표 시작 후보 — 이 라인이 |..| 형태 + 다음 라인이 |---| separator
    if (isTableHeaderLine(line) && i + 1 < lines.length && isTableSeparatorLine(lines[i + 1]!)) {
      flushBuf()
      const headers = parseTableRow(line)
      const colCount = headers.length
      i += 2  // header + separator skip
      const rows: string[][] = []
      while (i < lines.length && isTableHeaderLine(lines[i]!)) {
        const row = parseTableRow(lines[i]!)
        // 셀 수 정규화 (부족하면 빈 셀 채움, 초과하면 자름)
        while (row.length < colCount) row.push('')
        if (row.length > colCount) row.length = colCount
        rows.push(row)
        i++
      }
      out.push({type: 'table', headers, rows})
    } else {
      buffer.push(line)
      i++
    }
  }
  flushBuf()
  return out
}

// R2: text segment 안에서 multi-line JSON object/array 감지. 라인 시작이 `{`/`[` 이고
//   괄호 균형 + JSON.parse 검증 통과 시에만 JsonSegment 로 추출. 잘못 감지 위험을 막기 위해
//   문자열 안의 brace 도 포함되는 단순 depth count 후 JSON.parse 로 최종 검증.
function splitByJson(text: string): ContentSegment[] {
  const lines = text.split('\n')
  const out: ContentSegment[] = []
  let buffer: string[] = []
  const flushBuf = () => {
    if (buffer.length > 0) {
      out.push({type: 'text', text: buffer.join('\n')})
      buffer = []
    }
  }
  let i = 0
  while (i < lines.length) {
    const line = lines[i]!
    const trimmed = line.trim()
    const open = trimmed[0]
    if (open === '{' || open === '[') {
      const close = open === '{' ? '}' : ']'
      // depth 기반 끝 라인 후보 탐색 (string 내부 brace 도 셈 — JSON.parse 로 보정)
      let depth = 0
      let endIdx = -1
      for (let j = i; j < lines.length; j++) {
        for (const c of lines[j]!) {
          if (c === open) depth++
          else if (c === close) depth--
        }
        if (depth === 0) { endIdx = j; break }
      }
      if (endIdx === -1) {
        buffer.push(line); i++; continue
      }
      const combined = lines.slice(i, endIdx + 1).join('\n')
      try {
        JSON.parse(combined)
        flushBuf()
        out.push({type: 'json', text: combined})
        i = endIdx + 1
        continue
      } catch {
        // JSON 아님 — 일반 텍스트
      }
    }
    buffer.push(line); i++
  }
  flushBuf()
  return out
}

// R2: JsonBlock — 정렬 pretty-print + cli-highlight('json') 컬러
function JsonBlock({text, segKey}: {text: string; segKey: string}): React.ReactElement {
  let pretty = text
  try {
    pretty = JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    // 도달 안 함 (splitByJson 가 검증) — 방어
  }
  const highlighted = highlightCode(pretty, 'json')
  return (
    <Box flexDirection='column' marginY={0}>
      <Text dimColor>╭─ json ─────</Text>
      <Text key={`${segKey}-c`} wrap='wrap'>{highlighted}</Text>
      <Text dimColor>╰────────────</Text>
    </Box>
  )
}

// R1: TableBlock — 컬럼 너비 = 셀 max(stringWidth). 셀 사이 ' │ ', 헤더 아래 '─┼─' 분리선.
//   stringWidth 가 CJK wide-char 폭을 정확히 처리해 한글/한자 표도 정렬.
function TableBlock({headers, rows, segKey}: {
  headers: string[]; rows: string[][]; segKey: string
}): React.ReactElement {
  const colW = headers.map((h, i) => {
    let max = stringWidth(h)
    for (const r of rows) {
      const w = stringWidth(r[i] ?? '')
      if (w > max) max = w
    }
    return max
  })
  const SEP = ' │ '
  const padCell = (text: string, width: number) => {
    const pad = Math.max(0, width - stringWidth(text))
    return text + ' '.repeat(pad)
  }
  const sepLine = colW.map(w => '─'.repeat(w)).join('─┼─')
  return (
    <Box flexDirection='column' marginY={0}>
      <Text bold>{headers.map((h, i) => padCell(h, colW[i] ?? 0)).join(SEP)}</Text>
      <Text dimColor>{sepLine}</Text>
      {rows.map((r, ri) => (
        <Text key={`${segKey}-r${ri}`}>
          {r.map((c, i) => padCell(c, colW[i] ?? 0)).join(SEP)}
        </Text>
      ))}
    </Box>
  )
}

// **bold**, *italic*, `inline code`, [link](url), path/file.ext(:line(:col)?)? 인라인 파싱
// R3: 파일 경로 패턴 — 확장자 첫 글자 알파벳 강제로 1.5/2.0 같은 숫자 false-positive 회피
//   foo.ts · src/foo.ts · src/foo.ts:42 · src/foo.ts:42:7 · ~/.zshrc
const PATH_PATTERN = String.raw`\b[\w./~-]*\w+\.[a-zA-Z]\w{0,5}(?::\d+(?::\d+)?)?\b`
// R5: 숫자 + 단위 메트릭 — 245ms · 1.2 MB · 98.5% · 42s 등. 단위는 흔한 것만 등록 (false-positive 회피).
// 끝 \b 는 % 같은 non-word 문자 뒤에서 매치 실패해서 lookahead 로 word 끝 또는 비-단어/끝을 강제.
const NUMBER_UNIT_PATTERN = String.raw`\b\d+(?:\.\d+)?\s?(?:ms|us|ns|µs|s|min|h|day|days|B|KB|MB|GB|TB|fps|%)(?![\w])`
// alternation 안에 backtick(\x60) 패턴 포함 — String.raw 안에서 raw backtick 삽입이
// template literal 종료 문자라 \x60 으로 표기. 매칭 결과상 동일.
// 순서 — bold/italic/code/link 가장 먼저, 그 다음 NUMBER_UNIT (PATH 보다 먼저: '1.2MB' 가
// PATH 의 '1.5' false-positive 회피 패턴에 안 잡히므로 NUMBER 가 명시적으로 잡아야 함),
// 마지막 PATH (가장 광범위).
const INLINE_RE = new RegExp(
  String.raw`(\*\*[^*\n]+\*\*|\*[^*\n]+\*|\x60[^\x60\n]+\x60|\[[^\]\n]+\]\([^)\n]+\)|`
  + NUMBER_UNIT_PATTERN + '|' + PATH_PATTERN + ')',
  'g'
)

function InlineText({text, baseKey}: {text: string; baseKey: string}): React.ReactElement {
  // 새 RegExp 인스턴스로 stateful exec 격리 (모듈 레벨 RE 의 lastIndex 공유 회피)
  const re = new RegExp(INLINE_RE.source, 'g')
  const parts: React.ReactElement[] = []
  let last = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<Text key={`${baseKey}-t${i++}`}>{text.slice(last, m.index)}</Text>)
    const tok = m[0]
    if (tok.startsWith('**')) {
      parts.push(<Text key={`${baseKey}-b${i++}`} bold>{tok.slice(2, -2)}</Text>)
    } else if (tok.startsWith('*')) {
      parts.push(<Text key={`${baseKey}-i${i++}`} italic>{tok.slice(1, -1)}</Text>)
    } else if (tok.startsWith('`')) {
      parts.push(<Text key={`${baseKey}-c${i++}`} color='cyan'>{tok.slice(1, -1)}</Text>)
    } else if (tok.startsWith('[')) {
      const linkMatch = tok.match(/\[([^\]]+)\]\(([^)]+)\)/)
      if (linkMatch) {
        parts.push(
          <Link key={`${baseKey}-l${i++}`} url={linkMatch[2]!}>
            <Text color='blueBright' underline>{linkMatch[1]}</Text>
          </Link>
        )
      } else {
        parts.push(<Text key={`${baseKey}-t${i++}`}>{tok}</Text>)
      }
    } else if (/^\d/.test(tok)) {
      // R5: 숫자 + 단위 (245ms · 1.2 MB · 98.5%) — yellow 강조
      parts.push(<Text key={`${baseKey}-n${i++}`} color='yellow'>{tok}</Text>)
    } else {
      // R3: 파일 경로 — alternation 마지막 분기라 여기로만 떨어진다
      parts.push(<Text key={`${baseKey}-p${i++}`} color='cyan' underline>{tok}</Text>)
    }
    last = re.lastIndex
  }
  if (last < text.length) parts.push(<Text key={`${baseKey}-t${i}`}>{text.slice(last)}</Text>)
  if (parts.length === 0) return <Text />
  return <Text>{parts}</Text>
}

// 텍스트 한 줄 — 헤더 / 목록 / 수평선 / 일반 텍스트 분기
function TextLine({line, lineKey}: {line: string; lineKey: string}): React.ReactElement {
  // 인용문 >
  const bq = line.match(/^>\s*(.+)/)
  if (bq) {
    return (
      <Box paddingLeft={1}>
        <Text color='gray'>{'│ '}</Text>
        <Text italic dimColor><InlineText text={bq[1]!} baseKey={lineKey + '-i'} /></Text>
      </Box>
    )
  }
  // 헤더 ### / ## / #
  const h = line.match(/^(#{1,3}) (.+)/)
  if (h) {
    const isH1 = h[1].length === 1
    return <Text bold color='blue' underline={isH1}>{h[2]}</Text>
  }
  // 불릿 목록
  const ul = line.match(/^(\s*)[*-] (.+)/)
  if (ul) {
    return (
      <Box>
        <Text color='cyan'>{ul[1]}{'• '}</Text>
        <InlineText text={ul[2]!} baseKey={lineKey + '-i'} />
      </Box>
    )
  }
  // 번호 목록
  const ol = line.match(/^(\s*)(\d+)\. (.+)/)
  if (ol) {
    return (
      <Box>
        <Text color='cyan'>{ol[1]}{ol[2]}{'. '}</Text>
        <InlineText text={ol[3]!} baseKey={lineKey + '-i'} />
      </Box>
    )
  }
  // 수평선
  if (/^-{3,}$/.test(line.trim())) {
    return <Text dimColor>{'─'.repeat(40)}</Text>
  }
  // 일반 텍스트 (인라인 마크다운 포함)
  return <InlineText text={line} baseKey={lineKey} />
}

// diff 블록 — +/- 라인 색상 (git diff 스타일)
function DiffBlock({text, segKey}: {text: string; segKey: string}): React.ReactElement {
  const lines = text.split('\n')
  if (lines[lines.length - 1] === '') lines.pop()
  return (
    <Box flexDirection='column' marginY={1}>
      <Text dimColor>{'╭─ diff ─────────────────────'}</Text>
      {lines.map((line, i) => {
        const color =
          line.startsWith('+++') || line.startsWith('---') ? 'yellow' :
          line.startsWith('+')                              ? 'green'  :
          line.startsWith('-')                              ? 'red'    :
          line.startsWith('@@')                             ? 'cyan'   :
          undefined
        return (
          <Box key={`${segKey}-d${i}`} paddingLeft={1}>
            <Text color={color} wrap='wrap'>{line}</Text>
          </Box>
        )
      })}
      <Text dimColor>{'╰─────────────────────────────'}</Text>
    </Box>
  )
}

// unified diff 자동 감지
function looksLikeDiff(text: string, lang?: string): boolean {
  if (lang === 'diff' || lang === 'patch') return true
  return /^(---|\+\+\+|@@)/m.test(text) && /^\+/m.test(text) && /^-/m.test(text)
}

// 스트리밍 중 최대 표시 줄 수 — 초과분은 "+ N줄" 로 접어서 Ink 트리 크기 고정
const MAX_STREAMING_LINES = 30

// 코드블록 — 라인 번호 + 단일 Text 렌더
// streaming=true 이면 하이라이팅 생략 (부분 코드 → 깨진 ANSI 방지, 높이 점프 방지)
function CodeBlock({text, lang, segKey, columns, messageWidth, streaming}: {text: string; lang?: string; segKey: string; columns: number; messageWidth: number; streaming?: boolean}): React.ReactElement {
  if (!streaming && looksLikeDiff(text, lang)) return <DiffBlock text={text} segKey={segKey} />

  // 스트리밍 완료 후에만 하이라이팅 적용
  const displayCode = streaming ? text : highlightCode(text, lang)
  const allLines = displayCode.split('\n')
  if (allLines[allLines.length - 1] === '') allLines.pop()

  // 스트리밍 중 MAX_STREAMING_LINES 초과 시 마지막 N줄만 표시
  const hiddenCount = streaming && allLines.length > MAX_STREAMING_LINES
    ? allLines.length - MAX_STREAMING_LINES
    : 0
  const lines = hiddenCount > 0 ? allLines.slice(hiddenCount) : allLines
  const totalLines = allLines.length

  const numW = String(totalLines).length
  const langBadge = lang ? ` ${lang} ` : ''
  const barLen = Math.max(2, Math.min(columns - langBadge.length - 4, 40))

  const DIM_START = '\x1b[2m'
  const DIM_END = '\x1b[22m'

  const body = lines.map((line, i) =>
    `${DIM_START}${String(hiddenCount + i + 1).padStart(numW)}  │ ${DIM_END}${line}`
  ).join('\n')

  return (
    <Box flexDirection='column' marginY={1} width={messageWidth}>
      <Text dimColor>{`╭─${langBadge}${'─'.repeat(barLen)}`}</Text>
      {hiddenCount > 0 && (
        <Text dimColor>{`  … +${hiddenCount}줄`}</Text>
      )}
      <Text wrap='wrap'>{body}</Text>
      <Text dimColor>{'╰' + '─'.repeat(barLen + langBadge.length + 2)}</Text>
    </Box>
  )
}

const MessageBase: React.FC<MessageProps> = ({message, isStatic}) => {
  const columns = useTerminalColumns()
  // Static(완료된 메시지)일 경우 터미널 크기 조정 시 정렬 깨짐 방지를 위해 width를 크게 주어 터미널 native wrap에 맡김
  const messageWidth = isStatic ? 10000 : columns
  const roomName = useRoomStore((s) => s.roomName)
  const authorLabel = roomName && message.role === 'user'
    ? (typeof message.meta?.['author'] === 'string' ? message.meta['author'] : 'me')
    : null

  // AR-03a: content+streaming 키로 segments 캐시 — 동일 content 의 재파싱 비용 제거
  // R1: 표 패턴(`|---|`) 도 cheap detect 후 splitByTable 추가 적용
  // R2: JSON 패턴(라인 시작이 `{`/`[`) 도 cheap detect 후 splitByJson 적용
  const segments: ContentSegment[] = React.useMemo(() => {
    const hasCodeFence = message.content.includes('```')
    const hasTable = message.content.includes('|---') || message.content.includes('| ---')
    const hasJson = /^\s*[{[]/m.test(message.content)
    const codeSegs = hasCodeFence
      ? splitByCodeFence(message.content, message.streaming)
      : [{type: 'text', text: message.content} as ContentSegment]
    if (!hasTable && !hasJson) return codeSegs
    // text segment 만 추가 분리. table → json 순서 (table 우선, JSON 은 표 안 brace 와 충돌 회피)
    const expanded: ContentSegment[] = []
    for (const s of codeSegs) {
      if (s.type !== 'text') { expanded.push(s); continue }
      const tableSegs = hasTable ? splitByTable(s.text) : [s]
      for (const ts of tableSegs) {
        if (ts.type === 'text' && hasJson) expanded.push(...splitByJson(ts.text))
        else expanded.push(ts)
      }
    }
    return expanded
  }, [message.content, message.streaming])

  // ── user ──────────────────────────────────────────────────────
  if (message.role === 'user') {
    return (
      <Box marginTop={1} flexDirection='column' width={messageWidth}>
        <Box>
          {authorLabel && (
            <Text color={userColor(authorLabel)} bold>{`[${authorLabel}] `}</Text>
          )}
          <Text color='cyan' bold>{'❯ '}</Text>
          <Text bold wrap='wrap'>{message.content}</Text>
        </Box>
      </Box>
    )
  }

  // ── assistant ─────────────────────────────────────────────────
  if (message.role === 'assistant') {
    return (
      <Box marginTop={1} flexDirection='column' width={messageWidth}>
        {segments.map((seg, idx) => {
          const segKey = `${message.id}-seg-${idx}`
          if (seg.type === 'code') {
            return <CodeBlock key={segKey} text={seg.text} lang={seg.lang} segKey={segKey} columns={columns} messageWidth={messageWidth} streaming={message.streaming} />
          }
          if (seg.type === 'table') {
            return <TableBlock key={segKey} headers={seg.headers} rows={seg.rows} segKey={segKey} />
          }
          if (seg.type === 'json') {
            return <JsonBlock key={segKey} text={seg.text} segKey={segKey} />
          }
          const lines = seg.text.split('\n')
          return (
            <Box key={segKey} flexDirection='column'>
              {lines.map((line, li) => (
                <TextLine key={`${segKey}-l${li}`} line={line} lineKey={`${segKey}-l${li}`} />
              ))}
            </Box>
          )
        })}
      </Box>
    )
  }

  // ── tool ──────────────────────────────────────────────────────
  // AR-01: tool 이름 → 컴포넌트 registry 라우팅 (Pi Mono 패턴)
  // payload 가 dict 면 전용 컴포넌트, 아니면 DefaultToolBlock 가 fallbackContent 표시
  if (message.role === 'tool') {
    const Renderer = getToolRenderer(message.toolName ?? '')
    return (
      <Box width={messageWidth}>
        <Renderer
          name={message.toolName ?? ''}
          args={message.toolArgs}
          payload={message.toolPayload}
          streaming={message.streaming}
          fallbackContent={message.content}
        />
      </Box>
    )
  }

  // ── system ────────────────────────────────────────────────────
  return (
    <Box marginTop={0} width={messageWidth}>
      <Text color='gray' dimColor wrap='wrap'>{'  ℹ ' + message.content}</Text>
    </Box>
  )
}

// AR-03a: React.memo — message reference 동일 시 리렌더 skip
// (active 메시지는 매 token flush 마다 새 reference 라 효과 미미하지만,
//  user/system/tool 메시지가 한 번 완료되면 다른 store 업데이트에 영향 안 받음)
export const Message = React.memo(MessageBase)
