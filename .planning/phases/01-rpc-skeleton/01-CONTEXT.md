# Phase 01: RPC 골격 + read_file PoC - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Mode:** Claude-driven discussion (사용자 위임 — *"니가 알아서 해라"*)

<domain>
## Phase Boundary

WS 프로토콜에 RPC 패턴 (`tool_request`/`tool_result`) 을 도입하고, `read_file` 1개 도구를 클라이언트 측에서 실행하도록 위임한 후 외부 PC 클라이언트가 자기 PC 파일을 읽는 것을 수동 검증한다.

**In scope (RPC-01, RPC-02, RPC-03 의 read_file, RPC-05 의 read_file 회귀):**
- `protocol.ts` 에 `tool_request`/`tool_result` 타입
- `harness_server.py` 에 `pending_calls` dict + dispatch 진입점
- `agent.py` 의 도구 dispatch 분기 (`CLIENT_SIDE_TOOLS = {'read_file'}` 만)
- `ui-ink/src/tools/registry.ts` + `tools/fs.ts` 의 `read_file`
- `ui-ink/src/ws/dispatch.ts` 에 `tool_request` 핸들러
- `tools/fs.py:read_file` deletion + pytest read_file 케이스 deletion (phase 1 끝)
- vitest read_file 회귀 (~5건)
- 수동 검증: 외부 PC ui-ink → `read_file` → 외부 PC 파일 읽음 (서버 PC 아님)

**Out of scope (Phase 2~5 에서 처리):**
- write_file/edit_file/list_files/grep_search (Phase 2)
- shell + git (Phase 3)
- BB-2 deletion (Phase 4) — 본 phase 에서는 기존 Room 인프라와 공존
- MCP (Phase 5)
- PTY shell, schema codegen — v1.2+

</domain>

<decisions>
## Implementation Decisions

### RPC 프로토콜 (RPC-01)

- **D-01:** 메시지 타입 = `tool_request` (서버→클라) / `tool_result` (클라→서버). `call_id` (uuid v4) 로 correlation
- **D-02:** `tool_request` 페이로드 = `{type, call_id, name, args}`. `tool_result` 페이로드 = `{type, call_id, ok, result?, error?}`. 오류는 `error: {kind, message}`
- **D-03:** WS 동일 채널 사용. 별도 transport 없음. 기존 dispatch.ts 라우팅에 핸들러 추가
- **D-04:** discriminated union 패턴 유지 (`protocol.ts` 의 기존 메시지 타입 스타일 따름)

### 서버 측 pending_calls (RPC-01, RPC-02)

- **D-05:** `pending_calls` 위치 = 각 `ws` 객체 (또는 connection-scoped state). 1인 1세션 가정 — Room 단위 dict 아님. BB-2 가 Phase 4 에서 deletion 되므로 Phase 1 도 ws 단위로 시작 (전환 비용 0)
- **D-06:** 자료구조 = `pending_calls: dict[str, asyncio.Future]`. `tool_result` 수신 시 `future.set_result(result)`. timeout/disconnect 시 `future.set_exception(...)`
- **D-07:** 동일 ws 내 동시 `tool_request` 다중 가능 — `call_id` 가 unique 하면 OK (예: 한 LLM turn 에 read_file × 3 병렬)

### agent.py async 통합 (RPC-02)

- **D-08:** `agent.run()` 은 sync 유지. tool dispatch line (현 line 564 `fn = TOOL_MAP.get(fn_name)` 부근) 에서 `CLIENT_SIDE_TOOLS` 멤버십 체크 → 클라 위임 분기
- **D-09:** thread → asyncio bridge = 기존 confirm 패턴 그대로 응용 (`harness_server.py:275-285`). 즉 sync agent 가 `asyncio.run_coroutine_threadsafe(_send_tool_request(...), loop)` 로 ws 송신 + `asyncio.run_coroutine_threadsafe(asyncio.wait_for(future, timeout), loop).result()` 로 결과 대기
- **D-10:** Phase 1 의 `CLIENT_SIDE_TOOLS = {'read_file'}` 만. Phase 2/3 진행하며 fs/shell/git 추가

### 타임아웃 + disconnect (RPC-06 의 일부 — Phase 1 만 read_file 적용)

- **D-11:** 타임아웃 default = 30s (`.harness.toml` config 가능, key = `tool_call_timeout`)
- **D-12:** ws disconnect 시 그 ws 의 `pending_calls` 일괄 `future.cancel()` → agent 측 `RpcAbortedError` (CancelledError 변환). agent turn 종료
- **D-13:** Phase 1 에서는 disconnect cleanup 만 구현. reconnect 시 진행 중 tool 의 resume 안 함 (Phase 4 에서 PEXT-04 와 함께 재정의)

