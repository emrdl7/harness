'''의존성 0~1인 슬래시 핸들러.

콘솔/네트워크/스레드 의존이 없음. agent 실행이 필요한 /plan, /cplan은
다음 단계에서 callback 인젝션으로 추가.
'''
import os

import profile as prof
import session as sess

from .types import SlashState, SlashResult, SlashContext, evolve


def slash_clear(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/clear — 세션 메시지 비우기 (system 메시지도 비움; agent.run이 다시 채운다).'''
    return SlashResult.info(evolve(state, messages=[]), '대화 초기화')


def slash_undo(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/undo — 마지막 user/assistant 한 쌍 제거. system은 보존.'''
    non_system = [m for m in state.messages if m.get('role') != 'system']
    if len(non_system) < 2:
        return SlashResult.info(state, '취소할 내용이 없습니다')
    system = [m for m in state.messages if m.get('role') == 'system']
    new_state = evolve(
        state,
        messages=system + non_system[:-2],
        undo_count=state.undo_count + 1,
    )
    return SlashResult.info(new_state, '마지막 교환 취소됨')


def slash_cd(state: SlashState, ctx: SlashContext, path: str) -> SlashResult:
    '''/cd <path> — working_dir 변경. 새 디렉토리의 profile 다시 로드, 세션 초기화.'''
    if not path:
        return SlashResult.warn(state, '사용법: /cd <경로>')
    new_dir = os.path.expanduser(path.strip())
    if not os.path.isdir(new_dir):
        return SlashResult.error(state, f'없는 경로: {path}')
    new_dir = os.path.abspath(new_dir)
    new_state = evolve(
        state,
        working_dir=new_dir,
        profile=prof.load(new_dir),
        messages=[],
    )
    return SlashResult.ok(new_state, f'작업 디렉토리: {new_dir}')


def slash_init(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/init — working_dir에 .harness.toml 템플릿 생성.'''
    target = os.path.join(state.working_dir, '.harness.toml')
    if os.path.exists(target):
        return SlashResult.warn(state, f'이미 존재합니다: {target}')
    created = prof.create_template(state.working_dir)
    return SlashResult.ok(state, f'생성됨: {created}')


def slash_save(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/save — 현재 세션을 디스크에 저장. data={'filename': ...}.'''
    filename = sess.save(state.messages, state.working_dir)
    return SlashResult.ok(state, f'저장됨: {filename}', filename=filename)


def slash_resume(state: SlashState, ctx: SlashContext, filename: str = '') -> SlashResult:
    '''/resume [filename] — 세션 복원. filename 없으면 working_dir 최신 세션.

    성공 시: 메시지/working_dir 갱신 + data={'turns': N, 'filename': ...}.
    데이터 없으면 정보 메시지 반환 + 상태 변경 없음.
    '''
    target = filename.strip() if filename else None
    data = sess.load(target) if target else sess.load_latest(state.working_dir)
    if not data:
        return SlashResult.info(state, '불러올 세션이 없습니다')
    loaded = data['messages']
    new_state = evolve(
        state,
        messages=loaded,
        working_dir=data.get('working_dir', state.working_dir),
    )
    turns = sum(1 for m in loaded if m.get('role') == 'user')
    return SlashResult.ok(new_state, f'세션 복원 ({turns}턴)', turns=turns)


def slash_sessions(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/sessions — 저장된 세션 목록. data={'sessions': [...]} (전체, 호출자가 슬라이스).'''
    sessions = sess.list_sessions()
    if not sessions:
        return SlashResult.info(state, '저장된 세션이 없습니다', sessions=[])
    return SlashResult.ok(state, f'{len(sessions)}개 세션', sessions=sessions)


_FILES_IGNORE = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next'}


def _build_tree(working_dir: str, max_depth: int = 3) -> dict:
    '''파일 트리 dict — main과 server가 공유.

    노드 형식: {'name': str, 'children': [...]} (children 없으면 파일).
    '''
    def _walk(path: str, depth: int):
        if depth > max_depth:
            return None
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return None
        node = {'name': os.path.basename(path), 'children': []}
        for e in entries:
            fp = os.path.join(path, e)
            if os.path.isdir(fp):
                if e not in _FILES_IGNORE:
                    child = _walk(fp, depth + 1)
                    if child:
                        node['children'].append(child)
            else:
                node['children'].append({'name': e})
        return node

    return _walk(working_dir, 1) or {'name': os.path.basename(working_dir), 'children': []}


def slash_files(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/files — working_dir의 파일 트리. data={'tree': {...}}.'''
    tree = _build_tree(state.working_dir)
    return SlashResult.ok(state, '', tree=tree)


def slash_help(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/help — 정적 도움말. 프런트엔드는 notice를 그대로 보여주거나 자체 헬프 사용.'''
    text = (
        '명령어:\n'
        '  /clear         대화 초기화\n'
        '  /undo          마지막 교환 취소\n'
        '  /cd <경로>     작업 디렉토리 변경\n'
        '  /init          .harness.toml 생성\n'
        '  /help          이 도움말\n'
        '  /quit /exit    종료'
    )
    return SlashResult.info(state, text)
