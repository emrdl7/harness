#!/usr/bin/env bash
# CI 가드: alternate screen(ESC[?1049h) / mouse tracking(ESC[?1000h 계열) 금지 (FND-11)
# harness CLAUDE.md 절대 금지 목록 자동 검증

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")/src"

RESULT=$(grep -rn $'\x1b\[\?1049\|\x1b\[\?1000\|\x1b\[\?1002\|\x1b\[\?1003\|\x1b\[\?1006' "$SRC_DIR" 2>/dev/null || true)

if [ -n "$RESULT" ]; then
  echo "오류: alternate screen 또는 mouse tracking escape 코드 발견"
  echo "$RESULT"
  exit 1
fi

# 문자열 리터럴로도 검색
RESULT2=$(grep -rn '1049h\|1000h\|?1002\|?1003\|?1006\|smcup\|rmcup' "$SRC_DIR" 2>/dev/null || true)

if [ -n "$RESULT2" ]; then
  echo "오류: alternate screen 관련 패턴 발견"
  echo "$RESULT2"
  exit 1
fi

echo "OK: alternate screen / mouse tracking escape 코드 없음"
