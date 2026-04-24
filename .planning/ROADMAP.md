# harness — ui-ink Milestone Roadmap

**Generated:** 2026-04-23
**Source:** `.planning/PROJECT.md` + `.planning/REQUIREMENTS.md` + `.planning/research/SUMMARY.md`
**Granularity:** coarse (5 phase)
**Mode:** YOLO · Parallelization: enabled
**Coverage:** 85/85 v1 REQ-ID mapped

---

## Core Value

**"ui-ink 가 harness 의 기본이자 유일한 UI. 로컬과 원격이 동일한 경험을 갖고, 그 경험은 Claude Code 수준이다."**

모든 phase 는 이 한 문장을 우선순위 판단 기준으로 삼는다. UX 고도화가 최우선 — 백엔드 변경(PEXT) 도 UI 요구를 위한 것이다.

---

## Phases

- [x] **Phase 1: Foundation** — 의존성 bump · 프로토콜 정합성 복구 · 하드닝 · 스모크. 모든 후속 phase 의 물리적 전제. (completed 2026-04-23)
- [x] **Phase 2: Core UX** — 스트리밍 렌더 · 멀티라인 입력 · 슬래시 popup · Tool/Status 렌더 · Confirm 다이얼로그. Claude Code 급 로컬 UX 완성. (completed 2026-04-24)
- [ ] **Phase 3: Remote Room + Session Control** — 멤버 presence · 관전 모드 · 재연결 delta · one-shot/resume · 서버 WS 프로토콜 확장 5건 집결.
- [ ] **Phase 4: Testing + Docs + External Beta** — 통합 테스트 · 회귀 스냅샷 · CI matrix · PROTOCOL.md/CLIENT_SETUP.md · 외부 2인 beta 라운드. Legacy 삭제 전 품질 게이트.
- [ ] **Phase 5: Legacy Deletion + Milestone Closure** — Python UI 잔재 전수 삭제 · PROJECT.md Evolution 업데이트 · milestone 종료.

---

## Phase Details

### Phase 1: Foundation

**Goal**: ui-ink 스켈레톤을 Phase 2+ 빌드가 가능한 상태로 끌어올린다. 의존성 세대 격차 · 프로토콜 이름 불일치 · 하드닝 부재를 단일 phase 로 해소해 "`bun start` → 연결 → 토큰 스트리밍 → `agent_end`" end-to-end 스모크가 통과하는 상태를 만든다.

**Depends on**: Nothing (첫 phase)

**Requirements**: FND-01, FND-02, FND-03, FND-04, FND-05, FND-06, FND-07, FND-08, FND-09, FND-10, FND-11, FND-12, FND-13, FND-14, FND-15, FND-16

**Success Criteria** (what must be TRUE):
1. `bun start` 후 로컬 `harness_server.py` 에 WS 연결 → `"hello"` 입력 → assistant 토큰 스트리밍 렌더 완료 → `agent_end` 수신 후 프롬프트 복귀. (FND-16 exit smoke)
2. `tsc --noEmit` green · ESLint green (`process.stdout.write`/`console.log`/`<div>`/`child_process.spawn` 0건) · vitest 단위 테스트 green (`parseServerMsg` · store reducers · `dispatch` exhaustive switch · TTY 가드).
3. `grep '\x1b\[?1049\|?1000' ui-ink/src/` 빈 결과. `echo 'x' | harness` 실행 시 crash 없이 one-shot 경로로 분기.
4. `kill -9 <pid>` 이후 터미널 에코 · 라인 편집 · 커서 가시성 정상 복구. `SIGHUP`/`SIGINT`/`SIGTERM`/`uncaughtException`/`unhandledRejection` 5개 경로 모두 `setRawMode(false)` + 커서 복원 + `stdin.pause()` 수행.
5. `src/protocol.ts` 에 23+ ServerMsg discriminated union 정의 후 `src/ws/dispatch.ts` exhaustive switch 에서 미처리 이벤트 컴파일 시점 탐지 (intentional unknown event → `tsc` 실패 확인).

