// MultilineInput — useInput 기반 자체 구현 (INPT-01: 서드파티 텍스트 입력 컴포넌트 불사용)
// INPT-01: 자체 구현
// INPT-02: Enter 제출, Shift+Enter·Ctrl+J 개행
// INPT-03: ↑↓ history (store 위임)
// INPT-04: POSIX (Ctrl+A/E/K/W/U)
// INPT-05: 멀티라인 paste — Ink 7 usePaste hook(primary, bracketed paste 감지)
//           usePaste 이벤트에서 텍스트를 cursor 위치에 insertAt 으로 삽입, submit 발생 없음
import React from 'react'
import {Box, Text, useInput, usePaste} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useInputStore} from '../store/input.js'

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
  // 커서는 삽입된 텍스트의 "끝" 으로 이동
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
  // 앞쪽 공백 스킵
  while (i > 0 && line[i - 1] === ' ') i--
  // 단어 스킵
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
  // store — buffer 는 외부 단일 소스, cursor 만 로컬 state
  const {buffer, setBuffer, clearBuffer, pushHistory, historyUp, historyDown, slashOpen} = useInputStore(
    useShallow((s) => ({
      buffer: s.buffer,
      setBuffer: s.setBuffer,
      clearBuffer: s.clearBuffer,
      pushHistory: s.pushHistory,
      historyUp: s.historyUp,
      historyDown: s.historyDown,
      slashOpen: s.slashOpen,
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

  // INPT-05 primary: Ink 7 usePaste — bracketed paste 이벤트 수신
  // paste 텍스트는 cursor 위치에 삽입되며 submit 을 발생시키지 않음
  usePaste((pastedText) => {
    if (disabled) return
    const lines = splitLines(buffer)
    const r = insertAt(lines, cursor, pastedText)
    setBuffer(joinLines(r.lines))
    setCursor(r.cursor)
  })

  useInput((input, key) => {
    if (disabled) return

    const lines = splitLines(buffer)

    // Shift+Enter 또는 Ctrl+J → 개행 삽입 (INPT-02)
    if ((key.return && key.shift) || (key.ctrl && input === 'j')) {
      const r = insertAt(lines, cursor, '\n')
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }

    // Enter (단독) → 제출
    // usePaste 가 active 이면 paste 텍스트는 useInput 에 도달하지 않으므로
    // key.return 단독 체크만으로 안전하게 submit 처리 가능
    if (key.return && !key.shift) {
      const text = joinLines(lines)
      if (text.trim() === '') {
        // 빈 입력 제출 차단 (T-02C-04 완화)
        return
      }
      pushHistory(text)
      clearBuffer()
      setCursor({row: 0, col: 0})
      onSubmit(text)
      return
    }

    // slashOpen 중에는 ↑↓·Enter 를 SelectInput 에 패스스루 (history/submit 차단)
    if (slashOpen && (key.upArrow || key.downArrow || key.return)) return

    // history ↑↓ — store 에 위임. 단, 멀티라인 buffer 면 커서 이동 우선 처리
    if (key.upArrow) {
      // 멀티라인이고 현재 row > 0 이면 라인 이동
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
      // 현재 라인 전체 삭제
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
        // 라인 머지 — 현재 라인을 이전 라인 끝에 붙임
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

    // 일반 입력 — ctrl/meta 조합이 아니고 input 이 존재
    // usePaste 가 active 이면 paste 텍스트는 여기 도달하지 않음
    if (input && !key.ctrl && !key.meta) {
      const r = insertAt(lines, cursor, input)
      setBuffer(joinLines(r.lines))
      setCursor(r.cursor)
      return
    }
  })

  // 렌더 — 각 라인마다 prefix, 현재 cursor 라인의 cursor 위치에 inverse 문자
  const lines = splitLines(buffer)

  return (
    <Box flexDirection='column'>
      {lines.map((line, rowIdx) => {
        // prefix: 첫 라인은 ❯, 이후 라인은 …
        const prefix = rowIdx === 0 ? '❯ ' : '… '
        const isCursorLine = rowIdx === cursor.row
        if (!isCursorLine) {
          return (
            // 라인은 독립 식별자가 없고 buffer 에서 derive — string rowIdx 기반 key 사용
            // CLAUDE.md 금지는 messages 등 외부 도메인 엔티티 리스트의 index key 사용임
            <Box key={'line-' + rowIdx}>
              <Text dimColor={rowIdx > 0}>{prefix}</Text>
              <Text>{line}</Text>
            </Box>
          )
        }
        // cursor 라인 — before / cursor 문자(inverse) / after 분리 렌더
        const before = line.slice(0, cursor.col)
        const at = line.slice(cursor.col, cursor.col + 1) || ' '
        const after = line.slice(cursor.col + 1)
        return (
          <Box key={'line-' + rowIdx}>
            <Text color='cyan'>{prefix}</Text>
            <Text>{before}</Text>
            <Text inverse>{at}</Text>
            <Text>{after}</Text>
          </Box>
        )
      })}
    </Box>
  )
}
