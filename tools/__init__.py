# read_file 은 클라 측 (RPC-02 / agent.CLIENT_SIDE_TOOLS) — 서버 import 제외 (D-18, Phase 1).
from .fs import write_file, edit_file, list_files, grep_search
from .shell import run_command, run_python
from .git import git_status, git_diff, git_log, git_diff_full, git_add, git_commit, git_checkout, git_stash
from .web import search_web, fetch_page
from .claude_cli import ask as _claude_ask_raw, is_available as _claude_available

def ask_claude(query: str, context: str = '') -> dict:
    '''Claude CLI에 위임. 로컬 모델이 해결하기 어려운 복잡한 작업에 사용.'''
    if not _claude_available():
        return {'ok': False, 'error': 'claude CLI를 찾을 수 없습니다.'}
    try:
        full = f'{context}\n\n{query}' if context else query
        result = _claude_ask_raw(full)
        return {'ok': True, 'response': result}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .mcp import StdioMCPClient

TOOL_DEFINITIONS = [
    {
        'name': 'read_file',
        'description': (
            '파일 내용을 읽는다. 줄 번호가 앞에 붙어 반환됨.\n'
            '대용량 파일은 offset/limit으로 부분 읽기 가능.\n'
            '예: read_file(path="src/main.py", offset=50, limit=100)'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'path':   {'type': 'string',  'description': '파일 경로'},
                'offset': {'type': 'integer', 'description': '시작 줄 번호 (1-based, 기본 1)'},
                'limit':  {'type': 'integer', 'description': '읽을 줄 수 (기본 0=전체)'},
            },
            'required': ['path'],
        },
    },
    {
        'name': 'write_file',
        'description': '파일에 내용을 쓴다 (전체 덮어쓰기). 새 파일 생성 또는 전면 교체 시 사용. 부분 수정은 edit_file 사용.',
        'parameters': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': '파일 경로'},
                'content': {'type': 'string', 'description': '파일 내용 전체'},
            },
            'required': ['path', 'content'],
        },
    },
    {
        'name': 'edit_file',
        'description': (
            '파일의 특정 문자열을 다른 문자열로 교체한다. 부분 수정 시 write_file보다 우선 사용.\n'
            '- old_string이 1곳만 있으면 그 위치를 교체\n'
            '- old_string이 여러 곳 있으면 replace_all=true로 전체 교체, 아니면 더 구체적으로 지정\n'
            '- old_string 찾기 전에 반드시 read_file로 현재 내용 확인'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'path':        {'type': 'string',  'description': '파일 경로'},
                'old_string':  {'type': 'string',  'description': '교체할 기존 문자열 (정확히 일치해야 함)'},
                'new_string':  {'type': 'string',  'description': '새 문자열'},
                'replace_all': {'type': 'boolean', 'description': '모든 일치 항목 교체 여부 (기본 false)'},
            },
            'required': ['path', 'old_string', 'new_string'],
        },
    },
    {
        'name': 'grep_search',
        'description': (
            '파일 또는 디렉토리에서 정규식 패턴을 검색한다. list_files보다 코드 검색에 적합.\n'
            '예: grep_search(pattern="def run", path=".", include=r"\\.py$")'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'pattern': {'type': 'string', 'description': '검색할 정규식 패턴'},
                'path': {'type': 'string', 'description': '검색할 파일 또는 디렉토리 경로 (기본: 현재 디렉토리)'},
                'include': {'type': 'string', 'description': '파일 이름 필터 정규식. 예: \\.py$, \\.(ts|tsx)$'},
                'case_insensitive': {'type': 'boolean', 'description': '대소문자 무시 여부 (기본: false)'},
                'context_lines': {'type': 'integer', 'description': '매치 전후 표시할 줄 수 (기본: 0)'},
            },
            'required': ['pattern'],
        },
    },
    {
        'name': 'list_files',
        'description': (
            '글로브 패턴으로 파일 목록을 가져온다. pattern 인자 필수 — 빈 호출 금지. '
            '디렉토리 전체 나열은 pattern="*", 재귀 검색은 pattern="**/*.py" 같은 식으로. '
            '예: list_files(pattern="*.html"), list_files(pattern="src/**/*.ts")'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'pattern': {
                    'type': 'string',
                    'description': '글로브 패턴(필수). 예: *, *.py, src/**/*.ts. 빈 문자열 금지.',
                },
            },
            'required': ['pattern'],
        },
    },
    {
        'name': 'run_command',
        'description': '셸 명령어를 실행한다. 위험 명령어(rm, mv, chmod, kill 등)는 실행 전 사용자 확인이 필요하다.',
        'parameters': {
            'type': 'object',
            'properties': {
                'command': {'type': 'string', 'description': '실행할 명령어'},
            },
            'required': ['command'],
        },
    },
    {
        'name': 'run_python',
        'description': '파이썬 코드를 임시 파일로 실행하고 stdout/stderr를 반환한다',
        'parameters': {
            'type': 'object',
            'properties': {
                'code': {'type': 'string', 'description': '실행할 파이썬 코드'},
            },
            'required': ['code'],
        },
    },
    {
        'name': 'git_status',
        'description': 'git status --short 결과를 반환한다',
        'parameters': {
            'type': 'object',
            'properties': {
                'cwd': {'type': 'string', 'description': '작업 디렉토리 (기본값: 현재)'},
            },
        },
    },
    {
        'name': 'git_diff',
        'description': 'git diff 요약을 반환한다',
        'parameters': {
            'type': 'object',
            'properties': {
                'cwd': {'type': 'string', 'description': '작업 디렉토리'},
                'staged': {'type': 'boolean', 'description': 'staged diff 여부'},
            },
        },
    },
    {
        'name': 'git_log',
        'description': '최근 커밋 로그를 반환한다',
        'parameters': {
            'type': 'object',
            'properties': {
                'cwd': {'type': 'string', 'description': '작업 디렉토리'},
                'n': {'type': 'integer', 'description': '가져올 커밋 수 (기본 10)'},
            },
        },
    },
    {
        'name': 'git_diff_full',
        'description': 'git diff HEAD 전체 내용을 반환한다 (리뷰용)',
        'parameters': {
            'type': 'object',
            'properties': {
                'cwd': {'type': 'string', 'description': '작업 디렉토리'},
            },
        },
    },
    {
        'name': 'git_add',
        'description': '파일을 스테이징한다. git add. 커밋 전에 호출.',
        'parameters': {
            'type': 'object',
            'properties': {
                'paths': {
                    'description': '스테이징할 경로 (문자열 또는 배열). 기본 "." (전체)',
                    'oneOf': [
                        {'type': 'string'},
                        {'type': 'array', 'items': {'type': 'string'}},
                    ],
                },
                'cwd': {'type': 'string', 'description': '작업 디렉토리'},
            },
        },
    },
    {
        'name': 'git_commit',
        'description': '스테이징된 변경사항을 커밋한다. git commit -m.',
        'parameters': {
            'type': 'object',
            'properties': {
                'message': {'type': 'string', 'description': '커밋 메시지'},
                'cwd':     {'type': 'string', 'description': '작업 디렉토리'},
            },
            'required': ['message'],
        },
    },
    {
        'name': 'git_checkout',
        'description': '브랜치를 전환하거나 새 브랜치를 생성한다. git checkout [-b].',
        'parameters': {
            'type': 'object',
            'properties': {
                'branch': {'type': 'string',  'description': '브랜치 이름'},
                'create': {'type': 'boolean', 'description': '새 브랜치 생성 여부 (기본 false)'},
                'cwd':    {'type': 'string',  'description': '작업 디렉토리'},
            },
            'required': ['branch'],
        },
    },
    {
        'name': 'git_stash',
        'description': 'git stash. 작업 중 변경사항을 임시 저장하거나 복원한다.',
        'parameters': {
            'type': 'object',
            'properties': {
                'action':  {'type': 'string', 'description': 'push(저장)/pop(복원)/list(목록)/drop(삭제). 기본 push'},
                'message': {'type': 'string', 'description': 'stash 메시지 (push 시 선택)'},
                'cwd':     {'type': 'string', 'description': '작업 디렉토리'},
            },
        },
    },
    {
        'name': 'search_web',
        'description': (
            'DuckDuckGo로 웹 검색. 최신 정보, 라이브러리, 에러 메시지 등 검색 시 사용. API 키 불필요.\n'
            '쿼리 작성 규칙:\n'
            '- 게임·영화·제품 등 고유명사는 반드시 공식 명칭 사용 (음차/번역 금지)\n'
            '  예) 붉은 사막 → "Crimson Desert" 또는 "붉은 사막"\n'
            '  예) 젤다의 전설 → "The Legend of Zelda" 또는 "젤다의 전설"\n'
            '- 모르는 영문명은 원어(한국어) 그대로 검색\n'
            '- 키릴·그리스 등 다른 문자 체계를 억지로 섞지 말 것'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': '검색어 (공식 명칭 사용, 임의 음차 금지)'},
                'max_results': {'type': 'integer', 'description': '최대 결과 수 (기본 5)'},
            },
            'required': ['query'],
        },
    },
    {
        'name': 'fetch_page',
        'description': '특정 URL의 텍스트 내용을 가져온다 (HTML 태그 제거)',
        'parameters': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'description': '가져올 URL'},
                'max_chars': {'type': 'integer', 'description': '최대 문자 수 (기본 4000)'},
            },
            'required': ['url'],
        },
    },
    {
        'name': 'ask_claude',
        'description': (
            'Claude CLI에 작업을 위임한다. 다음 경우에만 사용:\n'
            '- 5개 이상의 파일에 걸친 복잡한 리팩토링\n'
            '- 동일한 접근으로 2회 이상 실패한 경우\n'
            '- 시스템 아키텍처 전반을 이해해야 하는 작업\n'
            '- 사용자가 명시적으로 "Claude에게" 또는 "더 정확하게" 요청한 경우\n'
            '다음에는 사용하지 말 것:\n'
            '- 단순 파일 편집, 단일 함수 구현, 문서화, 반복 패턴 작업'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Claude에게 전달할 질문 또는 작업 내용'},
                'context': {'type': 'string', 'description': '추가로 전달할 배경 정보 (선택)'},
            },
            'required': ['query'],
        },
    },
]

