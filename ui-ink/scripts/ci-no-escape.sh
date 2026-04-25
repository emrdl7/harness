#!/usr/bin/env bash
# CI 가드: 소스 코드 내 raw alternate-screen escape 하드코딩 금지
# (Ink 의 alternateScreen 옵션 경유는 합법 — Claude Code 식 alt buffer 모드)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")/src"

# 문자열 리터럴 형태 (raw stdout.write 우회 차단)
RESULT=$(grep -rn '1049h\|1000h\|?1002\|?1003\|?1006\|smcup\|rmcup' "$SRC_DIR" 2>/dev/null || true)

if [ -n "$RESULT" ]; then
  echo "오류: raw alternate-screen / mouse-tracking escape 발견"
  echo "Ink 의 alternateScreen 옵션 경유로 사용할 것"
  echo "$RESULT"
  exit 1
fi

echo "OK: raw alt-screen escape 없음 (Ink 옵션 경유만 허용)"
