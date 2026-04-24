// MultilineInput / SlashPopup / InputArea 단위·통합 테스트
// ink-testing-library 의 stdin.write 는 useInput 콜백을 트리거
// usePaste 는 별도 bracketed paste 이벤트 채널 — stdin.write 로는 직접 트리거 불가
// 따라서 paste 관련 테스트는 store 상태 직접 조작으로 검증
import React from 'react'
import {describe, it, expect, beforeEach, vi} from 'vitest'
import {render} from 'ink-testing-library'
import {MultilineInput} from '../components/MultilineInput.js'
import {SlashPopup} from '../components/SlashPopup.js'
import {InputArea} from '../components/InputArea.js'
import {useInputStore} from '../store/input.js'

// node:fs mock — input store 가 history.txt 파일에 접근함
vi.mock('node:fs', () => ({
  readFileSync: vi.fn(),
  appendFileSync: vi.fn(),
  mkdirSync: vi.fn(),
  existsSync: vi.fn(() => false),
}))

// 키 escape sequence 상수
const CR = '\r'           // Enter
const CTRL_U = '\x15'    // Ctrl+U
const ESC = '\x1b'       // Escape
const TAB = '\t'          // Tab

// React 상태 업데이트 + useEffect 안정화를 위한 지연
const flush = async () => {
  await new Promise((r) => setTimeout(r, 20))
}

describe('MultilineInput', () => {
  beforeEach(() => {
    // 각 테스트 전 store 초기화
    useInputStore.setState({
      buffer: '',
      history: [],
      historyIndex: -1,
      slashOpen: false,
    })
  })

  it('문자 입력 + Enter → onSubmit(text) 1회 호출', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('hello')
    await flush()
    stdin.write(CR)
    await flush()
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith('hello')
    unmount()
  })

  it('Ctrl+U → 현재 라인 전체 삭제 (buffer="")', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('abc')
    await flush()
    expect(useInputStore.getState().buffer).toBe('abc')
    stdin.write(CTRL_U)
    await flush()
    expect(useInputStore.getState().buffer).toBe('')
    expect(onSubmit).not.toHaveBeenCalled()
    unmount()
  })

  it('멀티라인 paste — setBuffer 로 직접 삽입 시 buffer 에 \\n 포함, onSubmit 미호출', async () => {
    // usePaste 는 stdin.write 로 직접 트리거 불가(별도 채널)
    // store 직접 조작으로 paste 후 상태 검증
    const onSubmit = vi.fn()
    const {unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    // paste 로 buffer 에 멀티라인 삽입 시뮬레이션
    useInputStore.getState().setBuffer('line1\nline2')
    await flush()
    expect(useInputStore.getState().buffer).toBe('line1\nline2')
    expect(onSubmit).not.toHaveBeenCalled()
    unmount()
  })

  it('↑ 화살표 → historyUp 위임 (store buffer 가 최근 history 로 교체)', async () => {
    useInputStore.setState({buffer: '', history: ['old1', 'old2'], historyIndex: -1})
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    // ANSI CSI Up arrow — Ink 가 key.upArrow=true 로 파싱
    stdin.write('\x1b[A')
    await flush()
    expect(useInputStore.getState().buffer).toBe('old2')
    unmount()
  })

  it('빈 buffer 에서 Enter → onSubmit 미호출 (T-02C-04 빈 입력 차단)', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write(CR)
    await flush()
    expect(onSubmit).not.toHaveBeenCalled()
    unmount()
  })

  it('Ctrl+J 는 개행만 하고 onSubmit 호출 안 함 (INPT-02)', async () => {
    // Ctrl+J = '\x0a' — Ink useInput 에서 key.ctrl && input==='j' 로 파싱됨
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('hello')
    await flush()
    stdin.write('\x0a')  // Ctrl+J
    await flush()
    expect(onSubmit).not.toHaveBeenCalled()
    // buffer 에 줄바꿈이 삽입되었음을 store 로 확인
    expect(useInputStore.getState().buffer).toBe('hello\n')
    unmount()
  })

  it('Ctrl+K 뒤 삭제 — 텍스트 입력 후 Ctrl+K → 커서 이후 텍스트 제거 (INPT-04)', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('hello')
    await flush()
    // Ctrl+A 로 줄 처음으로 이동
    stdin.write('\x01')
    await flush()
    // Ctrl+K — 커서 이후(전체) 삭제
    stdin.write('\x0b')
    await flush()
    expect(useInputStore.getState().buffer).toBe('')
    expect(onSubmit).not.toHaveBeenCalled()
    unmount()
  })

  it('Ctrl+W 단어 삭제 — 단어 뒤에서 Ctrl+W → 단어 제거 (INPT-04)', async () => {
    const onSubmit = vi.fn()
    const {stdin, unmount} = render(<MultilineInput onSubmit={onSubmit} />)
    stdin.write('hello world')
    await flush()
    // Ctrl+W — 커서 직전 단어('world') 삭제
    stdin.write('\x17')
    await flush()
    // 'hello ' 또는 'hello' 가 남아야 함 (deleteWordBefore 구현에 따라)
    const buf = useInputStore.getState().buffer
    expect(buf).toContain('hello')
    expect(buf).not.toContain('world')
    expect(onSubmit).not.toHaveBeenCalled()
    unmount()
  })

  it('Ctrl+A 줄 처음 이동 후 문자 삽입 — 크래시 없음 (INPT-04)', async () => {
    const {stdin, lastFrame, unmount} = render(<MultilineInput onSubmit={vi.fn()} />)
    stdin.write('hello')
    await flush()
    stdin.write('\x01')  // Ctrl+A — 줄 처음으로 이동
    await flush()
    // 추가 입력이 처음에 삽입됨 — 크래시 없어야 함
    stdin.write('X')
    await flush()
    expect(() => lastFrame()).not.toThrow()
    // 'X'가 'hello' 앞에 삽입됨
    expect(useInputStore.getState().buffer).toBe('Xhello')
    unmount()
  })

  it('빈 히스토리에서 ↑ 키 입력 시 크래시 없음 (INPT-03)', async () => {
    // 히스토리가 비어 있을 때 ↑ 를 눌러도 크래시가 발생하지 않아야 함
    useInputStore.setState({buffer: '', history: [], historyIndex: -1, slashOpen: false})
    const {stdin, lastFrame, unmount} = render(<MultilineInput onSubmit={vi.fn()} />)
    stdin.write('\x1b[A')  // ↑ 화살표
    await flush()
    expect(() => lastFrame()).not.toThrow()
    unmount()
  })
})

