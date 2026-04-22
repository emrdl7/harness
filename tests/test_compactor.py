'''session/compactor.py — §1.13/§1.14 회귀 방지 테스트.

_summarize는 Ollama를 호출하므로 monkeypatch로 차단.
'''
from session import compactor


def _fake_summary(text):
    def _patched(_messages):
        return text
    return _patched


class TestCompactFallback:
    '''§1.14 회귀 방지: 요약 실패 시 원본 유지.'''
    def test_summarize_fail_returns_original(self, monkeypatch, capsys):
        monkeypatch.setattr(compactor, '_summarize', _fake_summary(''))
        messages = [{'role': 'system', 'content': 's'}] + [
            {'role': 'user', 'content': f'q{i}'} for i in range(20)
        ]
        new_msgs, dropped = compactor.compact(messages)
        assert dropped == 0
        # 원본 메시지 개수 보존
        assert len(new_msgs) == len(messages)
        # stderr 경고
        assert '요약 생성 실패' in capsys.readouterr().err

    def test_summarize_success_keeps_recent(self, monkeypatch):
        monkeypatch.setattr(compactor, '_summarize', _fake_summary('SUMMARY_TEXT'))
        messages = [{'role': 'system', 'content': 's'}] + [
            {'role': 'user', 'content': f'q{i}'} for i in range(20)
        ]
        new_msgs, dropped = compactor.compact(messages)
        assert dropped > 0
        # 최근 KEEP_RECENT 보존
        assert len(new_msgs) == 1 + compactor.KEEP_RECENT
        # 요약이 system 메시지에 포함
        assert 'SUMMARY_TEXT' in new_msgs[0]['content']


class TestTruncateLargeToolOutputs:
    '''§1.13 회귀 방지: 거대 tool 결과 head+tail 축약.'''
    def test_small_tool_preserved(self):
        msgs = [{'role': 'tool', 'content': 'short result'}]
        out = compactor._truncate_large_tool_outputs(msgs)
        assert out[0]['content'] == 'short result'

    def test_large_tool_truncated(self):
        big = 'A' * (compactor._TOOL_RESULT_MAX_CHARS + 1000)
        msgs = [{'role': 'tool', 'content': big}]
        out = compactor._truncate_large_tool_outputs(msgs)
        assert len(out[0]['content']) < len(big)
        assert '중간' in out[0]['content']  # 생략 마커
        # head 와 tail 모두 'A'로 시작/끝
        assert out[0]['content'].startswith('A')
        assert out[0]['content'].endswith('A')

    def test_non_tool_untouched(self):
        big = 'A' * (compactor._TOOL_RESULT_MAX_CHARS + 1000)
        msgs = [{'role': 'assistant', 'content': big}]
        out = compactor._truncate_large_tool_outputs(msgs)
        assert out[0]['content'] == big
