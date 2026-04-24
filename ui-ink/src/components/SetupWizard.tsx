// 최초 실행 시 서버 URL + 토큰 입력 — 저장 후 자동 진입
import React, {useState} from 'react'
import {Box, Text, useInput} from 'ink'
import {TextInput} from '@inkjs/ui'
import {saveConfig, type HarnessConfig} from '../config.js'

interface Props {
  onDone: (cfg: HarnessConfig) => void
}

type Step = 'url' | 'token'

export const SetupWizard: React.FC<Props> = ({onDone}) => {
  const [step, setStep] = useState<Step>('url')
  const [url, setUrl] = useState('ws://127.0.0.1:7891')
  const [token, setToken] = useState('')
  const [error, setError] = useState('')

  useInput((_input, key) => {
    if (key.escape) {
      setError('')
    }
  })

  const handleUrlSubmit = (val: string) => {
    const trimmed = val.trim() || 'ws://127.0.0.1:7891'
    if (!trimmed.startsWith('ws://') && !trimmed.startsWith('wss://')) {
      setError('ws:// 또는 wss:// 로 시작해야 합니다')
      return
    }
    setError('')
    setUrl(trimmed)
    setStep('token')
  }

  const handleTokenSubmit = (val: string) => {
    const trimmed = val.trim()
    if (!trimmed) {
      setError('토큰을 입력하세요')
      return
    }
    setError('')
    const cfg: HarnessConfig = {url, token: trimmed}
    saveConfig(cfg)
    onDone(cfg)
  }

  return (
    <Box flexDirection='column' paddingTop={1}>
      <Text bold color='cyan'>
        {'   / /_  ____ ________  ___  __________'}
      </Text>
      <Text bold color='cyan'>
        {'  / __ \\/ __ `/ ___/ __ \\/ _ \\/ ___/ ___/'}
      </Text>
      <Text bold color='cyan'>
        {' / / / / /_/ / /  / / / /  __(__  |__  )'}
      </Text>
      <Text bold color='cyan'>
        {'/_/ /_/\\__,_/_/  /_/ /_/\\___/____/____/'}
      </Text>
      <Text color='gray'>{'  jabworks · harness v1.0'}</Text>

      <Box marginTop={1} flexDirection='column'>
        {step === 'url' && (
          <>
            <Text>서버 주소 <Text color='gray'>(기본: ws://127.0.0.1:7891)</Text></Text>
            <Box marginTop={0}>
              <Text color='green'>&gt; </Text>
              <TextInput
                placeholder='ws://127.0.0.1:7891'
                onSubmit={handleUrlSubmit}
              />
            </Box>
          </>
        )}

        {step === 'token' && (
          <>
            <Text color='gray'>서버: <Text color='white'>{url}</Text></Text>
            <Box marginTop={0}>
              <Text>접속 토큰 입력</Text>
            </Box>
            <Box>
              <Text color='green'>&gt; </Text>
              <TextInput
                placeholder='토큰을 붙여넣으세요'
                onSubmit={handleTokenSubmit}
              />
            </Box>
            <Text color='gray' dimColor>
              서버에서 토큰 생성: <Text color='white'>harness-token</Text>
            </Text>
          </>
        )}

        {error && <Text color='red'>{error}</Text>}
      </Box>
    </Box>
  )
}
