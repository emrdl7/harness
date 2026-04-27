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
      allowedPaths: new Set<string>(),
      allowedCmds: new Set<string>(),
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
      allowedPaths: new Set<string>(),
      allowedCmds: new Set<string>(),
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

  // B1: sticky-allow — 'a 항상 허용' 으로 등록된 path/cmd 는 다음부터 자동 통과
  it('Test 9 (B1): 초기 allowedPaths/allowedCmds 는 비어있고 deny 와 독립', () => {
    const s = useConfirmStore.getState()
    expect(s.allowedPaths.size).toBe(0)
    expect(s.allowedCmds.size).toBe(0)
    s.addDenied('path', '/foo')
    expect(s.isAllowed('path', '/foo')).toBe(false)  // deny 와 별개 Set
  })

  it('Test 10 (B1): addAllowed("path", "/foo") → isAllowed true, 다른 path 는 false', () => {
    useConfirmStore.getState().addAllowed('path', '/foo')
    expect(useConfirmStore.getState().isAllowed('path', '/foo')).toBe(true)
    expect(useConfirmStore.getState().isAllowed('path', '/bar')).toBe(false)
  })

  it('Test 11 (B1): addAllowed("cmd", "ls") → cmd 격리 — path 와 cross 안 됨', () => {
    useConfirmStore.getState().addAllowed('cmd', 'ls')
    expect(useConfirmStore.getState().isAllowed('cmd', 'ls')).toBe(true)
    expect(useConfirmStore.getState().isAllowed('path', 'ls')).toBe(false)
  })

  it('Test 12 (B1): clearAllowed() → 모두 비워짐 (clearDenied 와 독립)', () => {
    const s = useConfirmStore.getState()
    s.addAllowed('path', '/p')
    s.addAllowed('cmd', 'c')
    s.addDenied('path', '/d')
    s.clearAllowed()
    const after = useConfirmStore.getState()
    expect(after.allowedPaths.size).toBe(0)
    expect(after.allowedCmds.size).toBe(0)
    expect(after.isDenied('path', '/d')).toBe(true)  // deny 는 보존
  })
})
