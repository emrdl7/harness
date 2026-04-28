# Plan 01-03 Summary — vitest + Python deletion + 수동 검증

**Phase:** 01 — rpc-skeleton (RPC 골격 + read_file PoC)
**Plan:** 01-03
**Wave:** 3 of 3
**Status:** Task 1, 2 완료 / Task 3 (수동 checkpoint) 사용자 검증 대기
**Date:** 2026-04-27

---

## What Was Done

### Task 1 — vitest readFile 5+1 케이스 (RPC-05, D-17)

신규: `ui-ink/src/__tests__/tools-fs.test.ts`

테스트 5건 + 1건 (path 누락 가드 = D-17 권장 6번째 변형):
- 성공 (성공 + content + total_lines 검증)
- 파일 없음 (`{ok: false, error}`)
- 디렉토리 (디렉토리 read 시 ok=false)
- 심볼릭 링크 → offset+limit 으로 substitution (Plan-checker INFO-1: schema 정합성 우선)
- offset=N (start_line/end_line/content slice 검증)
- path 누락 (input validation)

vitest: 신규 6 + 기존 176 = **182 passed**.

**Commit:** `eb0e7e5 test(01-03): vitest readFile 5+1 케이스 추가 (RPC-05, D-17)`

### Task 2 — Python 측 read_file deletion (D-18, RPC-03)

수정:
- `tools/fs.py`: `read_file` 함수 본체 제거 (line 55-79). 주석으로 클라 이전 사실 명시
- `tools/__init__.py`: `read_file` import 제거 + `TOOL_MAP['read_file']` 제거. `TOOL_DEFINITIONS` 의 schema 는 유지 (LLM 호출 schema 인식용 — D-18)
- `tests/test_fs.py`: read_file 케이스 3건 deletion
  - `test_write_and_read_round_trip` → write 부분만 유지, read 검증은 `path.read_text()` 로 대체
  - `test_read_offset_limit` deletion (vitest 가 동등 회귀 담당)
  - `test_read_accepts_file_path_alias` deletion (alias 정규화는 agent.py 측에서 처리, `tests/test_agent_client_side_dispatch.py` 가 회귀 담당)
- `tests/test_tools_registry.py`: `test_definitions_match_map` 갱신. `CLIENT_SIDE_TOOLS` 멤버는 TOOL_MAP 부재가 정상이라는 가드 추가

pytest: **232 passed** (234 baseline → -3 read_file deletion + 1 test_tools_registry 변경 = -2 net). 회귀 0.

**Commit:** `cc24f3c refactor(01-03): tools/fs.py read_file 본체 deletion (D-18, RPC-03)`

### Task 3 — 외부 PC 수동 검증 (D-19) ✅ PASSED (2026-04-28)

**검증 PC**: johyeonchangs-Mac-mini (VPN 통해 ws://192.168.0.222:7891 접속)
**결정적 시나리오**:
- mac-mini 의 `/tmp/mac-mini-proof.txt` 에 `MAC-MINI-PROOF` 1줄 작성
- 서버 PC 에는 해당 파일 미존재 (`ls /tmp/mac-mini-proof.txt` → No such file or directory)
- ui-ink 에서 `"/tmp/mac-mini-proof.txt 읽어줘"` 입력
- LLM 응답에 `MAC-MINI-PROOF` 내용 인용됨 → **클라 측 read_file 실행 확정**

**의의**:
- CLIENT_SIDE_TOOLS = {'read_file'} 분기 정상 동작
- WS RPC 라운드트립 (서버 tool_request → 클라 dispatch → 클라 fs.ts:readFile → 클라 tool_result → 서버 future.set_result) 전 구간 검증
- 1인 1세션 모델 + RPC 위임 = Claude Code 셀프호스팅 패턴 동작 확인

**Phase 1 Goal 달성**: "외부 PC 클라가 자기 PC `read_file` 결과 받는 것 수동 검증" ✓

수동 검증 시나리오 (D-19):

1. 서버 PC (이 macOS) 에서 harness_server 구동:
   ```bash
   .venv/bin/python harness_server.py
   ```

2. 클라이언트 (외부 PC 또는 같은 PC 의 다른 cwd):
   ```bash
   cd /tmp/poc-test && bun /path/to/harness/ui-ink/src/index.tsx
   # 또는 환경변수 HARNESS_URL=ws://server-ip:7891 HARNESS_TOKEN=...
   ```

3. 클라이언트 cwd 에 `README.md` 같은 파일 준비. 서버 PC 에는 같은 경로의 다른 내용 (또는 미존재) 으로 명확히 구분.

4. ui-ink 입력: `"현재 폴더의 README.md 읽어줘"` 같은 자연어.

5. **검증 포인트**:
   - LLM 응답에 클라이언트 PC 의 `README.md` 내용이 인용되는가? ✓ = PoC 성공
   - 서버 PC 의 같은 경로 파일이 읽히는가? ✗ 이면 안 됨 (서버 위임이 아니라 클라 실행이라는 증거)
   - 네트워크 분리: 클라이언트의 `~/.harness.toml` 에서 working_dir 인식이 클라 PC 기준인지

6. 검증 결과를 사용자가 보고.

---

## Verification Summary

- vitest: 182/182 green (Task 1)
- pytest: 232/232 passed, 회귀 0 (Task 2)
- typecheck (ui-ink): exit 0 (Plan 01-01 시점에서 검증, Plan 01-03 의 변경은 vitest 만)
- 수동 검증: Task 3 — 사용자 응답 대기

---

## Key Decisions Honored

| ID | 결정 | 적용 |
|---|---|---|
| D-17 | vitest 5케이스 + path 누락 가드 추가 | ✓ Task 1 |
| D-18 | read_file deletion = Phase 1 끝 (vitest GREEN 후) | ✓ Task 2 |
| D-19 | 외부 PC 수동 검증 시나리오 | Task 3 (사용자 검증 대기) |

---

## Deviations

1. **Plan 의 D-17 verbatim 변형:** "심볼릭링크" 케이스 → "offset+limit" + "path 누락" 으로 substitution. 이유: schema 정합성 (offset+limit 가 cross-language equivalence 의 핵심), path 누락 input validation 이 보안적으로 중요. Plan-checker 의 INFO-1 비추 (defensible trade-off).

2. **이전 agent 한도 도달:** 첫 spawn 이 Task 2 의 `tools/fs.py`/`tools/__init__.py` modify 까지 진행 후 한도. orchestrator (이 세션) 가 잔여 deletion (TOOL_MAP 항목, test_fs read_file 3건, test_tools_registry 가드) + pytest 회귀 + commit + SUMMARY 직접 마무리.

---

## Commits (Plan 01-03)

| Task | Commit | Message |
|------|--------|---------|
| 1 | `eb0e7e5` | test(01-03): vitest readFile 5+1 케이스 추가 (RPC-05, D-17) |
| 2 | `cc24f3c` | refactor(01-03): tools/fs.py read_file 본체 deletion (D-18, RPC-03) |
| 3 | (수동 검증) | — checkpoint, 사용자 응답 후 SUMMARY 갱신 |

---

## Next Steps

1. **사용자**: 위 수동 검증 시나리오 실행 → 결과 보고
2. **검증 통과 시**: 본 SUMMARY 의 Task 3 섹션 갱신 + commit + Phase 01 verifier 단계로 진행
3. **검증 실패 시**: agent.py / harness_server.py 의 RPC bridge 디버그 (rpc_call 송신 여부 / tool_result 수신 여부 / args.path 정규화 여부)
