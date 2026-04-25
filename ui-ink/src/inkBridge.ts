// Ink 인스턴스 브릿지 — writeToStdout 으로 완료 메시지를 Ink 영역 위에 출력
// Ink 의 writeToStdout: log.clear() → 데이터 write → restoreLastOutput() (Ink active 보존)
// instances 는 비공개 WeakMap → 직접 상대 경로로 접근 (exports 우회)
// @ts-ignore
import instances from '../node_modules/ink/build/instances.js'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getInk(): any | null {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (instances as WeakMap<object, any>).get(process.stdout) ?? null
}

// 완료 메시지를 Ink active 영역 위에 안전하게 출력
// Ink 가 active 영역을 지운 뒤 데이터 write, 다시 active 복원
export function inkWriteAbove(data: string): void {
  const inst = getInk()
  if (inst?.writeToStdout) {
    inst.writeToStdout(data)
    return
  }
  // fallback — Ink 인스턴스 못 찾으면 raw write (테스트 환경 등)
  // eslint-disable-next-line no-restricted-syntax
  process.stdout.write(data)
}

// 화면 전체 클리어 (스냅샷 reload 등) — Ink active 는 restoreLastOutput 이 다시 그림
export function inkClearScreen(): void {
  inkWriteAbove('\x1b[2J\x1b[H')
}
