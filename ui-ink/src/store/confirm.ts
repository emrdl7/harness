// confirm 다이얼로그 슬라이스 (Phase 2 에서 완성)
import {create} from 'zustand'

export type ConfirmMode = 'none' | 'confirm_write' | 'confirm_bash' | 'cplan_confirm'

interface ConfirmState {
  mode: ConfirmMode
  payload: Record<string, unknown>
  setConfirm: (mode: ConfirmMode, payload: Record<string, unknown>) => void
  clearConfirm: () => void
}

export const useConfirmStore = create<ConfirmState>((set) => ({
  mode: 'none',
  payload: {},
  setConfirm: (mode, payload) => set({mode, payload}),
  clearConfirm: () => set({mode: 'none', payload: {}}),
}))
