'''HARNESS.md 변경 이력 추적'''
import os
import json
import hashlib
from datetime import datetime

HISTORY_PATH = os.path.expanduser('~/.harness/evolution/history.jsonl')


def _file_hash(path: str) -> str:
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def snapshot(paths: list[str], event: str, score: float, session_id: str):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    entry = {
        'ts': datetime.now().isoformat(),
        'event': event,
        'score': score,
        'session_id': session_id,
        'files': {p: _file_hash(p) for p in paths if os.path.exists(p)},
    }
    with open(HISTORY_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def recent(n: int = 20) -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    lines = []
    with open(HISTORY_PATH, encoding='utf-8') as f:
        for line in f:
            try:
                lines.append(json.loads(line))
            except Exception:
                pass
    return lines[-n:]


def avg_score(n: int = 10) -> float:
    entries = [e for e in recent(n * 2) if e.get('event') == 'session_end' and 'score' in e]
    if not entries:
        return 1.0
    return round(sum(e['score'] for e in entries[-n:]) / len(entries[-n:]), 3)
