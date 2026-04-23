// TTY 가드 유틸 — 테스트 가능한 독립 함수로 추출 (FND-12)
// index.tsx 에서 임포트해 사용

/**
 * 주어진 stdin 이 인터랙티브 TTY 인지 확인한다.
 * - isTTY 가 true 이고
 * - setRawMode 함수가 존재할 때만 true 반환
 */
export function isInteractiveTTY(stdin: NodeJS.ReadStream): boolean {
  return stdin.isTTY === true && typeof stdin.setRawMode === 'function'
}
