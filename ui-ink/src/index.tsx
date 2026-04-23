// harness ui-ink 진입점 (FND-12, FND-13, FND-14)
// TTY 가드, 시그널 핸들러, patchConsole: false
import React from 'react'
import {render} from 'ink'
import {App} from './App.js'
import {isInteractiveTTY} from './tty-guard.js'

// TTY 가드 — non-TTY 환경(파이프, CI)이거나 argv 에 질문이 있으면 one-shot 분기 (FND-12)
const isInteractive = isInteractiveTTY(process.stdin)

// 시그널/예외 클린업 헬퍼 (FND-13)
function cleanup(code = 1): never {
  try {
    // 커서 복원 — Ink 종료 후 터미널 복구용 (Ink 렌더 바깥, eslint 예외)
    // eslint-disable-next-line no-restricted-syntax
    process.stdout.write('\x1b[?25h')
    // raw mode 해제
    if (typeof process.stdin.setRawMode === 'function') {
      process.stdin.setRawMode(false)
    }
    // stdin 일시 정지
    process.stdin.pause()
  } catch {
    // cleanup 자체의 에러는 무시 — 진단 루프 방지
  }
  process.exit(code)
}

process.on('uncaughtException', (err) => {
  process.stderr.write(`[harness] uncaughtException: ${err.message}\n`)
  cleanup(1)
})

process.on('unhandledRejection', (reason) => {
  process.stderr.write(`[harness] unhandledRejection: ${reason}\n`)
  cleanup(1)
})

process.on('SIGHUP',  () => cleanup(0))
process.on('SIGTERM', () => cleanup(0))
// SIGINT: cleanup() 후 exit — Ink 핸들러보다 먼저 등록해 터미널 상태 복원 (FND-13)
process.on('SIGINT',  () => cleanup(0))

if (!isInteractive) {
  // One-shot 경로 (FND-12) — Phase 3 에서 실제 WS 연결 + stdout 출력으로 확장
  const query = process.argv[2]
  if (query) {
    // eslint-disable-next-line no-restricted-syntax
    process.stdout.write(`[one-shot] ${query}\n`)
  } else {
    process.stderr.write('[harness] non-TTY 환경. HARNESS_URL / HARNESS_TOKEN 으로 연결하세요.\n')
  }
  process.exit(0)
}

// Ink render — patchConsole: false (FND-14)
// alternate screen 비활성: 별도 옵션 없이 기본 Ink 는 inline 렌더
render(<App />, {patchConsole: false})
