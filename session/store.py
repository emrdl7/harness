import os
import json
import hashlib
from datetime import datetime

SESSION_DIR = os.path.expanduser('~/.harness/sessions')


def _ensure_dir():
    # CONCERNS.md §2.9 대응: 세션에는 프롬프트/툴 결과가 포함되어 잠재적으로
    # 민감. 디렉토리·파일 모두 소유자 전용 권한.
    os.makedirs(SESSION_DIR, exist_ok=True)
    try:
        os.chmod(SESSION_DIR, 0o700)
    except OSError:
        pass


def save(messages: list, working_dir: str) -> str:
    _ensure_dir()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dir_hash = hashlib.md5(working_dir.encode()).hexdigest()[:6]
    filename = f'{ts}_{dir_hash}.json'
    return save_named(filename, messages, working_dir)


def save_named(filename: str, messages: list, working_dir: str) -> str:
    '''동일 세션 동안 같은 파일에 덮어쓰기 — auto-save 용 (timestamp 파일 폭발 방지).
    save() 와 달리 호출자가 filename 을 결정. 첫 turn 에서 save() 로 생성한 filename 을
    Session 객체에 보존하고 이후 turn 마다 save_named 로 update.
    '''
    _ensure_dir()
    path = os.path.join(SESSION_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'working_dir': working_dir, 'messages': messages}, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return filename


def list_sessions() -> list[dict]:
    _ensure_dir()
    sessions = []
    for fname in sorted(os.listdir(SESSION_DIR), reverse=True):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(SESSION_DIR, fname)
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            user_msgs = [m for m in data['messages'] if m['role'] == 'user']
            preview = user_msgs[0]['content'][:60] if user_msgs else '(빈 세션)'
            sessions.append({
                'filename': fname,
                'working_dir': data.get('working_dir', '?'),
                'turns': len(user_msgs),
                'preview': preview,
            })
        except Exception:
            continue
    return sessions


def load(filename: str) -> dict:
    path = os.path.join(SESSION_DIR, filename)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_latest(working_dir: str = None) -> dict | None:
    sessions = list_sessions()
    if not sessions:
        return None
    if working_dir:
        for s in sessions:
            if s['working_dir'] == working_dir:
                return load(s['filename'])
    return load(sessions[0]['filename'])
