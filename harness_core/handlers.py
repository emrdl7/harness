'''의존성 0~1인 슬래시 핸들러.

콘솔/네트워크/스레드 의존이 없음. agent 실행이 필요한 /plan, /cplan은
다음 단계에서 callback 인젝션으로 추가.
'''
import os

import context
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


_IMPROVE_SYSTEM = '''당신은 이 하네스 시스템의 자기 개선 전문가입니다.
다음 단계로 개선을 수행하세요:

1. 실패 로그를 분석해 반복되는 문제 패턴을 파악하세요
2. 소스 코드를 읽어 해당 문제의 근본 원인을 찾으세요
3. 구체적인 개선안을 코드로 작성하고 write_file로 적용하세요

수정 가능한 파일 (HARNESS_DIR 기준):
- config.py, agent.py
- tools/__init__.py, tools/fs.py, tools/shell.py, tools/git.py
- context/indexer.py, context/retriever.py

주의사항:
- 파일 전체를 교체할 때만 write_file을 사용하세요
- 수정 후 반드시 run_command("python3 -m py_compile <파일>")로 검증하세요
- 검증 실패 시 원래대로 복구하세요
- 작업이 끝나면 어떤 파일을 왜 수정했는지 요약하세요
'''

_IMPROVE_VALIDATE_FILES = [
    'config.py', 'agent.py',
    'tools/__init__.py', 'tools/fs.py', 'tools/shell.py',
]


def slash_improve(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/improve — 하네스 자기 개선.

    1. 최근 실패 로그 수집 + 현재 소스 읽기
    2. backup_sources()로 스냅샷
    3. ctx.run_agent_ephemeral로 별도 세션에서 agent 실행
    4. py_compile 검증 결과 data['validation']에 담아 반환

    drift 정리: server와 main이 이제 동일한 검증/피드백 경로를 사용.
    '''
    if ctx.run_agent_ephemeral is None:
        return SlashResult.error(state, '내부 오류: run_agent_ephemeral 콜백이 없습니다')

    from session.logger import read_recent
    from tools.improve import (
        backup_sources, read_sources, validate_python, HARNESS_DIR,
    )

    logs = read_recent(days=7)
    sources = read_sources()
    backup_path = backup_sources()

    prompt = (
        '최근 실패 로그:\n'
        f'{logs}\n\n'
        '---\n'
        '하네스 소스 코드:\n'
        f'{sources[:12000]}\n\n'
        '위 로그와 소스를 분석해 개선이 필요한 부분을 찾고 수정하세요.\n'
        '수정 후 각 파일을 py_compile로 검증하세요.'
    )
    system_prompt = _IMPROVE_SYSTEM + f'\nHARNESS_DIR: {HARNESS_DIR}'

    ctx.run_agent_ephemeral(
        prompt,
        system_prompt=system_prompt,
        working_dir=HARNESS_DIR,
        profile=state.profile,
    )

    validation = []
    all_ok = True
    for rel in _IMPROVE_VALIDATE_FILES:
        fpath = os.path.join(HARNESS_DIR, rel)
        if not os.path.exists(fpath):
            continue
        r = validate_python(fpath)
        validation.append({
            'file': rel,
            'ok': r['ok'],
            'error': r.get('error', ''),
        })
        if not r['ok']:
            all_ok = False

    if all_ok:
        return SlashResult.ok(state, '개선 완료', backup=backup_path, validation=validation)
    return SlashResult.warn(state, '문법 오류 발견 — /restore 로 롤백 가능',
                            backup=backup_path, validation=validation)


_LEARN_SYSTEM = '''당신은 하네스의 자기학습 에이전트입니다.
세션 분석 결과를 바탕으로 HARNESS.md 파일을 개선하세요.

규칙:
- 기존 내용을 먼저 read_file로 확인 후 수정
- 중복 내용 추가 금지
- 마크다운 형식 유지
- 변경이 없으면 파일을 건드리지 말 것
- 완료 후 어떤 내용을 추가/수정했는지 한 줄 요약
'''


def slash_learn(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/learn — 현재 세션을 요약해 HARNESS.md에 반영.

    drift 정리: 기존 server는 profile={}로 agent.run 호출 → state.profile 사용으로 통일.
    '''
    if ctx.run_agent_ephemeral is None:
        return SlashResult.error(state, '내부 오류: run_agent_ephemeral 콜백이 없습니다')
    user_msgs = [m for m in state.messages if m.get('role') == 'user']
    if not user_msgs:
        return SlashResult.info(state, '학습할 세션 내용이 없습니다')

    from session.analyzer import summarize_session, build_learn_prompt

    summary = summarize_session(state.messages)
    global_doc = state.profile.get('global_doc', '')
    project_doc = state.profile.get('project_doc', '')
    learn_prompt = build_learn_prompt(summary, global_doc, project_doc, state.working_dir)

    ctx.run_agent_ephemeral(
        learn_prompt,
        system_prompt=_LEARN_SYSTEM,
        working_dir=state.working_dir,
        profile=state.profile,
    )
    return SlashResult.ok(state, 'HARNESS.md 갱신 완료')


def slash_plan(state: SlashState, ctx: SlashContext, query: str) -> SlashResult:
    '''/plan <작업> — agent를 plan_mode=True로 실행.

    ctx.run_agent 시그니처: (user_input, *, plan_mode, context_snippets) -> None.
    agent는 session_messages를 in-place 갱신하므로 핸들러는 state 변경 없이 반환.
    '''
    if not query:
        return SlashResult.warn(state, '사용법: /plan <작업 내용>')
    if ctx.run_agent is None:
        return SlashResult.error(state, '내부 오류: run_agent 콜백이 없습니다')
    snippets = context.search(query, state.working_dir) \
        if context.is_indexed(state.working_dir) else ''
    ctx.run_agent(query, plan_mode=True, context_snippets=snippets)
    return SlashResult.ok(state, '')


def slash_index(state: SlashState, ctx: SlashContext) -> SlashResult:
    '''/index — working_dir 인덱싱. data={'indexed': N, 'skipped': M}.

    context.index_directory는 I/O + 토크나이징이 있어 수초 소요될 수 있음.
    프런트엔드가 spinner/상태 알림을 띄워야 한다면 호출 전에 처리.
    '''
    result = context.index_directory(state.working_dir)
    return SlashResult.ok(
        state,
        f'인덱싱 완료 {result["indexed"]}개 청크',
        indexed=result['indexed'],
        skipped=result['skipped'],
    )


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
