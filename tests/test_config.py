'''config.py — runtime_override 동작.'''
import importlib
import pytest

import config


@pytest.fixture(autouse=True)
def reload_config():
    '''매 테스트 후 config 모듈을 재로딩 — 전역 상태 격리.'''
    yield
    importlib.reload(config)


class TestRuntimeOverride:
    def test_no_keys_keeps_defaults(self):
        original_model = config.MODEL
        original_ctx = config.CONTEXT_WINDOW
        config.runtime_override({})
        assert config.MODEL == original_model
        assert config.CONTEXT_WINDOW == original_ctx

    def test_model_override(self):
        config.runtime_override({'model': 'llama3.3:70b'})
        assert config.MODEL == 'llama3.3:70b'

    def test_ollama_url_override(self):
        config.runtime_override({'ollama_url': 'http://remote:11434'})
        assert config.OLLAMA_BASE_URL == 'http://remote:11434'

    def test_temperature_negative_ignored(self):
        before = config.OLLAMA_OPTIONS['temperature']
        config.runtime_override({'temperature': -1})
        assert config.OLLAMA_OPTIONS['temperature'] == before

    def test_temperature_zero_applied(self):
        '''0.0은 유효한 값 — -1만 무시되어야 함.'''
        config.runtime_override({'temperature': 0.0})
        assert config.OLLAMA_OPTIONS['temperature'] == 0.0

    def test_num_ctx_zero_ignored(self):
        before = config.CONTEXT_WINDOW
        config.runtime_override({'num_ctx': 0})
        assert config.CONTEXT_WINDOW == before

    def test_num_ctx_applied(self):
        config.runtime_override({'num_ctx': 16384})
        assert config.CONTEXT_WINDOW == 16384
        assert config.OLLAMA_OPTIONS['num_ctx'] == 16384

    def test_approval_mode_override(self):
        config.runtime_override({'approval_mode': 'full-auto'})
        assert config.APPROVAL_MODE == 'full-auto'

    def test_empty_string_model_ignored(self):
        before = config.MODEL
        config.runtime_override({'model': ''})
        assert config.MODEL == before
