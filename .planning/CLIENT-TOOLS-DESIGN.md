# Client-side Tool Execution — Design

> 작성일: 2026-04-27
> 상태: Draft — 차기 milestone formalize 전 검토 단계
> 작성 컨텍스트: v1.0 종료 후 사용자가 "외부에서 접속한 사용자는 자기 PC 의 파일로 작업해야 하는데 현재는 서버에서 도구가 돈다" 는 사실 지적

---

## 0. 어디서 잘못됐나 (객관 기록)

### 사용자 의도 (처음부터 일관되게)

CLAUDE.md 1번째 줄: *"**Claude Code 풍** 터미널 에이전트"*
PROJECT.md Core Value: *"그 경험은 **Claude Code 수준**이다."*

즉 처음부터 reference 모델이 박혀 있었다 — **Claude Code**.

Claude Code 의 동작 모델:
- LLM = Anthropic 서버 (`claude-opus-4-7` 등)
- 도구 (Read/Write/Edit/Bash/Grep/...) = 사용자 로컬 머신
- 클라이언트 = 사용자 PC 의 CLI 프로세스. tool call schema 는 LLM 이 생성하지만 **실행은 클라이언트가 자기 PC 에서**

> *"Claude Code 가 어디 Anthropic 서버의 파일을 수정하는 그런 솔루션이냐?"* — 사용자 발화, 2026-04-27

우리 시나리오와 1:1 매핑:

| 항목 | Claude Code | harness |
|---|---|---|
| LLM 위치 | Anthropic 서버 (서드파티) | 집 머신 MLX/Ollama (자가 호스팅) |
| 도구 위치 | 사용자 로컬 | (목표) 사용자 로컬 |
| 클라이언트 | CLI 프로세스 | ui-ink 프로세스 |
| 협업 단위 | (단독) | LLM + 방(컨텍스트) 공유 |

차이는 LLM 호스팅 위치 + 방 공유뿐. 도구가 클라 측이라는 핵심은 같다.

사용자가 발언한 "모델 공유" (2026-04-27) 도 이 reference 의 일부 — *"같은 LLM 인스턴스를 둘이 같이 쓴다"* 라는 의미. 도구는 처음부터 각자 PC.

### v1.0 PROJECT.md 의 잘못된 표현

PROJECT.md 첫 줄: *"... 각자 장비에서 접속해 **하나의 백엔드를 공유한다**."*

- v1.0 작성 시점에 사용자의 "Claude Code 처럼" + "모델 공유" 의도가 "백엔드 공유" 로 잘못 옮겨졌다.
- "백엔드 공유" 는 LLM + 도구 + 세션 모두 서버 측이라는 정반대 의미. Claude Code reference 와 정면 충돌.
- v1.0 implementation 이 그 잘못된 PROJECT.md 를 충실히 따랐고, 결과적으로 도구까지 서버 측에서 돌게 됐다.

### 결과 (현재 v1.0 상태)

| 컴포넌트 | 현재 위치 | Claude Code reference | 일치 여부 |
|---|---|---|---|
| LLM | 서버 PC | (서버 측) | ✓ |
| fs/shell/git 도구 | 서버 PC | 클라 측 | ✗ |
| 세션 저장 | 서버 PC | 클라 측 | ✗ |
| Confirm dialog | 클라 측 | 클라 측 | ✓ |

효과: 외부 사용자 ui-ink 에서 `read_file src/App.tsx` → 서버 PC 의 파일을 읽음 → Claude Code 와 정반대.

### 책임 소재

v1.0 implementation 의 결함이 아니라, v1.0 작성자(과거 Claude 세션) 가 사용자의 "Claude Code 처럼" reference 를 무시하고 "백엔드 공유" 로 잘못 옮긴 것이 근본 원인. 본 doc 작성자(현재 Claude 세션) 도 1차 draft 에서 같은 실수를 반복 — 사용자가 명시한 reference 를 무시하고 (A)/(B)/(C) 협업 모델 옵션을 던졌음 (사용자 정정 발화로 폐기). v1.1 에서 PROJECT.md 의 협업 모델 표현 자체를 Claude Code reference 와 일치하도록 정정하고, 도구 위치를 클라이언트로 이전한다.

