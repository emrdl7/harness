// ServerMsg → store action exhaustive switch 디스패처 (FND-04, FND-05)
// WS 레이어는 React 훅 바깥에서 useStore.getState() 를 직접 호출한다.
import type {ServerMsg} from '../protocol.js'
import {assertNever} from '../protocol.js'
import {useMessagesStore} from '../store/messages.js'
import {useStatusStore} from '../store/status.js'
import {useRoomStore} from '../store/room.js'
import {useConfirmStore} from '../store/confirm.js'

let _exit: (() => void) | null = null

export function bindExit(fn: (() => void) | null): void {
  _exit = fn
}

// AR-02: 60fps 스트리밍 token coalescer
// chunk 마다 set state 호출하면 Ink 재조정 폭주 → 한글 IME/긴 코드 깜빡거림.
// 16ms 동안 chunk 누적 → trailing flush 1회만 set 호출.
// agent_end / agent_cancelled / claude_end 등 turn 종료 이벤트 처리 직전엔 강제 flush — 토큰 손실 방지.
const FLUSH_INTERVAL_MS = 16
let _pendingTokens = ''
let _flushTimer: ReturnType<typeof setTimeout> | null = null

function scheduleFlush(): void {
  if (_flushTimer) return
  _flushTimer = setTimeout(() => {
    _flushTimer = null
    flushPendingTokens()
  }, FLUSH_INTERVAL_MS)
}

export function flushPendingTokens(): void {
  if (_flushTimer) {
    clearTimeout(_flushTimer)
    _flushTimer = null
  }
  if (_pendingTokens) {
    const text = _pendingTokens
    _pendingTokens = ''
    useMessagesStore.getState().appendToken(text)
  }
}


export function dispatch(msg: ServerMsg): void {
  const messages = useMessagesStore.getState()
  const status = useStatusStore.getState()
  const room = useRoomStore.getState()
  const confirm = useConfirmStore.getState()

  // PEXT-03: event_id 추적 — 모든 이벤트에 적용 (서버가 broadcast() 경유 메시지에 자동 부여)
  const rawMsg = msg as unknown as {event_id?: unknown}
  if ('event_id' in msg && typeof rawMsg.event_id === 'number') {
    room.setLastEventId(rawMsg.event_id)
  }

  switch (msg.type) {
    case 'token':
      // AR-02: 즉시 set 대신 16ms 윈도우에 누적 → trailing flush
      _pendingTokens += msg.text
      scheduleFlush()
      break

    case 'tool_start':
      flushPendingTokens()   // AR-02: tool 경계 — 누적 중인 텍스트 먼저 표시
      messages.appendToolStart(msg.name, msg.args)
      status.setActiveTool(msg.name, msg.args)
      break

    case 'tool_end':
      flushPendingTokens()
      messages.appendToolEnd(msg.name, msg.result)
      status.setActiveTool(null)
      break

    case 'agent_start':
      flushPendingTokens()
      messages.agentStart()
      status.setBusy(true)
      // PEXT-01: from_self 필드로 관전 모드 판정 (undefined → true = 구버전 호환)
      room.setActiveIsSelf(msg.from_self ?? true)
      break

    case 'agent_end':
      flushPendingTokens()   // AR-02: turn 종료 — 잔여 token 보장
      messages.agentEnd()
      status.setBusy(false)
      status.setActiveTool(null)
      break

    case 'agent_cancelled':
      // PEXT-05: 에이전트 실행 취소 알림 처리
      flushPendingTokens()
      messages.agentEnd()
      status.setBusy(false)
      status.setActiveTool(null)
      room.setActiveIsSelf(true)
      messages.appendSystemMessage('에이전트 실행이 취소되었습니다')
      break

    case 'error':

      messages.appendSystemMessage(`오류: ${msg.text}`)
      status.setBusy(false)
      break

    case 'info':
      messages.appendSystemMessage(msg.text)
      break

    case 'confirm_write':
      // PEXT-02: old_content 전달 (diff 기반 UX용)
      confirm.setConfirm('confirm_write', {path: msg.path, oldContent: msg.old_content})
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
      // msg.members는 optional — 없으면 빈 배열 (Pitfall H 수정, Plan 03-02에서 서버가 [] 전송)
      room.setRoom(msg.room, msg.members ?? [])
      break

    case 'room_member_joined':
      room.addMember(msg.user)
      // REM-05: UI-SPEC 포맷 교정 (B4: msg.user = token_hash[:8] 값)
      messages.appendSystemMessage(`↗ ${msg.user} 님이 참여했습니다`)
      break

    case 'room_member_left':
      room.removeMember(msg.user)
      // REM-05: UI-SPEC 포맷 교정
      messages.appendSystemMessage(`↘ ${msg.user} 님이 나갔습니다`)
      break

    case 'room_busy':
      room.setRoomBusy(true)
      break

    case 'state':
      status.setState({
        working_dir: msg.working_dir,
        model: msg.model,
        mode: msg.mode,
        turns: msg.turns,
        ctx_tokens: msg.ctx_tokens,
      })
      break

    case 'state_snapshot':
      status.setState({
        working_dir: msg.working_dir,
        model: msg.model,
        mode: msg.mode,
        turns: msg.turns,
        ctx_tokens: msg.ctx_tokens,
      })
      // REM-03: 과거 turn 히스토리 일괄 로드 (Static key remount 트리거)
      if (msg.messages && Array.isArray(msg.messages)) {
        messages.loadSnapshot(msg.messages)
      }
      break

    case 'slash_result': {
      const cmd = msg.cmd
      // cmd 화이트리스트 switch — unknown cmd 는 appendSystemMessage fallback 만 수행 (T-02A-01)
      switch (cmd) {
        case 'clear':
          messages.clearMessages()
          break
        case 'cd': {
          const path = typeof msg['path'] === 'string' ? (msg['path'] as string) : undefined
          if (path) status.setWorkingDir(path)
          messages.appendSystemMessage(`cd ${path ?? ''}`)
          break
        }
        case 'model': {
          const model = typeof msg['model'] === 'string' ? (msg['model'] as string) : undefined
          if (model) status.setModel(model)
          messages.appendSystemMessage(`model: ${model ?? ''}`)
          break
        }
        case 'mode': {
          const mode = typeof msg['mode'] === 'string' ? (msg['mode'] as string) : undefined
          if (mode) status.setMode(mode)
          messages.appendSystemMessage(`mode: ${mode ?? ''}`)
          break
        }
        case 'help': {
          const text = typeof msg['help_text'] === 'string'
            ? (msg['help_text'] as string)
            : '/help'
          messages.appendSystemMessage(text)
          break
        }
        case 'exit':
        case 'quit':
          _exit?.()
          break
        default:
          messages.appendSystemMessage(`/${cmd} 완료`)
      }
      break
    }

    case 'quit':
      _exit?.()
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
      flushPendingTokens()   // AR-02
      status.setBusy(false)
      break

    case 'claude_token':
      // AR-02: token 과 동일 coalesce 경로
      _pendingTokens += msg.text
      scheduleFlush()
      break

    default:
      // exhaustive switch — 위에서 처리 안 된 타입은 컴파일 에러
      assertNever(msg)
  }
}
