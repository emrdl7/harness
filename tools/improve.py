import os
import shutil
import ast
import py_compile
import tempfile
from datetime import datetime

HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(HARNESS_DIR, '.harness_bak')

EDITABLE_FILES = [
    'config.py',
    'agent.py',
    'tools/__init__.py',
    'tools/fs.py',
    'tools/shell.py',
    'tools/git.py',
    'context/indexer.py',
    'context/retriever.py',
]


def backup_sources() -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_DIR, ts)
    os.makedirs(dest, exist_ok=True)
    for rel in EDITABLE_FILES:
        src = os.path.join(HARNESS_DIR, rel)
        if os.path.exists(src):
            dst = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    return dest


def validate_python(filepath: str) -> dict:
    try:
        with open(filepath, encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return {'ok': True}
    except SyntaxError as e:
        return {'ok': False, 'error': f'문법 오류 {e.lineno}행: {e.msg}'}


def read_sources() -> str:
    parts = []
    for rel in EDITABLE_FILES:
        path = os.path.join(HARNESS_DIR, rel)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding='utf-8') as f:
                content = f.read()
            parts.append(f'=== {rel} ===\n{content}')
        except Exception:
            pass
    return '\n\n'.join(parts)


def list_backups() -> list[str]:
    if not os.path.exists(BACKUP_DIR):
        return []
    return sorted(os.listdir(BACKUP_DIR), reverse=True)


def restore_backup(ts: str) -> dict:
    src_dir = os.path.join(BACKUP_DIR, ts)
    if not os.path.exists(src_dir):
        return {'ok': False, 'error': f'백업 없음: {ts}'}
    for rel in EDITABLE_FILES:
        src = os.path.join(src_dir, rel)
        if os.path.exists(src):
            dst = os.path.join(HARNESS_DIR, rel)
            shutil.copy2(src, dst)
    return {'ok': True, 'restored': ts}