---

## 1. Scope

### In scope
- WS 프로토콜에 `tool_request`/`tool_result` 추가 — 서버 → 클라 RPC
- ui-ink 측 TS tool runtime — `ui-ink/src/tools/{fs,shell,git}.ts`
- `agent.py` 의 도구 dispatch → "RPC 위임 후 결과 대기" 로 전환
- 도구별 위치 분류 표 확정 (3장 참조)
- **BB-2 코드 전체 deletion** (5장) — Room/broadcast/active_input_from/presence/observer/snapshot 등. 1인 1세션 가정으로 단순화
- Confirm 플로우 재배치 — 클라 측 dialog → 클라 측 실행 (1인 가정, broadcast 없음)
- pytest 의 fs/shell/git 테스트를 vitest 동등 변환
- CLAUDE.md "legacy 삭제 default" 정책에 따라 클라 이전 완료 도구의 Python 측 파일 삭제
- `HARNESS_ROOM` / `--room` / `BB-2-DESIGN.md` 등 Room 관련 자산 일괄 정리

### Out of scope
- LLM 추론의 클라 측 분산 (서버 = 서버)
- MCP transport 변경 — 위치만 클라로 (sidecar). transport 재작성은 후속
- UI 컴포넌트 추가 (`UI-RENDER-PLAN.md` V2 잔여 = 별 트랙)
- 바이너리 배포 / 자동 업데이트 / IDE 통합

---

## 2. Constraints

| Constraint | 의미 |
|---|---|
| pytest 199건 (그 중 fs/shell/git ~70 추정) | 클라 이전 시 vitest 동등 작성 필요. Python 코드는 정책상 삭제 |
| BB-2 공유 방 (`active_input_from`/`broadcast`/`confirm 격리`) | 도구 실행 주체 = `active_input_from` 의 PC. 결과는 broadcast. 기존 가드 유지 |
| MCP (`tools/mcp.py`) | 클라 PC 의 IDE/DB 와 붙어야 의미. 클라 측 sidecar 또는 직접 호출로 이전 |
| RX-02 세션 (`~/.harness/sessions/`) | 현재 서버 측. 클라 이전 시 working_dir 도 클라 → 세션 위치 재결정 필요 |
| PEXT-04 reconnect delta replay | 진행 중 도구 실행 도중 disconnect 시 resume 불가능 (수용) |
| CLAUDE.md "legacy 삭제 default" | 클라 측 구현 완료 도구의 `tools/*.py` 즉시 삭제 — 병존 금지 |

---

## 3. 도구 분류

| 도구 | 위치 | 이유 |
|---|---|---|
| `read_file` `write_file` `edit_file` | **클라** | 사용자 코드 |
| `list_files` | **클라** | working_dir 트리 |
| `grep_search` | **클라** | regex / ripgrep |
| `run_command` `run_python` | **클라** | 사용자 환경 (PATH, venv, env vars) |
| `git_log` `git_diff` `git_status` | **클라** | 사용자 repo |
| `search_web` `fetch_page` | **서버** | 외부망 access 일관성 (클라가 firewall 뒤 가능) |
| MCP servers | **클라** | 사용자 IDE/DB |
| `claude_cli`, `external_ai` | **서버** | LLM API 키 / 라우팅 일관성 |
| `improve` (자기개선) | **서버** | 서버 코드 자기수정 도구 — 그대로 |
| `hooks` | **서버** | hooks.json 서버 측 자산 |

---

## 4. RPC 프로토콜

### 서버 → 클라
```json
{
  "type": "tool_request",
  "call_id": "uuid-v4",
  "name": "read_file",
  "args": { "path": "src/App.tsx" }
}
```

### 클라 → 서버
```json
{
  "type": "tool_result",
  "call_id": "uuid-v4",
  "ok": true,
  "result": { "content": "...", "size": 1234 }
}
```

오류 시 `ok=false`, `error: { kind, message }`.

