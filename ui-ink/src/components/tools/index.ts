// AR-01: tool 이름 → 렌더 컴포넌트 registry
// Pi Mono 패턴 — 각 tool 이 자기 시각화를 소유 (renderResult co-location)
//
// 새 tool 추가:
//   1. tools/<MyToolBlock>.tsx 작성 — types.ts 의 ToolBlockProps 따름
//   2. 아래 TOOL_REGISTRY 에 한 줄 추가
//   3. 끝 (Message.tsx 변경 불필요)
//
// registry 미매칭 → DefaultToolBlock fallback (= 기존 동작)
import {DefaultToolBlock} from './DefaultToolBlock.js'
import {BashBlock} from './BashBlock.js'
import {ReadFileBlock} from './ReadFileBlock.js'
import {FileEditBlock} from './FileEditBlock.js'
import {GrepResultBlock} from './GrepResultBlock.js'
import type {ToolBlockComponent} from './types.js'

export const TOOL_REGISTRY: Record<string, ToolBlockComponent> = {
  run_command: BashBlock,
  run_python:  BashBlock,
  read_file:   ReadFileBlock,
  write_file:  FileEditBlock,
  edit_file:   FileEditBlock,
  grep_search: GrepResultBlock,
}

export function getToolRenderer(name: string): ToolBlockComponent {
  return TOOL_REGISTRY[name] ?? DefaultToolBlock
}

export {DefaultToolBlock}
export type {ToolBlockProps, ToolBlockComponent} from './types.js'
