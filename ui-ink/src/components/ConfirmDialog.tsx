// ConfirmDialog — CNF-01/02/04/05 구현
// - confirm_write: 경로 + DiffPreview placeholder + y/n/d/Esc 힌트
// - confirm_bash: 커맨드 + 위험도 라벨 + y/n/Esc 힌트
// - cplan_confirm: task 문자열 + y/n/Esc 힌트 (CNF-05 — confirm_write 와 동일 프레임)
// - activeIsSelf=false: ConfirmReadOnlyView (관전자는 의사결정 불가, CNF-04)
// - sticky-deny: isDenied hit → 즉시 resolve(false) (Plan A store 사용)
import React, {useEffect, useState} from 'react'
import {Box, Text, useInput} from 'ink'
import {useShallow} from 'zustand/react/shallow'
import {useConfirmStore} from '../store/confirm.js'
import type {ConfirmMode} from '../store/confirm.js'
import {useRoomStore} from '../store/room.js'
import {DiffPreview} from './DiffPreview.js'

// CNF-02: 서버가 danger_level 을 보내지 않으므로 클라이언트에서 판정
const DANGEROUS_PATTERNS: RegExp[] = [
  /\brm\b/,
  /\bsudo\b/,
  /\bchmod\b/,
  /\bchown\b/,
  /[|&;<>`]/,     // 쉘 메타문자 / 파이프 / 리디렉션
  /\$\(/,         // command substitution
  /\bdd\b/,
  /\bmkfs\b/,
  /\beval\b/,
]

export function classifyCommand(cmd: string): 'safe' | 'dangerous' {
  return DANGEROUS_PATTERNS.some((p) => p.test(cmd)) ? 'dangerous' : 'safe'
}

export function ConfirmDialog(): React.ReactElement | null {
  // useShallow 로 필요한 필드만 subscribe (CLAUDE.md 금지 사항: 전체 store selector 금지)
  const {mode, payload, resolve, addDenied, isDenied, addAllowed, isAllowed, clearConfirm} = useConfirmStore(
    useShallow((s) => ({
      mode: s.mode,
      payload: s.payload,
      resolve: s.resolve,
      addDenied: s.addDenied,
      isDenied: s.isDenied,
      addAllowed: s.addAllowed,
      isAllowed: s.isAllowed,
      clearConfirm: s.clearConfirm,
    }))
  )
  const activeIsSelf = useRoomStore((s) => s.activeIsSelf)
  const [showDiff, setShowDiff] = useState(false)

  // CNF-03 sticky 자동 판정: mode 가 활성화되는 순간 1회 체크
  // B1 sticky-allow 가 sticky-deny 보다 우선 (사용자가 'a' 로 명시 허용한 게 우선)
  useEffect(() => {
    if (mode === 'none') return
    const key =
      mode === 'confirm_write' ? (payload['path'] as string | undefined) :
      mode === 'confirm_bash'  ? (payload['command'] as string | undefined) :
      undefined
    if (!key) return
    const kind: 'path' | 'cmd' = mode === 'confirm_write' ? 'path' : 'cmd'
    if (isAllowed(kind, key)) {
      resolve(true)
      return
    }
    if (isDenied(kind, key)) {
      resolve(false)
    }
  }, [mode, payload, resolve, isAllowed, isDenied])

  // mode 가 없으면 렌더하지 않는다 (App.tsx 에서 이미 분기하지만 이중 가드)
  if (mode === 'none') return null

  // CNF-04: 관전자는 read-only — useInput 이전에 분기해야 관전자가 키를 가로채지 않음
  if (!activeIsSelf) {
    return <ConfirmReadOnlyView mode={mode as Exclude<ConfirmMode, 'none'>} payload={payload} />
  }

  const handleAccept = () => {
    resolve(true)
    setShowDiff(false)
  }
  // B1: 항상 허용 — 동일 path/cmd 는 다음부터 자동 통과
  const handleAlwaysAllow = () => {
    const key =
      mode === 'confirm_write' ? (payload['path'] as string | undefined) :
      mode === 'confirm_bash'  ? (payload['command'] as string | undefined) :
      undefined
    if (key) {
      addAllowed(mode === 'confirm_write' ? 'path' : 'cmd', key)
    }
    resolve(true)
    setShowDiff(false)
  }
  const handleDeny = () => {
    // resolve 내부에서 addDenied 처리하지만, confirm_write/bash 는 여기서도 명시적 등록
    // sticky-deny: n/Esc 시 등록 (store.resolve 도 처리하지만 double-guard)
    const key =
      mode === 'confirm_write' ? (payload['path'] as string | undefined) :
      mode === 'confirm_bash'  ? (payload['command'] as string | undefined) :
      undefined
    if (key) {
      addDenied(mode === 'confirm_write' ? 'path' : 'cmd', key)
    }
    resolve(false)
    setShowDiff(false)
  }

  // useInput 은 관전자 분기 뒤에 위치 — 관전자는 키 입력을 가로채지 않음
  // 주의: 관전자 분기(!activeIsSelf) 이후 useInput 호출 — CNF-04 보안 요구사항으로 의도된 위치
  useInput((ch, key) => {
    if (ch === 'y' || ch === 'Y') { handleAccept(); return }
    if (ch === 'a' || ch === 'A') { handleAlwaysAllow(); return }  // B1
    if (ch === 'n' || ch === 'N') { handleDeny(); return }
    if (key.escape) { handleDeny(); return }
    if ((ch === 'd' || ch === 'D') && mode === 'confirm_write') {
      setShowDiff((v) => !v)
    }
  })

  // CNF-01: confirm_write
  if (mode === 'confirm_write') {
    const path = (payload['path'] as string) ?? '(경로 없음)'
    const content = payload['content'] as string | undefined
    // W1: old_content가 있으면 실제 diff, 없으면 신규 파일 표시 (PEXT-02)
    const oldContent = typeof payload['oldContent'] === 'string'
      ? payload['oldContent']
      : undefined
    return (
      <Box flexDirection='column' borderStyle='round' borderColor='yellow' paddingX={1}>
        <Text color='yellow'>파일 쓰기 확인</Text>
        <Text>경로: <Text bold>{path}</Text></Text>
        {showDiff && <DiffPreview path={path} newContent={content} oldContent={oldContent} />}
        <Text dimColor>
          <Text color='green'>y</Text> 허용 · <Text color='green'>a</Text> 항상 허용 · <Text color='red'>n</Text> 거부 · <Text color='cyan'>d</Text> 미리보기 · <Text color='gray'>Esc</Text> 취소
        </Text>
      </Box>
    )
  }

  // CNF-02: confirm_bash
  if (mode === 'confirm_bash') {
    const command = (payload['command'] as string) ?? ''
    const danger = classifyCommand(command)
    return (
      <Box flexDirection='column' borderStyle='round' borderColor={danger === 'dangerous' ? 'red' : 'yellow'} paddingX={1}>
        <Text color={danger === 'dangerous' ? 'red' : 'yellow'}>
          쉘 실행 확인 {danger === 'dangerous' ? '[위험]' : '[일반]'}
        </Text>
        <Text>커맨드: <Text bold>{command}</Text></Text>
        <Text dimColor>
          <Text color='green'>y</Text> 허용 · <Text color='green'>a</Text> 항상 허용 · <Text color='red'>n</Text> 거부 · <Text color='gray'>Esc</Text> 취소
        </Text>
      </Box>
    )
  }

  // CNF-05: cplan_confirm — confirm_write 와 동일한 프레임
  if (mode === 'cplan_confirm') {
    const task = (payload['task'] as string) ?? ''
    return (
      <Box flexDirection='column' borderStyle='round' borderColor='cyan' paddingX={1}>
        <Text color='cyan'>계획 확인</Text>
        <Text>작업: <Text bold>{task}</Text></Text>
        <Text dimColor>
          <Text color='green'>y</Text> 허용 · <Text color='red'>n</Text> 거부 · <Text color='gray'>Esc</Text> 취소
        </Text>
      </Box>
    )
  }

  return null
}

// CNF-04: 관전자 전용 뷰 — 내용만 보여주고 입력은 받지 않는다
interface ReadOnlyProps {
  mode: Exclude<ConfirmMode, 'none'>
  payload: Record<string, unknown>
}

function ConfirmReadOnlyView({mode, payload}: ReadOnlyProps): React.ReactElement {
  const label =
    mode === 'confirm_write' ? '파일 쓰기 대기 중' :
    mode === 'confirm_bash'  ? '쉘 실행 대기 중' :
                               '계획 확인 대기 중'
  const detail =
    mode === 'confirm_write' ? (payload['path'] as string | undefined) ?? '' :
    mode === 'confirm_bash'  ? (payload['command'] as string | undefined) ?? '' :
                               (payload['task'] as string | undefined) ?? ''
  return (
    <Box flexDirection='column' borderStyle='round' borderColor='gray' paddingX={1}>
      <Text color='gray'>{label} (관전 중 — 응답 불가)</Text>
      <Text dimColor>{detail}</Text>
    </Box>
  )
}
