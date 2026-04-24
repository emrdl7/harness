// confirm 슬라이스 단위 테스트 — stickyDeny + resolve + WS 응답 연결 (CNF-03, CNF-04, CNF-05)
import {describe, it, expect, beforeEach, afterEach, vi} from 'vitest'
import {useConfirmStore, bindConfirmClient} from '../store/confirm.js'
import type {HarnessClient} from '../ws/client.js'

describe('useConfirmStore (stickyDeny + resolve)', () => {
  // mock client — send 를 spy 로 추적
  const mockClient = {send: vi.fn()} as unknown as HarnessClient

  beforeEach(() => {
    // store 초기화
    useConfirmStore.setState({
      mode: 'none',
      payload: {},
      deniedPaths: new Set<string>(),
      deniedCmds: new Set<string>(),
    })
    // mock client 주입
    bindConfirmClient(mockClient)
    vi.clearAllMocks()
  })

  afterEach(() => {
    // 테스트 격리 — client 해제
    bindConfirmClient(null)
    useConfirmStore.setState({
      mode: 'none',
      payload: {},
      deniedPaths: new Set<string>(),
      deniedCmds: new Set<string>(),
    })
  })

  it('Test 1: 초기 deniedPaths/deniedCmds 는 비어있는 Set', () => {
    const {deniedPaths, deniedCmds} = useConfirmStore.getState()
    expect(deniedPaths.size).toBe(0)
    expect(deniedCmds.size).toBe(0)
  })

  it('Test 2: addDenied("path", "/etc/passwd") → isDenied("path", "/etc/passwd")===true', () => {
    useConfirmStore.getState().addDenied('path', '/etc/passwd')
    expect(useConfirmStore.getState().isDenied('path', '/etc/passwd')).toBe(true)
  })

  it('Test 3: addDenied("cmd", "rm -rf /") → isDenied("cmd") true, 다른 cmd 는 false', () => {
    useConfirmStore.getState().addDenied('cmd', 'rm -rf /')
    expect(useConfirmStore.getState().isDenied('cmd', 'rm -rf /')).toBe(true)
    expect(useConfirmStore.getState().isDenied('cmd', 'rm -rf /other')).toBe(false)
  })

  it('Test 4: clearDenied() → deniedPaths, deniedCmds 모두 비워짐', () => {
    useConfirmStore.getState().addDenied('path', '/foo')
    useConfirmStore.getState().addDenied('cmd', 'rm')
    useConfirmStore.getState().clearDenied()
    const {deniedPaths, deniedCmds} = useConfirmStore.getState()
    expect(deniedPaths.size).toBe(0)
    expect(deniedCmds.size).toBe(0)
  })

  it('Test 5: resolve(true) + mode="confirm_write" → client.send({type:"confirm_write_response", accept:true}), mode="none"', () => {
    useConfirmStore.setState({mode: 'confirm_write', payload: {path: '/tmp/file.txt'}})
    useConfirmStore.getState().resolve(true)
    expect(mockClient.send).toHaveBeenCalledWith({type: 'confirm_write_response', accept: true})
    expect(useConfirmStore.getState().mode).toBe('none')
  })

  it('Test 6: resolve(false) + mode="confirm_write" payload.path="/foo" → deniedPaths에 "/foo" 추가 (sticky deny)', () => {
    useConfirmStore.setState({mode: 'confirm_write', payload: {path: '/foo'}})
    useConfirmStore.getState().resolve(false)
    expect(mockClient.send).toHaveBeenCalledWith({type: 'confirm_write_response', accept: false})
    expect(useConfirmStore.getState().isDenied('path', '/foo')).toBe(true)
    expect(useConfirmStore.getState().mode).toBe('none')
  })

  it('Test 7: resolve(false) + mode="confirm_bash" payload.command="rm -rf /" → deniedCmds에 명령 추가', () => {
    useConfirmStore.setState({mode: 'confirm_bash', payload: {command: 'rm -rf /'}})
    useConfirmStore.getState().resolve(false)
    expect(mockClient.send).toHaveBeenCalledWith({type: 'confirm_bash_response', accept: false})
    expect(useConfirmStore.getState().isDenied('cmd', 'rm -rf /')).toBe(true)
    expect(useConfirmStore.getState().mode).toBe('none')
  })

  it('Test 8: resolve(true) + mode="cplan_confirm" → client.send 호출 없이 mode="none" (서버 응답 타입 미존재)', () => {
    useConfirmStore.setState({mode: 'cplan_confirm', payload: {task: 'some task'}})
    useConfirmStore.getState().resolve(true)
    // cplan_confirm 은 서버 응답 타입이 없으므로 send 호출 안 함
    expect(mockClient.send).not.toHaveBeenCalled()
    expect(useConfirmStore.getState().mode).toBe('none')
  })
})
