// 메시지 슬라이스 — 스트리밍 in-place 업데이트 패턴 (FND-07, FND-08)
import {create} from 'zustand'

export interface Message {
  id: string               // crypto.randomUUID() — React key 용 (FND-08)
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  streaming?: boolean      // 스트리밍 중인 assistant 메시지
  toolName?: string        // tool 메시지용
  meta?: Record<string, unknown>
}

interface MessagesState {
  messages: Message[]
  appendUserMessage: (content: string) => void
  agentStart: () => void
  appendToken: (text: string) => void    // in-place update, NOT push (FND-07)
  agentEnd: () => void
  appendToolStart: (name: string, args: Record<string, unknown>) => void
  appendToolEnd: (name: string, result: string) => void
  appendSystemMessage: (content: string) => void
  clearMessages: () => void
}

export const useMessagesStore = create<MessagesState>((set) => ({
  messages: [],

  appendUserMessage: (content) => set((s) => ({
    messages: [...s.messages, {id: crypto.randomUUID(), role: 'user', content}]
  })),

  agentStart: () => set((s) => ({
    messages: [...s.messages, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      streaming: true
    }]
  })),

  // 마지막 assistant streaming 메시지에 in-place append (새 push 금지)
  appendToken: (text) => set((s) => {
    const last = s.messages[s.messages.length - 1]
    if (last?.role === 'assistant' && last.streaming) {
      return {
        messages: [
          ...s.messages.slice(0, -1),
          {...last, content: last.content + text}
        ]
      }
    }
    // agentStart 없이 토큰이 오는 경우 방어 처리
    return {
      messages: [...s.messages, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: text,
        streaming: true
      }]
    }
  }),

  agentEnd: () => set((s) => {
    const last = s.messages[s.messages.length - 1]
    if (last?.role === 'assistant' && last.streaming) {
      return {
        messages: [...s.messages.slice(0, -1), {...last, streaming: false}]
      }
    }
    return {}
  }),

  appendToolStart: (name, args) => set((s) => ({
    messages: [...s.messages, {
      id: crypto.randomUUID(),
      role: 'tool',
      content: `[${name}] ${JSON.stringify(args)}`,
      toolName: name,
      streaming: true
    }]
  })),

  appendToolEnd: (name, result) => set((s) => {
    const idx = [...s.messages].reverse().findIndex(
      (m) => m.role === 'tool' && m.toolName === name && m.streaming
    )
    if (idx === -1) return {}
    const realIdx = s.messages.length - 1 - idx
    const updated = {...s.messages[realIdx], content: `[${name}] ${result}`, streaming: false}
    return {
      messages: [
        ...s.messages.slice(0, realIdx),
        updated,
        ...s.messages.slice(realIdx + 1)
      ]
    }
  }),

  appendSystemMessage: (content) => set((s) => ({
    messages: [...s.messages, {id: crypto.randomUUID(), role: 'system', content}]
  })),

  clearMessages: () => set({messages: []}),
}))
