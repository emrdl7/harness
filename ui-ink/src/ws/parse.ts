// JSON raw → ServerMsg 파서 (FND-04, FND-05)
import type {ServerMsg} from '../protocol.js'

export function parseServerMsg(raw: string): ServerMsg | null {
  try {
    const obj = JSON.parse(raw) as {type?: unknown}
    if (typeof obj?.type !== 'string') return null
    return obj as ServerMsg
  } catch {
    return null
  }
}
