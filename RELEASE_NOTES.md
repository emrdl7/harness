# Release Notes — ui-ink v1

**날짜:** 2026-04-24
**대상:** 기존 Python REPL (`main.py`) 사용자

## Python REPL 대비 달라진 점

### 실행 방법

| | Python REPL | ui-ink |
|--|--|--|
| 실행 | `python main.py` | `cd ui-ink && bun start` |
| 환경 설정 | `config.yaml` | 환경변수 |
| 원격 접속 | 미지원 | `HARNESS_ROOM=팀룸이름 bun start` |

### 키 바인딩

| 기능 | Python REPL | ui-ink |
|------|-------------|--------|
| 제출 | Enter | Enter |
| 개행 | Alt+Enter | Ctrl+J (또는 Shift+Enter) |
| 줄 처음/끝 | Ctrl+A / Ctrl+E | 동일 |
| 줄 전체 삭제 | Ctrl+U | 동일 |
| 단어 삭제 | Ctrl+W | 동일 |
| 히스토리 | ↑ / ↓ | 동일 |
| 에이전트 취소 | Ctrl+C | Ctrl+C (첫 번째) |
| 종료 | Ctrl+C 반복 | Ctrl+D (빈 입력) 또는 Ctrl+C 2회 |

### 히스토리 파일 호환

- **위치:** `~/.harness/history.txt`
- **Python REPL과 동일한 포맷** — 마이그레이션 없이 즉시 호환

### 새로 생긴 기능

- **공유 Room** — `HARNESS_ROOM` 으로 여러 사용자가 동일 세션 참여 및 관전
- **자동 재연결** — 서버 재시작 시 jitter backoff 재연결 + delta 이벤트 복구
- **Diff 미리보기** — `confirm_write` 시 기존 파일 대비 diff ± 표시
- **슬래시 팝업** — `/` 입력 시 실시간 필터 팝업 메뉴
- **one-shot** — `echo "질문" | bun start` (REPL 없이 즉시 응답)

### 없어진 것

- `config.yaml` 파일 → 환경변수로 대체
- `/theme` 명령 → v2 계획

## 알려진 버그

- **CR-01**: `confirm_write` 승인(y) 시 서버가 거부로 처리함.
  - 원인: `harness_server.py:782`가 `result` 필드를 읽지만 클라이언트는 `accept` 필드 전송
  - 임시 대응: 서버에서 `msg.get('result', msg.get('accept', False))` 로 수정 예정

## 업그레이드 경로

1. `git pull && cd ui-ink && bun install --frozen-lockfile`
2. 기존 `~/.harness/history.txt` 그대로 유지 (자동 호환)
3. `config.yaml` 설정 → 환경변수(`HARNESS_URL`, `HARNESS_TOKEN`)로 이전