**Plans**: 3 plans
Plans:
- [x] 01-PLAN-A-deps-build.md — 의존성 bump (ink@7, react@19.2, zustand@5), tsconfig react-jsx, ESLint 금지 규칙, CI escape 가드
- [x] 01-PLAN-B-ws-protocol.md — WS 프로토콜 정합성 복구 (protocol.ts), 5 슬라이스 store, HarnessClient, dispatch exhaustive switch
- [x] 01-PLAN-C-hardening-smoke.md — TTY 가드, 시그널 핸들러, patchConsole:false, harness.sh, vitest 4종, tsc smoke
**UI hint**: yes

---

### Phase 2: Core UX

**Goal**: Phase 1 의 동작하는 스켈레톤 위에 로컬 사용자가 Claude Code 급 경험을 누릴 수 있도록 스트리밍 렌더 · 멀티라인 입력 · 슬래시 popup · Tool/Status 렌더 · Confirm 다이얼로그를 완결한다. 이 phase 가 끝나면 **로컬 단독 사용** 시 기존 Python REPL 을 완전히 대체 가능.

**Depends on**: Phase 1 (의존성 bump · 프로토콜 · 스토어 구조 · 하드닝)

**Requirements**: INPT-01, INPT-02, INPT-03, INPT-04, INPT-05, INPT-06, INPT-07, INPT-08, INPT-09, INPT-10, RND-01, RND-02, RND-03, RND-04, RND-05, RND-06, RND-07, RND-08, RND-09, RND-10, RND-11, CNF-01, CNF-02, CNF-03, CNF-04, CNF-05, STAT-01, STAT-02

**Success Criteria** (what must be TRUE):
1. 500 토큰 연속 스트리밍 시 CPU 50% 미만 + flicker 0 + scrollback 에 spinner 프레임 잔재 0. 터미널 폭 200↔40 반복 resize 시 stale line 0 (한국어 + emoji 포함).
2. `<MultilineInput>` 이 Enter=제출 · Shift+Enter/Ctrl+J=개행 · ↑↓ 히스토리 (`~/.harness/history.txt` Python 포맷 즉시 호환) · POSIX 편집 단축키(Ctrl+A/E/K/W/U) · 500줄 bracketed paste 중간 submit 0회 + 전체 보존.
3. `/` 입력 시 `<SlashPopup>` 에 13개 슬래시 명령이 `harness_core` 메타에서 파생 렌더. 실시간 필터 · 방향키 네비 · Tab/Enter 보완 · Esc 닫기.
4. `confirm_write` 요청 → diff 패널 (경로 + DiffPreview placeholder) + y/n/d 키 · `confirm_bash` → 커맨드 프리뷰 + `tools/shell.py` 위험도 라벨 + y/n · `cplan_confirm` 동일 프레임 재사용. 동일 턴 반복 시 sticky-deny 로컬 거부.
5. `<StatusBar>` 에 `path · model · mode · turn · ctx% · room[members]` 전 세그먼트 렌더. 좁은 폭에서 `ctx% → room → mode → turn → path` 우선순위로 graceful drop 확인.
6. 코드 펜스는 `cli-highlight` 로 언어 감지 + syntax highlight · unified diff 는 `diff@9 structuredPatch` 로 hunk 분해 + ± 색 + 라인 번호 · tool 결과는 `<ToolCard>` 로 1줄 요약 (예: `read 120 lines (of 340)`).

**Plans**: TBD
**UI hint**: yes

---

### Phase 3: Remote Room + Session Control

