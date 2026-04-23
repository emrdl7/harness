'''터미널 렌더 유틸 — main.py에서 분리(Phase 3.1-B/3.1-C).

이 모듈에 모은 것:
- console / THEME — rich.Console 단일 인스턴스
- _TOOL_META + _tool_meta_for / _tool_result_hint — 툴 표시 메타
- _short_dir — 경로 약식 표시
- _infer_tool_purpose — 미등록 툴 이름→추정 기능 매퍼
- _Spinner / _SPINNER_FRAMES — stdout 스피너 (CONCERNS §1.12 인지)
- (3.1-C) SLASH_COMMANDS — 슬래시 명령 카탈로그
- (3.1-C) PT_STYLE / SlashCompleter — prompt_toolkit 자동완성
- (3.1-C) _render_core_notice / _render_sessions_table / _render_files_tree
- (3.1-C) _print_help / _DIR_ICON / _FILE_ICONS

`_INSTALLABLE_TOOLS`, `_BANNER_LINES`, `_ctx_display`, `_token_buf` 등
main.py state에 의존하는 함수는 후속 sub-phase에서 인자화 후 이동.
'''
import os
import sys
import threading

from rich.console import Console
from rich.theme import Theme
from rich.table import Table
from rich.tree import Tree
from rich import box

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style as PtStyle


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
class _ConsoleProxy:
    '''Rich Console 대체 가능 래퍼 — getattr/setattr 를 현재 target 으로 프록시.

    기본 target 은 stdout Console. `cli.app.run_app` 이 풀스크린 모드에 진입
    할 때 StringIO 기반 Console 을 push → agent 출력이 앱 내부 output Window
    로 라우팅. 종료 시 pop 으로 복구. 기존 `from cli.render import console`
    사용처는 모두 그대로 동작.
    '''
    __slots__ = ('_stack',)
    _own = frozenset({'_stack', 'push', 'pop', 'target'})

    def __init__(self, initial):
        object.__setattr__(self, '_stack', [initial])

    def push(self, target) -> None:
        self._stack.append(target)

    def pop(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()

    @property
    def target(self):
        return self._stack[-1]

    def __getattr__(self, name):
        return getattr(self._stack[-1], name)

    def __setattr__(self, name, value):
        if name in self._own:
            object.__setattr__(self, name, value)
        else:
            setattr(self._stack[-1], name, value)

    def __delattr__(self, name):
        if name in self._own:
            object.__delattr__(self, name)
        else:
            delattr(self._stack[-1], name)


console = _ConsoleProxy(Console(theme=THEME, highlight=False))


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


def _pt_app_running() -> bool:
    '''prompt_toolkit Application 이 지금 돌고 있는지.'''
    try:
        from prompt_toolkit.application.current import get_app_or_none
        return get_app_or_none() is not None
    except Exception:
        return False


# cli.app.run_app (Rich.Live 기반) 이 활성일 때는 live region 이 자체
# 스피너를 그리므로, 기존 `_Spinner` (stdout 에 ANSI escape 직접) 는
# 비활성화해 충돌 / 프레임마다 새 줄 찍히는 현상을 방지.
_spinner_disabled = False


class _Spinner:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self.active = False

    def start(self):
        if self.active:
            return
        if _pt_app_running() or _spinner_disabled:
            # prompt_toolkit Application 또는 Rich.Live 가 활성 — live 영역과
            # 충돌을 피하기 위해 no-op.
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


# ── Phase 3.1-C: 슬래시 명령 카탈로그 + 자동완성 + 결과 렌더 ────
SLASH_COMMANDS = {
    '/clear':    '대화 초기화',
    '/undo':     '마지막 질문·응답 취소',
    '/retry':    '마지막 질문을 같은 조건으로 재실행',
    '/diff':     '변경사항 확인  ex) /diff / /diff main.py',
    '/plan':     '로컬 모델이 플랜 작성 후 실행  ex) /plan 인증 모듈 리팩터링',
    '/cplan':    'Claude가 플랜 작성 → 로컬 모델이 실행  ex) /cplan 인증 모듈 리팩터링',
    '/cloop':    'Claude ↔ 로컬 모델 협업 루프 (계획→실행→검토 반복)  ex) /cloop 인증 모듈 리팩터링',
    '/compact':  '세션 대화를 요약 압축해 컨텍스트 확보',
    '/index':    '코드베이스 인덱싱',
    '/improve':  '하네스 자기 분석 및 개선',
    '/learn':    '세션 분석 후 HARNESS.md 즉시 갱신',
    '/evolve':          '진화 엔진 즉시 실행  ex) /evolve proposals / /evolve run / /evolve changelog',
    '/history':  '진화 이력 및 품질 트렌드 확인',
    '/restore':  '이전 백업으로 롤백',
    '/commit':   'git add -A + commit  ex) /commit 버튼 스타일 수정',
    '/push':     'git push',
    '/pull':     'git pull',
    '/cd':       '작업 디렉토리 변경  ex) /cd ~/myproject',
    '/files':    '현재 디렉토리 파일 트리',
    '/save':     '현재 세션 저장',
    '/resume':   '마지막 세션 불러오기',
    '/sessions': '저장된 세션 목록',
    '/init':     '.harness.toml 생성',
    '/claude':   'Claude CLI에 질문 (세션에 기록됨)  ex) /claude 이 함수 설명해줘',
    '/agents':   '등록된 외부 AI 에이전트 목록 (Claude / 향후 Codex·Gemini)',
    '/think':    '마지막 응답의 reasoning 블록(<think>) 펼쳐보기',
    '/mode':     '승인 모드 전환  ex) /mode suggest | auto-edit | full-auto',
    '/help':     '도움말',
    '/quit':     '종료',
}

PT_STYLE = PtStyle.from_dict({
    'prompt':                                  'ansicyan bold',
    'completion-menu.completion':              'bg:#1a1a2e #aaaaaa',
    'completion-menu.completion.current':      'bg:#0f3460 #ffffff bold',
    'completion-menu.meta.completion':         'bg:#1a1a2e #555555',
    'completion-menu.meta.completion.current': 'bg:#0f3460 #aaccff',
    # bottom_toolbar 기본 스타일은 'bg:#aaaaaa #222222' (역상). 이를 제거해
    # 터미널 기본 배경 + 기본 전경으로 띄움. 각 세그먼트가 자기 색만 입힘.
    'bottom-toolbar':                          'noreverse bg:default fg:default',
    'bottom-toolbar.text':                     'noreverse bg:default',
    # Application 기반 입력창 (get_input): 라운드 프레임 + 프롬프트 색
    'frame':                                   'fg:#5a6a7a',
    'input-prompt':                            'fg:ansicyan bold',
    'status-bar':                              'noreverse bg:default fg:default',
})


class SlashCompleter(Completer):
    def __init__(self):
        self.working_dir = os.getcwd()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith('/'):
            return

        parts = text.split(maxsplit=1)
        in_arg_mode = len(parts) >= 2 or (len(parts) == 1 and text.endswith(' '))

        if in_arg_mode:
            cmd = parts[0]
            arg = parts[1] if len(parts) >= 2 else ''
            yield from self._arg_completions(cmd, arg)
            return

        word = parts[0] if parts else '/'
        for cmd, desc in SLASH_COMMANDS.items():
            if cmd.startswith(word):
                yield Completion(
                    cmd[len(word):],
                    start_position=0,
                    display=cmd,
                    display_meta=desc.split('  ex)')[0],
                )

    def _arg_completions(self, cmd, arg):
        if cmd == '/cd':
            yield from self._path_completions(arg, dirs_only=True)
        elif cmd == '/diff':
            yield from self._git_changed_files(arg)
        elif cmd == '/restore':
            try:
                from tools.improve import list_backups
                for ts in list_backups()[:10]:
                    if ts.startswith(arg):
                        yield Completion(ts[len(arg):], start_position=0, display=ts)
            except Exception:
                pass
        elif cmd == '/mode':
            for m in ('suggest', 'auto-edit', 'full-auto'):
                if m.startswith(arg):
                    yield Completion(m[len(arg):], start_position=0, display=m)
        elif cmd == '/evolve':
            for sub in ('proposals', 'run', 'changelog'):
                if sub.startswith(arg):
                    yield Completion(sub[len(arg):], start_position=0, display=sub)

    def _path_completions(self, arg, dirs_only=False):
        try:
            expanded = os.path.expanduser(arg) if arg.startswith('~') else arg
            if expanded.startswith('/') or expanded.startswith('~'):
                parent = os.path.dirname(expanded) or '/'
                prefix = os.path.basename(expanded)
            else:
                parent = os.path.join(self.working_dir, os.path.dirname(arg))
                prefix = os.path.basename(arg)
            if not os.path.isdir(parent):
                return
            for name in sorted(os.listdir(parent)):
                if name.startswith('.'):
                    continue
                if prefix and not name.startswith(prefix):
                    continue
                full = os.path.join(parent, name)
                if dirs_only and not os.path.isdir(full):
                    continue
                suffix = '/' if os.path.isdir(full) else ''
                yield Completion(name[len(prefix):] + suffix, start_position=0, display=name + suffix)
        except OSError:
            pass

    def _git_changed_files(self, arg):
        import subprocess as _subp
        try:
            r = _subp.run(
                ['git', '-C', self.working_dir, 'diff', '--name-only'],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode != 0:
                return
            for f in r.stdout.strip().split('\n'):
                if f and f.startswith(arg):
                    yield Completion(f[len(arg):], start_position=0, display=f)
        except (OSError, _subp.TimeoutExpired):
            pass


# ── 슬래시 결과 렌더 ────────────────────────────────────────────
def _render_core_notice(notice: str, level: str) -> None:
    if not notice:
        return
    if level == 'ok':
        console.print(f'  [tool.ok]✓[/tool.ok] {notice}')
    elif level == 'warn':
        console.print(f'  [warn]{notice}[/warn]')
    elif level == 'error':
        console.print(f'  [tool.fail]✗[/tool.fail] {notice}')
    else:
        console.print(f'  [dim]{notice}[/dim]')


def _render_sessions_table(sessions: list) -> None:
    if not sessions:
        console.print('  [dim]저장된 세션이 없습니다[/dim]')
        return
    t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
    t.add_column('파일', style='dim')
    t.add_column('디렉토리')
    t.add_column('턴', justify='right', style='dim')
    t.add_column('첫 질문', style='white')
    for s in sessions[:10]:
        t.add_row(s['filename'], s['working_dir'], str(s['turns']), s['preview'])
    console.print(t)


_DIR_ICON = '📁'
_FILE_ICONS = {
    '.py': '🐍', '.js': '📜', '.ts': '📘', '.tsx': '📘', '.jsx': '📜',
    '.md': '📝', '.json': '📋', '.toml': '⚙', '.yaml': '⚙', '.yml': '⚙',
    '.sh': '⚡', '.go': '🐹', '.rs': '🦀', '.sql': '🗃',
}


def _render_files_tree(tree_dict: dict) -> None:
    '''harness_core가 빌드한 트리 dict를 Rich Tree로 변환해 출력.'''
    root_name = tree_dict.get('name', '?') or '?'
    rich_tree = Tree(f'[bold cyan]{root_name}[/bold cyan]', guide_style='dim')

    def _add(parent_node, children: list):
        dirs = [c for c in children if 'children' in c]
        files = [c for c in children if 'children' not in c]
        for d in dirs:
            branch = parent_node.add(f'[bold]{_DIR_ICON} {d["name"]}[/bold]')
            _add(branch, d.get('children', []))
        for f in files:
            ext = os.path.splitext(f['name'])[1].lower()
            icon = _FILE_ICONS.get(ext, '  ')
            parent_node.add(f'[dim]{icon}[/dim] {f["name"]}')

    _add(rich_tree, tree_dict.get('children', []))
    console.print(rich_tree)
    console.print()  # 트리 아래 빈 줄 — 원본 동작 유지


def _print_help() -> None:
    sections = {
        '대화':   ['/clear', '/undo', '/retry'],
        '실행':   ['/plan', '/cplan'],
        '검토':   ['/diff', '/think'],
        '인덱스': ['/index'],
        '진화':   ['/improve', '/learn', '/evolve', '/history', '/restore'],
        '파일':   ['/commit', '/push', '/pull', '/cd', '/files'],
        '세션':   ['/save', '/resume', '/sessions', '/init'],
        '외부 AI': ['/claude', '/agents'],
        '설정':   ['/mode'],
        '기타':   ['/help', '/quit'],
    }
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), border_style='dim')
    t.add_column('섹션',  style='dim',          no_wrap=True)
    t.add_column('명령어', style='bold magenta', no_wrap=True)
    t.add_column('설명',  style='white')
    for section, cmds in sections.items():
        first = True
        for cmd in cmds:
            desc = SLASH_COMMANDS.get(cmd, '').split('  ex)')[0]
            t.add_row(section if first else '', cmd, desc)
            first = False
    console.print('[bold]명령어[/bold]')
    console.print(t)
    console.print(
        '  [dim]@claude <질문>[/dim] — Claude에게 직접 질문 (세션에 기록)\n'
        '  [dim]@claude [/dim] 로 시작하는 입력은 슬래시 없이도 동작합니다\n'
    )


