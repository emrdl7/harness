// 환영 배너 — alt screen 모드에서 메시지 비어있을 때 표시 (Ink 트리 안)
import React from 'react'
import {Box, Text} from 'ink'

const LINES = [
  '   / /_  ____ ________  ___  __________',
  '  / __ \\/ __ `/ ___/ __ \\/ _ \\/ ___/ ___/',
  ' / / / / /_/ / /  / / / /  __(__  |__  )',
  '/_/ /_/\\__,_/_/  /_/ /_/\\___/____/____/',
] as const

const COLORS = ['magenta', 'blueBright', 'cyanBright', 'cyan'] as const

export const Banner: React.FC = () => (
  <Box flexDirection='column' marginTop={1} marginBottom={1}>
    {LINES.map((line, i) => (
      <Text key={i} color={COLORS[i]} bold>{line}</Text>
    ))}
    <Text color='white' dimColor>{'  jabworks · harness v1.0'}</Text>
  </Box>
)