def register_mcp_tools(clients: 'dict[str, StdioMCPClient]') -> list[str]:
    '''MCP 클라이언트 목록에서 툴을 TOOL_DEFINITIONS/TOOL_MAP에 동적 등록.
    등록된 툴 이름 목록을 반환.'''
    registered = []
    for server_name, client in clients.items():
        for tool in client.tools:
            qualified = f'mcp__{server_name}__{tool["name"]}'
            if qualified in TOOL_MAP:
                continue

            # MCP inputSchema → Ollama tool parameters 변환
            schema = tool.get('inputSchema') or tool.get('parameters') or {
                'type': 'object', 'properties': {},
            }

            TOOL_DEFINITIONS.append({
                'name': qualified,
                'description': f'[MCP:{server_name}] {tool.get("description", "")}',
                'parameters': schema,
            })

            # 클로저로 server_name과 tool_name 캡처
            def _make_caller(c, tn):
                def _call(**kwargs):
                    return c.call_tool(tn, kwargs)
                return _call

            TOOL_MAP[qualified] = _make_caller(client, tool['name'])
            registered.append(qualified)
    return registered


TOOL_MAP = {
    # read_file 본체는 클라 측 (RPC-03, D-18). agent.py:CLIENT_SIDE_TOOLS 분기가 TOOL_MAP lookup 보다 먼저 가로챔.
    'write_file': write_file,
    'edit_file': edit_file,
    'grep_search': grep_search,
    'list_files': list_files,
    'run_command': run_command,
    'run_python': run_python,
    'git_status': git_status,
    'git_diff': git_diff,
    'git_log': git_log,
    'git_diff_full': git_diff_full,
    'git_add':      git_add,
    'git_commit':   git_commit,
    'git_checkout': git_checkout,
    'git_stash':    git_stash,
    'search_web':   search_web,
    'fetch_page':   fetch_page,
    'ask_claude':   ask_claude,
}