### 타임아웃
- 기본 30s (config 가능)
- `run_command` 는 별도 (`.harness.toml` 의 `command_timeout` 따름)
- 타임아웃 시 서버 측 `asyncio.TimeoutError` → agent 에 `tool_error` 전달

### Disconnect 처리
- ws disconnect 시 `room.pending_calls` 일괄 cancel
- agent.py 의 `await rpc_call()` 가 `RpcAbortedError` 받음 → tool_result 자리에 에러 텍스트 삽입 후 LLM 에게 다음 turn 결정 위임
- `active_input_from` 이탈 시 = 도구 실행 주체 사라짐 = 도구 abort. agent turn 종료

### Reconnect
- 진행 중이던 도구는 잃음 (resume 안 함)
- LLM 컨텍스트엔 `tool_error: connection lost` 가 남음 → agent 가 retry 결정
- 이건 PEXT-04 의 메시지 delta replay 와 별개 (메시지는 재생, 도구는 재생 안 함)

### 보안
- 클라가 서버에 거짓 결과 전송 가능성 — but 클라는 사용자 자기 PC 라 LLM 한테 거짓말 하는 건 사용자 자기 손해. 위협 모델 외
- 서버는 받은 결과를 그대로 LLM 컨텍스트에 삽입 (cap 적용 — 기존 `MAX_TOOL_RESULT_CHARS` 그대로)

---

## 5. 운영 모델 (Claude Code 셀프호스팅 — 1인 1세션)

### 확정

레퍼런스 = **Claude Code**. 차이는 LLM 을 셀프호스팅한 것뿐.

> *"Claude Code 가 어디 Anthropic 서버의 파일을 수정하는 그런 솔루션이냐?"* (사용자 2026-04-27)
> *"각 유저가 같은 방에서 만난다는 개념을 나는 요구한 적이 없다."* (사용자 2026-04-27)
> *"같은 방에서 만날 필요 자체가 없다. 요새 메신저 좋다."* (사용자 2026-04-27)

운영 모델:
- 1인 1세션. 사용자가 자기 PC ui-ink → 집 머신 LLM → 자기 PC 도구
- 다른 사용자도 그 LLM 을 쓸 수 있다 = 같은 서버에 접속해서 **독립적으로** 자기 세션을 가짐. 컨텍스트 격리
- LLM 서버 = 멀티 테넌트 (Anthropic 서버처럼 N 사용자 동시 접속). 협업은 외부 메신저 책임
- "같은 방에서 만나기 / 공동 컨텍스트 공유 / presence" = **사용자 요구 아님 + 메신저로 충분**

### BB-2 처리 = 전체 deletion (확정)

v1.0 BB-2 Phase 1~4 의 모든 Room 인프라는 사용자 요구 외 기능. CLAUDE.md "legacy 삭제 default" 정책과 사용자 발화 *"같은 방에서 만날 필요 자체가 없다"* 에 따라 **deletion**.

deletion 대상:
- `harness_server.py` — `Room` dataclass, `ROOMS: dict`, `_get_or_create_room`, `_maybe_drop_room`, `broadcast`, `broadcast_state`, `active_input_from` 가드, `room_joined`/`room_busy`/`room_member_joined`/`room_member_left`/`state_snapshot`/`/who` 핸들러
- `ui-ink/src/components/PresenceSegment.tsx` `ReconnectOverlay.tsx` `ObserverOverlay.tsx`
- `ui-ink/src/store/room.ts` 및 관련 dispatch
- `protocol.ts` 의 room_* 메시지 타입
- `HARNESS_ROOM` 환경변수 + `--room` CLI 인자
- 관련 pytest ~30건 + vitest 테스트
- `BB-2-DESIGN.md` 도 archive 또는 deletion

유지:
- `HARNESS_TOKENS` 멀티유저 인증 (다른 사용자도 같은 LLM 쓰기 위한 최소 인프라)
- 1인 세션 기본 동작 (1 ws ↔ 1 session)

### Confirm

`active_input_from` 가드 폐기. confirm 은 그냥 그 ws 의 사용자에게 묻고 응답 받는 단순 구조.

---

