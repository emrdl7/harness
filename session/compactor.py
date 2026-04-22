import json
import requests
import config

# 비시스템 메시지 누적 문자가 이 값을 넘으면 compaction 트리거
# qwen3-coder:30b 기준 32K 컨텍스트 → 20K 문자(≈5K 토큰) 수준에서 압축
COMPACT_THRESHOLD = 20000
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


def _chars(messages: list) -> int:
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)


def needs_compaction(messages: list) -> bool:
    non_sys = [m for m in messages if m['role'] != 'system']
    return _chars(non_sys) > COMPACT_THRESHOLD


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
        return resp.json().get('message', {}).get('content', '').strip()
    except Exception:
        return f'(이전 {len(messages_to_summarize)}개 메시지 압축됨)'


def compact(messages: list) -> tuple[list, int]:
    '''compaction 실행. (새 메시지 목록, 압축된 메시지 수) 반환'''
    sys_msgs = [m for m in messages if m['role'] == 'system']
    non_sys  = [m for m in messages if m['role'] != 'system']

    if len(non_sys) <= KEEP_RECENT:
        return messages, 0

    to_summarize = non_sys[:-KEEP_RECENT]
    to_keep      = non_sys[-KEEP_RECENT:]

    summary = _summarize(to_summarize)

    # 기존 system 메시지에 요약을 덧붙임
    if sys_msgs:
        new_sys = {**sys_msgs[0], 'content': sys_msgs[0]['content'] + f'\n\n--- 이전 대화 요약 ---\n{summary}'}
        result  = [new_sys] + list(sys_msgs[1:]) + to_keep
    else:
        result  = [{'role': 'system', 'content': f'--- 이전 대화 요약 ---\n{summary}'}] + to_keep

    return result, len(to_summarize)
