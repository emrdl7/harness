// AR-01: registry 미매칭 fallback — 기존 한 줄 italic 동작 보존
// Test 5 (components.messagelist.test.tsx) 가 검증: '⚙' + '[name] {result}' 출력
import React from 'react'
import {Box, Text} from 'ink'
import type {ToolBlockProps} from './types.js'

export const DefaultToolBlock: React.FC<ToolBlockProps> = ({streaming, fallbackContent}) => {
  return (
    <Box marginTop={0}>
      <Text color={streaming ? 'yellow' : 'cyan'} dimColor>
        {streaming ? '  ⟳ ' : '  ⚙ '}
      </Text>
      <Text dimColor italic wrap='wrap'>{fallbackContent ?? ''}</Text>
    </Box>
  )
}