### read_file schema 동등성 (RPC-03 read_file 부분)

- **D-14:** Python 측 read_file 반환 형태 그대로 유지: `{ok: bool, path: str, content: str, ...}` 또는 `{ok: false, error: str}`
- **D-15:** TS 측 (`ui-ink/src/tools/fs.ts:read_file`) 도 동일 반환 — JSON serialization 시 동일 형태. 시그니처: `read_file({path, offset?, limit?}) -> { ok, path, content, error?, ... }`
- **D-16:** 인자 정규화 — Python 측 `path | file_path` alias 처리. TS 측은 `{path}` 만 받고 alias 없음. agent.py 가 args 전달 시 정규화

### Phase 1 PoC 검증 + deletion 시점 (RPC-05, RPC-06)

- **D-17:** vitest 작성 = read_file 5케이스 (성공/존재안함/디렉토리/심볼릭링크/대용량 offset). pytest read_file 의 동등 케이스 사전 매핑
- **D-18:** `tools/fs.py:read_file` deletion 시점 = Phase 1 끝 (vitest green + 수동 검증 후). pytest read_file 케이스 동시 deletion. dual-stack 기간 = phase 진행 중 (수일 단위)
- **D-19:** 수동 검증 시나리오 — 외부 PC (또는 같은 PC 의 다른 cwd) 에서 `bun start` → `harness "./CLAUDE.md 읽어줘"` → LLM 이 read_file 호출 → 외부 PC 의 CLAUDE.md 가 읽혀서 컨텍스트 삽입 → 응답에서 외부 PC 파일 내용 확인. 서버 PC 의 CLAUDE.md 는 안 읽힘

### Claude's Discretion

- agent.py 의 `_send_tool_request` 헬퍼 위치/이름 (run_agent 내부 클로저 vs 모듈 함수)
- TS 측 `tools/registry.ts` 의 등록 패턴 (단순 dict vs 클래스 vs Map)
- vitest mocking 전략 (실제 fs vs `node:test:t.mock.module`)
- 에러 메시지 한국어 vs 영어 — Python 측 한국어와 동일하게 한국어
- pending_calls 의 cleanup 메커니즘 (weakref vs 명시 cleanup)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design ground truth
- `.planning/CLIENT-TOOLS-DESIGN.md` — v1.1 의 ground truth. 0장 (오역 사실), 4장 (RPC 프로토콜), 5장 (운영 모델), 6장 (phase 분해)
- `.planning/PROJECT.md` — v1.1 milestone 정의 + Operating Model
- `.planning/REQUIREMENTS.md` — RPC-01~06 + BBR-01 + SES-01 + MCP-01 + DOC-01 정의

### 코드 ground truth
- `harness_server.py:138-285` — Room dataclass + confirm bridge 패턴 (thread → asyncio.Event). RPC 도 이 패턴 응용
- `harness_server.py:237-310` — `run_agent(ws, room, ...)` async wrapper. agent sync run 을 executor 로 띄움
- `agent.py:416-580` — `run()` 의 메인 loop. line 564 `fn = TOOL_MAP.get(fn_name)` 가 도구 dispatch 진입점
- `tools/fs.py:55-105` — `read_file` (+ write_file, edit_file) 시그니처 + 반환 형태
- `tools/__init__.py` — `TOOL_DEFINITIONS`/`TOOL_MAP` (dispatch 가 참조하는 레지스트리)
- `ui-ink/src/protocol.ts` — discriminated union 메시지 타입 (RPC 메시지 추가 위치)
- `ui-ink/src/ws/dispatch.ts` — WS 메시지 → store action 라우팅 (tool_request 핸들러 추가 위치)
- `ui-ink/src/components/tools/index.ts` — 기존 tool 결과 렌더 registry (RPC 의 도구 실행 registry 와는 별개 — 결과 렌더링은 그대로)

### 프로토콜 문서
- `docs/PROTOCOL.md` — 현재 WS 프로토콜 명세 (Phase 5 에서 RPC 추가 + room_* 제거 갱신 예정)
- `docs/CLIENT_SETUP.md` — 클라이언트 사용법 (HARNESS_URL/HARNESS_TOKEN — Phase 4 에서 HARNESS_ROOM 제거)

