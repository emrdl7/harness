// userColor 단위 테스트 (DIFF-04)
// 결정론적 색 해시 순수함수 검증
import {describe, it, expect, beforeEach, afterEach, vi} from 'vitest'

describe('userColor', () => {
  const PALETTE = ['cyan', 'green', 'yellow', 'magenta', 'blue', 'red', 'white', 'greenBright']

  beforeEach(() => {
    // HARNESS_TOKEN 환경변수 초기화
    delete process.env['HARNESS_TOKEN']
  })

  afterEach(() => {
    delete process.env['HARNESS_TOKEN']
    vi.resetModules()
  })

  it('Test U1: 빈 토큰 → PALETTE 중 하나 반환 (crash 없음)', async () => {
    const {userColor} = await import('../utils/userColor.js')
    const result = userColor('')
    expect(PALETTE).toContain(result)
  })

  it('Test U2: HARNESS_TOKEN과 동일 → cyan 반환', async () => {
    process.env['HARNESS_TOKEN'] = 'my-secret-token'
    vi.resetModules()
    const {userColor} = await import('../utils/userColor.js')
    const result = userColor('my-secret-token')
    expect(result).toBe('cyan')
  })

  it('Test U3: 동일 토큰 → 항상 동일 색 반환 (결정론)', async () => {
    const {userColor} = await import('../utils/userColor.js')
    const token = 'alice-token'
    const first = userColor(token)
    const second = userColor(token)
    const third = userColor(token)
    expect(first).toBe(second)
    expect(second).toBe(third)
  })

  it('Test U4: 두 다른 토큰 → PALETTE 범위 내 색 반환 (0..7 인덱스)', async () => {
    const {userColor} = await import('../utils/userColor.js')
    const color1 = userColor('alice')
    const color2 = userColor('bob')
    expect(PALETTE).toContain(color1)
    expect(PALETTE).toContain(color2)
  })
})