describe('SlashPopup', () => {
  it('query="" → 전체 catalog 중 /help 를 lastFrame 에 포함', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    const {lastFrame, unmount} = render(
      <SlashPopup query='' onSelect={onSelect} onClose={onClose} />
    )
    await flush()
    expect(lastFrame()).toContain('/help')
    unmount()
  })

  it('Esc → onClose 호출', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    const {stdin, unmount} = render(
      <SlashPopup query='' onSelect={onSelect} onClose={onClose} />
    )
    await flush()
    stdin.write(ESC)
    await flush()
    expect(onClose).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('Tab → highlighted command 으로 onSelect 호출 (leading slash 포함)', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    const {stdin, unmount} = render(
      <SlashPopup query='' onSelect={onSelect} onClose={onClose} />
    )
    await flush()
    stdin.write(TAB)
    await flush()
    expect(onSelect).toHaveBeenCalledTimes(1)
    // leading slash 포함 — '/help', '/clear' 등
    expect(onSelect.mock.calls[0]?.[0]).toMatch(/^\//)
    unmount()
  })

  it('query="he" → /help 포함 여부 확인 (filterSlash 위임)', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    const {lastFrame, unmount} = render(
      <SlashPopup query='/he' onSelect={onSelect} onClose={onClose} />
    )
    await flush()
    const frame = lastFrame() ?? ''
    expect(frame).toContain('/help')
    unmount()
  })

  it('후보 0개 → "일치하는 명령이 없습니다" 렌더', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    // 존재하지 않는 쿼리로 후보 0개 유도
    const {lastFrame, unmount} = render(
      <SlashPopup query='/zzzznotexist' onSelect={onSelect} onClose={onClose} />
    )
    await flush()
    expect(lastFrame()).toContain('일치하는 명령이 없습니다')
    unmount()
  })
})

describe('InputArea', () => {
  beforeEach(() => {
    useInputStore.setState({
      buffer: '',
      history: [],
      historyIndex: -1,
      slashOpen: false,
    })
  })

  it('buffer="/" → slashOpen=true 로 자동 전환', async () => {
    const onSubmit = vi.fn()
    const {unmount} = render(<InputArea onSubmit={onSubmit} />)
    useInputStore.getState().setBuffer('/')
    await flush()
    expect(useInputStore.getState().slashOpen).toBe(true)
    unmount()
  })

  it('buffer="hello" → slashOpen=false 유지', async () => {
    const onSubmit = vi.fn()
    const {unmount} = render(<InputArea onSubmit={onSubmit} />)
    useInputStore.getState().setBuffer('hello')
    await flush()
    expect(useInputStore.getState().slashOpen).toBe(false)
    unmount()
  })

  it('buffer="" → slashOpen=false 유지', async () => {
    const onSubmit = vi.fn()
    const {unmount} = render(<InputArea onSubmit={onSubmit} />)
    useInputStore.getState().setBuffer('')
    await flush()
    expect(useInputStore.getState().slashOpen).toBe(false)
    unmount()
  })
})
