// TTY 가드 단위 테스트 (FND-12)
// isInteractiveTTY 함수를 직접 테스트
import {describe, it, expect} from 'vitest'
import {isInteractiveTTY} from '../tty-guard.js'

describe('isInteractiveTTY', () => {
  it('isTTY === undefined 이면 false 반환', () => {
    // non-TTY 환경 (파이프 등)
    const fakePipe = {isTTY: undefined, setRawMode: () => {}} as unknown as NodeJS.ReadStream
    expect(isInteractiveTTY(fakePipe)).toBe(false)
  })

  it('isTTY === false 이면 false 반환', () => {
    const fakeNonTTY = {isTTY: false, setRawMode: () => {}} as unknown as NodeJS.ReadStream
    expect(isInteractiveTTY(fakeNonTTY)).toBe(false)
  })

  it('isTTY === true + setRawMode 함수 존재 → true 반환', () => {
    const fakeTTY = {isTTY: true, setRawMode: () => {}} as unknown as NodeJS.ReadStream
    expect(isInteractiveTTY(fakeTTY)).toBe(true)
  })

  it('isTTY === true 이지만 setRawMode 없으면 false 반환', () => {
    // setRawMode 가 없는 경우 (드문 환경)
    const fakeTTYNoRaw = {isTTY: true} as unknown as NodeJS.ReadStream
    expect(isInteractiveTTY(fakeTTYNoRaw)).toBe(false)
  })

  it('isTTY === true + setRawMode 가 함수가 아닌 경우 false 반환', () => {
    // setRawMode 가 다른 타입인 경우
    const fakeTTYWrongType = {isTTY: true, setRawMode: 'not-a-function'} as unknown as NodeJS.ReadStream
    expect(isInteractiveTTY(fakeTTYWrongType)).toBe(false)
  })
})
