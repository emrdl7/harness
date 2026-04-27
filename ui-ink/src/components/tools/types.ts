// AR-01: tool 컴포넌트 공통 타입
// Pi Mono 의 renderResult(args, payload) 패턴을 React 컴포넌트로 구현
// 백엔드 harness_server.py:251 가 dict 그대로 broadcast — payload 는 tool 마다 다른 dict
//
// 새 tool 추가 절차:
//   1. tools/<MyToolBlock>.tsx 작성 — props: ToolBlockProps
//   2. tools/index.ts 의 TOOL_REGISTRY 에 한 줄 추가
// (Message.tsx 손댈 일 없음 — registry lookup 자동)
import type React from 'react'

export interface ToolBlockProps {
  name: string                              // tool 이름 (registry 키)
  args?: Record<string, unknown>            // tool_start 시 인자 (없을 수 있음 — snapshot 로드 등)
  payload?: unknown                         // tool_end 시 결과 dict (streaming 중엔 undefined)
  streaming?: boolean                       // 진행 중 여부
  fallbackContent?: string                  // registry 미사용 시의 content (snapshot 호환용)
}

export type ToolBlockComponent = React.FC<ToolBlockProps>
