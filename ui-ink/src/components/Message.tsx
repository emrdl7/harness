// 단일 Message 기본 렌더 — role 별 prefix + 색상 (RND-10, RND-11)
// cli-highlight 코드 펜스 하이라이트 통합 (RND-06, Task E-1)
// DIFF-02: room 모드에서 user 메시지에 [author] prefix 표시
import React from 'react'
import {Box, Text} from 'ink'
import {highlight} from 'cli-highlight'
import type {Message as MessageType} from '../store/messages.js'
import {useRoomStore} from '../store/room.js'
import {userColor} from '../utils/userColor.js'

interface MessageProps {
  message: MessageType
  columns?: number   // 터미널 폭 — Box 명시적 width 지정으로 wrap 계산 정확도 향상
}

// 코드 펜스 세그먼트 타입 정의
interface TextSegment {
  type: 'text'
  text: string
}

interface CodeSegment {
  type: 'code'
  text: string
  lang?: string
}

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
    segments.push({
      type: 'code',
      text: match[2],
      lang: rawLang !== '' ? rawLang : undefined,
    })
    lastIndex = fenceRe.lastIndex
  }

  if (lastIndex < content.length) {
    segments.push({type: 'text', text: content.slice(lastIndex)})
  }
  if (segments.length === 0) {
    segments.push({type: 'text', text: content})
  }

  return segments
}

export const Message: React.FC<MessageProps> = ({message, columns}) => {
  const roomName = useRoomStore((s) => s.roomName)
  const authorLabel = roomName && message.role === 'user'
    ? (typeof message.meta?.['author'] === 'string' ? message.meta['author'] : 'me')
    : null

  const hasCodeFence = message.content.includes('```')
  const segments: ContentSegment[] = hasCodeFence
    ? splitByCodeFence(message.content)
    : [{type: 'text', text: message.content}]

  const w = columns ?? 80

  // ── user ──────────────────────────────────────────────────────
  if (message.role === 'user') {
    return (
      <Box marginTop={1} marginBottom={0} flexDirection='column' width={w}>
        <Box width={w}>
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
      <Box marginTop={1} marginBottom={0} flexDirection='column' width={w}>
        {segments.map((seg, idx) => {
          const key = `${message.id}-seg-${idx}`
          if (seg.type === 'code') {
            return (
              <Box key={key} flexDirection='column' marginTop={0} width={w}>
                <Text dimColor>{'  ┌─'}</Text>
                <Box paddingLeft={2} width={w}>
                  <Text wrap='wrap'>{highlightCode(seg.text, seg.lang)}</Text>
                </Box>
                <Text dimColor>{'  └─'}</Text>
              </Box>
            )
          }
          return (
            <Text key={key} wrap='wrap'>{seg.text}</Text>
          )
        })}
      </Box>
    )
  }

  // ── tool ──────────────────────────────────────────────────────
  if (message.role === 'tool') {
    const isStreaming = message.streaming
    return (
      <Box marginTop={0} marginBottom={0} width={w}>
        <Text color={isStreaming ? 'yellow' : 'green'} dimColor>
          {isStreaming ? '  ⟳ ' : '  ✓ '}
        </Text>
        <Text dimColor wrap='wrap'>{message.content}</Text>
      </Box>
    )
  }

  // ── system ────────────────────────────────────────────────────
  return (
    <Box marginTop={0} marginBottom={0} width={w}>
      <Text dimColor wrap='wrap'>{'  ' + message.content}</Text>
    </Box>
  )
}
