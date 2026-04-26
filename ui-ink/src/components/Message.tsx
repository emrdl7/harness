// Message — Gemini CLI 스타일 마크다운 렌더 (RND-06, RND-10, RND-11)
// 코드블록: 라인 번호 + 신택스 하이라이트
// 텍스트: **bold**, `inline code`, # 헤더, - / 1. 목록, --- 수평선
import React from 'react'
import {Box, Text, useStdout} from 'ink'
import {highlight} from 'cli-highlight'
import type {Message as MessageType} from '../store/messages.js'
import {useRoomStore} from '../store/room.js'
import {userColor} from '../utils/userColor.js'

interface MessageProps {
  message: MessageType
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

function splitByCodeFence(content: string): ContentSegment[] {
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
  if (lastIndex < content.length) {
    segments.push({type: 'text', text: content.slice(lastIndex)})
  }
  if (segments.length === 0) segments.push({type: 'text', text: content})
  return segments
}

// **bold** 와 `inline code` 인라인 파싱
function InlineText({text, baseKey}: {text: string; baseKey: string}): React.ReactElement {
  const re = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g
  const parts: React.ReactElement[] = []
  let last = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<Text key={`${baseKey}-t${i++}`}>{text.slice(last, m.index)}</Text>)
    const tok = m[0]
    if (tok.startsWith('**')) {
      parts.push(<Text key={`${baseKey}-b${i++}`} bold>{tok.slice(2, -2)}</Text>)
    } else {
      parts.push(<Text key={`${baseKey}-c${i++}`} color='cyan'>{tok.slice(1, -1)}</Text>)
    }
    last = re.lastIndex
  }
  if (last < text.length) parts.push(<Text key={`${baseKey}-t${i}`}>{text.slice(last)}</Text>)
  if (parts.length === 0) return <Text />
  return <Text>{parts}</Text>
}

// 텍스트 한 줄 — 헤더 / 목록 / 수평선 / 일반 텍스트 분기
function TextLine({line, lineKey}: {line: string; lineKey: string}): React.ReactElement {
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

// 코드블록 — 라인 번호 + 단일 Text 렌더 (per-line Box 방식은 이 포크에서 홀짝 라인 버그 있음)
function CodeBlock({text, lang, segKey, columns}: {text: string; lang?: string; segKey: string; columns: number}): React.ReactElement {
  if (looksLikeDiff(text, lang)) return <DiffBlock text={text} segKey={segKey} />
  const lines = text.split('\n')
  if (lines[lines.length - 1] === '') lines.pop()
  const numW = String(lines.length).length
  const langBadge = lang ? ` ${lang} ` : ''
  const barLen = Math.max(2, Math.min(columns - langBadge.length - 4, 40))
  // ANSI 없이 plain text 로 단일 문자열 구성 — Ink 높이 계산이 \n 기준으로 정확히 동작
  const body = lines.map((line, i) =>
    `${String(i + 1).padStart(numW)}  │ ${line}`
  ).join('\n')
  return (
    <Box flexDirection='column' marginY={1} width={columns}>
      <Text dimColor>{`╭─${langBadge}${'─'.repeat(barLen)}`}</Text>
      <Text wrap='wrap'>{body}</Text>
      <Text dimColor>{'╰' + '─'.repeat(barLen + langBadge.length + 2)}</Text>
    </Box>
  )
}

export const Message: React.FC<MessageProps> = ({message}) => {
  const {stdout} = useStdout()
  const columns = stdout?.columns ?? 80
  const roomName = useRoomStore((s) => s.roomName)
  const authorLabel = roomName && message.role === 'user'
    ? (typeof message.meta?.['author'] === 'string' ? message.meta['author'] : 'me')
    : null

  const hasCodeFence = message.content.includes('```')
  const segments: ContentSegment[] = hasCodeFence
    ? splitByCodeFence(message.content)
    : [{type: 'text', text: message.content}]

  // ── user ──────────────────────────────────────────────────────
  if (message.role === 'user') {
    return (
      <Box marginTop={1} flexDirection='column' width={columns}>
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
      <Box marginTop={1} flexDirection='column' width={columns}>
        {segments.map((seg, idx) => {
          const segKey = `${message.id}-seg-${idx}`
          if (seg.type === 'code') {
            return <CodeBlock key={segKey} text={seg.text} lang={seg.lang} segKey={segKey} columns={columns} />
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
  if (message.role === 'tool') {
    const isStreaming = message.streaming
    return (
      <Box marginTop={0} width={columns}>
        <Text color={isStreaming ? 'yellow' : 'green'} dimColor>
          {isStreaming ? '  ⟳ ' : '  ✓ '}
        </Text>
        <Text dimColor wrap='wrap'>{message.content}</Text>
      </Box>
    )
  }

  // ── system ────────────────────────────────────────────────────
  return (
    <Box marginTop={0} width={columns}>
      <Text dimColor wrap='wrap'>{'  ' + message.content}</Text>
    </Box>
  )
}