### 메모리
- `~/.claude/projects/-Users-johyeonchang-harness/memory/project_harness_v11_pivot.md` — v1.0 오역 사실 + 사용자 의도 확정 (4개 발화 인용)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`harness_server.py` confirm bridge 패턴** (line 275-285) — `asyncio.Event` + `asyncio.run_coroutine_threadsafe` + `asyncio.wait_for(timeout)`. RPC 도 이 패턴 응용. Future 1개로 송신과 결과 대기 묶음
- **`ui-ink/src/protocol.ts` discriminated union** — `tool_request`/`tool_result` 도 같은 패턴으로 추가. type narrowing 가능
- **`ui-ink/src/ws/dispatch.ts` 라우팅** — switch (msg.type) 에 case 추가만으로 핸들러 등록. AR-01 패턴과 일관
- **AR-01 tool registry** (`ui-ink/src/components/tools/index.ts`) — 결과 *렌더* 용 registry. RPC 의 도구 *실행* registry 는 별개 (`ui-ink/src/tools/registry.ts` 신규) 지만 같은 dict-lookup 패턴

### Established Patterns

- **Sync agent ↔ async server** = `loop.run_in_executor` 로 agent 띄우고, 콜백/이벤트는 `run_coroutine_threadsafe`. 이미 confirm/on_tool/on_token 에서 검증됨
- **Tool 반환 = dict with `ok`** — Python 측 모든 tool 이 `{ok: bool, ...}` 또는 `{ok: false, error}`. TS 측도 동일 유지
- **JSON serialization** — Python `json.dumps` ↔ TS `JSON.parse`. Date/Bytes 같은 비표준 타입 없음 (string/number/bool/null/array/object). content 는 string. 바이너리 파일 read_file 호출 미정 — Phase 2 에서 결정

### Integration Points

- **`harness_server.py` 의 dispatch loop** — `_dispatch_loop` 코루틴 (line ~340 추정). `tool_result` 메시지 case 추가
- **`agent.py:564` 의 dispatch line** — `if fn_name in CLIENT_SIDE_TOOLS: result = await rpc_call(...)` else `fn(...)` 분기
- **`harness_server.py:run_agent` 의 콜백 주입** — `_sync_run_agent` 또는 동등에 `rpc_call` 콜백 추가. agent 가 module-level 함수 호출 대신 주입 받은 콜백 호출
- **ui-ink `App.tsx` 의 client init** — HarnessClient 가 `tool_request` 수신 시 `tools/registry.ts` 의 dispatcher 호출

### Constraints

- Bun child_process API — Phase 3 까지 안 건드리지만 호환성 고려해서 tool 함수는 async 유지 (`fs.ts:read_file = async (args) => Promise<Result>`)
- 1인 1세션 가정 — pending_calls 가 ws scope 라 Room 폐기 (Phase 4) 시 변경 0

</code_context>

<specifics>
## Specific Ideas

- 수동 검증 = 외부 PC (또는 같은 macOS 의 다른 cwd) 에서 ui-ink 띄우고, "현재 폴더의 README.md 읽어줘" 같은 자연어 요청. LLM 이 `read_file` 호출 → 클라 PC 의 README.md 가 응답에 인용되면 PoC 성공
- read_file 결과의 content cap = 기존 `MAX_TOOL_RESULT_CHARS` (agent.py 측에서 cap) 그대로 적용. 클라가 보내는 결과는 cap 안 함, 서버가 LLM 컨텍스트 삽입 시 cap

</specifics>

<deferred>
## Deferred Ideas

- **PTY 기반 shell** — Phase 3 의 simple spawn 으로는 부족한 시나리오 (ssh/htop 같은 인터랙티브). v1.2+
- **Tool schema 단일 진실원** — Python pydantic ↔ TS zod codegen. drift 방지. v1.2+
- **MCP 의 transport 재작성** — 현재 stdio. 클라 측 sidecar 후 transport 변경 가능성. v1.2+
- **Reconnect 시 도구 resume** — 진행 중 tool 잃음 (Phase 4 에서 PEXT-04 재정의 시 다시 평가)
- **클라 측 도구 결과 broadcast 시각화** — 1인 1세션이라 broadcast 자체가 없음. 다중 ws 가 같은 LLM 컨텍스트 보는 use case 발생 시 재고
- **Tool 호출의 user-visible audit log** — 어떤 도구가 어떤 인자로 호출됐는지 ui-ink 측에서 시각화 (현재는 ToolCard 가 partial)

</deferred>

---

*Phase: 01-rpc-skeleton*
*Context gathered: 2026-04-27 — Claude-driven (사용자 위임)*
