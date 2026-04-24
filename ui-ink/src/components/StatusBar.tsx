// StatusBar — path / model / mode / turn / ctx% / room 6 세그먼트 (STAT-01, STAT-02)
// 좁은 폭에서는 우선순위 순으로 세그먼트 드롭 (room → ctx% → turn → mode → model → path)
import React from 'react'
import {Box, Text} from 'ink'
import Spinner from 'ink-spinner'
import {useShallow} from 'zustand/react/shallow'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {theme} from '../theme.js'

interface StatusBarProps {
  columns: number
}

interface Segment {
  key: string
  render: () => React.ReactElement
  textLen: number     // 대략적인 가시 길이 (ANSI/색 제외)
  priority: number    // 낮을수록 먼저 드롭
}

// path 축약 — 홈은 ~, 절대경로는 마지막 2 세그먼트만
function shortenPath(p: string): string {
  if (!p) return ''
  const home = process.env['HOME']
  let out = p
  if (home && p.startsWith(home)) out = '~' + p.slice(home.length)
  const parts = out.split('/').filter(Boolean)
  if (parts.length > 2) {
    return (out.startsWith('/') || out.startsWith('~')) && !out.startsWith('~/') && !out.startsWith('~')
      ? '/' + '…/' + parts.slice(-2).join('/')
      : '…/' + parts.slice(-2).join('/')
  }
  return out
}

// D-01 최하단 — busy spinner 좌측, 세그먼트들 우측 흐름
export const StatusBar: React.FC<StatusBarProps> = ({columns}) => {
  const {connected, busy, workingDir, model, mode, turns, ctxTokens} = useStatusStore(
    useShallow((s) => ({
      connected: s.connected,
      busy: s.busy,
      workingDir: s.workingDir,
      model: s.model,
      mode: s.mode,
      turns: s.turns,
      ctxTokens: s.ctxTokens,
    })),
  )
  const roomName = useRoomStore(useShallow((s) => s.roomName))

  // ctx% = ctxTokens / 32768 (임시 기준 — Wave 2 에서 모델별 정밀화)
  const CTX_CAP = 32768
  const ctxPct = typeof ctxTokens === 'number'
    ? Math.min(100, Math.round((ctxTokens / CTX_CAP) * 100))
    : undefined

  // 세그먼트 정의 — priority 낮은 것부터 좁은 폭에서 드롭됨
  const segments: Segment[] = []

  // path — priority 최고 (절대 드롭 안 됨)
  const pathText = shortenPath(workingDir ?? '')
  if (pathText) {
    segments.push({
      key: 'path',
      render: () => <Text color={theme.muted}>{pathText}</Text>,
      textLen: pathText.length,
      priority: 100,
    })
  }

  if (model) {
    segments.push({
      key: 'model',
      render: () => <Text color={theme.muted}>{model}</Text>,
      textLen: model.length,
      priority: 80,
    })
  }

  if (mode) {
    const modeColor = (theme.mode as Record<string, string>)[mode] ?? theme.mode.default
    segments.push({
      key: 'mode',
      render: () => <Text color={modeColor}>{mode}</Text>,
      textLen: mode.length,
      priority: 60,
    })
  }

  if (typeof turns === 'number') {
    const turnText = `turn ${turns}`
    segments.push({
      key: 'turn',
      render: () => <Text color={theme.muted}>{turnText}</Text>,
      textLen: turnText.length,
      priority: 50,
    })
  }

  if (ctxPct !== undefined) {
    const ctxText = `ctx ${ctxPct}%`
    segments.push({
      key: 'ctx',
      render: () => <Text color={theme.muted}>{ctxText}</Text>,
      textLen: ctxText.length,
      priority: 40,
    })
  }

  if (roomName) {
    const roomText = `#${roomName}`
    segments.push({
      key: 'room',
      render: () => <Text color={theme.muted}>{roomText}</Text>,
      textLen: roomText.length,
      priority: 30,
    })
  }

  // connected 상태 — 고정 표시
  const connText = connected ? '● connected' : '○ disconnected'
  const connColor = connected ? theme.status.connected : theme.status.disconnected

  // 좁은 폭 처리 — 총 길이 + separator(' | ') 계산
  const SEP = ' | '
  const spinnerLen = 2 // spinner 문자 + 공백
  const fixedLen = connText.length + spinnerLen
  const budget = Math.max(0, columns - fixedLen)

  // priority 높은 순으로 포함 여부 결정
  const sorted = [...segments].sort((a, b) => b.priority - a.priority)
  const kept: Segment[] = []
  let used = 0
  for (const seg of sorted) {
    const cost = seg.textLen + (kept.length > 0 ? SEP.length : 0)
    if (used + cost <= budget) {
      kept.push(seg)
      used += cost
    }
  }
  // 원래 priority 순서(path → ... → room)로 다시 정렬
  kept.sort((a, b) => b.priority - a.priority)

  return (
    <Box>
      {busy
        ? <Text color={theme.status.busy}><Spinner type='dots'/>{' '}</Text>
        : <Text>{'  '}</Text>}
      <Text color={connColor}>{connText}</Text>
      {kept.map((seg) => (
        <React.Fragment key={seg.key}>
          <Text color={theme.muted}>{SEP}</Text>
          {seg.render()}
        </React.Fragment>
      ))}
    </Box>
  )
}
