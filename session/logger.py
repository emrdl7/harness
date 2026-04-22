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
    return failure_stats(days)['text']


def failure_stats(days: int = 7) -> dict:
    '''최근 N개 일자 파일의 tool_failure 통계.

    반환:
      - count: 실패 건수
      - latest_ts: 가장 최근 실패의 ISO timestamp (없으면 None)
      - text: read_recent와 동일한 사람용 요약 ("실패 로그 없음" 또는 "- [ts] tool: err"...)

    /improve가 입력 데이터의 신선도/건수를 가드할 때 사용.
    '''
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
        return {'count': 0, 'latest_ts': None, 'text': '최근 로그 없음'}
    failures: list[str] = []
    latest_ts: str | None = None
    for line in lines:
        try:
            e = json.loads(line)
            if e.get('type') != 'tool_failure':
                continue
            ts = e.get('ts', '')
            failures.append(f"- [{ts[:16]}] {e['tool']}: {e['error']}")
            if ts and (latest_ts is None or ts > latest_ts):
                latest_ts = ts
        except Exception:
            pass
    text = '\n'.join(failures[-50:]) if failures else '실패 로그 없음'
    return {'count': len(failures), 'latest_ts': latest_ts, 'text': text}