## 6. 마이그레이션 단계 (Phase 단위)

### Phase 1 — RPC 골격 + read_file PoC
- `protocol.ts` 에 `tool_request`/`tool_result` 타입 추가
- `harness_server.py` 에 `room.pending_calls: dict[str, asyncio.Future]` + dispatch 진입점
- `agent.py` 의 도구 dispatch → 위임 분기 (`CLIENT_SIDE_TOOLS = {'read_file'}` 만 시작)
- ui-ink: `tools/registry.ts` + `tools/fs.ts` 의 `read_file` 만 구현 + `dispatch.ts` 에 `tool_request` 핸들러
- 수동 검증: 외부 PC ui-ink → `read_file src/App.tsx` → 클라 PC 파일이 읽힘
- vitest 5건 (read_file 케이스)
- `tools/fs.py:read_file` Python 측 + pytest 케이스 즉시 삭제 (정책)

### Phase 2 — fs 도구 전체 클라 이전
- `tools/fs.ts` 에 `write_file` `edit_file` `list_files` `grep_search` 구현
- agent.py 의 `CLIENT_SIDE_TOOLS` 확장
- vitest 회귀 (pytest fs.py 의 케이스 동등 변환 ~30건)
- Confirm 다이얼로그 클라 측 통합 — `write_file`/`edit_file` 시 ConfirmDialog → 사용자 응답 → 클라 실행
- `tool_decision` broadcast 추가
- `tools/fs.py` 삭제 + pytest fs 테스트 삭제

### Phase 3 — shell + git 클라 이전
- `tools/shell.ts` — `run_command`/`run_python` (Bun child_process spawn). PTY 는 v1.2 이후
- `tools/git.ts` — `git_log`/`git_diff`/`git_status` (child_process git)
- 위험한 명령 분류 (현재 Python 의 `_classify` 동등) — 클라 측 재구현
- vitest ~25건
- `tools/shell.py` `tools/git.py` 삭제 + pytest 삭제

### Phase 4 — BB-2 deletion + RX-02 세션 위치
- `harness_server.py` Room/broadcast/active_input_from/snapshot/who 일괄 제거 → 1 ws ↔ 1 session 단순화
- ui-ink: `PresenceSegment` `ReconnectOverlay` `ObserverOverlay` `store/room.ts` 삭제, `protocol.ts` room_* 타입 제거, `--room`/`HARNESS_ROOM` 제거
- 관련 pytest ~30건 + vitest 테스트 삭제
- `BB-2-DESIGN.md` archive
- RX-02 세션 위치 = 클라 측 `./.harness/sessions/` 으로 이전 (Room 폐기로 hybrid 의미 사라짐 → 클라 단독)

### Phase 5 — MCP 클라 이전 + cleanup
- `tools/mcp.py` → ui-ink 측 sidecar 프로세스 또는 Bun 직접 호출
- MCP 서버 정의 위치 = `~/.harness/mcp.json` (클라 측)
- 잔여 정리 — `tools/__init__.py` 의 import 갱신, agent.py 의 dispatch 단순화
- 회귀 — pytest 잔여 (web/claude_cli/improve/hooks) + vitest 전체 green

---

## 7. Open Decisions

D1, D9 사용자 발화로 확정. D4 도 D9 따라 자동 확정. 잔여 D2/D3/D5/D6/D7/D8.

| # | 결정 | 옵션 | 권장 / 결정 |
|---|---|---|---|
| ~~D1~~ | ~~운영 모델~~ | — | **확정**: Claude Code 셀프호스팅, 1인 1세션 (사용자 발화) |
| D2 | shell 구현 | PTY (node-pty) / simple spawn | **simple spawn** 시작, PTY 는 v1.2 |
| D3 | MCP 이전 시점 | 본 milestone Phase 5 / 후속 milestone | **Phase 5** (위치만, transport 그대로) |
| ~~D4~~ | ~~RX-02 세션 위치~~ | — | **확정**: 클라 단독 (`./.harness/sessions/`) — Room 폐기로 hybrid 의미 사라짐 |
| D5 | search_web/fetch_page | 서버 유지 / 클라 이전 | **서버 유지** (3장 표) |
| D6 | tools/improve.py | 서버 유지 / deprecate | **서버 유지** (서버 자기수정 도구) |
| D7 | 이번 milestone 이름/번호 | v1.1 / v2.0 | **v1.1** (내부 아키텍처 변경, UX 큰 변화 없음) |
| D8 | Python 측 도구 삭제 시점 | 즉시 (phase 별) / milestone 끝에 일괄 | **즉시** (CLAUDE.md 정책) |
| ~~D9~~ | ~~BB-2 처리~~ | — | **확정**: 전체 deletion (사용자 발화 *"같은 방에서 만날 필요 자체가 없다. 메신저 좋다"*) |

