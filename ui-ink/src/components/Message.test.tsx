// Task E-1: Message.tsx cli-highlight 코드 펜스 통합 TDD 테스트 (RND-06)
import React from 'react'
import {describe, it, expect, beforeEach, afterEach, vi} from 'vitest'
import {render} from 'ink-testing-library'
import * as cliHighlight from 'cli-highlight'

// vi.mock 으로 cli-highlight 스파이 설정 — ANSI 출력 대신 마킹된 문자열 반환
vi.mock('cli-highlight', async (importOriginal) => {
  const actual = await importOriginal<typeof cliHighlight>()
  return {
    ...actual,
    highlight: vi.fn((code: string, _opts?: unknown) => `[HIGHLIGHTED:${code}]`),
  }
})

// 모킹 이후 임포트
const {Message} = await import('./Message.js')
const {highlight} = await import('cli-highlight')
const highlightSpy = highlight as unknown as ReturnType<typeof vi.fn>

describe('Message — cli-highlight 코드 펜스 통합 (E-1)', () => {
  beforeEach(() => {
    highlightSpy.mockClear()
    highlightSpy.mockImplementation((code: string) => `[HIGHLIGHTED:${code}]`)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('Test 1: 코드 펜스(ts) — highlight() 호출 + ANSI 문자열 렌더', () => {
    // 백틱 3개로 구성된 ts 코드 펜스
    const content = '```ts\nconst x = 1\n```'
    const msg = {id: 'm1', role: 'assistant' as const, content}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''

    // highlight 가 호출되었는지 확인
    expect(highlightSpy).toHaveBeenCalledWith('const x = 1\n', expect.objectContaining({ignoreIllegals: true}))
    // ANSI(모의) 출력이 렌더됨
    expect(frame).toContain('HIGHLIGHTED')
    unmount()
  })

  it('Test 2: 언어 미지정 펜스 — lang=undefined 로 highlight 호출 후 실패 시 원본 반환', () => {
    // highlight 가 원본 반환하도록 mock
    highlightSpy.mockImplementationOnce(() => { throw new Error('언어 감지 실패') })
    const content = '```\nplain text\n```'
    const msg = {id: 'm2', role: 'assistant' as const, content}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''

    // highlight 는 lang=undefined (또는 '' 가 falsy 로 처리되어 undefined 전달)로 호출됨
    expect(highlightSpy).toHaveBeenCalled()
    // 실패했으므로 원본 text 반환
    expect(frame).toContain('plain text')
    unmount()
  })

  it('Test 3: 잘못된 언어 — ignoreIllegals:true 로 throw 안 하고 원본 반환', () => {
    // ignoreIllegals:true 가 없으면 throw 될 수 있으나, 실제 구현은 try/catch 로 처리
    highlightSpy.mockImplementationOnce(() => { throw new Error('unknown language') })
    const content = '```nonexistent_lang\nfoo bar\n```'
    const msg = {id: 'm3', role: 'user' as const, content}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''

    // 크래시 없이 원본 반환
    expect(frame).toContain('foo bar')
    unmount()
  })

  it('Test 4: 코드 펜스 없는 일반 텍스트 — highlight() 호출 안 됨', () => {
    const content = '안녕하세요. 이것은 일반 텍스트입니다.'
    const msg = {id: 'm4', role: 'assistant' as const, content}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''

    // highlight 는 호출되지 않아야 함
    expect(highlightSpy).not.toHaveBeenCalled()
    expect(frame).toContain('일반 텍스트')
    unmount()
  })

  it('Test 5: 복수 코드 펜스 블록 — 각 블록이 독립적으로 highlight 됨', () => {
    const content = '```js\nconst a = 1\n```\n중간 텍스트\n```py\nprint("hello")\n```'
    const msg = {id: 'm5', role: 'assistant' as const, content}
    const {lastFrame, unmount} = render(<Message message={msg}/>)
    const frame = lastFrame() ?? ''

    // js, py 각각 1회씩 — 총 2회
    expect(highlightSpy).toHaveBeenCalledTimes(2)
    expect(highlightSpy).toHaveBeenCalledWith('const a = 1\n', expect.objectContaining({language: 'js'}))
    expect(highlightSpy).toHaveBeenCalledWith('print("hello")\n', expect.objectContaining({language: 'py'}))
    // 중간 텍스트도 렌더됨
    expect(frame).toContain('중간 텍스트')
    unmount()
  })
})
