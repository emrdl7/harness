'''슬래시 라우터 — 명령 문자열을 파싱해 적절한 핸들러로 디스패치.'''
from .types import SlashState, SlashResult, SlashContext
from . import handlers as h


# 라우터가 알고 있는 명령 → (핸들러, 인자가 필요한지)
# 인자 필요 명령은 호출자가 cmd 문자열에서 추출해 핸들러에 전달.
KNOWN_COMMANDS = {
    '/clear':    (h.slash_clear,    False),
    '/undo':     (h.slash_undo,     False),
    '/cd':       (h.slash_cd,       True),
    '/init':     (h.slash_init,     False),
    '/help':     (h.slash_help,     False),
    '/save':     (h.slash_save,     False),
    '/resume':   (h.slash_resume,   True),   # 인자 옵셔널이지만 라우터는 '있어도 됨'으로 처리
    '/sessions': (h.slash_sessions, False),
    '/files':    (h.slash_files,    False),
    '/index':    (h.slash_index,    False),
    '/plan':     (h.slash_plan,     True),
}


def parse(cmd: str) -> tuple[str, str]:
    '''"/cd /tmp/foo" → ("/cd", "/tmp/foo"). 인자 없으면 빈 문자열.'''
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0] if parts else ''
    arg = parts[1] if len(parts) > 1 else ''
    return name, arg


def dispatch(cmd: str, state: SlashState, ctx: SlashContext | None = None) -> SlashResult:
    '''명령 문자열을 파싱해 핸들러 호출.

    ctx: 핸들러가 사용할 콜백/외부 함수. None이면 빈 SlashContext()를 만들어 사용.
    알 수 없는 명령은 SlashResult.unknown으로 반환 (handled=False).
    프런트엔드는 handled=False일 때 자기 로컬 핸들러로 폴백할 수 있다.
    '''
    if ctx is None:
        ctx = SlashContext()
    name, arg = parse(cmd)
    if name not in KNOWN_COMMANDS:
        return SlashResult.unknown(state, f'알 수 없는 명령: {name}')
    fn, needs_arg = KNOWN_COMMANDS[name]
    if needs_arg:
        return fn(state, ctx, arg)
    return fn(state, ctx)
