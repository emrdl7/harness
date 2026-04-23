# harness-ink

Claude Code 스타일 TUI — **Ink + React + Zustand + bun + TypeScript**.

## 배경

Python (prompt_toolkit / Rich.Live) 로는 Claude Code 의 Ink-based UX 를 제대로
재현할 수 없다는 결론 (resize 시 wrap 추적 불가, 이중 버퍼링 없음).
Claude Code 와 동일한 스택으로 UI 층을 재작성.

기존 Python 백엔드 (`harness_server.py`, `agent.py`, `tools/`, `session/`,
`evolution/`) 는 그대로 유지하고 WS 로 연결. 필요 시 점진적 포팅.

## Setup

```bash
cd ui-ink
bun install
HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=... bun start
```

환경변수:
- `HARNESS_URL` — harness_server.py WebSocket 주소
- `HARNESS_TOKEN` — 서버 `HARNESS_TOKENS` 중 하나
- `HARNESS_ROOM` — 공유 룸 이름(선택)

## 구조

```
src/
  index.tsx   Ink render 진입점
  App.tsx     메인 레이아웃 (message list + input + status bar)
  store.ts    Zustand 글로벌 상태 (messages / input / status / busy)
  ws.ts       harness_server.py WebSocket 클라이언트
```

## 현 상태 (2026-04-23 세션)

스켈레톤만. 다음 세션에 GSD plan → implement 로 제대로 채울 항목:
- slash 명령 popup / 자동완성
- 멀티라인 입력 (Shift+Enter / Ctrl+J)
- confirm_write / confirm_bash 다이얼로그
- tool 결과 렌더 (diff Panel, Syntax highlight, Write 요약)
- ctx bar / mode / turn 등 status bar 세그먼트
- 스크롤 (PgUp/PgDn / 마우스 휠)
- 리모트 룸 (member list, busy 표시)
- one-shot / resume 모드
