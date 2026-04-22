import readline from 'readline'
import WebSocket from 'ws'
import os from 'os'
import path from 'path'

const PORT = process.env.HARNESS_PORT || '7891'
const MODEL = 'qwen2.5-coder:32b'

// ── ANSI ─────────────────────────────────────────────────────────
const C = {
  reset:  '\x1b[0m',
  dim:    '\x1b[2m',
  bold:   '\x1b[1m',
  cyan:   '\x1b[36m',
  yellow: '\x1b[33m',
  green:  '\x1b[32m',
  red:    '\x1b[31m',
  orange: '\x1b[38;2;212;162;127m',
  lblue:  '\x1b[38;2;111;179;210m',
}

const TOOL_META = {
  read_file:    { label: 'Read',      color: C.cyan,   arg: a => a.path || '' },
  write_file:   { label: 'Write',     color: C.yellow, arg: a => a.path || '' },
  edit_file:    { label: 'Edit',      color: C.yellow, arg: a => a.path || '' },
  grep_search:  { label: 'Grep',      color: C.cyan,   arg: a => a.pattern || '' },
  list_files:   { label: 'Glob',      color: C.cyan,   arg: a => a.pattern || '' },
  run_command:  { label: 'Bash',      color: C.green,  arg: a => (a.command || '').slice(0, 60) },
  run_python:   { label: 'Python',    color: C.green,  arg: a => (a.code || '').split('\n')[0].slice(0, 60) },
  git_status:   { label: 'Git',       color: C.green,  arg: () => 'status' },
  git_diff:     { label: 'Git',       color: C.green,  arg: a => 'diff' + (a.staged ? ' --staged' : '') },
  git_log:      { label: 'Git',       color: C.green,  arg: a => `log -${a.n || 10}` },
  git_diff_full:{ label: 'Git',       color: C.green,  arg: () => 'diff HEAD' },
  search_web:   { label: 'WebSearch', color: C.cyan,   arg: a => (a.query || '').slice(0, 60) },
  fetch_page:   { label: 'WebFetch',  color: C.cyan,   arg: a => (a.url || '').slice(0, 60) },
}

function shortDir(dir) {
  const home = os.homedir()
  if (dir.startsWith(home)) dir = '~' + dir.slice(home.length)
  const parts = dir.split(path.sep)
  return parts.length > 3 ? ['…', ...parts.slice(-2)].join(path.sep) : dir
}

function toolHint(name, result) {
  if (!result.ok) return (result.error || result.stderr || '').toString().slice(0, 80)
  if (name === 'read_file') {
    const total = result.total_lines ?? (result.content || '').split('\n').length
    const start = result.start_line, end = result.end_line
    return (start && end && (start > 1 || end < total))
      ? `lines ${start}–${end} / ${total}`
      : `${total} lines`
  }
  if (name === 'write_file')  return 'saved'
  if (name === 'list_files')  return `${(result.files || []).length} files`
  if (name === 'run_command' || name === 'run_python') {
    const out = (result.stdout || result.stderr || '').trim()
    return out ? out.split('\n')[0].slice(0, 60) : `exit ${result.returncode ?? 0}`
  }
  if (name.startsWith('git_')) {
    const out = (result.output || result.stdout || '').trim()
    return out ? out.split('\n')[0].slice(0, 60) : 'ok'
  }
  return 'ok'
}

// ── 출력 헬퍼 ────────────────────────────────────────────────────
const out = process.stdout

// readline 프롬프트가 표시된 줄을 지우고 커서를 앞으로
function clearPromptLine() {
  readline.clearLine(out, 0)
  readline.cursorTo(out, 0)
}

function println(text = '') {
  out.write(text + '\n')
}


// ── 상태 ─────────────────────────────────────────────────────────
let stateInfo     = { working_dir: process.env.HARNESS_CWD || process.cwd(), indexed: false, claude_available: false, compact_count: 0 }
let turns         = 0
let agentRunning  = false
let tokenBuf      = ''
let mode          = 'input'
let confirmPath   = ''
let confirmCmd    = ''
let cplanTask     = ''

// ── 스피너 ────────────────────────────────────────────────────────
const SPINNER_FRAMES = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
let spinnerTimer  = null
let spinnerIdx    = 0

function spinnerStart() {
  // 프롬프트 줄을 지우고 출력 영역에 스피너 줄 생성
  readline.clearLine(out, 0)
  readline.cursorTo(out, 0)
  out.write(`${C.cyan}⠋${C.reset}\n`)
  spinnerIdx = 1
  spinnerTimer = setInterval(() => {
    const frame = SPINNER_FRAMES[spinnerIdx++ % SPINNER_FRAMES.length]
    // 한 줄 위로 올라가 덮어쓰기
    out.write(`\x1b[1A\r\x1b[K${C.cyan}${frame}${C.reset}\n`)
  }, 80)
}

