#!/usr/bin/env bash
# 금지 패턴 CI 가드 — CLAUDE.md 절대 금지 사항
# index.tsx 는 Ink 렌더 바깥 진입점 — process.stdout.write 예외 허용
set -euo pipefail

cd "$(dirname "$0")/.."

FAIL=0

check() {
  local desc="$1"
  local pattern="$2"
  shift 2
  if grep -rnE "$pattern" src/ --include='*.ts' --include='*.tsx' "$@" >/dev/null 2>&1; then
    echo "FAIL: $desc"
    grep -rnE "$pattern" src/ --include='*.ts' --include='*.tsx' "$@" || true
    FAIL=1
  else
    echo "OK: $desc"
  fi
}

# process.stdout.write (테스트 파일 + index.tsx + one-shot.ts 제외 — Ink 바깥 진입점들)
check 'no process.stdout.write in components/stores' '\bprocess\.stdout\.write\b' \
  --exclude-dir=__tests__ \
  --exclude='index.tsx' \
  --exclude='one-shot.ts'

# console.log (테스트 파일 제외)
check 'no console.log (non-test)' '\bconsole\.log\b' --exclude-dir=__tests__

# child_process — 절대 금지
check 'no child_process import' "from ['\"]child_process['\"]"

# DOM 태그 (Ink 에는 없음)
check 'no <div>' '<div[ >]'
check 'no <span>' '<span[ >]'

# alternate screen / mouse tracking escapes (소스 코드 내 하드코딩 금지)
check 'no alternate screen escape (1049h)' '\\\\x1b\[\\\\?1049h'
check 'no mouse tracking escape (1000h)'   '\\\\x1b\[\\\\?100[0-3]h'

if [[ $FAIL -eq 1 ]]; then
  echo ''
  echo '금지 패턴이 감지되었습니다. CLAUDE.md 참조.'
  exit 1
fi
echo ''
echo '모든 금지 패턴 체크 통과.'
