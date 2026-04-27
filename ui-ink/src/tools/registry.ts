// RPC-02/03: 클라 측 도구 실행 registry. dispatch.ts 의 'tool_request' 가 진입점.
// 새 도구 추가 절차: tools/<file>.ts 작성 → TOOL_RUNTIME 에 한 줄 추가 → 끝.
// store/confirm.ts 의 boundClient 패턴을 그대로 차용 — store → client 순환 의존 회피.
import {readFile} from './fs.js'
import type {HarnessClient} from '../ws/client.js'
import type {ClientMsg} from '../protocol.js'

// 도구 함수가 반환하는 결과 형태 (TS 측 내부 표현 — Python schema 와 1:1).
// ok=true 시: {ok: true, ...payload} (예: content, total_lines, start_line, end_line)
// ok=false 시: {ok: false, error: string}
export type ToolResult =
  | ({ok: true} & Record<string, unknown>)
  | {ok: false; error: string}

export type ToolFn = (args: Record<string, unknown>) => Promise<ToolResult>

// Phase 1 = read_file 만. Phase 2 에서 write_file/edit_file/list_files/grep_search 추가.
export const TOOL_RUNTIME: Record<string, ToolFn> = {
  read_file: readFile,
}

// store/confirm.ts:9-13 의 boundClient 패턴 — registry → client → dispatch → registry 순환 차단
let boundClient: HarnessClient | null = null
export function bindToolClient(client: HarnessClient | null): void {
  boundClient = client
}

// dispatch.ts 의 case 'tool_request' 가 호출. Promise 는 fire-and-forget 으로 래핑.
// 결과는 boundClient.send 를 통해 ClientMsg(tool_result) 로 회신한다.
export async function runClientTool(
  call_id: string,
  name: string,
  args: Record<string, unknown>,
): Promise<void> {
  const fn = TOOL_RUNTIME[name]
  let response: ClientMsg
  if (!fn) {
    response = {
      type: 'tool_result',
      call_id,
      ok: false,
      error: {kind: 'unknown_tool', message: `클라 측 도구 미등록: ${name}`},
    }
  } else {
    try {
      const r = await fn(args)
      if (r.ok) {
        // ok 플래그는 envelope 의 ok 로, 나머지 payload 만 result 에 포장.
        const {ok: _ok, ...rest} = r
        response = {type: 'tool_result', call_id, ok: true, result: rest}
      } else {
        response = {
          type: 'tool_result',
          call_id,
          ok: false,
          error: {kind: 'tool_error', message: r.error},
        }
      }
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e)
      response = {
        type: 'tool_result',
        call_id,
        ok: false,
        error: {kind: 'exception', message: m},
      }
    }
  }
  boundClient?.send(response)
}