function spinnerStop() {
  if (!spinnerTimer) return
  clearInterval(spinnerTimer)
  spinnerTimer = null
  // 스피너 줄 지우고 커서를 그 자리에 둠 (이후 출력이 거기서 시작)
  out.write('\x1b[1A\r\x1b[K')
}

// ── 메시지 렌더러 ─────────────────────────────────────────────────
function printUserMsg(text) {
  println()
  println(`${C.cyan}${C.bold}❯${C.reset} ${text}`)
}

function flushStream() {
  spinnerStop()  // 스피너 줄 지우고 커서 그 자리
  if (tokenBuf.trim()) {
    println(`${C.orange}${C.bold}● ${MODEL}${C.reset}`)
    println(tokenBuf)
  }
  tokenBuf = ''
}

function printToolStart(name, args) {
  flushStream()
  const meta = TOOL_META[name] || { label: name, color: C.reset, arg: () => '' }
  const argStr = meta.arg(args || {})
  println(`${meta.color}${C.bold}● ${meta.label}${C.reset}${C.dim}(${argStr})${C.reset}`)
}

function printToolEnd(name, result) {
  const ok = result?.ok
  const hint = toolHint(name, result || {})
  if (ok) {
    println(`${C.dim}└ ${hint}${C.reset}`)
  } else {
    println(`${C.dim}└ ${C.reset}${C.red}${hint}${C.reset}`)
  }
}

function printSlashResult(cmd, data) {
  switch (cmd) {
    case 'clear':   println(`${C.dim}  대화 초기화${C.reset}`); break
    case 'undo':    println(`${C.dim}  ${data.ok ? '취소됨' : '취소할 내용 없음'}${C.reset}`); break
    case 'save':    println(`${C.green}  ✓ ${data.filename}${C.reset}`); break
    case 'resume':  println(data.ok !== false
                      ? `${C.green}  ✓ ${data.turns}턴 복원${C.reset}`
                      : `${C.yellow}  불러올 세션 없음${C.reset}`); break
    case 'index':   println(`${C.green}  ✓ ${data.indexed}개 청크${C.reset}`); break
    case 'cd':      println(`${C.dim}  → ${data.working_dir}${C.reset}`); break
    case 'init':    println(`${C.green}  ✓ ${data.path}${C.reset}`); break
    case 'learn':
    case 'improve': println(`${C.green}  ✓ 완료${C.reset}`); break
    case 'help':    printHelp(); break
    case 'files':   printFileTree(data.tree || {}); break
    case 'sessions':printSessions(data.sessions || []); break
    default:        println(`${C.dim}  /${cmd}${C.reset}`)
  }
}

function printHelp() {
  const cmds = [
    ['/clear','대화 초기화'], ['/undo','마지막 교환 취소'],
    ['/plan','플랜 후 실행'], ['/cplan','Claude 플랜 → 실행'],
    ['/index','인덱싱'],      ['/improve','자기 개선'],
    ['/learn','HARNESS.md'], ['/cd','디렉토리 변경'],
    ['/save','세션 저장'],    ['/resume','세션 불러오기'],
    ['/claude','Claude 질문'],['/quit','종료'],
  ]
  for (const [cmd, desc] of cmds) {
    println(`  ${C.cyan}${cmd.padEnd(12)}${C.reset}${C.dim}${desc}${C.reset}`)
  }
}

function fileTreeLines(node, prefix = '') {
  const lines = []
  for (let i = 0; i < (node.children || []).length; i++) {
    const child = node.children[i]
    const isLast = i === node.children.length - 1
    const isDir  = !!child.children
    lines.push({ text: prefix + (isLast ? '└── ' : '├── ') + child.name + (isDir ? '/' : ''), isDir })
    if (isDir) lines.push(...fileTreeLines(child, prefix + (isLast ? '    ' : '│   ')))
  }
  return lines
}

function printFileTree(tree) {
  println(`  ${C.cyan}${C.bold}${tree.name || ''}/  ${C.reset}`)
  for (const { text, isDir } of fileTreeLines(tree)) {
    println(`  ${isDir ? C.cyan : ''}${text}${C.reset}`)
  }
}

function printSessions(sessions) {
  if (!sessions.length) { println(`${C.dim}  저장된 세션 없음${C.reset}`); return }
  for (const s of sessions) {
    const name = s.filename.replace('.json', '').slice(0, 22).padEnd(23)
    println(`  ${C.cyan}${name}${C.reset}${C.dim}  ${shortDir(s.working_dir)}  ${s.turns}턴${C.reset}  ${s.preview}`)
  }
}

// ── 프롬프트 ─────────────────────────────────────────────────────
function buildPromptStr() {
  if (mode === 'confirm_write') return `${C.yellow}Write ${confirmPath}? (y/n) ${C.reset}`
  if (mode === 'confirm_bash')  return `${C.red}Run: ${confirmCmd}? (y/n) ${C.reset}`
  if (mode === 'cplan_confirm') return `${C.yellow}위 플랜 실행? (y/n) ${C.reset}`
  return `${C.cyan}${C.bold}❯ ${C.reset}`
}

