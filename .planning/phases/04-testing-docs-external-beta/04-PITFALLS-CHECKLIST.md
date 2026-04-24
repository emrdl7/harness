# Phase 4 PITFALLS 수동 체크리스트

**대상 Phase:** 4 (Testing + Docs + External Beta)
**작성 기준:** `.planning/research/PITFALLS.md` "Looks Done But Isn't" 섹션
**사용 방법:** beta 진행 전 모든 항목 [ ]을 [x]로 완료해야 함. 자동 검증 가능한 항목은 명령어 기재.

---

| # | 항목 | 심각도 | 확인 방법 | 자동/수동 | 상태 |
|---|------|--------|-----------|-----------|------|
| P01 | Alternate screen 미발생 — 세션 종료 후 Cmd+↑/Shift+PgUp으로 scrollback 접근 가능 | H | `bun run ci:no-escape` 통과 확인 | 자동 | [ ] |
| P02 | resize 후 stale line 없음 — 터미널 폭 200→40→200 반복, 한국어+emoji 포함 | H | 터미널 수동 resize + 화면 확인 | 수동 | [ ] |
| P03 | Raw mode 복구 — `kill -9 <pid>` 후 터미널 에코/라인편집 정상 | H | `kill -9 $(pgrep -f "bun start")` 후 `stty -a` 확인 | 수동 | [ ] |
| P04 | 큰 paste — 500줄 텍스트 붙여넣기 시 첫 줄에서 submit 안 됨 | H | 500줄 텍스트 실제 paste 테스트 | 수동 | [ ] |
| P05 | macOS IME — 한국어 조합 중 submit 안 됨, 완성 후만 submit | H | macOS 한국어 입력기로 "안녕하세요" 입력 테스트 | 수동 | [ ] |
| P06 | 스트리밍 500 토큰 — flicker 없음, CPU 50% 미만, scrollback spinner 찌꺼기 없음 | H | 장문 응답 요청 후 `top` 모니터링 | 수동 | [ ] |
| P07 | WS 재연결 — 서버 kill→restart 시 자동 재연결 + 이벤트 복구 | M | `kill $(pgrep -f harness_server)` 후 서버 재시작 | 수동 | [ ] |
| P08 | 3 사용자 동시 재연결 — 로컬+원격 2인 전원 자연 복구 | M | 3터미널 동시 접속 후 서버 재시작 | 수동 | [ ] |
| P09 | non-TTY one-shot — `echo 'test' \| bun start` crash 없이 one-shot 동작 | H | `echo 'test' \| cd ui-ink && bun start` 실행 | 자동 가능 | [ ] |
| P10 | /undo 후 새 메시지 순서 정확 — 덮어쓰기 없음 | M | `/undo` 후 새 메시지 입력 + 메시지 목록 순서 확인 | 수동 | [ ] |
| P11 | child_process 흔적 없음 | M | `grep -rn 'spawn\|exec' ui-ink/src/` → 빈 결과 | 자동 | [ ] |
| P12 | process.stdout.write / console.log 흔적 없음 | H | `bun run guard` 통과 | 자동 | [ ] |
| P13 | 세션 200 메시지 타이핑 lag 없음 — messages 리스트 매 타이핑 리렌더 안 함 | M | 200메시지 후 타이핑 응답성 체감 확인 | 수동 | [ ] |
| P14 | 토큰 인증 실패 시 친절한 에러 + 정상 종료 | M | 잘못된 HARNESS_TOKEN으로 `bun start` 실행 | 수동 | [ ] |
| P15 | fresh 환경 setup 10분 이내 — `git clone + bun install + bun start` | M | fresh VM 또는 신규 사용자 환경에서 시계 측정 | 수동 | [ ] |
| P16 | 한국어 wrap 글자 깨짐 없음 — 폭 40에서 wrap 시 | M | 터미널 폭 40으로 축소 후 한국어 메시지 확인 | 수동 | [ ] |
| P17 | Ctrl+C 2단계 — 첫 번째 = turn 취소, 두 번째 = exit | M | 에이전트 실행 중 Ctrl+C 1회 → 취소 확인 → 다시 Ctrl+C → exit 확인 | 수동 | [ ] |

---

## 자동 검증 가능 항목 일괄 실행

```bash
# P01: alternate screen 가드
cd ui-ink && bun run ci:no-escape

# P09: non-TTY one-shot
echo 'test' | cd /Users/johyeonchang/harness/ui-ink && HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=test bun start 2>&1 | head -5

# P11: child_process 흔적
grep -rn 'spawn\|exec' ui-ink/src/ && echo "발견됨!" || echo "OK — 없음"

# P12: guard
cd ui-ink && bun run guard
```

---

## 수동 검증 기록

beta 진행 후 각 항목 결과를 여기에 기록:

| # | 검증일 | 결과 | 비고 |
|---|--------|------|------|
| P01 | | | |
| P02 | | | |
| P03 | | | |
| P04 | | | |
| P05 | | | |
| P06 | | | |
| P07 | | | |
| P08 | | | |
| P09 | | | |
| P10 | | | |
| P11 | | | |
| P12 | | | |
| P13 | | | |
| P14 | | | |
| P15 | | | |
| P16 | | | |
| P17 | | | |

---

*Source: `.planning/research/PITFALLS.md` "Looks Done But Isn't" (17항목)*
*Phase 4 산출물: TST-05*
