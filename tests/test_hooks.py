'''tools/hooks.py — 훅 실행 + fail-mode 정책 (CONCERNS §1.9).

보안 hook이 timeout/exception으로 실행 실패할 때 기본은 deny(False),
HARNESS_HOOK_FAIL_MODE=allow opt-in 시에만 allow(True).
'''
import subprocess

import pytest

from tools import hooks


class TestRunHookBasic:
    def test_empty_command_returns_true(self):
        assert hooks.run_hook('', 'pre_tool_use') is True
        assert hooks.run_hook('   ', 'pre_tool_use') is True

    def test_zero_exit_returns_true(self):
        assert hooks.run_hook('true', 'pre_tool_use') is True

    def test_nonzero_exit_returns_false(self):
        assert hooks.run_hook('false', 'pre_tool_use') is False


class TestFailModeDeny:
    '''기본 mode — timeout/exception은 False (보안 hook 무력화 차단).'''

    def test_timeout_denies_by_default(self, monkeypatch):
        monkeypatch.delenv('HARNESS_HOOK_FAIL_MODE', raising=False)

        def _raise_timeout(*a, **k):
            raise subprocess.TimeoutExpired(cmd='x', timeout=1)

        monkeypatch.setattr(hooks.subprocess, 'run', _raise_timeout)
        assert hooks.run_hook('whatever', 'pre_tool_use') is False

    def test_generic_exception_denies_by_default(self, monkeypatch):
        monkeypatch.delenv('HARNESS_HOOK_FAIL_MODE', raising=False)

        def _raise(*a, **k):
            raise FileNotFoundError('hook binary missing')

        monkeypatch.setattr(hooks.subprocess, 'run', _raise)
        assert hooks.run_hook('/nonexistent/hook', 'pre_tool_use') is False

    def test_deny_explicitly(self, monkeypatch):
        monkeypatch.setenv('HARNESS_HOOK_FAIL_MODE', 'deny')

        def _raise(*a, **k):
            raise RuntimeError('boom')

        monkeypatch.setattr(hooks.subprocess, 'run', _raise)
        assert hooks.run_hook('x', 'pre_tool_use') is False


class TestFailModeAllow:
    '''opt-in — HARNESS_HOOK_FAIL_MODE=allow 시 기존 fail-open 동작 복원.'''

    def test_timeout_allows_when_opted_in(self, monkeypatch):
        monkeypatch.setenv('HARNESS_HOOK_FAIL_MODE', 'allow')

        def _raise_timeout(*a, **k):
            raise subprocess.TimeoutExpired(cmd='x', timeout=1)

        monkeypatch.setattr(hooks.subprocess, 'run', _raise_timeout)
        assert hooks.run_hook('slow-hook', 'pre_tool_use') is True

    def test_exception_allows_when_opted_in(self, monkeypatch):
        monkeypatch.setenv('HARNESS_HOOK_FAIL_MODE', 'allow')

        def _raise(*a, **k):
            raise FileNotFoundError('missing')

        monkeypatch.setattr(hooks.subprocess, 'run', _raise)
        assert hooks.run_hook('x', 'pre_tool_use') is True

    def test_allow_value_case_insensitive(self, monkeypatch):
        monkeypatch.setenv('HARNESS_HOOK_FAIL_MODE', 'ALLOW')

        def _raise(*a, **k):
            raise RuntimeError('boom')

        monkeypatch.setattr(hooks.subprocess, 'run', _raise)
        assert hooks.run_hook('x', 'pre_tool_use') is True
