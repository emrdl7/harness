// Ink 내부 frame counter 초기화 브릿지 — resize 시 좀비 방지
// ink/build/instances.js 는 exports 미공개 → 상대 경로로 직접 접근
// log.reset(): stdout 미출력, previousLineCount/cursorWasShown 만 0 으로 리셋
// @ts-ignore
import instances from '../node_modules/ink/build/instances.js'

export function resetInkLog(): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const inst = (instances as WeakMap<object, any>).get(process.stdout)
  inst?.log?.reset?.()
}
