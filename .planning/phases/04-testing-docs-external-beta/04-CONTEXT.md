# Phase 4: Testing + Docs + External Beta — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1~3에서 구현된 기능의 **품질을 자동 검증**하고, 외부 2인 beta를 위한 **준비 자료를 완성**한다. Legacy 삭제(Phase 5) 전 마지막 게이트.

- **In scope**: 통합 테스트(Fake WS 서버) · 회귀 스냅샷 · CI matrix(ubuntu + macOS) · PITFALLS 17항목 수동 체크리스트 · CLIENT_SETUP.md 재작성 · PROTOCOL.md 신규 작성 · 릴리스 노트
- **Out of scope**: 실제 외부 beta 실행(하드웨어 미준비 — 준비 자료만 완성) · Legacy 삭제(Phase 5) · 신규 기능 추가

</domain>

<decisions>
## Implementation Decisions

### 통합 테스트 아키텍처 (TST-02)

- **D-01: Fake WS 서버 구현** — `ws` 라이브러리로 in-process 실제 WS 서버를 랜덤 포트로 기동. vi.mock() 기반 이벤트 주입이 아닌 실제 TCP 핸드셰이크 방식. reconnect delta 및 3인 동시 재접속 시나리오 신뢰도를 위해 선택.
- **D-02: 테스트 파일 위치** — 기존 `src/__tests__/` 패턴 유지. 통합 테스트도 동일 디렉토리에 `integration.*.test.ts(x)` 명명 규칙으로 구분.
- **D-03: 서버 lifecycle** — `beforeAll` / `afterAll` 에서 Fake 서버 start/stop. 각 테스트는 포트 고정 없이 랜덤 할당.

### CI matrix (TST-04)

- **D-04: OS matrix** — ubuntu-latest + macOS-latest 양쪽. beta 사용자가 mac + Windows WSL이므로 ubuntu가 WSL 호환 커버, macOS가 mac 커버.
- **D-05: 런타임 matrix** — bun (최신) + Node 22 양쪽. REQUIREMENTS.md TST-04: "bun + Node 22 양쪽 green" 명시.
- **D-06: 파일 위치** — `.github/workflows/ci.yml` 레포 root 단일 파일. ui-ink vitest + Python pytest 260건 + tsc --noEmit + ESLint guard + ci-no-escape 전부 포함.
- **D-07: 트리거** — `push` + `pull_request` (main 브랜치). 별도 nightly 없음.

### 문서 (TST-06/07)

- **D-08: CLIENT_SETUP.md 타겟** — 최소화 원칙. `git clone → bun install --frozen-lockfile → env var 3개 → bun start` 까지만. 트러블슈팅·IME 섹션 생략. 사용자가 직접 구두 설명 예정이므로 문서는 명령어 위주로.
- **D-09: PROTOCOL.md 포맷** — AI 에이전트 친화적. 이벤트별 TypeScript interface/JSON schema 수준의 타입 정의 + 필드 설명. 시퀀스 다이어그램 없이 데이터 형상 중심. Claude/Codex가 파싱하여 구현할 수 있는 밀도.
- **D-10: 릴리스 노트 (TST-09)** — "Python REPL 대비 달라진 점" 항목 중심. 마이그레이션 관점(히스토리 파일 위치·포맷 호환 등) 포함.

### Beta 준비 범위 (TST-08)

- **D-11: Phase 4 범위** — CLIENT_SETUP.md + PITFALLS 17항목 체크리스트 완성까지. 실제 외부 2인 beta 실행은 하드웨어 준비 후 수동 진행 (Phase 4 성공 기준에 실제 beta 실행 포함하지 않음).
- **D-12: Beta 대상** — mac 1인 + Windows WSL 1인. CI matrix와 동일한 OS 조합.

### Claude's Discretion

- **TST-01 기존 단위 테스트 보완** — 어떤 항목이 아직 REQUIREMENTS.md 대비 미커버인지 분석 후 추가 판단 (MultilineInput 키 시퀀스 일부, TTY 가드 등 이미 존재).
- **TST-03 회귀 스냅샷** — 500 토큰 스트리밍·한국어+emoji wrap·resize 200↔40·`/undo`+새 메시지 스냅샷을 ink-testing-library render() output 기반으로 구현. 구체적 assertion 방식은 Claude 판단.
- **TST-05 수동 체크리스트 포맷** — PITFALLS.md 17항목을 Phase 4 산출물에 어떻게 구조화할지(별도 파일 vs VERIFICATION.md 통합) Claude 판단.
- **Python pytest 기준** — REQUIREMENTS.md에 199건 명시되어 있으나 현재 260건. 기준은 "현재 통과 건수 유지" (회귀 없음).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 요구사항 및 성공 기준

