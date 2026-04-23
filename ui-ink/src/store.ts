import {create} from 'zustand';

export interface Message {
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  meta?: Record<string, unknown>;
}

export interface StatusSegment {
  label: string;
  color?: string;
}

interface State {
  // agent 출력 / 사용자 입력 누적 로그
  messages: Message[];
  // 현재 입력 중인 텍스트
  input: string;
  // 하단 status bar 세그먼트들 (path · model · turn · mode · ctx 등)
  status: StatusSegment[];
  // agent 가 응답/툴 실행 중인지 여부 (spinner 표시용)
  busy: boolean;

  setInput: (v: string) => void;
  appendMessage: (m: Message) => void;
  clearMessages: () => void;
  setStatus: (s: StatusSegment[]) => void;
  setBusy: (b: boolean) => void;
}

export const useStore = create<State>((set) => ({
  messages: [],
  input: '',
  status: [{label: 'harness-ink', color: 'cyan'}],
  busy: false,

  setInput: (v) => set({input: v}),
  appendMessage: (m) => set((s) => ({messages: [...s.messages, m]})),
  clearMessages: () => set({messages: []}),
  setStatus: (s) => set({status: s}),
  setBusy: (b) => set({busy: b}),
}));
