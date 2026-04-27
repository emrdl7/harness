// RPC-03 (Phase 1): read_file — Python tools/fs.py:read_file 와 동등 schema (D-14, D-15).
// alias 처리 (file_path → path) 는 agent.py 측 (D-16) — TS 는 path 만 받는다.
// 성공: {ok: true, content, total_lines, start_line, end_line}
// 실패: {ok: false, error: string}
import {promises as fs} from 'node:fs'
import type {ToolResult} from './registry.js'

export async function readFile(rawArgs: Record<string, unknown>): Promise<ToolResult> {
  const path = typeof rawArgs['path'] === 'string' ? rawArgs['path'] : ''
  const offset = typeof rawArgs['offset'] === 'number' ? rawArgs['offset'] : 1
  const limit = typeof rawArgs['limit'] === 'number' ? rawArgs['limit'] : 0
  if (!path) {
    return {ok: false, error: 'path 누락'}
  }
  try {
    const buf = await fs.readFile(path, 'utf-8')
    // Python f.readlines() 동등 — 줄바꿈 보존 (keepends).
    // 빈 파일 → 빈 배열. 마지막 줄에 \n 없을 수도 있음.
    const lines = buf.length === 0 ? [] : buf.split(/(?<=\n)/)
    const total = lines.length
    const start = Math.max(1, offset) - 1
    const end = limit > 0 ? Math.min(start + limit, total) : total
    const sliced = start >= total ? [] : lines.slice(start, end)
    // cat -n 스타일 — Python 의 f'{n:4d}\t{l}' 동등 (4자리 right-aligned + tab).
    const content = sliced
      .map((l, i) => `${String(start + i + 1).padStart(4, ' ')}\t${l}`)
      .join('')
    return {
      ok: true,
      content,
      total_lines: total,
      start_line: start + 1,
      end_line: start + sliced.length,
    }
  } catch (e) {
    const m = e instanceof Error ? e.message : String(e)
    return {ok: false, error: m}
  }
}
