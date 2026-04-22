'''세션 간 실패 패턴을 누적 추적. 같은 패턴이 반복되면 자동 개선 트리거.'''
import os
import re
import json
from datetime import datetime

TRACKER_PATH = os.path.expanduser('~/.harness/evolution/patterns.json')
RECURRENCE_THRESHOLD = 3  # N세션 이상 반복이면 자동 개선


def _normalize(error: str) -> str:
    '''오류 메시지를 패턴으로 정규화 (값 제거, 구조만 남김)'''
    s = re.sub(r"'[^']*'", "'?'", error)
    s = re.sub(r'"[^"]*"', '"?"', s)
    s = re.sub(r'\d+', 'N', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:120]


def _load() -> dict:
    if not os.path.exists(TRACKER_PATH):
        return {}
    try:
        with open(TRACKER_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(TRACKER_PATH), exist_ok=True)
    with open(TRACKER_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record(failures: list[str], session_id: str):
    data = _load()
    today = datetime.now().isoformat()[:10]

    for error in failures:
        pattern = _normalize(error)
        if not pattern or pattern == '없음':
            continue
        if pattern not in data:
            data[pattern] = {'count': 0, 'sessions': [], 'first_seen': today}
        entry = data[pattern]
        if session_id not in entry['sessions']:
            entry['sessions'].append(session_id)
            entry['count'] += 1
        entry['last_seen'] = today

    _save(data)


def get_recurring(threshold: int = RECURRENCE_THRESHOLD) -> list[dict]:
    data = _load()
    result = []
    for pattern, info in data.items():
        if info['count'] >= threshold:
            result.append({'pattern': pattern, **info})
    return sorted(result, key=lambda x: x['count'], reverse=True)


def dismiss(pattern: str):
    '''해결된 패턴 제거'''
    data = _load()
    if pattern in data:
        del data[pattern]
        _save(data)


def dismiss_all():
    _save({})
