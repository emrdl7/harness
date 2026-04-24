// 입력 슬라이스 — buffer + history + slashOpen + 파일 persistence (INPT-03, RND-05)
import {create} from 'zustand'
import {readFileSync, appendFileSync, mkdirSync, existsSync} from 'node:fs'
import {homedir} from 'node:os'
import {join, dirname} from 'node:path'

const HISTORY_MAX = 500
// ~/.harness/history.txt — Python REPL 과 동일 경로 (INPT-03)
export const HISTORY_PATH = join(homedir(), '.harness', 'history.txt')

// 파일에서 history 를 읽어 "오래된 → 최신" 배열로 반환.
// 파일 형식: 한 줄당 한 항목, 가장 위가 오래된 것 (append 로 쌓이므로 자연스러움).
// 반환 배열 순서: oldest first, 최대 HISTORY_MAX 개로 truncate.
export function loadHistory(): string[] {
  try {
    if (!existsSync(HISTORY_PATH)) return []
    const raw = readFileSync(HISTORY_PATH, 'utf8')
    const lines = raw.split('\n').filter((l) => l.length > 0)
    // 파일이 MAX 초과로 커졌을 때는 뒤쪽(최신) 500개만 사용
    return lines.slice(-HISTORY_MAX)
  } catch {
    // 읽기 실패는 치명적이지 않음 — 세션은 빈 history 로 계속
    return []
  }
}

// history.txt 에 한 줄 추가. 디렉터리 없으면 생성. 실패해도 swallow.
export function appendHistory(text: string): void {
  try {
    const dir = dirname(HISTORY_PATH)
    if (!existsSync(dir)) mkdirSync(dir, {recursive: true})
    // trailing newline 포함 — Python readline 포맷 호환
    appendFileSync(HISTORY_PATH, text + '\n', 'utf8')
  } catch {
    // 디스크 full / 권한 문제 등 — UI 는 계속 동작
  }
}

interface InputState {
  buffer: string
  history: string[]         // 오래된 → 최신 순
  historyIndex: number      // -1 = 미선택 (buffer 편집 중)
  slashOpen: boolean
  setBuffer: (v: string) => void
  clearBuffer: () => void
  pushHistory: (entry: string) => void
  historyUp: () => void     // 이전 history 를 buffer 에 로드
  historyDown: () => void   // 최신 방향으로 이동
  setSlashOpen: (open: boolean) => void
  hydrate: () => void       // 마운트 시 1회 — history.txt 로드
}

export const useInputStore = create<InputState>((set, get) => ({
  buffer: '',
  history: [],
  historyIndex: -1,
  slashOpen: false,

  setBuffer: (v) => set({buffer: v}),
  clearBuffer: () => set({buffer: '', historyIndex: -1}),

  pushHistory: (entry) => {
    const trimmed = entry.trim()
    if (!trimmed) return
    const state = get()
    // 직전 항목과 동일하면 파일에도 쓰지 않고 skip
    if (state.history[state.history.length - 1] === trimmed) {
      set({historyIndex: -1})
      return
    }
    const next = [...state.history, trimmed]
    if (next.length > HISTORY_MAX) next.shift()
    set({history: next, historyIndex: -1})
    // 파일 persistence — 실패해도 메모리 상태는 유지됨
    appendHistory(trimmed)
  },

  historyUp: () => set((s) => {
    if (s.history.length === 0) return {}
    const nextIdx = Math.min(s.historyIndex + 1, s.history.length - 1)
    const entry = s.history[s.history.length - 1 - nextIdx]
    return {historyIndex: nextIdx, buffer: entry ?? ''}
  }),

  historyDown: () => set((s) => {
    if (s.historyIndex <= 0) {
      return {historyIndex: -1, buffer: ''}
    }
    const nextIdx = s.historyIndex - 1
    const entry = s.history[s.history.length - 1 - nextIdx]
    return {historyIndex: nextIdx, buffer: entry ?? ''}
  }),

  setSlashOpen: (open) => set({slashOpen: open}),

  // App.tsx 마운트 시 useEffect 에서 1회 호출 — history.txt 를 메모리로 로드
  hydrate: () => {
    const loaded = loadHistory()
    if (loaded.length > 0) {
      set({history: loaded, historyIndex: -1})
    }
  },
}))