---

## 8. 회귀 위험

1. **pytest 198건 → ~130건** — fs/shell/git ~70건은 deletion. vitest 측 동등 작성 필요. 그 사이 transitional state (~ 1일) 동안 fs 신뢰성 일시 하락
2. **BB-2 `active_input_from` 가드** — RPC 시 가드는 서버가 아니라 "tool_request 수신 측 ws == active_input_from" 검증으로 이동. 누락 시 다른 멤버 PC 가 도구 실행하는 사고
3. **MCP 임시 미동작 (Phase 1~4 동안)** — MCP 사용자가 있으면 임시 우회 (서버 측 MCP 유지하되 클라 PC 와 IPC) 또는 사전 공지
4. **PEXT-04 resume** — 진행 중 도구 잃음. agent 측에서 retry 자동화 (현재 한 차례 retry 로직 있음) 로 보완
5. **Python 3.14 venv pytest 운영 부담 감소** — long term 으로 Python 측 코드 줄어 운영 단순화. 단기적으론 dual stack
6. **Bun 측 child_process 의 timeout/kill** — 신중히 구현 필요. node-child_process API 의존

---

## 9. 외부 AI plan 과의 차이

외부 AI (사용자 제공) 가 짚은 plan 의 강점:
- 진단 정확 (서버 측 cwd/glob 문제)
- RPC 패턴 (call_id correlation, asyncio.Event) — 표준
- Open Question 3개 (전면 포팅 vs 워커 / confirm 이관 / 임시 vs 정식)

외부 AI plan 의 누락 (본 doc 에서 보강):
- BB-2 공유 방 시나리오 미언급
- MCP 처리 미정
- pytest 199건 회귀 처리 미정
- 도구별 위치 분류 부재 (전면 클라 가정)
- 타임아웃/disconnect/reconnect 정책 부재
- RX-02 세션 위치 미정
- Schema unification (Python/TS 양쪽 도구 정의 drift) 미언급

본 doc 의 외부 AI Open Question 권장 답:
- Q1 (전면 포팅 vs 워커) → **전면 TS 포팅**. Python 워커는 PATH/venv/PTY 가 클라 PC 에 있어야 의미인데 사이드카로 옮겨도 같은 일 + IPC 한 단 추가
- Q2 (confirm 이관) → **부분 동의**. 결정은 클라(active_input_from), 결과는 방 broadcast (협업 가시성)
- Q3 (임시 vs 정식) → **정식 RPC**. 임시는 BB-2 처음부터 깨짐 + 1주 후 어차피 다시 짜야

---

## 10. 다음 단계

본 doc 검토 → D1~D8 결정 → 차기 milestone (v1.1 후보) formalize:

1. `PROJECT.md` 갱신 — 협업 모델 (A) 명시 + Validated 에 v1.0 의 implicit (C) 모델이 외부 사용자 시나리오 미충족이었음 evolution 기록
2. `MILESTONES.md` 에 v1.1 항목 추가
3. `/gsd-new-milestone` 또는 수동 milestone 디렉토리 생성
4. `ROADMAP.md` 에 6 phase 분해 (위 6장)
5. `REQUIREMENTS.md` 에 RPC-* 시리즈 ID 신설 (예 RPC-01 protocol, RPC-02 read_file PoC, ...)

검토 후 D1~D8 답변 받으면 위 1~5 즉시 진행.
