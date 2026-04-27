# Phase 01: rpc-skeleton - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `01-CONTEXT.md` — this log preserves the reasoning context.

**Date:** 2026-04-27
**Phase:** 01-rpc-skeleton (RPC 골격 + read_file PoC)
**Mode:** Claude-driven (사용자 위임 — *"니가 알아서 해라"*)

---

## 모드 선택의 컨텍스트

본 phase 의 discuss-phase 는 표준 인터랙티브 흐름 (AskUserQuestion 으로 area-by-area 선택) 대신 Claude-driven 으로 진행됐다. 이유:

1. v1.1 milestone 시작 직전 사용자가 *"니가 알아서 해라"* 라고 명시 위임
2. 직전 대화에서 사용자가 phase 1 의 핵심 gray area (agent.py async 통합, pending_calls 위치, read_file schema, 타임아웃, deletion 시점) 5건을 이미 파악하고 동의
3. `.planning/CLIENT-TOOLS-DESIGN.md` 의 4장 (RPC 프로토콜) + 6장 (phase 분해) 이 ground truth 로 이미 작성됨 — gray area 의 절반 이상이 design doc 시점에 결정됨
4. 사용자가 v1.1 진행 과정에서 옵션 비교를 짜증으로 받아들임 (*"오새 메신저 좋다?"*, "옵션 늘어놓지 말고 진행")

따라서 Claude 가 직접 결정하되, **D-01~D-19 모든 결정은 사용자 검토 가능** 하도록 CONTEXT.md 에 명시했고, 권장안이 아닌 결정에는 ground truth (CLIENT-TOOLS-DESIGN.md, agent.py, harness_server.py) 와 confirm 패턴 같은 기존 코드 근거를 달았다.

---

## Gray Areas Identified

식별된 gray area 5개. 표준 모드였다면 multi-select 로 사용자가 골랐을 영역.

| # | Area | 결정 위치 | 근거 |
|---|---|---|---|
| 1 | RPC 프로토콜 정의 | D-01 ~ D-04 | CLIENT-TOOLS-DESIGN.md 4장 + protocol.ts discriminated union 패턴 |
| 2 | 서버 측 pending_calls 위치 | D-05 ~ D-07 | BB-2 폐기 결정 (Phase 4) → 1인 1세션 → ws scope |
| 3 | agent.py async 통합 | D-08 ~ D-10 | harness_server.py:275-285 의 confirm bridge 패턴 재사용 |
| 4 | 타임아웃 + disconnect | D-11 ~ D-13 | Phase 1 은 read_file 만 → 30s default 충분, run_command timeout 은 Phase 3 |
| 5 | read_file schema 동등성 + deletion 시점 | D-14 ~ D-19 | Python 측 dict 반환 그대로 TS 측 mirror, deletion 은 phase 끝 |

---

## Decisions (D-01 ~ D-19)

각 결정의 reasoning 은 `01-CONTEXT.md` 의 `<decisions>` 섹션 참조. 요약 표:

| Decision | 핵심 | 채택 근거 |
|---|---|---|
| D-01 | message type = `tool_request`/`tool_result` | 표준 RPC 패턴 |
| D-02 | payload = `{call_id, name, args}` / `{call_id, ok, result?, error?}` | discriminated union 호환 |
| D-03 | WS 동일 채널 | 별도 transport 도입 비용 회피 |
| D-04 | discriminated union 유지 | 기존 protocol.ts 스타일 일관 |
| D-05 | pending_calls = ws scope (Room scope 아님) | BB-2 폐기로 Room 없음 → ws 단위 자연스러움 |
| D-06 | dict[str, asyncio.Future] | confirm 패턴과 동일 — 결과+예외+cancel 통합 |
| D-07 | 동시 다중 tool_request OK | call_id unique 만 보장하면 race-free |
| D-08 | agent.run() = sync 유지 | TOOL_MAP dispatch line (564) 만 분기로 변경 — 최소 침습 |
| D-09 | thread→async bridge = run_coroutine_threadsafe + Future.result(timeout) | confirm 패턴 (line 275-285) 그대로 응용 |
| D-10 | CLIENT_SIDE_TOOLS = {'read_file'} 만 | Phase 1 = PoC. Phase 2/3 에서 확장 |
| D-11 | timeout default = 30s, key = `tool_call_timeout` | 일반 read 충분, config 가능 |
| D-12 | disconnect = pending_calls future.cancel() → RpcAbortedError | asyncio 표준 cancel chain |
| D-13 | reconnect resume 안 함 | Phase 4 PEXT-04 와 함께 재정의 (deferred) |
| D-14 | Python read_file 반환 형태 유지 | 기존 agent 가 그 형태로 LLM 컨텍스트에 삽입 — 변경 비용 0 |
| D-15 | TS 측 동일 반환 — JSON serialization 시 동일 | drift 방지 |
| D-16 | path / file_path alias 정규화 = agent.py 측 | TS 측은 단순화, dispatch 측에서 normalize |
| D-17 | vitest = 5케이스 (성공/없음/디렉토리/심볼릭링크/offset) | pytest 의 동등 케이스에서 직접 매핑 |
| D-18 | fs.py:read_file deletion = phase 1 끝 (vitest green + 수동 검증 후) | dual-stack 최소화, 정책 일관성 |
| D-19 | 수동 검증 = 외부 PC 에서 자기 폴더 README.md 읽음 | PoC 의 정의상 핵심 |

---

## Claude's Discretion (downstream agents 결정 위임)

- `_send_tool_request` 헬퍼 위치 (closure vs module-level)
- TS `tools/registry.ts` 등록 패턴 (dict vs Map vs class)
- vitest mocking 전략 (실제 fs vs `node:test:t.mock.module`)
- 에러 메시지 — 한국어 (Python 측 일관성)
- pending_calls cleanup 메커니즘 (weakref vs 명시 cleanup)

---

## Deferred Ideas

CONTEXT.md `<deferred>` 섹션 참조. 요약:
- PTY 기반 shell — v1.2+
- Tool schema 단일 진실원 (zod ↔ pydantic codegen) — v1.2+
- MCP transport 재작성 — v1.2+
- Reconnect 시 도구 resume — Phase 4 에서 PEXT-04 재정의 시 평가
- 클라 측 도구 결과 broadcast 시각화 — 1인 1세션이라 N/A

---

## Cross-references

- Design ground truth: `.planning/CLIENT-TOOLS-DESIGN.md`
- Milestone def: `.planning/PROJECT.md`
- REQ definitions: `.planning/REQUIREMENTS.md`
- Memory: `~/.claude/projects/-Users-johyeonchang-harness/memory/project_harness_v11_pivot.md`
- 사용자 위임 발화: 2026-04-27 — *"니가 알아서 해라"*

---

*Generated: 2026-04-27 — Claude-driven discussion (no AskUserQuestion calls)*
