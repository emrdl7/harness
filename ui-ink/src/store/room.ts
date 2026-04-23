// 룸 슬라이스 (Phase 3 에서 확장 예정)
import {create} from 'zustand'

interface RoomState {
  roomName: string
  members: string[]
  activeInputFrom: string | null  // turn-taking (BB-2-DESIGN)
  activeIsSelf: boolean
  busy: boolean
  setRoom: (name: string, members: string[]) => void
  addMember: (user: string) => void
  removeMember: (user: string) => void
  setActiveInputFrom: (user: string | null) => void
  setActiveIsSelf: (v: boolean) => void
  setRoomBusy: (v: boolean) => void
}

export const useRoomStore = create<RoomState>((set) => ({
  roomName: '',
  members: [],
  activeInputFrom: null,
  activeIsSelf: true,
  busy: false,
  setRoom: (name, members) => set({roomName: name, members}),
  addMember: (user) => set((s) => ({members: [...s.members.filter(m => m !== user), user]})),
  removeMember: (user) => set((s) => ({members: s.members.filter(m => m !== user)})),
  setActiveInputFrom: (user) => set({activeInputFrom: user}),
  setActiveIsSelf: (v) => set({activeIsSelf: v}),
  setRoomBusy: (v) => set({busy: v}),
}))
