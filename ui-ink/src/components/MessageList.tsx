// MessageList — completedMessages 는 <Static>, activeMessage 는 일반 Box (RND-01, RND-02)
// <Static>: append-only 로 이미 렌더된 프레임을 재렌더하지 않음 → scrollback 안정
// active: in-place 업데이트로 매 토큰마다 리렌더 가능
// resize 대응: 창 크기 변경 시 화면 클리어 + Static key 갱신으로 전체 remount (좀비 제거)
import React, {useEffect, useRef, useState} from 'react'
import {Box, Static, useStdout} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useMessagesStore} from '../store/messages.js'
import {Message} from './Message.js'

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
    let timer: ReturnType<typeof setTimeout> | null = null
    const handleResize = () => {
      if (timer) clearTimeout(timer)
      // 100ms debounce — tmux 탭 전환 시 순간 SIGWINCH 무시
      timer = setTimeout(() => {
        const c = stdout.columns ?? 80
        if (c === columnsRef.current) return  // 실제 크기 변경 없으면 무시
        columnsRef.current = c
        // 화면 클리어 — Static 재마운트 전 구 줄바꿈 잔재 제거 (좀비 방지)
        // eslint-disable-next-line no-restricted-syntax
        process.stdout.write('\x1b[2J\x1b[H')
        setColumns(c)
      }, 100)
    }
    stdout.on('resize', handleResize)
    return () => {
      stdout.off('resize', handleResize)
      if (timer) clearTimeout(timer)
    }
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