- `.planning/REQUIREMENTS.md` §TST-01..09 — Phase 4 전체 9개 요구사항 정의
- `.planning/ROADMAP.md` Phase 4 section — 5개 Success Criteria (SC-1..5)

### 테스트 인프라

- `ui-ink/src/__tests__/` — 기존 21개 테스트 파일 (패턴 확인 후 확장)
- `ui-ink/src/__tests__/ws-backoff.test.ts` — 기존 backoff 테스트 (mock 패턴 참조)
- `ui-ink/src/__tests__/dispatch.test.ts` — dispatch 테스트 패턴 참조

### 버그 및 검증 기준

- `.planning/research/PITFALLS.md` §"Looks Done But Isn't" — 17항목 수동 체크리스트
- `.planning/phases/03-remote-room-session-control/03-VERIFICATION.md` — CR-01 이슈: `confirm.ts:61 accept` vs `harness_server.py:782 result` 불일치 (Phase 4 TST-02에서 통합 테스트 자동 발견 예정)

### 프로토콜 및 서버

- `harness_server.py` — 실제 WS 서버 구현 (Fake 서버 설계 시 참조)
- `ui-ink/src/protocol.ts` — 23+ ServerMsg discriminated union (PROTOCOL.md 작성 소스)
- `ui-ink/src/ws/client.ts` — HarnessClient (통합 테스트 대상)
- `.planning/BB-2-DESIGN.md` — Room·turn-taking·confirm 격리 설계 (WS 프로토콜 ground truth)

### 기존 문서 (재작성 대상)

- `CLIENT_SETUP.md` — 현재 Node.js/`ui/` 기준 구버전 (재작성 필요)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `ui-ink/src/__tests__/` — 21개 테스트 파일, 146건 통과. 통합 테스트를 같은 디렉토리에 추가.
- `ui-ink/scripts/ci-no-escape.sh` — CI escape guard 스크립트 (기존 CI에 포함)
- `ui-ink/scripts/guard-forbidden.sh` — 금지 패턴 guard (bun run guard)
- `ui-ink/package.json` scripts: `test`, `typecheck`, `lint`, `ci:no-escape`, `guard`, `ci` — CI yml에서 직접 호출

### Established Patterns

- vitest 4 + bun + ink-testing-library 4 (Phase 1~3 확립)
- `src/__tests__/` 단일 디렉토리 구조
- `beforeAll` / `afterAll` 패턴 (`ws-backoff.test.ts` 참조)
- Python tests: `.venv/bin/python -m pytest -x --tb=short` (현재 260건 통과)

### Integration Points

- Fake WS 서버 → `HarnessClient` (ws/client.ts) 연결 테스트
- CI: Python pytest는 레포 root에서, ui-ink tests는 `cd ui-ink && bun run ci` 로 분리 실행

</code_context>

<specifics>
## Specific Ideas

- **CR-01 자동 발견**: TST-02 통합 테스트에서 `confirm_write accept` 시나리오 실행 시 CR-01 버그(accept vs result 필드 불일치)가 자동으로 잡혀야 함. 이 테스트가 실패로 떠야 정상.
- **PROTOCOL.md 대상**: Claude, Codex 같은 AI가 읽고 새 클라이언트를 구현할 수 있는 수준의 정밀도. 인간 독자는 부차적.
- **CLIENT_SETUP.md 간결성**: 명령어만. 설명 최소화. 사용자가 직접 구두 설명할 것이므로 "why"는 생략.

</specifics>

<deferred>
## Deferred Ideas

- **실제 외부 beta 실행** — 하드웨어 준비 후 수동 진행. Phase 4 성공 기준에서 제외.
- **릴리스 노트 히스토리 마이그레이션 스크립트** — `~/.harness/history.txt` 포맷 변환 스크립트는 필요 시 별도 Phase로.
- **바이너리 배포 prototype (D2-04)** — `bun build --compile` 단일 실행파일. v2 요구사항, 이번 Phase 범위 외.

</deferred>

---

*Phase: 04-testing-docs-external-beta*
*Context gathered: 2026-04-24*
