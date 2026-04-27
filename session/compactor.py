import json
import requests
import config

# 비시스템 메시지 누적 문자가 이 값을 넘으면 compaction 트리거
# config.CONTEXT_WINDOW * 2 (한국어 1자 ≈ 0.5~0.7 토큰 가정 시 컨텍스트 ~70% 도달 시점)
# 동적이므로 .harness.toml 의 num_ctx 변경 시 자동 추종.
def _compact_threshold() -> int:
    return config.CONTEXT_WINDOW * 2

# compaction 후 유지할 최근 메시지 수
KEEP_RECENT = 10

_SUMMARY_SYSTEM = '대화 요약 전문가. 간결하고 정확하게.'
_SUMMARY_PROMPT = (
    '다음 대화를 구조화하여 요약해. 한국어로 답해.\n\n'
    '출력 형식 (각 항목은 bullet로):\n'
    '## 완료된 작업\n'
    '## 발견된 사실 (파일 구조·버그 원인·설정 등)\n'
    '## 현재 상태 (진행 중인 작업·마지막 위치)\n\n'
    '대화:\n'
)


_TOOL_RESULT_MAX_CHARS = 8000  # tool 결과 1개가 이 크기 넘으면 head+tail truncate


def _chars(messages: list) -> int:
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)


def _truncate_large_tool_outputs(messages: list) -> list:
    '''CONCERNS.md §1.13 대응: 거대한 tool 결과가 KEEP_RECENT 윈도우에 남으면
    compact해도 threshold를 못 내려 다음 턴에도 needs_compaction=True로 남는다.
    개별 tool 메시지를 head+tail로 줄여 threshold 안쪽으로 끌어내린다.'''
    out = []
    for m in messages:
        content = m.get('content')
        if m.get('role') != 'tool' or not isinstance(content, str):
            out.append(m)
            continue
        if len(content) <= _TOOL_RESULT_MAX_CHARS:
            out.append(m)
            continue
        head = _TOOL_RESULT_MAX_CHARS // 2
        tail = _TOOL_RESULT_MAX_CHARS - head
        omitted = len(content) - _TOOL_RESULT_MAX_CHARS
        new_content = (
            content[:head]
            + f'\n…[tool 결과 중간 {omitted}자 생략]…\n'
            + content[-tail:]
        )
        out.append({**m, 'content': new_content})
    return out


def needs_compaction(messages: list) -> bool:
    non_sys = [m for m in messages if m['role'] != 'system']
    return _chars(non_sys) > _compact_threshold()


def _summarize(messages_to_summarize: list) -> str:
    lines = []
    for m in messages_to_summarize:
        role = m['role']
        content = m.get('content') or ''
        if isinstance(content, list):
            content = ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
        lines.append(f'[{role}] {content[:300]}')

    payload = {
        'model': config.MODEL,
        'messages': [
            {'role': 'system', 'content': _SUMMARY_SYSTEM},
            {'role': 'user', 'content': _SUMMARY_PROMPT + '\n'.join(lines)},
        ],
        'stream': False,
        'options': {**config.OLLAMA_OPTIONS, 'num_predict': 512},
    }
    try:
        resp = requests.post(
            f'{config.OLLAMA_BASE_URL}/api/chat',
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json().get('message', {}).get('content', '').strip()
        return text or ''  # 빈 응답도 '실패'로 취급 → 호출자가 원본 보존
    except Exception:
        return ''  # 빈 문자열 = 요약 실패 신호


def compact(messages: list) -> tuple[list, int]:
    '''compaction 실행. (새 메시지 목록, 압축된 메시지 수) 반환.

    CONCERNS.md §1.14 대응: Ollama 실패 시 placeholder 삼키지 않고 원본 유지.
    요약이 비어 있으면 (messages, 0)을 돌려줘 호출자가 압축 건너뜀을 인지.
    '''
    sys_msgs = [m for m in messages if m['role'] == 'system']
    non_sys  = [m for m in messages if m['role'] != 'system']

    if len(non_sys) <= KEEP_RECENT:
        return messages, 0

    to_summarize = non_sys[:-KEEP_RECENT]
    to_keep      = non_sys[-KEEP_RECENT:]

    summary = _summarize(to_summarize)
    if not summary:
        # 요약 실패 — 원본 유지하되 거대 tool 결과는 줄여 다음 턴의 spin 방지
        import sys as _sys
        print('[compactor] 요약 생성 실패 — 세션 원본 유지', file=_sys.stderr)
        safe_messages = sys_msgs + _truncate_large_tool_outputs(non_sys)
        return safe_messages, 0

    # 성공 시에도 to_keep 내 대용량 tool 결과는 다듬어 threshold 여유 확보
    to_keep = _truncate_large_tool_outputs(to_keep)

    # 기존 system 메시지에 요약을 덧붙임
    if sys_msgs:
        new_sys = {**sys_msgs[0], 'content': sys_msgs[0]['content'] + f'\n\n--- 이전 대화 요약 ---\n{summary}'}
        result  = [new_sys] + list(sys_msgs[1:]) + to_keep
    else:
        result  = [{'role': 'system', 'content': f'--- 이전 대화 요약 ---\n{summary}'}] + to_keep

    return result, len(to_summarize)