# ── Write/Edit diff 렌더 (Claude Code 스타일) ─────────────────────
_LEXER_BY_EXT = {
    '.py': 'python', '.pyi': 'python',
    '.js': 'javascript', '.mjs': 'javascript', '.jsx': 'jsx',
    '.ts': 'typescript', '.tsx': 'tsx',
    '.html': 'html', '.htm': 'html',
    '.css': 'css', '.scss': 'scss', '.sass': 'sass',
    '.json': 'json', '.jsonc': 'json',
    '.toml': 'toml', '.yaml': 'yaml', '.yml': 'yaml',
    '.md': 'markdown', '.markdown': 'markdown',
    '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
    '.go': 'go', '.rs': 'rust', '.rb': 'ruby',
    '.sql': 'sql', '.xml': 'xml',
    '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp',
    '.java': 'java', '.kt': 'kotlin',
    '.swift': 'swift', '.dart': 'dart',
    '.lua': 'lua', '.php': 'php',
    '.dockerfile': 'dockerfile',
}


def _lexer_for_path(path: str) -> str:
    '''확장자 → pygments lexer 이름. 모르면 text.'''
    ext = os.path.splitext(path.lower())[1]
    return _LEXER_BY_EXT.get(ext, 'text')


def _summarize_diff(diff: list, path: str) -> dict:
    '''unified_diff 결과에서 추가/삭제 카운트 + 샘플 라인(최대 6개) 추출.

    반환: {'path', 'added', 'removed', 'samples': [(line_no, kind, content), ...]}
    '''
    import re
    added = 0
    removed = 0
    samples: list = []
    old_ln = 0
    new_ln = 0
    for d in diff:
        if d.startswith('---') or d.startswith('+++'):
            continue
        if d.startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', d)
            if m:
                old_ln = int(m.group(1))
                new_ln = int(m.group(2))
            continue
        if d.startswith('+'):
            added += 1
            if len(samples) < 6:
                samples.append((new_ln, '+', d[1:].rstrip('\n')))
            new_ln += 1
        elif d.startswith('-'):
            removed += 1
            if len(samples) < 6:
                samples.append((old_ln, '-', d[1:].rstrip('\n')))
            old_ln += 1
        else:
            old_ln += 1
            new_ln += 1
    return {'path': path, 'added': added, 'removed': removed, 'samples': samples}


