// MessageList — completedMessages 는 <Static>, activeMessage 는 일반 Box (RND-01, RND-02)
// <Static>: append-only 로 이미 렌더된 프레임을 재렌더하지 않음 → scrollback 안정
// active: in-place 업데이트로 매 토큰마다 리렌더 가능
// resize 대응: log.reset() + 화면 클리어 + Static key 갱신으로 좀비 완전 제거
import React, {useEffect, useRef, useState} from 'react'
import {Box, Static, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {Message} from './Message.js'
import {resetInkLog} from '../inkReset.js'

export const MessageList: React.FC = () => {
  const {completedMessages: completed, snapshotKey} = useMessagesStore(useShallow((s) => ({
    completedMessages: s.completedMessages,
    snapshotKey: s.snapshotKey,
  })))
  const active = useMessagesStore(useShallow((s) => s.activeMessage))
  const {stdout} = useStdout()
  const [columns, setColumns] = useState(() => stdout?.columns ?? 80)
  const columnsRef = useRef(columns)

  useEffect(() => {
    if (!stdout) return
    const handleResize = () => {
      const c = stdout.columns ?? 80
      if (c === columnsRef.current) return  // tmux 탭 전환 등 실제 변경 없으면 무시
      columnsRef.current = c
      // 1) Ink frame counter 초기화 — previousLineCount/cursorWasShown 리셋 (stdout 미출력)
      resetInkLog()
      // 2) 화면 클리어 — 구 Static 잔재(좀비) 제거 후 Static 재마운트가 전체 재출력
      // eslint-disable-next-line no-restricted-syntax
      process.stdout.write('\x1b[2J\x1b[H')
      setColumns(c)
    }
    stdout.on('resize', handleResize)
    return () => { stdout.off('resize', handleResize) }
  }, [stdout])

  return (
    <Box flexDirection='column' width={columns}>
      {/* REM-03: snapshotKey 변경 시 Static 강제 remount (snapshot 로드) */}
      {/* resize 시 columns 변경 → key 갱신 → Static remount → 새 폭으로 전체 재출력 */}
      <Static key={`${snapshotKey}-${columns}`} items={completed} style={{width: columns}}>
        {(m) => <Message key={m.id} message={m} columns={columns}/>}
      </Static>
      {active ? (
        <Box flexDirection='column' width={columns}>
          <Message message={active} columns={columns}/>
        </Box>
      ) : null}
    </Box>
  )
}
