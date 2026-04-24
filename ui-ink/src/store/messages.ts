// 메시지 슬라이스 — completed(Static 전용) + active(streaming 전용) 분리 (RND-01, RND-02)
import {create} from 'zustand'

export interface Message {
  id: string               // crypto.randomUUID() — React key 용 (FND-08)
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  streaming?: boolean      // 스트리밍 중인 메시지 여부
  toolName?: string        // tool 메시지용
  meta?: Record<string, unknown>
}

interface MessagesState {
  completedMessages: Message[]    // <Static> 전용 append-only — agent_end 시에만 push
  activeMessage: Message | null   // 스트리밍 중 assistant — 일반 트리에만 렌더
  snapshotKey: number             // Phase 3: Static key remount 트리거 (REM-03)
  appendUserMessage: (content: string, meta?: Record<string, unknown>) => void
  agentStart: () => void
  appendToken: (text: string) => void    // activeMessage in-place 업데이트 (NOT completedMessages push)
  agentEnd: () => void
  appendToolStart: (name: string, args: Record<string, unknown>) => void
  appendToolEnd: (name: string, result: string) => void
  appendSystemMessage: (content: string) => void
  clearMessages: () => void
  loadSnapshot: (rawMessages: unknown[]) => void  // Phase 3: state_snapshot 히스토리 로드 (REM-03)
}

export const useMessagesStore = create<MessagesState>((set) => ({
  completedMessages: [],
  activeMessage: null,
  snapshotKey: 0,

  appendUserMessage: (content, meta?) => set((s) => ({
    completedMessages: [...s.completedMessages, {
      id: crypto.randomUUID(), role: 'user', content, meta,
    }],
  })),

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
    }
  }),

  appendToolStart: (name, args) => set((s) => ({
    completedMessages: [...s.completedMessages, {
      id: crypto.randomUUID(),
      role: 'tool',
      content: `[${name}] ${JSON.stringify(args)}`,
      toolName: name,
      streaming: true,
    }],
  })),

  // tool 은 completedMessages 안에서 in-place 업데이트 (streaming → false)
  appendToolEnd: (name, result) => set((s) => {
    const revIdx = [...s.completedMessages].reverse().findIndex(
      (m) => m.role === 'tool' && m.toolName === name && m.streaming,
    )
    if (revIdx === -1) return {}
    const realIdx = s.completedMessages.length - 1 - revIdx
    const updated = {
      ...s.completedMessages[realIdx],
      content: `[${name}] ${result}`,
      streaming: false,
    }
    return {
      completedMessages: [
        ...s.completedMessages.slice(0, realIdx),
        updated,
        ...s.completedMessages.slice(realIdx + 1),
      ],
    }
  }),

  appendSystemMessage: (content) => set((s) => ({
    completedMessages: [...s.completedMessages, {
      id: crypto.randomUUID(), role: 'system', content,
    }],
  })),

  clearMessages: () => set({completedMessages: [], activeMessage: null}),

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
    return {
      snapshotKey: s.snapshotKey + 1,  // Static key remount 트리거
      completedMessages: parsed,
      activeMessage: null,
    }
  }),
}))
