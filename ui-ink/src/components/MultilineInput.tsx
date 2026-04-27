// MultilineInput — useInput 기반 자체 구현 (INPT-01: 서드파티 텍스트 입력 컴포넌트 불사용)
// INPT-01: 자체 구현
// INPT-02: Enter 제출, Shift+Enter·Ctrl+J 개행
// INPT-03: ↑↓ history (store 위임)
// INPT-04: POSIX (Ctrl+A/E/K/W/U)
// INPT-05: 멀티라인 paste — usePasteCompat (bracketed paste 직접 감지)
//           paste 텍스트는 cursor 위치에 insertAt 으로 삽입, submit 발생 없음
import React from 'react'
import {Box, Text, useInput} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useInputStore} from '../store/input.js'
import {usePaste} from '../hooks/usePasteCompat.js'

// 커서 상태 — row/col 을 buffer 문자열의 라인 배열과 동기화
interface Cursor {
  row: number
  col: number
}

interface MultilineInputProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

// 내부 유틸 — buffer 를 라인 배열로 쪼개기
const splitLines = (s: string): string[] => (s === '' ? [''] : s.split('\n'))
const joinLines = (ls: string[]): string => ls.join('\n')

// cursor 위치에 paste 또는 단일 문자를 삽입
const insertAt = (lines: string[], cur: Cursor, text: string): {lines: string[]; cursor: Cursor} => {
  const before = lines[cur.row]?.slice(0, cur.col) ?? ''
  const after = lines[cur.row]?.slice(cur.col) ?? ''
  const merged = before + text + after
  const mergedLines = merged.split('\n')
  const next = [...lines.slice(0, cur.row), ...mergedLines, ...lines.slice(cur.row + 1)]
  const lastInserted = mergedLines[mergedLines.length - 1] ?? ''
  const newRow = cur.row + mergedLines.length - 1
  const newCol = mergedLines.length === 1
    ? before.length + text.length
    : lastInserted.length - after.length
  return {lines: next, cursor: {row: newRow, col: newCol}}
}

// Ctrl+W 단어 삭제 (cursor 직전 공백 아닌 연속 문자 블록)
const deleteWordBefore = (lines: string[], cur: Cursor): {lines: string[]; cursor: Cursor} => {
  const line = lines[cur.row] ?? ''
  let i = cur.col
  while (i > 0 && line[i - 1] === ' ') i--
  while (i > 0 && line[i - 1] !== ' ') i--
  const next = line.slice(0, i) + line.slice(cur.col)
  const newLines = [...lines]
  newLines[cur.row] = next
  return {lines: newLines, cursor: {row: cur.row, col: i}}
}

// Ctrl+K — cursor 이후부터 라인 끝까지 삭제
const killToEnd = (lines: string[], cur: Cursor): {lines: string[]; cursor: Cursor} => {
  const line = lines[cur.row] ?? ''
  const next = line.slice(0, cur.col)
  const newLines = [...lines]
  newLines[cur.row] = next
  return {lines: newLines, cursor: cur}
}

