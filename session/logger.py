import os
import json
from datetime import datetime

LOG_DIR = os.path.expanduser('~/.harness/logs')


def _ensure():
    os.makedirs(LOG_DIR, exist_ok=True)


def _today_path() -> str:
    return os.path.join(LOG_DIR, datetime.now().strftime('%Y%m%d') + '.jsonl')


def log_tool_failure(tool_name: str, args: dict, error: str, working_dir: str):
    _ensure()
    entry = {
        'ts': datetime.now().isoformat(),
        'type': 'tool_failure',
        'tool': tool_name,
        'args': args,
        'error': error,
        'cwd': working_dir,
    }
    with open(_today_path(), 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def log_reflection(reason: str):
    _ensure()
    entry = {'ts': datetime.now().isoformat(), 'type': 'reflection', 'reason': reason}
    with open(_today_path(), 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def read_recent(days: int = 7) -> str:
    _ensure()
    lines = []
    for fname in sorted(os.listdir(LOG_DIR), reverse=True)[:days]:
        if not fname.endswith('.jsonl'):
            continue
        path = os.path.join(LOG_DIR, fname)
        try:
            with open(path, encoding='utf-8') as f:
                lines.extend(f.readlines())
        except Exception:
            pass
    if not lines:
        return '최근 로그 없음'
    # 실패 항목만 요약
    failures = []
    for line in lines:
        try:
            e = json.loads(line)
            if e.get('type') == 'tool_failure':
                failures.append(f"- [{e['ts'][:16]}] {e['tool']}: {e['error']}")
        except Exception:
            pass
    return '\n'.join(failures[-50:]) if failures else '실패 로그 없음'
