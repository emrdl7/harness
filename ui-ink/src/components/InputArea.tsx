// InputArea — MultilineInput 과 SlashPopup 을 묶는 컨테이너
// D-11: SlashPopup 은 InputArea "위쪽" 에 표시 → flexDirection='column' 에서 SlashPopup 먼저 렌더
// 본 Plan 은 실제 WS 송신이나 messages store push 를 수행하지 않음
// onSubmit 은 상위(App.tsx) 가 WS 송신을 처리함
import React from 'react'
import {Box, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useInputStore} from '../store/input.js'
import {MultilineInput} from './MultilineInput.js'
import {SlashPopup} from './SlashPopup.js'

interface InputAreaProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

export const InputArea: React.FC<InputAreaProps> = ({onSubmit, disabled}) => {
  const {stdout} = useStdout()
  const columns = stdout?.columns ?? 80

  const {buffer, setBuffer, slashOpen, setSlashOpen} = useInputStore(
    useShallow((s) => ({
      buffer: s.buffer,
      setBuffer: s.setBuffer,
      slashOpen: s.slashOpen,
      setSlashOpen: s.setSlashOpen,
    }))
  )

  // buffer 가 '/' 로 시작하면 popup 자동 open, 아니면 자동 close
  React.useEffect(() => {
    const shouldOpen = buffer.startsWith('/')
    if (shouldOpen !== slashOpen) {
      setSlashOpen(shouldOpen)
    }
  }, [buffer, slashOpen, setSlashOpen])

  const handleSlashSelect = React.useCallback(
    (commandName: string) => {
      // 선택된 명령으로 buffer 를 교체하고 trailing space 추가
      // INPT-08(Tab 인자 자동완성) 확장 훅 — 실제 인자 자동완성은 후속 Plan 에서 구현
      setBuffer(commandName + ' ')
      setSlashOpen(false)
    },
    [setBuffer, setSlashOpen]
  )

  const handleSlashClose = React.useCallback(() => {
    setSlashOpen(false)
  }, [setSlashOpen])

  // slashQuery — buffer 전체(leading '/' 포함)에서 첫 공백까지만 전달
  // filterSlash 가 leading '/' 를 내부적으로 제거하여 처리
  // 첫 공백 이후는 '명령 인자' 구간이므로 팝업 필터에서 제외
  const slashQuery = React.useMemo(() => {
    if (!buffer.startsWith('/')) return ''
    const spaceIdx = buffer.indexOf(' ')
    return spaceIdx === -1 ? buffer : buffer.slice(0, spaceIdx)
  }, [buffer])

  return (
    <Box flexDirection='column' width={columns} backgroundColor='#222222' paddingY={1} paddingX={2}>
      {slashOpen && (
        <SlashPopup
          query={slashQuery}
          onSelect={handleSlashSelect}
          onClose={handleSlashClose}
        />
      )}
      <MultilineInput onSubmit={onSubmit} disabled={disabled} />
    </Box>
  )
}
