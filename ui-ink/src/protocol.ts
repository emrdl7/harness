// harness WS 프로토콜 타입 정의 (FND-04)
// ground truth: harness_server.py 의 send/broadcast 호출

// ─── 서버 → 클라 메시지 타입들 ───────────────────────────────────────────────

export interface TokenMsg        { type: 'token';               text: string }
export interface ToolStartMsg    { type: 'tool_start';          name: string; args: Record<string, unknown> }
export interface ToolEndMsg      { type: 'tool_end';            name: string; result: string }
export interface AgentStartMsg   { type: 'agent_start' }
export interface AgentEndMsg     { type: 'agent_end' }
export interface ErrorMsg        { type: 'error';               text: string }  // .text, .message 아님
export interface InfoMsg         { type: 'info';                text: string }
export interface ConfirmWriteMsg { type: 'confirm_write';       path: string }
export interface ConfirmBashMsg  { type: 'confirm_bash';        command: string }
export interface CplanConfirmMsg { type: 'cplan_confirm';       task: string }
export interface ReadyMsg        { type: 'ready';               room: string }
export interface RoomJoinedMsg   { type: 'room_joined';         room: string; members: string[] }
export interface RoomMemberJoinedMsg { type: 'room_member_joined'; user: string }
export interface RoomMemberLeftMsg   { type: 'room_member_left';   user: string }
export interface RoomBusyMsg     { type: 'room_busy' }
export interface StateSnapshotMsg {
  type: 'state_snapshot'
  working_dir: string
  model: string
  mode: string
  turns: number
  ctx_tokens?: number
  messages?: unknown[]
}
export interface StateMsg        { type: 'state';               working_dir: string; model: string; mode: string; turns: number; ctx_tokens?: number }
export interface SlashResultMsg  { type: 'slash_result';        cmd: string; [key: string]: unknown }
export interface QuitMsg         { type: 'quit' }
export interface QueueMsg        { type: 'queue';               position: number }
export interface QueueReadyMsg   { type: 'queue_ready' }
export interface PongMsg         { type: 'pong' }
export interface ClaudeStartMsg  { type: 'claude_start' }
export interface ClaudeEndMsg    { type: 'claude_end' }
export interface ClaudeTokenMsg  { type: 'claude_token';        text: string }

// discriminated union — 모든 서버 메시지 (25종)
export type ServerMsg =
  | TokenMsg | ToolStartMsg | ToolEndMsg
  | AgentStartMsg | AgentEndMsg
  | ErrorMsg | InfoMsg
  | ConfirmWriteMsg | ConfirmBashMsg | CplanConfirmMsg
  | ReadyMsg
  | RoomJoinedMsg | RoomMemberJoinedMsg | RoomMemberLeftMsg | RoomBusyMsg
  | StateSnapshotMsg | StateMsg
  | SlashResultMsg
  | QuitMsg | QueueMsg | QueueReadyMsg | PongMsg
  | ClaudeStartMsg | ClaudeEndMsg | ClaudeTokenMsg

// ─── 클라 → 서버 메시지 타입들 ───────────────────────────────────────────────

export interface InputMsg             { type: 'input';                  text: string }
export interface ConfirmWriteResponse { type: 'confirm_write_response'; accept: boolean }
export interface ConfirmBashResponse  { type: 'confirm_bash_response';  accept: boolean }
export interface SlashMsg             { type: 'slash';                  name: string; args?: string }
export interface PingMsg              { type: 'ping' }

export type ClientMsg =
  | InputMsg | ConfirmWriteResponse | ConfirmBashResponse | SlashMsg | PingMsg

// ─── exhaustive switch 가드 ───────────────────────────────────────────────────
// dispatch.ts 에서 미처리 이벤트를 컴파일 에러로 탐지하는 헬퍼
export function assertNever(x: never): never {
  throw new Error(`Unhandled ServerMsg type: ${(x as { type: string }).type}`)
}
