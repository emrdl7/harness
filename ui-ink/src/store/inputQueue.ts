// AR-04: Two-lane input queue (Pi Mono game-engine 패턴)
// busy=true 동안 사용자가 추가 입력 가능 — 큐에 쌓이고 turn 종료 시 자동 flush.
//
// kind 의미:
//   - 'steer'    — Enter (default). 다음 turn 시작 직전 send. 현재 LLM 응답에 영향 줄 수 있음.
//   - 'followUp' — 향후 확장 (Shift+Enter 가 multiline newline 으로 점유 중이라 키 미할당).
//                  현재는 'steer' 와 동일 동작. 별도 처리는 추후.
//
// 큐 flush 책임: App.tsx 의 useEffect([busy, queueLen]) 가 busy=false 전환 시 dequeue + send
import {create} from 'zustand'

export type InputKind = 'steer' | 'followUp'

export interface QueuedInput {
  id: string
  text: string
  kind: InputKind
  enqueuedAt: number
}

interface InputQueueState {
  queue: QueuedInput[]
  enqueue: (text: string, kind?: InputKind) => void
  dequeue: () => QueuedInput | null     // shift + return
  clear: () => void
}

export const useInputQueueStore = create<InputQueueState>((set, get) => ({
  queue: [],

  enqueue: (text, kind = 'steer') => {
    const trimmed = text.trim()
    if (!trimmed) return
    set((s) => ({
      queue: [...s.queue, {
        id: crypto.randomUUID(),
        text: trimmed,
        kind,
        enqueuedAt: Date.now(),
      }],
    }))
  },

  dequeue: () => {
    const {queue} = get()
    if (queue.length === 0) return null
    const [next, ...rest] = queue
    set({queue: rest})
    return next
  },

  clear: () => set({queue: []}),
}))
