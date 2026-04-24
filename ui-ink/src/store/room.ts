// 룸 슬라이스 (Phase 3 확장: wsState/reconnectAttempt/lastEventId — WSR-01~03)
import {create} from 'zustand'

interface RoomState {
  roomName: string
  members: string[]
  activeInputFrom: string | null  // turn-taking (BB-2-DESIGN)
  activeIsSelf: boolean
  busy: boolean
  // Phase 3 추가 (WSR-01~03)
  wsState: 'connected' | 'reconnecting' | 'failed'
  reconnectAttempt: number
  lastEventId: number | null
  // 기존 actions
  setRoom: (name: string, members: string[]) => void
  addMember: (user: string) => void
  removeMember: (user: string) => void
  setActiveInputFrom: (user: string | null) => void
  setActiveIsSelf: (v: boolean) => void
  setRoomBusy: (v: boolean) => void
  // Phase 3 신규 actions
  setWsState: (s: 'connected' | 'reconnecting' | 'failed') => void
  setReconnectAttempt: (n: number) => void
  setLastEventId: (id: number) => void
}

export const useRoomStore = create<RoomState>((set) => ({
  roomName: '',
  members: [],
  activeInputFrom: null,
  activeIsSelf: true,
  busy: false,
  // Phase 3 초기값
  wsState: 'connected',
  reconnectAttempt: 0,
  lastEventId: null,
  // 기존 actions (변경 없음)
  setRoom: (name, members) => set({roomName: name, members}),
  addMember: (user) => set((s) => ({members: [...s.members.filter(m => m !== user), user]})),
  removeMember: (user) => set((s) => ({members: s.members.filter(m => m !== user)})),
  setActiveInputFrom: (user) => set({activeInputFrom: user}),
  setActiveIsSelf: (v) => set({activeIsSelf: v}),
  setRoomBusy: (v) => set({busy: v}),
  // Phase 3 신규 actions
  setWsState: (s) => set({wsState: s}),
  setReconnectAttempt: (n) => set({reconnectAttempt: n}),
  setLastEventId: (id) => set({lastEventId: id}),
}))
