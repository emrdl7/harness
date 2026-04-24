// ~/.harness/config.json 읽기/쓰기 — 토큰·서버 URL 영속
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'fs'
import {homedir} from 'os'
import {join} from 'path'

const CONFIG_DIR = join(homedir(), '.harness')
const CONFIG_FILE = join(CONFIG_DIR, 'config.json')

export interface HarnessConfig {
  url: string
  token: string
  room?: string
}

export function loadConfig(): HarnessConfig | null {
  try {
    if (!existsSync(CONFIG_FILE)) return null
    const raw = readFileSync(CONFIG_FILE, 'utf-8')
    const parsed = JSON.parse(raw)
    if (parsed.url && parsed.token) return parsed as HarnessConfig
    return null
  } catch {
    return null
  }
}

export function saveConfig(cfg: HarnessConfig): void {
  if (!existsSync(CONFIG_DIR)) mkdirSync(CONFIG_DIR, {recursive: true})
  writeFileSync(CONFIG_FILE, JSON.stringify(cfg, null, 2), {mode: 0o600})
}

export function configPath(): string {
  return CONFIG_FILE
}