**Goal**: Phase 2 의 로컬 UX 위에 "공유 · 재연결 · 세션 진입 모드" 를 얹어 로컬+원격 2 = 3 사용자가 동일한 경험으로 하나의 방을 공유한다. **서버 WS 프로토콜 확장 5건이 이 phase 에 집결**해 이후 drift 를 최소화한다. Phase 2 의 CNF-01 DiffPreview 는 여기서 PEXT-02 `old_content` 필드 추가로 완성된다.

**Depends on**: Phase 2 (메시지 렌더 · InputArea · ConfirmDialog · 메시지 id 기반 아키텍처)

**Requirements**: REM-01, REM-02, REM-03, REM-04, REM-05, REM-06, SES-01, SES-02, SES-03, SES-04, WSR-01, WSR-02, WSR-03, WSR-04, PEXT-01, PEXT-02, PEXT-03, PEXT-04, PEXT-05, DIFF-01, DIFF-02, DIFF-03, DIFF-04, DIFF-05

**Success Criteria** (what must be TRUE):
1. 로컬 + 원격 2명 = 3 클라이언트가 같은 room 에 접속 → 한 명 입력 시 다른 두 명이 토큰 스트리밍을 라이브 관전. 관전자 `<InputArea>` disabled + "A is typing" 오버레이. `room.activeIsSelf === true` 인 클라만 confirm 다이얼로그 활성.
2. 서버 kill → restart 시 3 클라 전원 jitter exponential backoff 로 자연 재연결 (thundering herd 없음) + `resume_from: <last_event_id>` 헤더로 delta 수신 → 중간 이벤트 0 유실. 재연결 구간 `disconnected — reconnecting...` 오버레이 + 로컬 입력 버퍼링.
3. `harness "질문"` → REPL 없이 answer stdout 출력 후 exit (non-TTY 시 ANSI off). `harness --resume <id>` → 저장 세션 로드 후 REPL. `harness --room <name> "질문"` → 방 one-shot.
4. 서버 WS 프로토콜 확장 5건 완료: `agent_start.from_self: bool` · `confirm_write.old_content?: string` · 서버 monotonic `event_id` + room 당 60초 ring buffer · 클라→서버 `resume_from` 헤더 파싱 · 클라→서버 `cancel` 메시지 타입 + agent asyncio task 안전 중단 경로. Python pytest 199건 유지.
5. Presence 세그먼트 `🟢 2명 [alice·me]` + join/leave 시 system 메시지 1줄 `<Static>` append + 사용자 색 해시 (토큰 기반 deterministic) 가 StatusBar 와 author prefix `[alice]` 에 일관 적용.
6. `ws://127.0.0.1` 로컬 시나리오와 `ws://external-host` 원격 시나리오가 동일한 통합 테스트 시퀀스에서 green (로컬-원격 동등성 — REM-06).

**Plans**: 6 plans
Plans:
- [ ] 03-01-PLAN.md — 서버 PEXT-01~03 (Room event_id ring buffer + agent_start per-subscriber + confirm_write old_content)
- [ ] 03-02-PLAN.md — 서버 PEXT-04~05 (resume_from delta replay + cancel asyncio 중단)
- [ ] 03-03-PLAN.md — 클라이언트 protocol 타입 + store 확장 + dispatch 배선
- [ ] 03-04-PLAN.md — 신규 컴포넌트 (PresenceSegment · ReconnectOverlay · ObserverOverlay · userColor)
- [ ] 03-05-PLAN.md — HarnessClient jitter backoff + one-shot.ts + index.tsx argv 파싱
- [ ] 03-06-PLAN.md — App.tsx 치환 우선순위 + StatusBar/Message 배선 + 수동 검증
**UI hint**: yes

---

### Phase 4: Testing + Docs + External Beta

**Goal**: Phase 1~3 에서 구현된 기능의 품질을 보증하고 외부 2인 beta 로 실사용 검증한다. Legacy 삭제 전 반드시 통과해야 할 게이트 — 여기서 blocker 발견 시 legacy 롤백 경로가 살아있다. PITFALLS.md "Looks Done But Isn't" 체크리스트 17건이 이 phase 의 manual verification.

