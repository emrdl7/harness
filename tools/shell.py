import subprocess
import tempfile
import os
import re
import shlex

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
    r'\bsu\b',
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
    r'\bfind\b.*\s-delete\b',
    r'\bfind\b.*\s-exec\b',
    r'\b(curl|wget)\b.*\|\s*(bash|sh|zsh)',
    r'>\s*/etc/',
    r'>\s*/dev/',
    r'>\s*~/\.ssh',
    r'\beval\b',
    r'\bexec\b',
    # CONCERNS.md §2.1 대응: exfiltration 및 shadow path 차단 강화
    r'\bnc\b', r'\bncat\b', r'\bnetcat\b',    # 네트워크 파이프
    r'\bssh\b', r'\bscp\b', r'\brsync\b',     # 원격 전송
    r'\bsource\b', r'\.\s+\S+\.sh\b',         # 원격 스크립트 소싱
    r'\b/bin/(rm|mv|cp|sh|bash)\b',           # absolute path 우회 차단
    r'\bpython\b.*-c\b', r'\bbash\b.*-c\b',   # inline 스크립트 실행
    r'`[^`]+`', r'\$\(',                      # 명령 치환
    r'\btar\b.*\|',                           # tar + pipe = 흔한 exfil
]

_DANGEROUS_RE = re.compile('|'.join(_DANGEROUS))

# 셸 메타문자 — 존재하면 shell=True 필요, 동시에 dangerous 분류
# |, &, ;, <, >, `, $, $(, ||, &&, >>
_SHELL_META_RE = re.compile(r'[|&;<>`]|\$\(|\$\{')


def classify_command(command: str) -> str:
    '''위험 명령어면 "dangerous", 아니면 "safe" 반환.

    셸 메타문자(파이프/리다이렉트/명령치환 등)가 있거나
    알려진 파괴적 명령 패턴에 매칭되면 dangerous.
    '''
    if _SHELL_META_RE.search(command):
        return 'dangerous'
    if _DANGEROUS_RE.search(command):
        return 'dangerous'
    return 'safe'


def should_confirm(command: str, sticky_deny: bool = False) -> bool:
    '''명령어 실행 전 사용자 confirm이 필요한지 결정.

    sticky_deny: 같은 turn 내에 사용자가 한 번이라도 confirm을 거부했으면 True.
    이 경우 모델이 safe 명령으로 우회하려는 것을 막기 위해 모든 후속
    run_command/run_python에 confirm을 강제한다.
    '''
    if sticky_deny:
        return True
    return classify_command(command) == 'dangerous'


def run_command(command: str, cwd: str = None) -> dict:
    '''명령어를 가능하면 shell=False + shlex로 실행, 메타문자 있으면 shell=True.'''
    has_shell_meta = bool(_SHELL_META_RE.search(command))
    try:
        if has_shell_meta:
            # 파이프/리다이렉트 등 포함 → 셸 필요
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                cwd=cwd,
            )
        else:
            # 셸 개입 없이 argv로 직접 실행 (인젝션 방어)
            try:
                argv = shlex.split(command)
            except ValueError as e:
                return {'ok': False, 'error': f'명령어 파싱 실패: {e}'}
            if not argv:
                return {'ok': False, 'error': '빈 명령어'}
            result = subprocess.run(
                argv,
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
    except FileNotFoundError as e:
        return {'ok': False, 'error': f'명령어 없음: {e}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


_RUN_PYTHON_INLINE_LIMIT = 8_000  # 이보다 작으면 임시파일 없이 `python3 -c` 사용


def run_python(code: str, cwd: str = None) -> dict:
    '''CONCERNS.md §1.6 대응:
    - 작은 코드(<8KB)는 `python3 -c`로 바로 실행 → 임시파일 자체가 없음
    - 큰 코드는 tempfile 경로 유지하되 BaseException까지 finally로 정리해
      Ctrl+C 인터럽트 시 누수 방지
    '''
    if len(code) <= _RUN_PYTHON_INLINE_LIMIT:
        try:
            result = subprocess.run(
                ['python3', '-c', code],
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

    tmp_path = None
    try:
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
        # KeyboardInterrupt/SystemExit 포함 모든 종료 경로에서 정리
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
