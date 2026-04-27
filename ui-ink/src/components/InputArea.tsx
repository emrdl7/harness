// InputArea — MultilineInput 과 SlashPopup/FilePicker 를 묶는 컨테이너
// 자식 순서: MultilineInput → SlashPopup → FilePicker (popup 들이 input 아래로 표시)
//   이전엔 popup 이 input 위였지만 입력창 위치가 popup 등장/사라짐에 따라
//   요동치는 UX 문제로 input 을 위에 고정하고 popup 을 아래로 변경.
// 본 Plan 은 실제 WS 송신이나 messages store push 를 수행하지 않음
// onSubmit 은 상위(App.tsx) 가 WS 송신을 처리함
import React from 'react'
import {Box} from 'ink'
import {useTerminalColumns} from '../hooks/useTerminalColumns.js'
import {useShallow} from 'zustand/react/shallow'
import {useInputStore} from '../store/input.js'
import {MultilineInput} from './MultilineInput.js'
import {SlashPopup} from './SlashPopup.js'
import {FilePicker} from './FilePicker.js'

interface InputAreaProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

export const InputArea: React.FC<InputAreaProps> = ({onSubmit, disabled}) => {
  const columns = useTerminalColumns()

  const {buffer, setBuffer, slashOpen, setSlashOpen, filePickerOpen, setFilePickerOpen} = useInputStore(
    useShallow((s) => ({
      buffer: s.buffer,
      setBuffer: s.setBuffer,
      slashOpen: s.slashOpen,
      setSlashOpen: s.setSlashOpen,
      filePickerOpen: s.filePickerOpen,
      setFilePickerOpen: s.setFilePickerOpen,
    }))
  )

  // IX-01: buffer 안 마지막 @token 추출 — '여기 @src/foo' → {token:'src/foo', start:3}
  // @ 앞이 공백/시작이어야 (이메일 같은 케이스 제외), token 안에는 공백/개행 없음
  const atToken = React.useMemo(() => {
    const atIdx = buffer.lastIndexOf('@')
    if (atIdx === -1) return null
    if (atIdx > 0 && !/\s/.test(buffer[atIdx - 1] ?? '')) return null
    const after = buffer.slice(atIdx + 1)
    if (/[\s\n]/.test(after)) return null
    return {token: after, start: atIdx}
  }, [buffer])

  // buffer 가 '/' 로 시작하면 slash popup 자동 open, 아니면 자동 close
  React.useEffect(() => {
    const shouldOpen = buffer.startsWith('/')
    if (shouldOpen !== slashOpen) {
      setSlashOpen(shouldOpen)
    }
  }, [buffer, slashOpen, setSlashOpen])

  // IX-01: @ 토큰 활성 시 file picker 자동 open. slash popup 과 동시 활성화는 X (slash 우선)
  React.useEffect(() => {
    const shouldOpen = atToken !== null && !buffer.startsWith('/')
    if (shouldOpen !== filePickerOpen) {
      setFilePickerOpen(shouldOpen)
    }
  }, [atToken, buffer, filePickerOpen, setFilePickerOpen])

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

  // IX-01: file picker 선택 — buffer 의 @token 부분을 절대경로로 치환 + trailing space
  const handleFileSelect = React.useCallback(
    (path: string) => {
      if (!atToken) {
        setFilePickerOpen(false)
        return
      }
      const before = buffer.slice(0, atToken.start)
      setBuffer(before + path + ' ')
      setFilePickerOpen(false)
    },
    [atToken, buffer, setBuffer, setFilePickerOpen]
  )

  const handleFileClose = React.useCallback(() => {
    setFilePickerOpen(false)
  }, [setFilePickerOpen])

  // slashQuery — buffer 전체(leading '/' 포함)에서 첫 공백까지만 전달
  // filterSlash 가 leading '/' 를 내부적으로 제거하여 처리
  // 첫 공백 이후는 '명령 인자' 구간이므로 팝업 필터에서 제외
  const slashQuery = React.useMemo(() => {
    if (!buffer.startsWith('/')) return ''
    const spaceIdx = buffer.indexOf(' ')
    return spaceIdx === -1 ? buffer : buffer.slice(0, spaceIdx)
  }, [buffer])

  return (
    <Box flexDirection='column' width={columns} paddingY={0} paddingX={2} borderStyle="single" borderLeft={false} borderRight={false} borderColor="gray">
      <MultilineInput onSubmit={onSubmit} disabled={disabled} />
      {slashOpen && (
        <SlashPopup
          query={slashQuery}
          onSelect={handleSlashSelect}
          onClose={handleSlashClose}
        />
      )}
      {filePickerOpen && atToken && (
        <FilePicker
          query={atToken.token}
          onSelect={handleFileSelect}
          onClose={handleFileClose}
        />
      )}
    </Box>
  )
}
