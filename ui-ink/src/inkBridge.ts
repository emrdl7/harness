// Ink 인스턴스 브릿지 — Ink active 영역 위쪽 stdout 에 안전하게 출력
// 직접 writeToStdout 을 쓰지 않는 이유: 그 안의 restoreLastOutput 이 OLD frame
// (stream 중인 active 포함)을 다시 그려서 viewport 넘으면 dividers 가 스크롤백에 박힘.
// 대신: log.clear() 로 active 만 지우고 raw write, lastOutput 리셋 → Ink 다음 render
// 가 cursor 위치에 깨끗한 새 frame 을 그림.
// instances 는 비공개 WeakMap → 직접 상대 경로 import (exports 우회)
// @ts-ignore
import instances from '../node_modules/ink/build/instances.js'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getInk(): any | null {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (instances as WeakMap<object, any>).get(process.stdout) ?? null
}

export function inkWriteAbove(data: string): void {
  const inst = getInk()
  if (inst?.log?.clear && inst?.options?.stdout) {
    // 1) Ink active 영역 erase (previousLineCount 도 0 으로 리셋)
    inst.log.clear()
    // 2) 우리 데이터 write — 현재 cursor (active 가 시작했던 위치) 부터 자연스럽게 누적
    inst.options.stdout.write(data)
    // 3) Ink 의 lastOutput 무효화 → 다음 render 가 깨끗하게 다시 그림 (restore 안 함)
    inst.lastOutput = ''
    inst.lastOutputToRender = ''
    return
  }
  // fallback — Ink 인스턴스 못 찾으면 raw write (테스트 환경 등)
  // eslint-disable-next-line no-restricted-syntax
  process.stdout.write(data)
}

export function inkClearScreen(): void {
  inkWriteAbove('\x1b[2J\x1b[H')
}
