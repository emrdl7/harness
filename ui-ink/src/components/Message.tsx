// 단일 Message 기본 렌더 — role 별 prefix + 색상 (RND-10, RND-11)
// 코드 블록 / diff / syntax highlight 는 Wave 2 에서 확장.
import React from 'react'
import {Box, Text} from 'ink'
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

export const Message: React.FC<MessageProps> = ({message}) => {
  const color = theme.role[message.role]
  const prefix = PREFIX[message.role]
  return (
    <Box marginBottom={0}>
      <Text color={color} bold={message.role !== 'system'}>{prefix}</Text>
      <Text wrap='wrap'>{message.content}</Text>
    </Box>
  )
}
