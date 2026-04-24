// 사용자 색 해시 유틸 (DIFF-04, REM-02)
// 결정론적 — 동일 토큰은 항상 동일 색 반환 (재접속 후에도 동일)
// 03-UI-SPEC.md §사용자 색 해시 규격

const PALETTE = ['cyan', 'green', 'yellow', 'magenta', 'blue', 'red', 'white', 'greenBright'] as const

// djb2 변형: 16비트 범위 유지
function _hash(token: string): number {
  return token.split('').reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) & 0xffff, 0)
}

export function userColor(token: string): string {
  // 자기 자신은 항상 cyan — 기존 user role 색과 통일 (03-UI-SPEC.md)
  const myToken = process.env['HARNESS_TOKEN'] ?? ''
  if (token === myToken || token === 'me') return 'cyan'
  return PALETTE[_hash(token) % PALETTE.length]
}
