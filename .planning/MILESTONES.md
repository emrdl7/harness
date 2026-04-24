# harness — Milestones

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
