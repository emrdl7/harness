'''외부 AI 에이전트 레지스트리 — Claude / Codex / Gemini 등 슬롯.

현재 등록: Claude (tools/claude_cli.py 래핑)

미래에 Codex/Gemini를 붙일 때:
1. tools/codex_cli.py 같은 어댑터 작성 — ask/is_available 두 함수만 만들면 됨
2. 이 모듈 하단 _register_defaults() 에 한 줄 등록
3. /agents 에서 자동 표시. /ask_all 같은 병렬 라우터 도입 시 바로 활용 가능

ExternalAgent.ask 프로토콜 (모든 어댑터가 준수):
    ask(query: str, on_token=None, cwd: str | None = None,
        model: str | None = None) -> str

    - 스트리밍으로 응답을 받아 on_token 콜백에 라인 단위 전달
    - 최종 전체 응답 문자열을 반환
    - 실패 시 RuntimeError (미설치/네트워크/권한 등)

is_available() -> bool 은 CLI 바이너리 존재 혹은 API 키 유무를 빠르게 체크.
'''
from dataclasses import dataclass
from typing import Callable


@dataclass
class ExternalAgent:
    key: str                        # 'claude', 'codex', 'gemini'
    name: str                       # 표시용 'Claude', 'Codex', 'Gemini'
    ask: Callable                   # (query, on_token=None, cwd=None, model=None) -> str
    is_available: Callable          # () -> bool
    default_model: str | None = None
    description: str = ''


_REGISTRY: dict[str, ExternalAgent] = {}


def register(agent: ExternalAgent) -> None:
    '''에이전트 등록. 같은 key 재등록 시 덮어씀(테스트 편의).'''
    _REGISTRY[agent.key] = agent


def get(key: str) -> ExternalAgent | None:
    return _REGISTRY.get(key)


def list_all() -> list[ExternalAgent]:
    '''등록된 모든 에이전트(미설치 포함). 표시/진단용.'''
    return list(_REGISTRY.values())


def list_available() -> list[ExternalAgent]:
    '''실제 호출 가능한 에이전트만. 라우터 후보군.'''
    return [a for a in _REGISTRY.values() if a.is_available()]


def _register_defaults() -> None:
    '''모듈 import 시점에 기본 어댑터 등록.

    Claude는 tools.claude_cli 를 그대로 래핑(시그니처가 이미 프로토콜과 일치).
    '''
    from tools import claude_cli
    register(ExternalAgent(
        key='claude',
        name='Claude',
        ask=claude_cli.ask,
        is_available=claude_cli.is_available,
        description='Anthropic Claude Code CLI (서브프로세스)',
    ))


_register_defaults()
