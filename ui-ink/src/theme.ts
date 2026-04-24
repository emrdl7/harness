// 색상 팔레트 — role/mode/status 별 일관된 색 (RND-10, RND-11)
// Ink 의 color prop 에 그대로 전달 가능한 문자열.

export const theme = {
  role: {
    user: 'cyan',
    assistant: 'yellow',
    tool: 'green',
    system: 'gray',
  },
  status: {
    connected: 'green',
    disconnected: 'red',
    busy: 'cyan',
  },
  mode: {
    agent: 'yellow',
    plan: 'magenta',
    review: 'blue',
    default: 'white',
  },
  danger: {
    safe: 'green',
    dangerous: 'red',
  },
  muted: 'gray',
} as const

export type RoleColor = keyof typeof theme.role
