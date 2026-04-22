import subprocess
import tempfile
import os
import re

TIMEOUT = 30
_MAX_OUT = 8000
_HEAD    = 4000
_TAIL    = 3000

def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUT:
        return text
    omitted = len(text) - _HEAD - _TAIL
    return text[:_HEAD] + f'\n... ({omitted}자 생략) ...\n' + text[-_TAIL:]

# 위험 명령어 패턴 — 파괴적 / 권한 상승 / 시스템 변경
_DANGEROUS = [
    r'\brm\b',
    r'\brmdir\b',
    r'\bshred\b',
    r'\btruncate\b',
    r'\bmv\b',
    r'\bchmod\b',
    r'\bchown\b',
    r'\bchgrp\b',
    r'\bkill\b',
    r'\bpkill\b',
    r'\bkillall\b',
    r'\bsudo\b',
    r'\bapt\b',
    r'\bapt-get\b',
    r'\byum\b',
    r'\bdnf\b',
    r'\bbrew\s+(install|uninstall|upgrade|remove)\b',
    r'\bpip\s+(install|uninstall)\b',
    r'\bnpm\s+(install|uninstall)\s+-g\b',
    r'\bshutdown\b',
    r'\breboot\b',
    r'\binit\b',
    r'\bdd\b',
    r'\bmkfs\b',
    r'\bfdisk\b',
    r'\bdiskutil\s+(erase|format|partition)\b',
]

_DANGEROUS_RE = re.compile('|'.join(_DANGEROUS))


def classify_command(command: str) -> str:
    '''위험 명령어면 "dangerous", 아니면 "safe" 반환'''
    return 'dangerous' if _DANGEROUS_RE.search(command) else 'safe'


def run_command(command: str, cwd: str = None) -> dict:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=cwd,
        )
        return {
            'ok': result.returncode == 0,
            'stdout': _truncate(result.stdout),
            'stderr': _truncate(result.stderr),
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': f'{TIMEOUT}초 초과'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def run_python(code: str, cwd: str = None) -> dict:
    with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ['python3', tmp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=cwd,
        )
        return {
            'ok': result.returncode == 0,
            'stdout': _truncate(result.stdout),
            'stderr': _truncate(result.stderr),
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': f'{TIMEOUT}초 초과'}
    finally:
        os.unlink(tmp_path)
