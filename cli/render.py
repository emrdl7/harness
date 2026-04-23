'''터미널 렌더 유틸 — main.py에서 분리(Phase 3.1-B).

이 모듈에 모은 것 (Phase 3.1-B 한정):
- `console` / `THEME`: rich.Console 단일 인스턴스
- `_TOOL_META` + `_tool_meta_for` / `_tool_result_hint`: 툴 호출 표시 메타
- `_short_dir`: 경로 약식 표시
- `_infer_tool_purpose`: 미등록 툴 이름→추정 기능 매퍼
- `_Spinner` / `_SPINNER_FRAMES`: stdout 직접 제어 스피너 (CONCERNS §1.12 인지)

main.py state(`SLASH_COMMANDS`, `_INSTALLABLE_TOOLS`, `_BANNER_LINES`,
`_ctx_display`, `_token_buf`)에 의존하는 print/render 함수는 후속 sub-phase
에서 옮긴다 — 의존을 인자로 받게 리팩토링한 뒤 이동.
'''
import os
import sys
import threading

from rich.console import Console
from rich.theme import Theme


THEME = Theme({
    'tool.read':    'cyan',
    'tool.write':   'yellow',
    'tool.run':     'magenta',
    'tool.git':     'green',
    'tool.ok':      'green',
    'tool.fail':    'bold red',
    'tool.hint':    'dim white',
    'response':     'white',
    'prompt':       'bold cyan',
    'cmd':          'bold magenta',
    'info':         'dim white',
    'warn':         'yellow',
    'claude.label': 'bold blue',
})
console = Console(theme=THEME, highlight=False)


# ── 도구 메타데이터 ─────────────────────────────────────────────
_TOOL_META = {
    'read_file':     ('Read',    'tool.read',  lambda a: a.get('path', '')),
    'write_file':    ('Write',   'tool.write', lambda a: a.get('path', '')),
    'list_files':    ('Glob',    'tool.read',  lambda a: a.get('pattern', '')),
    'run_command':   ('Run',     'tool.run',   lambda a: a.get('command', '')[:70]),
    'run_python':    ('Python',  'tool.run',   lambda a: (a.get('code', '').split('\n')[0])[:70]),
    'git_status':    ('Git',     'tool.git',   lambda _: 'status'),
    'git_diff':      ('Git',     'tool.git',   lambda a: 'diff' + (' --staged' if a.get('staged') else '')),
    'git_log':       ('Git',     'tool.git',   lambda a: f'log -{a.get("n", 10)}'),
    'git_diff_full': ('Git',     'tool.git',   lambda _: 'diff HEAD'),
    'search_web':    ('Search',  'cyan',       lambda a: a.get('query', '')[:70]),
    'fetch_page':    ('Fetch',   'cyan',       lambda a: a.get('url', '')[:70]),
}


def _tool_meta_for(name: str) -> tuple:
    if name in _TOOL_META:
        return _TOOL_META[name]
    if name.startswith('mcp__'):
        parts = name.split('__', 2)
        server = parts[1] if len(parts) > 1 else 'mcp'
        tool = parts[2] if len(parts) > 2 else name
        return (f'MCP:{server}', 'cyan', lambda a: tool)
    return (name, 'dim white', lambda _: '')


def _tool_result_hint(name: str, result: dict) -> str:
    if not result.get('ok'):
        err = result.get('error') or result.get('stderr') or ''
        return err.strip()[:80]
    if name == 'read_file':
        lines = result.get('content', '').count('\n') + 1
        return f'{lines}줄'
    if name == 'write_file':
        return '저장됨'
    if name == 'list_files':
        return f'{len(result.get("files", []))}개 파일'
    if name in ('run_command', 'run_python'):
        out = (result.get('stdout') or result.get('stderr') or '').strip()
        first = out.split('\n')[0][:60] if out else ''
        rc = result.get('returncode', 0)
        return f'{first}' if first else f'exit {rc}'
    if name.startswith('git_'):
        out = (result.get('output') or result.get('stdout') or '').strip()
        return out.split('\n')[0][:60] if out else 'ok'
    return 'ok'


# ── 경로 표시 ───────────────────────────────────────────────────
def _short_dir(path: str) -> str:
    home = os.path.expanduser('~')
    if path.startswith(home):
        path = '~' + path[len(home):]
    parts = path.split(os.sep)
    if len(parts) > 3:
        return os.sep.join(['…'] + parts[-2:])
    return path


# ── 미등록 툴 추정 ─────────────────────────────────────────────
def _infer_tool_purpose(name: str, args: dict) -> str:
    '''툴 이름과 호출 인자로 추정 기능 설명 생성.'''
    n = name.lower()
    arg_parts = []
    for k, v in (args or {}).items():
        v_str = str(v)[:40] + ('...' if len(str(v)) > 40 else '')
        arg_parts.append(f'{k}={v_str}')
    args_str = f'  [dim]인자: {", ".join(arg_parts)}[/dim]' if arg_parts else ''

    if 'status' in n or 'info' in n:
        purpose = '프로젝트/상태 정보를 조회하는 툴'
    elif 'search' in n or 'find' in n or 'query' in n:
        purpose = '검색/탐색을 수행하는 툴'
    elif 'read' in n or 'get' in n or 'fetch' in n or 'load' in n:
        purpose = '데이터를 읽어오는 툴'
    elif 'write' in n or 'save' in n or 'store' in n or 'create' in n:
        purpose = '데이터를 저장/생성하는 툴'
    elif 'run' in n or 'exec' in n or 'execute' in n:
        purpose = '명령/코드를 실행하는 툴'
    elif 'test' in n or 'check' in n or 'lint' in n or 'valid' in n:
        purpose = '검증/테스트를 수행하는 툴'
    elif 'acknowledge' in n or 'confirm' in n or 'respond' in n or 'reply' in n:
        purpose = '대화 응답용 (실제 기능 없음 — 모델이 잘못 호출한 것일 수 있음)'
    else:
        purpose = '기능 미상 — 이름으로 유추 불가'

    return purpose, args_str


# ── 스피너 (CONCERNS §1.12: rich.Live와 동시 활성화 시 충돌 가능 — 이후 통합) ─
_SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


class _Spinner:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self.active = False

    def start(self):
        if self.active:
            return
        self.active = True
        self._stop.clear()
        sys.stdout.write(f'\x1b[36m⠋\x1b[0m\n')
        sys.stdout.flush()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        i = 1
        while not self._stop.wait(0.08):
            frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
            sys.stdout.write(f'\x1b[1A\r\x1b[K\x1b[36m{frame}\x1b[0m\n')
            sys.stdout.flush()
            i += 1

    def stop(self):
        if not self.active:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        sys.stdout.write('\x1b[1A\r\x1b[K')
        sys.stdout.flush()
        self.active = False