**Depends on**: Phase 3 (기능 완결 · 프로토콜 stable)

**Requirements**: TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, TST-07, TST-08, TST-09

**Success Criteria** (what must be TRUE):
1. vitest 4 + ink-testing-library 4 단위/통합 테스트 green: `parseServerMsg` · store reducer · dispatch exhaustive switch · `<MultilineInput>` 키 시퀀스 · TTY 가드 · Fake Harness WS 서버 통합 (agent 턴 · confirm_write accept · room busy · reconnect delta · one-shot · 3인 동시 재접속 시뮬).
2. 회귀 스냅샷 green: 500 토큰 스트리밍 · 한국어+emoji wrap · resize 200↔40 · `/undo` + 새 메시지 · `<Static>` 오염 0.
3. CI matrix green: bun + Node 22 양쪽 + `tsc --noEmit` + ESLint 가드 + Python pytest 199건.
4. `CLIENT_SETUP.md` 재작성 완료 (`git clone + bun install --frozen-lockfile + bun start` · `HARNESS_URL`/`HARNESS_TOKEN`/`HARNESS_ROOM` env var · troubleshooting: native dep · bun 버전 mismatch · macOS IME) + `PROTOCOL.md` 작성 (23+ 기존 이벤트 + PEXT-01..05 확장 전수) + "이전과 달라진 점" 릴리스 노트.
5. 외부 2인 beta 라운드 완료: fresh VM 에서 10분 내 설치 · REPL UX · Ctrl+R 등가 · macOS IME · history persist · `/save` 포맷 확인 · blocker 0 · "다운그레이드" 피드백 0. PITFALLS.md 체크리스트 17건 전원 수동 ✓.

**Plans**: TBD
**UI hint**: yes

---

### Phase 5: Legacy Deletion + Milestone Closure

**Goal**: Phase 4 beta greenlight 이후에만 진입. 사용자 명시 요청 "기존 코드 유지해보니까 gsd나 다른 에이전트들이 헷깔리는 경우가 상당히 많음" 이행 + PROJECT.md Key Decision "Legacy Python UI 전부 삭제" 실행. 이 phase 를 Phase 4 앞으로 당기면 regression 롤백 경로가 사라지므로 절대 역순 불가.

**Depends on**: Phase 4 (beta green + blocker 0)

**Requirements**: LEG-01, LEG-02, LEG-03, LEG-04, LEG-05, LEG-06, LEG-07, LEG-08

**Success Criteria** (what must be TRUE):
1. `ui/index.js` 삭제 · `main.py` REPL 경로 + `cli/intent.py`/`cli/render.py`/`cli/claude.py`/`cli/setup.py`/`cli/callbacks.py`/`cli/slash.py` 삭제 · `cli/tui.py`/`cli/app.py` 잔재 제거. `session/`·`evolution/`·`tools/`·`harness_core/`·`harness_server.py` 는 유지 (PROJECT.md Validated).
2. `grep -rn "prompt_toolkit" .` 빈 결과 · `python -c "import cli"` 의도적 실패 · `harness_server.py` + `ui-ink` 가 유일 실행 경로.
3. `main.py` 가 남는다면 `harness_server.py` 서버 엔트리만 래핑하는 thin shim 으로 축소, 그렇지 않으면 완전 삭제.
4. 최종 회귀 라운드 green: Python pytest 199건 + ui-ink vitest 전 테스트.
5. PROJECT.md Evolution 섹션 업데이트 완료 — Active 의 ui-ink 항목들 → Validated 이동 · Key Decisions Outcome "Pending" → "Validated" 확정 · milestone closure 섹션 추가. `.planning/codebase/CONCERNS.md` §1.12(spinner vs Live) · §3 Architecture 잔여 중 Python REPL 관련 항목 close 처리.

**Plans**: TBD
**UI hint**: yes

---

