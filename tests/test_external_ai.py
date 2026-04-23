'''tools.external_ai — 외부 AI 에이전트 레지스트리.

Claude는 기본 등록. Codex/Gemini 같은 새 어댑터를 register로 붙일 수 있는
확장 지점인지 검증.
'''
import pytest

from tools import external_ai


class TestDefaultRegistration:
    def test_claude_registered_by_default(self):
        a = external_ai.get('claude')
        assert a is not None
        assert a.key == 'claude'
        assert a.name == 'Claude'

    def test_claude_ask_is_callable(self):
        a = external_ai.get('claude')
        assert callable(a.ask)
        assert callable(a.is_available)

    def test_list_all_includes_claude(self):
        keys = [a.key for a in external_ai.list_all()]
        assert 'claude' in keys


class TestRegistryAPI:
    @pytest.fixture(autouse=True)
    def _isolate_registry(self):
        '''테스트마다 registry 스냅샷 → 복원 — 교차 오염 방지.'''
        snapshot = external_ai._REGISTRY.copy()
        yield
        external_ai._REGISTRY.clear()
        external_ai._REGISTRY.update(snapshot)

    def test_register_new_agent(self):
        stub = external_ai.ExternalAgent(
            key='testfoo',
            name='TestFoo',
            ask=lambda q, on_token=None, cwd=None, model=None: 'ok',
            is_available=lambda: True,
            description='unit test stub',
        )
        external_ai.register(stub)
        assert external_ai.get('testfoo') is stub

    def test_register_overwrites_same_key(self):
        '''같은 key 재등록은 덮어쓰기 — 테스트/hot reload 편의.'''
        s1 = external_ai.ExternalAgent(
            key='dup', name='v1',
            ask=lambda q, **kw: 'v1',
            is_available=lambda: True,
        )
        s2 = external_ai.ExternalAgent(
            key='dup', name='v2',
            ask=lambda q, **kw: 'v2',
            is_available=lambda: True,
        )
        external_ai.register(s1)
        external_ai.register(s2)
        assert external_ai.get('dup').name == 'v2'

    def test_list_available_filters_unavailable(self):
        external_ai.register(external_ai.ExternalAgent(
            key='ghost', name='Ghost',
            ask=lambda q, **kw: '',
            is_available=lambda: False,
        ))
        external_ai.register(external_ai.ExternalAgent(
            key='live', name='Live',
            ask=lambda q, **kw: 'ok',
            is_available=lambda: True,
        ))
        available_keys = [a.key for a in external_ai.list_available()]
        assert 'live' in available_keys
        assert 'ghost' not in available_keys

    def test_get_missing_returns_none(self):
        assert external_ai.get('nonexistent') is None


class TestProtocolCompliance:
    '''Claude 어댑터가 선언된 ExternalAgent.ask 시그니처와 호환되는지.'''

    def test_claude_ask_signature_matches_protocol(self):
        import inspect
        a = external_ai.get('claude')
        sig = inspect.signature(a.ask)
        params = sig.parameters
        # query 는 첫 번째, 나머지는 키워드로 접근 가능해야 함
        assert 'query' in params
        for kw in ('on_token', 'cwd', 'model'):
            assert kw in params, f'{kw} missing from ask signature'
