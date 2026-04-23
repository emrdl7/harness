// parseServerMsg 단위 테스트 (FND-04)
import {describe, it, expect} from 'vitest'
import {parseServerMsg} from '../ws/parse.js'

describe('parseServerMsg', () => {
  it('정상 token 메시지를 파싱해 TokenMsg 반환', () => {
    const result = parseServerMsg('{"type":"token","text":"hello"}')
    expect(result).not.toBeNull()
    expect(result?.type).toBe('token')
    expect((result as {type: string; text: string}).text).toBe('hello')
  })

  it('정상 agent_end 메시지를 파싱해 AgentEndMsg 반환', () => {
    const result = parseServerMsg('{"type":"agent_end"}')
    expect(result).not.toBeNull()
    expect(result?.type).toBe('agent_end')
  })

  it('잘못된 JSON 입력은 null 반환', () => {
    const result = parseServerMsg('{invalid json')
    expect(result).toBeNull()
  })

  it('error 메시지의 text 필드가 올바르게 파싱됨 (.message 아님)', () => {
    const result = parseServerMsg('{"type":"error","text":"oops"}')
    expect(result).not.toBeNull()
    expect(result?.type).toBe('error')
    // ErrorMsg 는 .text 필드 사용 (.message 금지 — protocol.ts FND-04)
    expect((result as {type: string; text: string}).text).toBe('oops')
  })

  it('알 수 없는 미래 타입도 type 필드를 가진 객체로 반환됨', () => {
    const result = parseServerMsg('{"type":"unknown_future_type"}')
    // parseServerMsg 는 타입 가드 없이 파싱만 — unknown 타입도 반환
    expect(result).not.toBeNull()
    expect(result?.type).toBe('unknown_future_type')
  })

  it('type 필드가 없으면 null 반환', () => {
    const result = parseServerMsg('{"data":"no type field"}')
    expect(result).toBeNull()
  })
})
