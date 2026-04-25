// Message → ANSI 문자열 포맷터 — 완료 메시지를 stdout 직접 출력용
// Message.tsx 의 React 렌더와 동일 스타일 (cli-highlight 코드펜스 포함)
import {highlight} from 'cli-highlight'
import type {Message} from '../store/messages.js'
import {userColor} from './userColor.js'

const RESET = '\x1b[0m'
const BOLD = '\x1b[1m'
const DIM = '\x1b[2m'

const ANSI: Record<string, string> = {
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  blue: '\x1b[34m',
  red: '\x1b[31m',
  white: '\x1b[37m',
  greenBright: '\x1b[92m',
}

function color(name: string): string {
  return ANSI[name] ?? ''
}

interface CodeSeg { type: 'code', text: string, lang?: string }
interface TextSeg { type: 'text', text: string }
type Seg = CodeSeg | TextSeg

function splitByCodeFence(content: string): Seg[] {
  const segments: Seg[] = []
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
  if (segments.length === 0) {
    segments.push({type: 'text', text: content})
  }
  return segments
}

function highlightCode(code: string, lang?: string): string {
  try {
    return highlight(code, {language: lang, ignoreIllegals: true})
  } catch {
    return code
  }
}

export interface FormatOpts {
  roomName?: string | null
}

export function formatMessage(m: Message, opts: FormatOpts = {}): string {
  const {roomName} = opts

  if (m.role === 'user') {
    const authorLabel = roomName
      ? (typeof m.meta?.['author'] === 'string' ? m.meta['author'] as string : 'me')
      : null
    let s = '\n'
    if (authorLabel) {
      s += `${BOLD}${color(userColor(authorLabel))}[${authorLabel}] ${RESET}`
    }
    s += `${BOLD}${color('cyan')}❯ ${RESET}`
    s += `${BOLD}${m.content}${RESET}`
    s += '\n'
    return s
  }

  if (m.role === 'assistant') {
    const segments = m.content.includes('```') ? splitByCodeFence(m.content) : [{type: 'text' as const, text: m.content}]
    let s = '\n'
    for (const seg of segments) {
      if (seg.type === 'code') {
        s += `${DIM}  ┌─${RESET}\n`
        const highlighted = highlightCode(seg.text, seg.lang)
        for (const line of highlighted.split('\n')) {
          s += `  ${line}\n`
        }
        s += `${DIM}  └─${RESET}\n`
      } else {
        s += seg.text
      }
    }
    if (!s.endsWith('\n')) s += '\n'
    return s
  }

  if (m.role === 'tool') {
    const isStreaming = m.streaming
    const prefix = isStreaming
      ? `${DIM}${color('yellow')}  ⟳ ${RESET}`
      : `${DIM}${color('green')}  ✓ ${RESET}`
    return `${prefix}${DIM}${m.content}${RESET}\n`
  }

  // system
  return `${DIM}  ${m.content}${RESET}\n`
}