## Phase Ordering Rationale

- **Phase 1 ≺ 모든 후속** — 의존성 bump 없이 Phase 2 의 `usePaste`/`useWindowSize` 불가, 프로토콜 정합성 없이 어떤 렌더도 동작 안 함, 하드닝 없이 crash 시 터미널 망가져 beta 불가. 세 리서처(STACK/ARCHITECTURE/PITFALLS)가 이 phase 에 각자 다른 이유로 동일 작업을 몰아넣은 이유.
- **Phase 2 ≺ Phase 3 (레이어링)** — Remote/Room/Session 은 Phase 2 의 `<Static>`+active slot + `<InputArea>`/`<ConfirmDialog>` + 메시지 id 위에 조건 분기로 얹는다. Phase 2 의 CNF-04 입력 주체 격리는 설계 레벨에서 의식하지만 실제 room 구현은 Phase 3 에서 완결.
- **Phase 3 에 서버 WS 프로토콜 확장 집결** (PEXT-01~05) — "한번에 프로토콜 확장 라운드" 로 서버 drift 최소화. PROJECT.md Constraint "기존 이벤트 의미 변경 금지, 필드 추가 OK" 전수 준수.
- **Phase 4 (beta) ≺ Phase 5 (legacy 삭제) 절대 순서** — Pitfall 16 사용자 괴리 · Pitfall 18 bun install 은 fresh VM beta 에서만 확인. beta 에서 blocker 발견 시 legacy 가 있어야 롤백 경로가 남는다. 뒤집으면 돌이킬 수 없다.

---

## Requirement Coverage Map

총 85개 v1 REQ-ID · 100% 매핑 · 중복 0 · 누락 0.

| Phase | REQ 수 | 요구사항 |
|-------|--------|----------|
| Phase 1 | 16 | FND-01..16 |
| Phase 2 | 28 | INPT-01..10, RND-01..11, CNF-01..05, STAT-01..02 |
| Phase 3 | 24 | REM-01..06, SES-01..04, WSR-01..04, PEXT-01..05, DIFF-01..05 |
| Phase 4 | 9 | TST-01..09 |
| Phase 5 | 8 | LEG-01..08 |
| **합계** | **85** | **85/85 ✓** |

---

## Progress Tracking

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-04-23 |
| 2. Core UX | 5/5 | Complete | 2026-04-24 |
| 3. Remote Room + Session Control | 0/6 | In progress | - |
| 4. Testing + Docs + External Beta | 0/0 | Not started | - |
| 5. Legacy Deletion + Milestone Closure | 0/0 | Not started | - |

---

## Research Flags (SUMMARY.md 에서 파생)

다음 phase 는 planning 단계에서 `/gsd-research-phase` 로 심화 연구 권장:
- **Phase 2** — Ink 7 `usePaste` 가 bun 런타임에서 bracketed paste 를 정확히 전달하는지 · macOS IME 한국어 조합 완성 시점에서 Enter 전달 동작 · `@inkjs/ui@2` + `ink-select-input@6.2` 의 ink@7 peer 실전 호환 (Phase 1 초반 스모크에서 1차 검증됨).
- **Phase 3** — PEXT-01~05 를 Python `harness_server.py` · `harness_core` · `session/` 중 어느 레이어에 넣을지 · Room/turn-taking/active_input_from 기존 로직과의 충돌 지점 · `cancel` 메시지가 agent asyncio task 를 안전하게 끊는 방법 · ring buffer 위치.
- **Phase 4** — 3 클라 동시 재접속 · RTT 200ms 시뮬 · fresh VM `bun install --frozen-lockfile` CI 자동화 (macOS/Linux arm64/x64 matrix).

Phase 1 과 Phase 5 는 research-phase 스킵 가능 (STACK.md + PITFALLS.md 에서 이미 구체적 처방 확보).

---

*Last updated: 2026-04-23 via /gsd-roadmap*
