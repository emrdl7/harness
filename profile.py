import os
import tomllib

HARNESS_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBAL_DOC  = os.path.join(HARNESS_DIR, 'HARNESS.md')

# 전역 설정 파일 위치 (~/.harness.toml)
GLOBAL_CONFIG = os.path.expanduser('~/.harness.toml')

# 프로젝트 지침 파일 (우선순위 순)
_GUIDE_NAMES = ['CLAUDE.md', 'HARNESS.md']

# 보조 문서 후보 — working_dir에서만 탐색
_EXTRA_CANDIDATES = [
    'README.md', 'CONTRIBUTING.md', 'DEVELOPMENT.md',
    'ARCHITECTURE.md', '.cursorrules',
]
_EXTRA_MAX_CHARS = 4000

DEFAULTS = {
    'language':       'korean',
    'max_retries':    3,
    'confirm_writes': True,
    'confirm_bash':   True,
    'auto_index':     True,
    'ignore_dirs':    [],
    'context_files':  [],
    'conventions':    '',
    # 모델 설정 — 비어 있으면 config.py 기본값 유지
    'model':          '',
    'ollama_url':     '',
    'temperature':    -1.0,
    'num_ctx':        0,
    'num_predict':    0,
    # MCP 서버 목록 — [[mcp_servers]] 배열
    'mcp_servers':    [],
    # 자율 기능 진화 — 세션 종료 시 패턴 분석 + 유휴 시 코드 개선 실행
    'auto_evolve':    False,
}

# 환경변수 → 설정 키 매핑 (값 타입 포함)
_ENV_MAP = {
    'HARNESS_LANGUAGE':       ('language',       'str'),
    'HARNESS_CONFIRM_WRITES': ('confirm_writes',  'bool'),
    'HARNESS_CONFIRM_BASH':   ('confirm_bash',    'bool'),
    'HARNESS_AUTO_INDEX':     ('auto_index',      'bool'),
    'HARNESS_MAX_RETRIES':    ('max_retries',     'int'),
}


def load(working_dir: str) -> dict:
    # 1단계: 기본값
    config = dict(DEFAULTS)

    # 2단계: 전역 설정 (~/.harness.toml)
    _merge_toml(config, GLOBAL_CONFIG)

    # 3단계: 프로젝트 설정 ({working_dir}/.harness.toml)
    _merge_toml(config, os.path.join(working_dir, '.harness.toml'))

    # 4단계: 환경변수 (최우선)
    _merge_env(config)

    # 문서 로드 (설정과 무관하게 항상)
    config['global_doc'] = _load_text(GLOBAL_DOC)

    guide_path = _find_guide(working_dir)
    if guide_path and os.path.abspath(guide_path) != os.path.abspath(GLOBAL_DOC):
        config['project_doc']      = _load_text(guide_path)
        config['project_doc_path'] = guide_path
    else:
        config['project_doc']      = ''
        config['project_doc_path'] = ''

    config['extra_docs'] = _load_extra_docs(working_dir, config.get('context_files', []))

    return config


_LIST_MERGE_KEYS = {'mcp_servers'}


def _merge_toml(config: dict, path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        for k, v in data.items():
            if k in _LIST_MERGE_KEYS and isinstance(v, list):
                # 배열 키는 덮어쓰지 않고 합산
                config[k] = list(config.get(k) or []) + v
            else:
                config[k] = v
    except Exception:
        pass


def _merge_env(config: dict) -> None:
    for env_key, (cfg_key, typ) in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        if typ == 'bool':
            config[cfg_key] = val.lower() in ('1', 'true', 'yes')
        elif typ == 'int':
            try:
                config[cfg_key] = int(val)
            except ValueError:
                pass
        else:
            config[cfg_key] = val


def _find_guide(start: str) -> str:
    '''start 디렉토리부터 위로 올라가며 CLAUDE.md / HARNESS.md 탐색.
    .git 루트 또는 홈 디렉토리에서 멈춤.'''
    home    = os.path.expanduser('~')
    current = os.path.abspath(start)
    visited = set()
    while current not in visited:
        visited.add(current)
        for name in _GUIDE_NAMES:
            path = os.path.join(current, name)
            if os.path.exists(path):
                return path
        if os.path.exists(os.path.join(current, '.git')):
            break
        parent = os.path.dirname(current)
        if parent == current or current == home:
            break
        current = parent
    return ''


def _load_extra_docs(working_dir: str, custom_files: list) -> list:
    '''[(filename, content), ...] 반환'''
    docs = []
    seen = set()

    candidates = list(_EXTRA_CANDIDATES) + [
        os.path.expanduser(f) if f.startswith('~') else os.path.join(working_dir, f)
        for f in custom_files
    ]

    for item in candidates:
        path = item if os.path.isabs(item) else os.path.join(working_dir, item)
        path = os.path.abspath(path)
        if path in seen or not os.path.exists(path):
            continue
        seen.add(path)
        content = _load_text(path, max_chars=_EXTRA_MAX_CHARS)
        if content.strip():
            docs.append((os.path.basename(path), content))

    return docs


def _load_text(path: str, max_chars: int = 0) -> str:
    if not os.path.exists(path):
        return ''
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + '\n... (truncated)'
        return text
    except Exception:
        return ''


def create_template(working_dir: str) -> str:
    path = os.path.join(working_dir, '.harness.toml')
    template = '''# harness 프로젝트 설정
language = "korean"
confirm_writes = true
confirm_bash = true
auto_index = true

conventions = """
"""

context_files = []
ignore_dirs = []

# ── 모델 설정 ──────────────────────────────────────────────────────
# 이 섹션만 바꾸면 모델 전환 완료. 비워두면 config.py 기본값 사용.
model       = ""           # 예: "llama3.3:70b", "deepseek-coder:33b"
ollama_url  = ""           # 예: "http://remote-server:11434"
temperature = -1.0         # -1 = 기본값(0.2) 유지. 범위: 0.0~1.0
num_ctx     = 0            # 0 = 기본값(32768) 유지
num_predict = 0            # 0 = 기본값(4096) 유지

# ── MCP 서버 설정 ────────────────────────────────────────────────
# 각 [[mcp_servers]] 블록이 하나의 서버. 툴은 mcp__<name>__<tool> 형식으로 등록됨.
# 예:
# [[mcp_servers]]
# name    = "filesystem"
# command = ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
#
# [[mcp_servers]]
# name    = "memory"
# command = ["npx", "-y", "@modelcontextprotocol/server-memory"]
# [mcp_servers.env]
# SOME_VAR = "value"

# ── 자율 진화 설정 ───────────────────────────────────────────────
# auto_evolve = true 이면:
#   - 세션 종료 시 사용 패턴 분석 → 개선 제안서 생성
#   - 유휴 시간에 제안서를 실제 코드로 구현 (하루 최대 3회)
# /evolve proposals  → 대기 중인 제안서 확인
# /evolve run        → 즉시 실행
# /evolve changelog  → 변경 이력 확인
auto_evolve = false

# ── 훅 설정 ──────────────────────────────────────────────────────
# 사용 가능한 환경변수: HARNESS_TOOL, HARNESS_ARGS, HARNESS_RESULT_OK, HARNESS_WORKING_DIR
[hooks]
pre_tool_use  = ""   # 비-0 종료 시 툴 실행 차단
post_tool_use = ""
on_stop       = ""
'''
    with open(path, 'w', encoding='utf-8') as f:
        f.write(template)
    return path