export const MultilineInput: React.FC<MultilineInputProps> = ({onSubmit, disabled}) => {
  const {buffer, setBuffer, clearBuffer, pushHistory, historyUp, historyDown, slashOpen, filePickerOpen} = useInputStore(
    useShallow((s) => ({
      buffer: s.buffer,
      setBuffer: s.setBuffer,
      clearBuffer: s.clearBuffer,
      pushHistory: s.pushHistory,
      historyUp: s.historyUp,
      historyDown: s.historyDown,
      slashOpen: s.slashOpen,
      filePickerOpen: s.filePickerOpen,
    }))
  )

  const [cursor, setCursor] = React.useState<Cursor>({row: 0, col: 0})

  // buffer 변경 시 cursor 가 out-of-range 가 되지 않도록 clamp
  React.useEffect(() => {
    const lines = splitLines(buffer)
    setCursor((c) => {
      const row = Math.min(c.row, lines.length - 1)
      const col = Math.min(c.col, (lines[row] ?? '').length)
      if (row === c.row && col === c.col) return c
      return {row, col}
    })
  }, [buffer])

  // INPT-05: bracketed paste — cursor 위치에 삽입, submit 없음
  usePaste((pastedText) => {
    const lines = splitLines(buffer)
    const r = insertAt(lines, cursor, pastedText)
    setBuffer(joinLines(r.lines))
    setCursor(r.cursor)
  })

  useInput((input, key) => {
    const lines = splitLines(buffer)

    // 터미널 제약으로 Shift+Enter 가 일반 Enter 와 동일하게 인식되는 경우가 많음
    // 보완책으로 Option+Enter(Mac) / Alt+Enter 또는 Ctrl+J 를 개행으로 처리
    if ((key.return && (key.shift || key.meta)) || (key.ctrl && input === 'j')) {
      // AR-04: busy 중에도 개행 허용 — onSubmit 측 enqueue 로 처리
      void disabled
      const r = insertAt(lines, cursor, '\n')
      setBuffer(joinLines(r.lines))
      // 개행 시 커서를 다음 줄 처음으로 이동
      setCursor({
        row: cursor.row + 1,
        col: 0,
      })
      return
    }

    // IX-01: filePickerOpen 시 Enter/Tab 은 FilePicker 가 path 치환 처리 → submit 안 함
    if (filePickerOpen && (key.return || key.tab)) return

    // Enter (단독) → 제출
    // AR-04: busy 중에도 onSubmit 호출 — App.tsx 가 busy 분기로 enqueue/send 결정
    if (key.return && !key.shift) {
      const text = joinLines(lines)
      if (text.trim() === '') return
      pushHistory(text)
      clearBuffer()
      setCursor({row: 0, col: 0})
      onSubmit(text)
      return
    }

    // slashOpen / filePickerOpen 중에는 ↑↓·Enter 를 popup 에 패스스루
    if ((slashOpen || filePickerOpen) && (key.upArrow || key.downArrow || key.return)) return

    // history ↑↓
    if (key.upArrow) {
      if (lines.length > 1 && cursor.row > 0) {
        const newRow = cursor.row - 1
        const newCol = Math.min(cursor.col, (lines[newRow] ?? '').length)
        setCursor({row: newRow, col: newCol})
        return
      }
      historyUp()
      return
    }
    if (key.downArrow) {
      if (lines.length > 1 && cursor.row < lines.length - 1) {
        const newRow = cursor.row + 1
        const newCol = Math.min(cursor.col, (lines[newRow] ?? '').length)
        setCursor({row: newRow, col: newCol})
        return
      }
      historyDown()
      return
    }

    if (key.leftArrow) {
      if (cursor.col > 0) {
        setCursor({row: cursor.row, col: cursor.col - 1})
      } else if (cursor.row > 0) {
        const prev = lines[cursor.row - 1] ?? ''
        setCursor({row: cursor.row - 1, col: prev.length})
      }
      return
    }
    if (key.rightArrow) {
      const line = lines[cursor.row] ?? ''
      if (cursor.col < line.length) {
        setCursor({row: cursor.row, col: cursor.col + 1})
      } else if (cursor.row < lines.length - 1) {
        setCursor({row: cursor.row + 1, col: 0})
      }
      return
    }

    // POSIX 단축키 (INPT-04)
    if (key.ctrl && input === 'a') {
      setCursor({row: cursor.row, col: 0})
      return
    }
    if (key.ctrl && input === 'e') {
      setCursor({row: cursor.row, col: (lines[cursor.row] ?? '').length})
      return
    }
    if (key.ctrl && input === 'k') {
      const r = killToEnd(lines, cursor)
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }
    if (key.ctrl && input === 'w') {
      const r = deleteWordBefore(lines, cursor)
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }
    if (key.ctrl && input === 'u') {
      const newLines = [...lines]
      newLines[cursor.row] = ''
      setBuffer(joinLines(newLines))
      setCursor({row: cursor.row, col: 0})
      return
    }

    // Backspace / Delete
    if (key.backspace || key.delete) {
      if (cursor.col > 0) {
        const line = lines[cursor.row] ?? ''
        const next = line.slice(0, cursor.col - 1) + line.slice(cursor.col)
        const newLines = [...lines]
        newLines[cursor.row] = next
        setBuffer(joinLines(newLines))
        setCursor({row: cursor.row, col: cursor.col - 1})
      } else if (cursor.row > 0) {
        const prev = lines[cursor.row - 1] ?? ''
        const curLine = lines[cursor.row] ?? ''
        const merged = prev + curLine
        const newLines = [
          ...lines.slice(0, cursor.row - 1),
          merged,
          ...lines.slice(cursor.row + 1),
        ]
        setBuffer(joinLines(newLines))
        setCursor({row: cursor.row - 1, col: prev.length})
      }
      return
    }

    // 일반 입력
    if (input && !key.ctrl && !key.meta) {
      const r = insertAt(lines, cursor, input)
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }
  })

  const lines = splitLines(buffer)

  return (
    <Box flexDirection='column'>
      {lines.map((line, rowIdx) => {
        const prefix = rowIdx === 0 ? '❯ ' : '… '
        const isCursorLine = rowIdx === cursor.row
        if (!isCursorLine) {
          return (
            <Text key={'line-' + rowIdx} dimColor={rowIdx > 0}>{prefix}{line}</Text>
          )
        }
        // cursor 라인 — terminalCursorFocus 로 포크 렌더러에 IME 커서 위치 전달
        // terminalCursorPosition: prefix(2자) + cursor.col 이 '▏' 위치(0-indexed)
        const before = line.slice(0, cursor.col)
        const after = line.slice(cursor.col)
        return (
          <Text
            key={'line-' + rowIdx}
            terminalCursorFocus={true}
            terminalCursorPosition={prefix.length + cursor.col}
          >
            <Text color='cyan'>{prefix}</Text>{before}<Text color='cyan'>{'▏'}</Text>{after}
          </Text>
        )
      })}
    </Box>
  )
}
