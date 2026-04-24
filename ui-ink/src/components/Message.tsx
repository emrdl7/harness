// 단일 Message 기본 렌더 — role 별 prefix + 색상 (RND-10, RND-11)
// cli-highlight 코드 펜스 하이라이트 통합 (RND-06, Task E-1)
import React from 'react'
import {Box, Text} from 'ink'
import {highlight} from 'cli-highlight'
import type {Message as MessageType} from '../store/messages.js'
import {theme} from '../theme.js'

interface MessageProps {
  message: MessageType
}

const PREFIX: Record<MessageType['role'], string> = {
  user: '❯ ',
  assistant: '● ',
  tool: '└ ',
  system: '  ',
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

// 코드 펜스 하이라이트 — cli-highlight 의 ANSI 출력을 Ink Text 로 pass-through
// 실패 시(언어 불명, ignoreIllegals 에서도 throw 할 경우) 원본 코드 반환
function highlightCode(code: string, lang?: string): string {
  try {
    return highlight(code, {language: lang, ignoreIllegals: true})
  } catch {
    // 언어 감지 실패 또는 highlight 오류 시 원본 반환 (T-02E-01 크래시 차단)
    return code
  }
}

// 코드 펜스 정규식으로 content 를 텍스트/코드 세그먼트 배열로 분리
function splitByCodeFence(content: string): ContentSegment[] {
  const segments: ContentSegment[] = []
  const fenceRe = /```(\w*)\n([\s\S]*?)```/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = fenceRe.exec(content)) !== null) {
    // 펜스 앞 일반 텍스트
    if (match.index > lastIndex) {
      segments.push({type: 'text', text: content.slice(lastIndex, match.index)})
    }
    // 코드 세그먼트 — lang 이 빈 문자열이면 undefined 로 처리 (highlight 에 lang 미전달)
    const rawLang = match[1]
    segments.push({
      type: 'code',
      text: match[2],
      lang: rawLang !== '' ? rawLang : undefined,
    })
    lastIndex = fenceRe.lastIndex
  }

  // 마지막 텍스트 세그먼트
  if (lastIndex < content.length) {
    segments.push({type: 'text', text: content.slice(lastIndex)})
  }

  // 코드 펜스가 전혀 없는 경우
  if (segments.length === 0) {
    segments.push({type: 'text', text: content})
  }

  return segments
}

export const Message: React.FC<MessageProps> = ({message}) => {
  const color = theme.role[message.role]
  const prefix = PREFIX[message.role]

  // 코드 펜스가 있는지 빠른 체크 — 없으면 파싱 생략
  const hasCodeFence = message.content.includes('```')
  const segments: ContentSegment[] = hasCodeFence
    ? splitByCodeFence(message.content)
    : [{type: 'text', text: message.content}]

  return (
    <Box marginBottom={0} flexDirection='column'>
      <Box>
        <Text color={color} bold={message.role !== 'system'}>{prefix}</Text>
        {segments.map((seg, idx) => {
          // React key — id + 인덱스 조합으로 고유성 보장 (index 단독 금지 준수)
          const key = `${message.id}-seg-${idx}`
          if (seg.type === 'code') {
            // 코드 펜스 하이라이트 — cli-highlight ANSI 출력 pass-through
            const highlighted = highlightCode(seg.text, seg.lang)
            return <Text key={key} wrap='wrap'>{highlighted}</Text>
          }
          return <Text key={key} wrap='wrap'>{seg.text}</Text>
        })}
      </Box>
    </Box>
  )
}
