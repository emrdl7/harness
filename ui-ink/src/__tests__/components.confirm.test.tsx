// ConfirmDialog 통합 테스트 — CNF-01/02/04/05 동작 검증
import React from 'react'
import {describe, it, expect, beforeEach} from 'vitest'
import {render} from 'ink-testing-library'
import {ConfirmDialog, classifyCommand} from '../components/ConfirmDialog.js'
import {useConfirmStore} from '../store/confirm.js'
import {useRoomStore} from '../store/room.js'

// 각 테스트 간 store 초기화
beforeEach(() => {
  useConfirmStore.getState().clearConfirm()
  useConfirmStore.getState().clearDenied()
  useRoomStore.setState({activeIsSelf: true})
})

describe('classifyCommand (CNF-02)', () => {
  it('평문 명령은 safe 로 판정한다', () => {
    expect(classifyCommand('ls -la')).toBe('safe')
    expect(classifyCommand('echo hello')).toBe('safe')
  })
  it('rm / sudo / chmod 는 dangerous', () => {
    expect(classifyCommand('rm -rf /')).toBe('dangerous')
    expect(classifyCommand('sudo apt update')).toBe('dangerous')
    expect(classifyCommand('chmod 777 file')).toBe('dangerous')
  })
  it('쉘 메타 문자 및 command substitution 은 dangerous', () => {
    expect(classifyCommand('ls | grep foo')).toBe('dangerous')
    expect(classifyCommand('echo $(whoami)')).toBe('dangerous')
    expect(classifyCommand('cat a > b')).toBe('dangerous')
  })
})

describe('ConfirmDialog rendering', () => {
  it('confirm_write 모드: 경로와 y/n/d/Esc 힌트를 표시한다 (CNF-01)', () => {
    // setConfirm 은 2-인자 (mode, payload) — resolve 는 store 필드
    useConfirmStore.getState().setConfirm(
      'confirm_write',
      {path: '/tmp/foo.txt'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('/tmp/foo.txt')
    expect(frame).toContain('y')
    expect(frame).toContain('n')
    expect(frame).toContain('d')
    expect(frame).toContain('Esc')
  })

  it('confirm_bash 모드: 커맨드와 위험 라벨을 표시한다 (CNF-02)', () => {
    useConfirmStore.getState().setConfirm(
      'confirm_bash',
      {command: 'rm -rf /'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('rm -rf /')
    expect(frame).toContain('[위험]')
  })

  it('confirm_bash 안전 커맨드: [일반] 라벨', () => {
    useConfirmStore.getState().setConfirm(
      'confirm_bash',
      {command: 'ls -la'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    expect(lastFrame() ?? '').toContain('[일반]')
  })

  it('cplan_confirm 모드: task 와 힌트를 표시한다 (CNF-05)', () => {
    useConfirmStore.getState().setConfirm(
      'cplan_confirm',
      {task: 'refactor auth flow'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('refactor auth flow')
    expect(frame).toContain('y')
    expect(frame).toContain('n')
  })

  it('activeIsSelf=false: read-only 뷰를 렌더한다 (CNF-04)', () => {
    useRoomStore.setState({activeIsSelf: false})
    useConfirmStore.getState().setConfirm(
      'confirm_write',
      {path: '/tmp/foo.txt'},
    )
    const {lastFrame} = render(<ConfirmDialog />)
    const frame = lastFrame() ?? ''
    expect(frame).toContain('응답 불가')
    expect(frame).toContain('/tmp/foo.txt')
    // y/n 허용 힌트는 나오면 안 됨 (read-only)
    expect(frame).not.toMatch(/y\s.*허용/)
  })

  it('mode=none 일 때 null 을 반환한다', () => {
    useConfirmStore.getState().clearConfirm()
    const {lastFrame} = render(<ConfirmDialog />)
    expect((lastFrame() ?? '').trim()).toBe('')
  })
})
