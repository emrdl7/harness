// 룸 입장 시 닉네임 입력 — 저장 후 자동 진입
import React, {useState} from 'react'
import {Box, Text} from 'ink'
import {TextInput} from '@inkjs/ui'
import {saveConfig, type HarnessConfig} from '../config.js'

interface Props {
  cfg: HarnessConfig
  onDone: (cfg: HarnessConfig) => void
}

export const NickPrompt: React.FC<Props> = ({cfg, onDone}) => {
  const [error, setError] = useState('')

  const handleSubmit = (val: string) => {
    const nick = val.trim()
    if (!nick) {
      setError('닉네임을 입력하세요')
      return
    }
    const next = {...cfg, nick}
    saveConfig(next)
    onDone(next)
  }

  return (
    <Box flexDirection='column' paddingTop={1}>
      <Text bold>룸 <Text color='cyan'>{cfg.room}</Text> 입장</Text>
      <Box marginTop={1} flexDirection='column'>
        <Text>닉네임 입력</Text>
        <Box>
          <Text color='green'>&gt; </Text>
          <TextInput placeholder='닉네임을 입력하세요' onSubmit={handleSubmit} />
        </Box>
        {error && <Text color='red'>{error}</Text>}
      </Box>
    </Box>
  )
}
