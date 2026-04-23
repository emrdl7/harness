#!/usr/bin/env bash
# harness 쉘 진입 스크립트 — 터미널 raw mode 안전망 (FND-15)
# crash 시 stty sane 으로 터미널 복구

# 쉘 종료 시(정상/비정상 모두) 터미널 상태 복원
trap 'stty sane 2>/dev/null || true' EXIT

# ui-ink 디렉토리가 스크립트 위치 기준
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bun run "$SCRIPT_DIR/src/index.tsx" "$@"
