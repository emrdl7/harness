// ServerMsg → store action exhaustive switch 디스패처 (FND-04, FND-05)
// WS 레이어는 React 훅 바깥에서 useStore.getState() 를 직접 호출한다.
import type {ServerMsg} from '../protocol.js'
import {assertNever} from '../protocol.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'

export function dispatch(msg: ServerMsg): void {
  const messages = useMessagesStore.getState()
  const status = useStatusStore.getState()
  const room = useRoomStore.getState()
  const confirm = useConfirmStore.getState()

  switch (msg.type) {
    case 'token':
      messages.appendToken(msg.text)
      break

    case 'tool_start':
      messages.appendToolStart(msg.name, msg.args)
      break

    case 'tool_end':
      messages.appendToolEnd(msg.name, msg.result)
      break

    case 'agent_start':
      messages.agentStart()
      status.setBusy(true)
      break

    case 'agent_end':
      messages.agentEnd()
      status.setBusy(false)
      break

    case 'error':
      messages.appendSystemMessage(`오류: ${msg.text}`)
      status.setBusy(false)
      break

    case 'info':
      messages.appendSystemMessage(msg.text)
      break

    case 'confirm_write':
      confirm.setConfirm('confirm_write', {path: msg.path})
      break

    case 'confirm_bash':
      confirm.setConfirm('confirm_bash', {command: msg.command})
      break

    case 'cplan_confirm':
      confirm.setConfirm('cplan_confirm', {task: msg.task})
      break

    case 'ready':
      status.setConnected(true)
      break

    case 'room_joined':
      room.setRoom(msg.room, msg.members)
      break

    case 'room_member_joined':
      room.addMember(msg.user)
      messages.appendSystemMessage(`[${msg.user}] 님이 참가했습니다`)
      break

    case 'room_member_left':
      room.removeMember(msg.user)
      messages.appendSystemMessage(`[${msg.user}] 님이 나갔습니다`)
      break

    case 'room_busy':
      room.setRoomBusy(true)
      break

    case 'state':
    case 'state_snapshot':
      status.setState({
        working_dir: msg.working_dir,
        model: msg.model,
        mode: msg.mode,
        turns: msg.turns,
        ctx_tokens: msg.ctx_tokens,
      })
      break

    case 'slash_result':
      // Phase 2 에서 cmd 별 처리 확장 예정 — 현재는 시스템 메시지로 표시
      messages.appendSystemMessage(`/${msg.cmd} 완료`)
      break

    case 'quit':
      // Phase 3 의 useApp().exit() 연동 — 현재는 상태 표시만
      messages.appendSystemMessage('서버 종료 요청')
      break

    case 'queue':
      messages.appendSystemMessage(`큐 대기 중 (${msg.position}번째)`)
      break

    case 'queue_ready':
      messages.appendSystemMessage('큐 준비 완료')
      break

    case 'pong':
      // heartbeat 응답 — 무시
      break

    case 'claude_start':
      status.setBusy(true)
      break

    case 'claude_end':
      status.setBusy(false)
      break

    case 'claude_token':
      messages.appendToken(msg.text)
      break

    default:
      // exhaustive switch — 위에서 처리 안 된 타입은 컴파일 에러
      assertNever(msg)
  }
}
