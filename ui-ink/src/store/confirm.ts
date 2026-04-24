// confirm 다이얼로그 슬라이스 (CNF-03, CNF-04, CNF-05)
import {create} from 'zustand'
import type {ClientMsg} from '../protocol.js'
import type {HarnessClient} from '../ws/client.js'

export type ConfirmMode = 'none' | 'confirm_write' | 'confirm_bash' | 'cplan_confirm'
export type DenyKind = 'path' | 'cmd'

// WS 응답을 보낼 client 를 런타임에 주입 (store → client 순환 의존 회피)
let boundClient: HarnessClient | null = null
export function bindConfirmClient(client: HarnessClient | null): void {
  boundClient = client
}

interface ConfirmState {
  mode: ConfirmMode
  payload: Record<string, unknown>
  deniedPaths: Set<string>
  deniedCmds: Set<string>
  setConfirm: (mode: ConfirmMode, payload: Record<string, unknown>) => void
  clearConfirm: () => void
  addDenied: (kind: DenyKind, key: string) => void
  isDenied: (kind: DenyKind, key: string) => boolean
  clearDenied: () => void
  resolve: (accept: boolean) => void
}

export const useConfirmStore = create<ConfirmState>((set, get) => ({
  mode: 'none',
  payload: {},
  deniedPaths: new Set<string>(),
  deniedCmds: new Set<string>(),

  setConfirm: (mode, payload) => set({mode, payload}),
  clearConfirm: () => set({mode: 'none', payload: {}}),

  addDenied: (kind, key) => set((s) => {
    if (kind === 'path') {
      const next = new Set(s.deniedPaths); next.add(key)
      return {deniedPaths: next}
    }
    const next = new Set(s.deniedCmds); next.add(key)
    return {deniedCmds: next}
  }),

  isDenied: (kind, key) => {
    const s = get()
    return kind === 'path' ? s.deniedPaths.has(key) : s.deniedCmds.has(key)
  },

  clearDenied: () => set({deniedPaths: new Set(), deniedCmds: new Set()}),

  resolve: (accept) => {
    const s = get()
    const mode = s.mode
    const payload = s.payload

    // WS 응답 전송
    let response: ClientMsg | null = null
    if (mode === 'confirm_write') {
      response = {type: 'confirm_write_response', accept}
      if (!accept && typeof payload['path'] === 'string') {
        get().addDenied('path', payload['path'] as string)
      }
    } else if (mode === 'confirm_bash') {
      response = {type: 'confirm_bash_response', accept}
      if (!accept && typeof payload['command'] === 'string') {
        get().addDenied('cmd', payload['command'] as string)
      }
    } else if (mode === 'cplan_confirm') {
      // cplan 은 현재 서버 측 응답 타입이 없음 — 로컬 상태만 변경
      response = null
    }

    if (response && boundClient) {
      boundClient.send(response)
    }
    set({mode: 'none', payload: {}})
  },
}))
