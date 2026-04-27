# harness — Milestones

---

## v1.1 — Client-side Tool Execution (in progress)

**Started:** 2026-04-27
**Status:** Active — design doc 확정, phase planning 대기

### Why

v1.0 의 "하나의 백엔드 공유" 협업 모델이 사용자 의도 (*"Claude Code 처럼"*, *"LLM 만 공유, 도구는 각자 PC"*) 와 어긋났음 (2026-04-27 발화로 확인). 도구가 서버 측에서 도는 결과 외부 사용자가 자기 PC 코드를 작업할 수 없는 상태. 이를 정정한다.

### Plan

- 도구 실행을 클라 측으로 RPC 위임 (fs/shell/git/MCP). 서버는 web/claude_cli/improve 만 보유
- BB-2 코드 (Room/broadcast/presence/active_input_from/snapshot/who) 일괄 deletion — 사용자 요구 외 기능
- pytest fs/shell/git ~70건 → vitest 동등 변환
- RX-02 세션 위치 클라 측 이전, MCP 클라 측 이전

### Reference

- `.planning/PROJECT.md` — milestone 정의 (v1.1)
- `.planning/CLIENT-TOOLS-DESIGN.md` — design ground truth

---

## v1.0 — ui-ink UI 재작성

**Shipped:** 2026-04-24
**Phases:** 5 | **Plans:** 22 | **Commits:** 237
**Timeline:** 2026-04-22 → 2026-04-24 (3 days)
**Files:** 182 changed, +34,977 / -3,142 LOC
**Tests:** pytest 224건 · vitest 163건 green

### Delivered

Python(prompt_toolkit+Rich) UI 층을 Node+Ink+Zustand+bun+TypeScript 로 전면 재작성. 로컬·원격 2인이 동일한 ui-ink 클라이언트를 공유하고, Python REPL 잔재 5,440줄을 완전 삭제.

### Key Accomplishments

1. **Foundation** — ink@7·react@19.2·zustand@5 bump, WS 프로토콜 정합성 복구 (protocol.ts discriminated union), HarnessClient, ESLint 금지 규칙, CI escape 가드
2. **Core UX** — 스트리밍 렌더·MultilineInput·SlashPopup 13종·ToolCard·DiffPreview·ConfirmDialog·StatusBar 전 세그먼트 — 로컬 Python REPL 완전 대체
3. **Remote Room** — PEXT-01~05 WS 확장, PresenceSegment·ReconnectOverlay·ObserverOverlay, jitter backoff, one-shot/resume, 로컬+원격 3 클라 동일 경험
4. **Testing + Docs** — Fake WS 통합 테스트 6종, CI matrix, PROTOCOL.md·CLIENT_SETUP.md·RELEASE_NOTES.md, CR-01 수정
5. **Legacy Deletion** — cli/ 9종 + main.py + ui/index.js 삭제, pytest 224건·vitest 163건 green 유지, PROJECT.md Validated 확정

### Known Deferred Items at Close: 3
(see STATE.md Deferred Items — SC-2 Presence 멀티 터미널 검증, Phase 01/03 VERIFICATION human_needed 잔재)

### Archive

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`

---
