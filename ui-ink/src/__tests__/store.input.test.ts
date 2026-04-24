// input 슬라이스 단위 테스트 — history + slashOpen + 파일 persistence (INPT-03)
import {describe, it, expect, beforeEach, vi, afterEach} from 'vitest'
import {useInputStore} from '../store/input.js'

// node:fs 를 mock 하여 파일 시스템 접근 테스트
vi.mock('node:fs', () => ({
  readFileSync: vi.fn(),
  appendFileSync: vi.fn(),
  mkdirSync: vi.fn(),
  existsSync: vi.fn(),
}))

// mock 임포트
import * as fs from 'node:fs'

describe('useInputStore (history + slashOpen + persistence)', () => {
  beforeEach(() => {
    // store 초기화
    useInputStore.setState({
      buffer: '',
      history: [],
      historyIndex: -1,
      slashOpen: false,
    })
    // mock 리셋
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('Test 1: 초기 상태 — buffer="", history=[], historyIndex=-1, slashOpen=false', () => {
    const {buffer, history, historyIndex, slashOpen} = useInputStore.getState()
    expect(buffer).toBe('')
    expect(history).toEqual([])
    expect(historyIndex).toBe(-1)
    expect(slashOpen).toBe(false)
  })

  it('Test 2: pushHistory("hello") → history=["hello"], historyIndex=-1 (커서 리셋)', () => {
    useInputStore.getState().pushHistory('hello')
    const {history, historyIndex} = useInputStore.getState()
    expect(history).toEqual(['hello'])
    expect(historyIndex).toBe(-1)
  })

  it('Test 3: pushHistory 동일 문자열 연속 중복 저장 안 함', () => {
    useInputStore.getState().pushHistory('같은 명령')
    useInputStore.getState().pushHistory('같은 명령')
    const {history} = useInputStore.getState()
    expect(history).toHaveLength(1)
    expect(history[0]).toBe('같은 명령')
  })

  it('Test 4: history 최대 500개 cap — 501번째 push 시 가장 오래된 것 제거', () => {
    // 500개 채우기
    for (let i = 0; i < 500; i++) {
      useInputStore.getState().pushHistory(`cmd-${i}`)
    }
    expect(useInputStore.getState().history).toHaveLength(500)
    // 501번째 — 가장 오래된 "cmd-0" 제거, 최신이 마지막에
    useInputStore.getState().pushHistory('cmd-500')
    const {history} = useInputStore.getState()
    expect(history).toHaveLength(500)
    expect(history[0]).toBe('cmd-1')
    expect(history[499]).toBe('cmd-500')
  })

  it('Test 5: historyUp() — index=0, buffer가 history 마지막 항목으로 교체', () => {
    useInputStore.getState().pushHistory('첫 번째')
    useInputStore.getState().pushHistory('두 번째')
    useInputStore.getState().pushHistory('세 번째')
    useInputStore.getState().historyUp()
    const {historyIndex, buffer} = useInputStore.getState()
    expect(historyIndex).toBe(0)
    expect(buffer).toBe('세 번째')
  })

  it('Test 6: historyUp 추가 호출 — index=1, buffer가 history[length-2]로 교체', () => {
    useInputStore.getState().pushHistory('첫 번째')
    useInputStore.getState().pushHistory('두 번째')
    useInputStore.getState().pushHistory('세 번째')
    useInputStore.getState().historyUp()
    useInputStore.getState().historyUp()
    const {historyIndex, buffer} = useInputStore.getState()
    expect(historyIndex).toBe(1)
    expect(buffer).toBe('두 번째')
  })

  it('Test 7: historyDown() — index 감소, -1에 도달하면 buffer 빈 문자열', () => {
    useInputStore.getState().pushHistory('항목 A')
    useInputStore.getState().pushHistory('항목 B')
    useInputStore.getState().historyUp()
    useInputStore.getState().historyUp()
    // index=1, buffer='항목 A'
    useInputStore.getState().historyDown()
    expect(useInputStore.getState().historyIndex).toBe(0)
    expect(useInputStore.getState().buffer).toBe('항목 B')
    useInputStore.getState().historyDown()
    expect(useInputStore.getState().historyIndex).toBe(-1)
    expect(useInputStore.getState().buffer).toBe('')
  })

  it('Test 8: setSlashOpen(true) → slashOpen=true', () => {
    useInputStore.getState().setSlashOpen(true)
    expect(useInputStore.getState().slashOpen).toBe(true)
  })

  it('Test 9: loadHistory() — 파일 없으면 [] 반환', async () => {
    const {existsSync} = fs as unknown as {existsSync: ReturnType<typeof vi.fn>}
    existsSync.mockReturnValue(false)
    const {loadHistory} = await import('../store/input.js')
    const result = loadHistory()
    expect(result).toEqual([])
  })

  it('Test 10: loadHistory() — 파일에 "a\\nb\\nc\\n" 있으면 ["a","b","c"] 반환', async () => {
    const {existsSync, readFileSync} = fs as unknown as {
      existsSync: ReturnType<typeof vi.fn>
      readFileSync: ReturnType<typeof vi.fn>
    }
    existsSync.mockReturnValue(true)
    readFileSync.mockReturnValue('a\nb\nc\n')
    const {loadHistory} = await import('../store/input.js')
    const result = loadHistory()
    // 가장 오래된 것부터 (oldest first), 최대 500개
    expect(result).toEqual(['a', 'b', 'c'])
  })

  it('Test 11: appendHistory("x") — appendFileSync 가 "x\\n" 으로 호출됨', async () => {
    const {existsSync, appendFileSync: appendFileSyncMock} = fs as unknown as {
      existsSync: ReturnType<typeof vi.fn>
      appendFileSync: ReturnType<typeof vi.fn>
    }
    existsSync.mockReturnValue(true) // 디렉터리 존재
    const {appendHistory, HISTORY_PATH} = await import('../store/input.js')
    appendHistory('x')
    expect(appendFileSyncMock).toHaveBeenCalledWith(HISTORY_PATH, 'x\n', 'utf8')
  })

  it('Test 12: hydrate() — loadHistory 결과를 store.history 에 로드', async () => {
    const {existsSync, readFileSync} = fs as unknown as {
      existsSync: ReturnType<typeof vi.fn>
      readFileSync: ReturnType<typeof vi.fn>
    }
    existsSync.mockReturnValue(true)
    readFileSync.mockReturnValue('cmd1\ncmd2\ncmd3\n')
    const {useInputStore: freshStore} = await import('../store/input.js')
    freshStore.setState({history: [], historyIndex: -1})
    freshStore.getState().hydrate()
    const {history} = freshStore.getState()
    expect(history).toEqual(['cmd1', 'cmd2', 'cmd3'])
  })

  it('Test 13: pushHistory() 호출 후 appendFileSync spy 가 호출됨 (파일 즉시 반영)', async () => {
    const {existsSync, appendFileSync: appendFileSyncMock} = fs as unknown as {
      existsSync: ReturnType<typeof vi.fn>
      appendFileSync: ReturnType<typeof vi.fn>
    }
    existsSync.mockReturnValue(true)
    useInputStore.getState().pushHistory('파일에 저장될 명령')
    expect(appendFileSyncMock).toHaveBeenCalledTimes(1)
  })
})
