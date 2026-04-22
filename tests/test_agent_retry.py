'''agent._stream_response — Ollama 재시도 동작 (CONCERNS §1.21).

requests.post를 monkeypatch로 가짜로 바꿔 재시도 횟수와 분기를 검증.
실제 Ollama / 백오프 sleep은 일어나지 않는다.
'''
import json

import pytest
import requests

import agent


class _MockResponse:
    def __init__(self, status_code: int = 200, lines: list[bytes] | None = None):
        self.status_code = status_code
        self._lines = lines or []

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}', response=self)

    def iter_lines(self):
        return iter(self._lines)

    def close(self):
        pass


def _ok_lines(text: str = 'ok') -> list[bytes]:
    return [json.dumps({'message': {'content': text}, 'done': True}).encode('utf-8')]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    '''백오프 sleep을 즉시 통과시켜 테스트 시간을 0초로.'''
    monkeypatch.setattr(agent.time, 'sleep', lambda _s: None)


class TestStreamRetry:
    def test_retries_on_connection_error_then_succeeds(self, monkeypatch):
        calls = []

        def mock_post(*a, **k):
            calls.append(1)
            if len(calls) < 2:
                raise requests.ConnectionError('boom')
            return _MockResponse(200, lines=_ok_lines('hello'))

        monkeypatch.setattr(agent.requests, 'post', mock_post)
        notices: list[str] = []
        result = agent._stream_response([], on_token=notices.append)
        assert len(calls) == 2
        assert result['content'] == 'hello'
        # 재시도 알림이 한 번 떴어야 함
        assert any('재연결' in n and '2/3' in n for n in notices)

    def test_retries_on_5xx_then_succeeds(self, monkeypatch):
        calls = []

        def mock_post(*a, **k):
            calls.append(1)
            if len(calls) < 2:
                return _MockResponse(503)
            return _MockResponse(200, lines=_ok_lines('rec'))

        monkeypatch.setattr(agent.requests, 'post', mock_post)
        result = agent._stream_response([])
        assert len(calls) == 2
        assert result['content'] == 'rec'

    def test_4xx_does_not_retry(self, monkeypatch):
        '''클라이언트 오류는 재시도하지 않고 즉시 raise.'''
        calls = []

        def mock_post(*a, **k):
            calls.append(1)
            return _MockResponse(404)

        monkeypatch.setattr(agent.requests, 'post', mock_post)
        with pytest.raises(requests.HTTPError):
            agent._stream_response([])
        assert len(calls) == 1

    def test_all_three_attempts_fail_raises(self, monkeypatch):
        '''3회 모두 ConnectionError면 마지막 예외가 그대로 올라간다.'''
        calls = []

        def mock_post(*a, **k):
            calls.append(1)
            raise requests.ConnectionError('boom')

        monkeypatch.setattr(agent.requests, 'post', mock_post)
        with pytest.raises(requests.ConnectionError):
            agent._stream_response([])
        assert len(calls) == 3

    def test_timeout_is_retried(self, monkeypatch):
        calls = []

        def mock_post(*a, **k):
            calls.append(1)
            if len(calls) < 2:
                raise requests.Timeout('slow')
            return _MockResponse(200, lines=_ok_lines('done'))

        monkeypatch.setattr(agent.requests, 'post', mock_post)
        result = agent._stream_response([])
        assert len(calls) == 2
        assert result['content'] == 'done'

    def test_5xx_after_3_attempts_raises(self, monkeypatch):
        '''503이 계속 와도 3회 후엔 raise.'''
        calls = []

        def mock_post(*a, **k):
            calls.append(1)
            return _MockResponse(503)

        monkeypatch.setattr(agent.requests, 'post', mock_post)
        with pytest.raises(requests.HTTPError):
            agent._stream_response([])
        assert len(calls) == 3
