// RPC-05 (D-17): read_file 5케이스 vitest 회귀.
// Python tests/test_fs.py:TestReadWriteEdit (line 56-83) 의 동등 변환 +
// 존재안함/디렉토리/대용량 offset/path 누락 가드 추가.
import {describe, it, expect, beforeEach, afterEach} from 'vitest'
import {promises as fs} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {readFile} from '../tools/fs.js'

describe('readFile (RPC-03)', () => {
  let dir: string

  beforeEach(async () => {
    // 격리 fixture — 매 테스트마다 새 tmpdir 생성.
    dir = await fs.mkdtemp(join(tmpdir(), 'harness-fs-'))
  })
  afterEach(async () => {
    await fs.rm(dir, {recursive: true, force: true})
  })

  it('성공 — 전체 읽기 시 줄 번호 prefix + total_lines 반환', async () => {
    // Python test_write_and_read_round_trip 동등 (read 부분만).
    const p = join(dir, 'sample.txt')
    await fs.writeFile(p, 'hello\nworld\n')
    const r = await readFile({path: p})
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r['total_lines']).toBe(2)
      expect(r['content']).toContain('hello')
      expect(r['content']).toContain('world')
      // cat -n 스타일 — 4자리 right-aligned padding + tab.
      expect(r['content']).toMatch(/^\s+1\thello\n/)
    }
  })

  it('성공 — offset/limit 분기 (Python test_read_offset_limit 동등)', async () => {
    const p = join(dir, 'multi.txt')
    const lines = Array.from({length: 10}, (_, i) => `line${i}\n`).join('')
    await fs.writeFile(p, lines)
    const r = await readFile({path: p, offset: 3, limit: 2})
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r['start_line']).toBe(3)
      expect(r['end_line']).toBe(4)
      expect(r['content']).toContain('line2')
      expect(r['content']).toContain('line3')
      expect(r['content']).not.toContain('line0')
      expect(r['content']).not.toContain('line4')
    }
  })

  it('실패 — 존재하지 않는 파일은 ok=false', async () => {
    const r = await readFile({path: join(dir, 'nope.txt')})
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(typeof r.error).toBe('string')
      expect(r.error.length).toBeGreaterThan(0)
    }
  })

  it('실패 — 디렉토리는 ok=false (EISDIR)', async () => {
    const r = await readFile({path: dir})
    expect(r.ok).toBe(false)
  })

  it('대용량 offset — 파일 끝 너머 offset 도 안전 (sliced 빈 배열)', async () => {
    // Python tools/fs.py:read_file 동등 산출.
    // start = max(1, 100) - 1 = 99, sliced = lines[99:99+10] = [] (lines 길이 2),
    // start_line = start + 1 = 100, end_line = start + len(sliced) = 99.
    const p = join(dir, 'small.txt')
    await fs.writeFile(p, 'a\nb\n')
    const r = await readFile({path: p, offset: 100, limit: 10})
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r['content']).toBe('')
      expect(r['start_line']).toBe(100)
      expect(r['end_line']).toBe(99)
    }
  })

  it('인자 누락 — path 없으면 ok=false 명시 에러', async () => {
    const r = await readFile({})
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error).toContain('path')
    }
  })
})
