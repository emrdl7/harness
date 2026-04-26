#!/usr/bin/env bun
// harness ui-ink 진입점 (FND-12, FND-13, FND-14)
// TTY 가드, 시그널 핸들러, patchConsole: false
import React from 'react'
import {render} from 'ink'
// @ts-ignore: ink의 package.json exports에 노출되지 않은 내부 모듈 사용 (RND-09)
import {setStringWidthFunction} from '../node_modules/ink/build/measure-text.js'
import {App} from './App.js'
import {stringWidth} from './utils/stringWidth.js'
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

// async IIFE — one-shot 동적 import + await 지원 (SES-01/02/03)
;(async () => {
  if (!isInteractive) {
    // SES-01/02/03: argv 파싱
    const resumeIdx = process.argv.indexOf('--resume')
    const resumeId = resumeIdx > -1 ? process.argv[resumeIdx + 1] : undefined
    const roomIdx = process.argv.indexOf('--room')
    const roomName = roomIdx > -1 ? process.argv[roomIdx + 1] : process.env['HARNESS_ROOM']

    // query: '--' 접두사가 아니고 --room/--resume의 값이 아닌 첫 번째 인자
    const skipIndices = new Set<number>()
    if (roomIdx > -1) { skipIndices.add(roomIdx); skipIndices.add(roomIdx + 1) }
    if (resumeIdx > -1) { skipIndices.add(resumeIdx); skipIndices.add(resumeIdx + 1) }
    const query = process.argv.slice(2).find(
      (a, i) => !a.startsWith('--') && !skipIndices.has(i + 2),
    )

    // env var 우선 → config 파일 fallback
    let url = process.env['HARNESS_URL']
    let token = process.env['HARNESS_TOKEN']
    if (!url || !token) {
      const {loadConfig} = await import('./config.js')
      const fileCfg = loadConfig()
      if (fileCfg) {
        url = fileCfg.url
        token = fileCfg.token
        if (!roomName && fileCfg.room) process.env['HARNESS_ROOM'] = fileCfg.room
      }
    }
    if (!url || !token) {
      process.stderr.write('[harness] 연결 정보 없음 — env var(HARNESS_URL/HARNESS_TOKEN) 또는 ~/.harness/config.json 필요\n')
      process.exit(1)
    }

    if (query && !resumeId) {
      // SES-01/SES-03: one-shot (--room 조합 가능)
      const {runOneShot} = await import('./one-shot.js')
      await runOneShot({
        url,
        token,
        room: roomName,
        query,
        ansi: process.stdout.isTTY === true,
      })
      process.exit(0)
    } else if (resumeId) {
      // SES-02: --resume <id> — 세션 로드 후 REPL 모드 진입
      // ConnectOptions.resumeSession 필드를 통해 App.tsx에 전달
      process.env['HARNESS_RESUME_SESSION'] = resumeId
      // isInteractive를 우회하여 아래 render 블록으로 진행 (REPL 모드)
    } else {
      process.stderr.write('[harness] non-TTY 환경. HARNESS_URL / HARNESS_TOKEN 으로 연결하세요.\n')
      process.exit(0)
    }
  }

  // interactive 모드 argv 파싱 — --room, --nick
  const iRoomIdx = process.argv.indexOf('--room')
  if (iRoomIdx > -1 && process.argv[iRoomIdx + 1]) {
    process.env['HARNESS_ROOM'] = process.argv[iRoomIdx + 1]
  }
  const iNickIdx = process.argv.indexOf('--nick')
  if (iNickIdx > -1 && process.argv[iNickIdx + 1]) {
    process.env['HARNESS_NICK'] = process.argv[iNickIdx + 1]
  }

  // Ink의 기본 width 계산을 CJK가 지원되는 커스텀 stringWidth로 교체
  setStringWidthFunction(stringWidth)

  // 일반 터미널 모드 (Claude Code 식 스크롤백 지원)
  // 시작 전 화면 클리어 + 커서 홈으로 이동하여 프롬프트 잔상 방지
  process.stdout.write('\x1b[2J\x1b[3J\x1b[H')

  // 첫 배너를 터미널 상단에 일반 텍스트로 고정 출력 (RND-11)
  const banner = [
    '\n',
    '\x1b[1m\x1b[35m   / /_  ____ ________  ___  __________\x1b[0m',
    '\x1b[1m\x1b[94m  / __ \\/ __ `/ ___/ __ \\/ _ \\/ ___/ ___/\x1b[0m',
    '\x1b[1m\x1b[96m / / / / /_/ / /  / / / /  __(__  |__  )\x1b[0m',
    '\x1b[1m\x1b[36m/_/ /_/\\__,_/_/  /_/ /_/\\___/____/____/\x1b[0m',
    '\x1b[2m\x1b[37m  jabworks · harness v1.0\x1b[0m\n\n'
  ].join('\n')
  process.stdout.write(banner)

  render(<App />, {patchConsole: false})
})()