def _render_diff_body(diff: list, max_lines: int = 60):
    '''unified_diff → Claude Code 스타일 Renderable (rich.console.Group).

    - 추가: 녹색 배경 + `+` + 라인번호(new)
    - 삭제: 적색 배경 + `-` + 라인번호(old)
    - 컨텍스트: dim + new 라인번호
    - @@ 헤더: cyan dim, 이후 라인번호 재설정
    - 파일 헤더(---/+++) 는 스킵 (Panel title로 대체)
    '''
    import re
    from rich.console import Group
    from rich.text import Text

    ADD_BG = 'on #0a2a0a'
    DEL_BG = 'on #3a0f0f'
    CONTEXT_STYLE = 'dim'
    MARKER_ADD = 'bold green'
    MARKER_DEL = 'bold red'
    LN_STYLE = 'dim #4a6a8a'

    rendered: list = []
    old_ln = 0
    new_ln = 0
    count = 0

    for line in diff:
        if line.startswith('---') or line.startswith('+++'):
            continue
        if count >= max_lines:
            break
        if line.startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if m:
                old_ln = int(m.group(1))
                new_ln = int(m.group(2))
            rendered.append(Text(line, style='dim cyan'))
            count += 1
            continue
        if line.startswith('+') and not line.startswith('+++'):
            content = line[1:].rstrip('\n')
            t = Text(no_wrap=True)
            t.append(f'{new_ln:>4} ', style=LN_STYLE)
            t.append('+ ', style=MARKER_ADD)
            t.append(content.ljust(160), style=ADD_BG)
            rendered.append(t)
            new_ln += 1
        elif line.startswith('-') and not line.startswith('---'):
            content = line[1:].rstrip('\n')
            t = Text(no_wrap=True)
            t.append(f'{old_ln:>4} ', style=LN_STYLE)
            t.append('- ', style=MARKER_DEL)
            t.append(content.ljust(160), style=DEL_BG)
            rendered.append(t)
            old_ln += 1
        else:
            content = (line[1:] if line.startswith(' ') else line).rstrip('\n')
            t = Text(no_wrap=True)
            t.append(f'{new_ln:>4} ', style=LN_STYLE)
            t.append('  ', style='')
            t.append(content, style=CONTEXT_STYLE)
            rendered.append(t)
            old_ln += 1
            new_ln += 1
        count += 1

    return Group(*rendered)
