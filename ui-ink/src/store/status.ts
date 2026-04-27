// 상태 표시줄 슬라이스
import {create} from 'zustand'

export interface StatusSegment {
  label: string
  color?: string
}

interface StatusState {
  connected: boolean
  workingDir: string
  model: string
  mode: string
  turns: number
  ctxTokens?: number
  busy: boolean
  activeTool: string | null
  activeToolArgs: Record<string, unknown> | null
  setConnected: (v: boolean) => void
  setState: (s: {working_dir?: string; model?: string; mode?: string; turns?: number; ctx_tokens?: number}) => void
  setBusy: (v: boolean) => void
  setWorkingDir: (working_dir: string) => void
  setModel: (model: string) => void
  setMode: (mode: string) => void
  setActiveTool: (name: string | null, args?: Record<string, unknown> | null) => void
}

export const useStatusStore = create<StatusState>((set) => ({
  connected: false,
  workingDir: '',
  model: '',
  mode: '',
  turns: 0,
  ctxTokens: undefined,
  busy: false,
  activeTool: null,
  activeToolArgs: null,
  setConnected: (v) => set({connected: v}),
  setState: (s) => set((cur) => ({
    workingDir: s.working_dir ?? cur.workingDir,
    model: s.model ?? cur.model,
    mode: s.mode ?? cur.mode,
    turns: s.turns ?? cur.turns,
    ctxTokens: s.ctx_tokens ?? cur.ctxTokens,
  })),
  setBusy: (v) => set({busy: v}),
  // slash_result cmd 별 개별 setter (A-5)
  setWorkingDir: (working_dir: string) => set({workingDir: working_dir}),
  setModel: (model: string) => set({model}),
  setMode: (mode: string) => set({mode}),
  setActiveTool: (name, args = null) => set({activeTool: name, activeToolArgs: args ?? null}),
}))
