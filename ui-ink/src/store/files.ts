// IX-01: @ 파일 픽커 캐시 — file_list_request 보내고 file_list_response 받으면 저장
import {create} from 'zustand'
import type {ClientMsg} from '../protocol.js'
import type {HarnessClient} from '../ws/client.js'

// confirm 슬라이스와 동일 패턴 — store → client 순환 의존 회피
let boundClient: HarnessClient | null = null
export function bindFilesClient(client: HarnessClient | null): void {
  boundClient = client
}

interface FileListState {
  files: string[]
  loaded: boolean             // 첫 응답 받음
  requested: boolean          // 요청 in-flight (중복 발송 회피)
  setFiles: (files: string[]) => void
  request: () => void         // 첫 호출만 실제 WS 발송, 이후는 캐시 재사용
  invalidate: () => void      // 캐시 무효화 (예: cwd 변경 시)
}

export const useFileListStore = create<FileListState>((set, get) => ({
  files: [],
  loaded: false,
  requested: false,

  setFiles: (files) => set({files, loaded: true, requested: false}),

  request: () => {
    const s = get()
    if (s.loaded || s.requested) return
    if (!boundClient) return
    set({requested: true})
    const msg: ClientMsg = {type: 'file_list_request'}
    boundClient.send(msg)
  },

  invalidate: () => set({files: [], loaded: false, requested: false}),
}))
