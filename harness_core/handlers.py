'''의존성 0~1인 슬래시 핸들러 — 1차 추출.

여기 모인 핸들러는 콘솔/네트워크/스레드 의존이 전혀 없다.
agent 실행이 필요한 /plan, /cplan 등은 다음 단계에서 callback 인젝션으로 추가.
'''
import os

import profile as prof

from .types import SlashState, SlashResult, evolve


def slash_clear(state: SlashState) -> SlashResult:
    '''/clear — 세션 메시지 비우기 (system 메시지도 비움; agent.run이 다시 채운다).'''
    return SlashResult.info(evolve(state, messages=[]), '대화 초기화')


def slash_undo(state: SlashState) -> SlashResult:
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


def slash_cd(state: SlashState, path: str) -> SlashResult:
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


def slash_init(state: SlashState) -> SlashResult:
    '''/init — working_dir에 .harness.toml 템플릿 생성.'''
    target = os.path.join(state.working_dir, '.harness.toml')
    if os.path.exists(target):
        return SlashResult.warn(state, f'이미 존재합니다: {target}')
    created = prof.create_template(state.working_dir)
    return SlashResult.ok(state, f'생성됨: {created}')


def slash_help(state: SlashState) -> SlashResult:
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
