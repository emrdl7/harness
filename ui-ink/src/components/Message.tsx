// Message — Gemini CLI 스타일 마크다운 렌더 (RND-06, RND-10, RND-11)
// 코드블록: 라인 번호 + 신택스 하이라이트
// 텍스트: **bold**, `inline code`, # 헤더, - / 1. 목록, --- 수평선
import React from 'react'
import {Box, Text} from 'ink'
import Link from 'ink-link'
import {useTerminalColumns} from '../hooks/useTerminalColumns.js'
import {highlight} from 'cli-highlight'
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
type ContentSegment = TextSegment | CodeSegment

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

// **bold**, *italic*, `inline code`, [link](url), path/file.ext(:line(:col)?)? 인라인 파싱
// R3: 파일 경로 패턴 — 확장자 첫 글자 알파벳 강제로 1.5/2.0 같은 숫자 false-positive 회피
//   foo.ts · src/foo.ts · src/foo.ts:42 · src/foo.ts:42:7 · ~/.zshrc
const PATH_PATTERN = String.raw`\b[\w./~-]*\w+\.[a-zA-Z]\w{0,5}(?::\d+(?::\d+)?)?\b`
// alternation 안에 backtick(\x60) 패턴 포함 — String.raw 안에서 raw backtick 삽입이
// template literal 종료 문자라 \x60 으로 표기. 매칭 결과상 동일.
const INLINE_RE = new RegExp(
  String.raw`(\*\*[^*\n]+\*\*|\*[^*\n]+\*|\x60[^\x60\n]+\x60|\[[^\]\n]+\]\([^)\n]+\)|` + PATH_PATTERN + ')',
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
  const segments: ContentSegment[] = React.useMemo(() => {
    const hasCodeFence = message.content.includes('```')
    return hasCodeFence
      ? splitByCodeFence(message.content, message.streaming)
      : [{type: 'text', text: message.content}]
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