function showPrompt() {
  const dir    = shortDir(stateInfo.working_dir || process.cwd())
  const idxTxt  = stateInfo.indexed ? 'indexed' : 'not indexed'
  const clTxt   = stateInfo.claude_available ? 'claude ✓' : 'claude ✗'
  const cmpTxt  = stateInfo.compact_count > 0 ? `  ·  compacted ×${stateInfo.compact_count}` : ''
  println(`${C.dim}  ${MODEL}  ·  ${dir}  ·  ${idxTxt}  ·  ${clTxt}  ·  turns: ${turns}${cmpTxt}${C.reset}`)
  rl.setPrompt(buildPromptStr())
  rl.prompt()
}

// ── WebSocket ────────────────────────────────────────────────────
const ws = new WebSocket(`ws://localhost:${PORT}`)

ws.on('error', () => {
  console.error(`\nharness server 연결 실패 (ws://localhost:${PORT})`)
  console.error('먼저: cd ~/harness && .venv/bin/python harness_server.py\n')
  process.exit(1)
})

ws.on('open', () => {
  ws.on('message', raw => {
    let msg
    try { msg = JSON.parse(raw.toString()) } catch { return }

    switch (msg.type) {
      case 'state':
        turns = msg.turns ?? 0
        stateInfo = msg
        break

      case 'ready':
        showPrompt()
        return

      case 'token':
        tokenBuf += msg.text
        break

      case 'agent_start':
        clearPromptLine()
        agentRunning = true
        tokenBuf = ''
        spinnerStart()
        break

      case 'agent_end':
        flushStream()
        agentRunning = false
        showPrompt()
        break

      case 'claude_start':
        tokenBuf = ''
        break

      case 'claude_token':
        tokenBuf += msg.text
        break

      case 'claude_end':
        if (tokenBuf.trim()) {
          println()
          println(`${C.lblue}${C.bold}● Claude${C.reset}`)
          println(tokenBuf)
        }
        tokenBuf = ''
        break

      case 'tool_start':
        flushStream()
        printToolStart(msg.name, msg.args || {})
        spinnerStart()
        break

      case 'tool_end':
        spinnerStop()
        printToolEnd(msg.name, msg.result || {})
        spinnerStart()
        break

      case 'confirm_write':
        flushStream()
        confirmPath = msg.path
        mode = 'confirm_write'
        showPrompt()
        break

      case 'confirm_bash':
        flushStream()
        confirmCmd = (msg.command || '').slice(0, 80)
        mode = 'confirm_bash'
        showPrompt()
        break

      case 'cplan_confirm':
        cplanTask = msg.task
        mode = 'cplan_confirm'
        showPrompt()
        break

      case 'info':
        clearPromptLine()
        println(`${C.dim}${msg.text}${C.reset}`)
        break

      case 'error':
        clearPromptLine()
        flushStream()
        println(`${C.red}● ${msg.text}${C.reset}`)
        if (!agentRunning) showPrompt()
        break

      case 'slash_result':
        printSlashResult(msg.cmd, msg)
        if (!agentRunning) showPrompt()
        break

      case 'quit':
        rl.close()
        ws.close()
        process.exit(0)
        break
    }
  })
})

// ── readline ─────────────────────────────────────────────────────
const rl = readline.createInterface({
  input:  process.stdin,
  output: process.stdout,
})

rl.on('line', line => {
  const text = line.trim()

  if (mode === 'confirm_write') {
    const ok = text.toLowerCase() === 'y' || text.toLowerCase() === 'yes'
    ws.send(JSON.stringify({ type: 'confirm_write_response', result: ok }))
    println(`${C.dim}  ${ok ? `✓ Write ${confirmPath}` : 'Write 취소'}${C.reset}`)
    mode = 'input'
    return
  }

  if (mode === 'confirm_bash') {
    const ok = text.toLowerCase() === 'y' || text.toLowerCase() === 'yes'
    ws.send(JSON.stringify({ type: 'confirm_bash_response', result: ok }))
    println(`${C.dim}  ${ok ? `✓ 실행: ${confirmCmd}` : 'Bash 취소'}${C.reset}`)
    mode = 'input'
    return
  }

  if (mode === 'cplan_confirm') {
    const ok = text.toLowerCase() === 'y' || text.toLowerCase() === 'yes'
    if (ok) ws.send(JSON.stringify({ type: 'cplan_execute', task: cplanTask }))
    else    println(`${C.dim}  취소${C.reset}`)
    mode = 'input'
    return
  }

  if (!text) { showPrompt(); return }

  // readline이 이미 입력 내용을 화면에 표시하므로 중복 출력 없이 빈 줄만 추가
  println()
  ws.send(JSON.stringify({ type: 'input', text }))
})

rl.on('close', () => {
  ws.close()
  process.exit(0)
})
