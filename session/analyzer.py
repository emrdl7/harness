import json


def summarize_session(messages: list) -> dict:
    '''세션에서 학습 포인트 추출용 요약 생성'''
    turns = []
    failures = []
    undos = 0
    reflections = 0

    for msg in messages:
        if msg['role'] == 'user':
            turns.append(msg['content'][:200])
        elif msg['role'] == 'tool':
            try:
                result = json.loads(msg['content'])
                if not result.get('ok'):
                    failures.append(result.get('error', result.get('stderr', ''))[:150])
            except Exception:
                pass
        elif msg['role'] == 'assistant':
            if '반성' in msg.get('content', '') or 'REFLECTION' in msg.get('content', ''):
                reflections += 1

    return {
        'turn_count': len(turns),
        'user_queries': turns,
        'failures': failures,
        'reflections': reflections,
    }


def build_learn_prompt(summary: dict, current_global_doc: str, current_project_doc: str, working_dir: str) -> str:
    failure_block = '\n'.join(f'- {f}' for f in summary['failures']) or '없음'
    query_block = '\n'.join(f'- {q}' for q in summary['user_queries']) or '없음'

    return f'''이번 세션을 분석해 HARNESS.md를 개선하세요.

## 세션 요약
- 총 {summary["turn_count"]}턴
- 툴 실패: {len(summary["failures"])}건
- 반성 루프 진입: {summary["reflections"]}회

## 사용자 질문 패턴
{query_block}

## 발생한 실패
{failure_block}

---

## 현재 전역 HARNESS.md (~/harness/HARNESS.md)
{current_global_doc}

## 현재 프로젝트 HARNESS.md ({working_dir}/HARNESS.md)
{current_project_doc or "(없음 — 필요시 새로 생성)"}

---

다음을 수행하세요:

1. 반복된 실패 패턴 → 전역 HARNESS.md의 "파일 작업 원칙" 또는 "자주 쓰는 패턴" 보강
2. 이번 세션에서 발견한 프로젝트 특화 규칙 → 프로젝트 HARNESS.md에 추가
   - 프로젝트 경로: {working_dir}/HARNESS.md
   - 없으면 새로 생성
3. 이미 문서화된 내용은 중복 추가하지 말 것
4. 변경이 불필요하면 "학습할 내용 없음"이라고 말하고 종료

write_file로 직접 파일을 수정하세요.
'''
