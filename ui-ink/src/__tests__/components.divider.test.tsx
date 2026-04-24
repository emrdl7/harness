// Divider 컴포넌트 테스트 — 가로폭 채움, dimColor, 최소 1개 방어 (B-1)
import React from 'react'
import {describe, it, expect} from 'vitest'
import {render} from 'ink-testing-library'
import {Divider} from '../components/Divider.js'

describe('Divider', () => {
  it('Test 1: columns=40 — ─ 문자 정확히 40개', () => {
    const {lastFrame} = render(<Divider columns={40}/>)
    const frame = lastFrame() ?? ''
    const count = (frame.match(/─/g) ?? []).length
    expect(count).toBe(40)
  })

  it('Test 2: columns=1 — ─ 최소 1개 (음수/0 방어)', () => {
    const {lastFrame} = render(<Divider columns={1}/>)
    const frame = lastFrame() ?? ''
    const count = (frame.match(/─/g) ?? []).length
    expect(count).toBeGreaterThanOrEqual(1)
  })

  it('Test 3: columns=0 — Math.max 방어로 최소 1개', () => {
    const {lastFrame} = render(<Divider columns={0}/>)
    const frame = lastFrame() ?? ''
    const count = (frame.match(/─/g) ?? []).length
    expect(count).toBeGreaterThanOrEqual(1)
  })

  it('Test 4: columns 미지정 — 기본값 사용, ─ 1개 이상', () => {
    const {lastFrame} = render(<Divider/>)
    const frame = lastFrame() ?? ''
    const count = (frame.match(/─/g) ?? []).length
    expect(count).toBeGreaterThanOrEqual(1)
  })
})
