// 입력 슬라이스
import {create} from 'zustand'

interface InputState {
  buffer: string
  setBuffer: (v: string) => void
  clearBuffer: () => void
}

export const useInputStore = create<InputState>((set) => ({
  buffer: '',
  setBuffer: (v) => set({buffer: v}),
  clearBuffer: () => set({buffer: ''}),
}))
