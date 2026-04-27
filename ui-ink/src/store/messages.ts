// 메시지 슬라이스 — completed(Static 전용) + active(streaming 전용) 분리 (RND-01, RND-02)
import {create} from 'zustand'

export interface Message {
  id: string               // crypto.randomUUID() — React key 용 (FND-08)
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  streaming?: boolean      // 스트리밍 중인 메시지 여부
  toolName?: string        // tool 메시지용
  toolArgs?: Record<string, unknown>   // AR-01: tool_start 시 인자 (registry 컴포넌트용)
  toolPayload?: unknown                // AR-01: tool_end 시 dict 결과 (registry 컴포넌트용)
  meta?: Record<string, unknown>
}

interface MessagesState {
  completedMessages: Message[]    // <Static> 전용 append-only — agent_end / tool_end 시에만 push
  activeMessage: Message | null   // 스트리밍 중 assistant — 일반 트리에만 렌더
  // 진행 중 tool — Static 의 in-place 업데이트가 화면에 안 반영되는 문제 회피.
  // tool_start 시 set, tool_end 시 streaming=false + toolPayload 부착해서 completedMessages 로 이동.
  activeToolMessage: Message | null
  snapshotKey: number             // Phase 3: Static key remount 트리거 (REM-03)
  pendingUserMessage: Message | null  // 재연결 시 state_snapshot 덮어쓰기 방지용
  appendUserMessage: (content: string, meta?: Record<string, unknown>) => void
  agentStart: () => void
  appendToken: (text: string) => void    // activeMessage in-place 업데이트 (NOT completedMessages push)
  agentEnd: () => void
  appendToolStart: (name: string, args: Record<string, unknown>) => void
  appendToolEnd: (name: string, payload: unknown) => void   // AR-01: dict 결과 받음
  appendSystemMessage: (content: string) => void
  clearMessages: () => void
  loadSnapshot: (rawMessages: unknown[]) => void  // Phase 3: state_snapshot 히스토리 로드 (REM-03)
}

export const useMessagesStore = create<MessagesState>((set) => ({
  completedMessages: [],
  activeMessage: null,
  activeToolMessage: null,
  snapshotKey: 0,
  pendingUserMessage: null,

  appendUserMessage: (content, meta?) => set((s) => {
    const msg: Message = {id: crypto.randomUUID(), role: 'user', content, meta}
    return {
      completedMessages: [...s.completedMessages, msg],
      pendingUserMessage: msg,
    }
  }),

  agentStart: () => set(() => ({
    activeMessage: {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      streaming: true,
    },
  })),

  // activeMessage in-place 업데이트 — completedMessages 는 건드리지 않음 (RND-02)
  appendToken: (text) => set((s) => {
    if (s.activeMessage && s.activeMessage.role === 'assistant') {
      return {activeMessage: {...s.activeMessage, content: s.activeMessage.content + text}}
    }
    // agentStart 없이 token 수신 방어 처리
    return {
      activeMessage: {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: text,
        streaming: true,
      },
    }
  }),

  // D-04 — agent_end 수신 시에만 completedMessages 로 이동 (Static 안정성 핵심)
  agentEnd: () => set((s) => {
    if (!s.activeMessage) return {}
    return {
      completedMessages: [...s.completedMessages, {...s.activeMessage, streaming: false}],
      activeMessage: null,
      pendingUserMessage: null,  // 턴 완료 — pending 해제
    }
  }),

  // tool_start: activeToolMessage 슬롯에만 set. completedMessages 에 push 하면
  // Ink <Static> 의 append-only 특성상 tool_end 시 in-place 업데이트가 화면에 반영되지 않음.
  appendToolStart: (name, args) => set(() => ({
    activeToolMessage: {
      id: crypto.randomUUID(),
      role: 'tool',
      content: `[${name}] ${JSON.stringify(args)}`,
      toolName: name,
      toolArgs: args,
      streaming: true,
    },
  })),

  // tool_end: activeToolMessage 를 streaming=false + toolPayload 부착해서 completedMessages 로 이동.
  // AR-01: payload 는 dict (백엔드가 dict broadcast). content 는 fallback 표시용 string 유지.
  appendToolEnd: (name, payload) => set((s) => {
    const fallback = typeof payload === 'string'
      ? payload
      : JSON.stringify(payload).slice(0, 200)
    // 매칭 실패 (snapshot 로드 / tool_start 없이 tool_end 도달) → 새 메시지로 직접 push
    if (!s.activeToolMessage || s.activeToolMessage.toolName !== name) {
      return {
        completedMessages: [...s.completedMessages, {
          id: crypto.randomUUID(),
          role: 'tool',
          content: `[${name}] ${fallback}`,
          toolName: name,
          toolPayload: payload,
          streaming: false,
        }],
      }
    }
    const finished: Message = {
      ...s.activeToolMessage,
      content: `[${name}] ${fallback}`,
      toolPayload: payload,
      streaming: false,
    }
    return {
      activeToolMessage: null,
      completedMessages: [...s.completedMessages, finished],
    }
  }),

  appendSystemMessage: (content) => set((s) => ({
    completedMessages: [...s.completedMessages, {
      id: crypto.randomUUID(), role: 'system', content,
    }],
  })),

  clearMessages: () => set({completedMessages: [], activeMessage: null, activeToolMessage: null}),

  // Phase 3: state_snapshot 히스토리 일괄 로드 (REM-03)
  // T-03-03-01: rawMessages 악성 데이터 방어 — object만 허용, role 화이트리스트, content string 강제
  loadSnapshot: (rawMessages) => set((s) => {
    const parsed: Message[] = rawMessages
      .filter((m): m is Record<string, unknown> => typeof m === 'object' && m !== null)
      .map((m) => ({
        id: crypto.randomUUID(),
        role: (['user', 'assistant', 'tool', 'system'].includes(String(m['role']))
          ? m['role'] as Message['role']
          : 'system'),
        content: typeof m['content'] === 'string' ? m['content'] : JSON.stringify(m),
        meta: typeof m['meta'] === 'object' && m['meta'] !== null
          ? m['meta'] as Record<string, unknown>
          : undefined,
      }))
    // 재연결 race: 서버 스냅샷이 pending 유저 메시지를 포함하지 않을 경우 보존
    const pending = s.pendingUserMessage
    const hasPending = pending !== null && !parsed.some(
      m => m.role === 'user' && m.content === pending.content
    )
    return {
      snapshotKey: s.snapshotKey + 1,  // Static key remount 트리거
      completedMessages: hasPending ? [...parsed, pending] : parsed,
      activeMessage: null,
      activeToolMessage: null,
    }
  }),
}))
