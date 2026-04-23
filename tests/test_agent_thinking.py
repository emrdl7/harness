'''agent._ThinkingParser — <think>...</think> 스트리밍 파서.

로컬 reasoning 모델(DeepSeek-R1, Qwen3 thinking 등)의 토큰 스트림에서
사고 블록을 분리한다. 토큰 경계가 태그 중간을 가르는 경우가 핵심 엣지.
'''
import pytest
from agent import _ThinkingParser


def _collect(parser_args=None):
    '''Parser + answer/thought/end 수집 리스트를 만들어 반환.'''
    answers, thoughts, ends = [], [], []

    def on_answer(t): answers.append(t)
    def on_thought(t): thoughts.append(t)
    def on_thought_end(text, duration, tokens):
        ends.append({'text': text, 'tokens': tokens})

    p = _ThinkingParser(
        on_answer=on_answer, on_thought=on_thought, on_thought_end=on_thought_end,
        **(parser_args or {}),
    )
    return p, answers, thoughts, ends


class TestBasicParsing:
    '''단순 케이스 — 토큰이 태그 경계를 가르지 않음.'''

    def test_no_thinking_passes_through(self):
        '''일반 모델(태그 없음): 전부 answer로.'''
        p, a, t, e = _collect()
        p.feed('그냥 일반 답변입니다.')
        p.flush()
        assert ''.join(a) == '그냥 일반 답변입니다.'
        assert t == []
        assert e == []
        assert p.accumulated == '그냥 일반 답변입니다.'

    def test_single_thinking_block(self):
        '''<think>...</think> 하나 + 뒤에 답변.'''
        p, a, t, e = _collect()
        p.feed('<think>고민 중</think>최종 답변')
        p.flush()
        assert ''.join(a) == '최종 답변'
        assert ''.join(t) == '고민 중'
        assert len(e) == 1
        assert e[0]['text'] == '고민 중'

    def test_answer_before_and_after_thinking(self):
        '''앞뒤로 answer가 감싸는 드문 케이스.'''
        p, a, t, e = _collect()
        p.feed('시작 ')
        p.feed('<think>중간 사고</think>')
        p.feed(' 끝')
        p.flush()
        assert ''.join(a) == '시작  끝'
        assert ''.join(t) == '중간 사고'
        assert len(e) == 1

    def test_multiple_thinking_blocks(self):
        '''여러 블록 — 각각 별도 end 이벤트.'''
        p, a, t, e = _collect()
        p.feed('<think>첫번째</think>잠깐')
        p.feed('<think>두번째</think>완료')
        p.flush()
        assert ''.join(a) == '잠깐완료'
        assert len(e) == 2
        assert e[0]['text'] == '첫번째'
        assert e[1]['text'] == '두번째'


class TestTokenBoundarySplits:
    '''핵심 — 스트리밍 토큰이 태그 중간에서 쪼개진 경우.'''

    def test_open_tag_split_across_tokens(self):
        '''<th | ink> 같이 여는 태그가 갈라짐.'''
        p, a, t, e = _collect()
        for tok in ['<th', 'ink>', '사고', '</think>', '답변']:
            p.feed(tok)
        p.flush()
        assert ''.join(a) == '답변'
        assert ''.join(t) == '사고'

    def test_close_tag_split_across_tokens(self):
        '''</th | ink> 갈라짐.'''
        p, a, t, e = _collect()
        for tok in ['<think>', '사고', '</th', 'ink>', '답변']:
            p.feed(tok)
        p.flush()
        assert ''.join(a) == '답변'
        assert ''.join(t) == '사고'

    def test_tag_split_many_ways(self):
        '''모든 경계에서 1글자씩 쪼개는 극단.'''
        stream = '안녕<think>깊은생각</think>결과'
        p, a, t, e = _collect()
        for ch in stream:
            p.feed(ch)
        p.flush()
        assert ''.join(a) == '안녕결과'
        assert ''.join(t) == '깊은생각'
        assert len(e) == 1

    def test_partial_tag_that_is_not_a_tag(self):
        '''<th 로 시작하지만 실제로는 <thanks> 같은 다른 문자열일 때.
        → 태그 아님이 확정되면 answer로 흘러가야 함.'''
        p, a, t, e = _collect()
        p.feed('<th')
        p.feed('anks for this>')
        p.flush()
        assert ''.join(a) == '<thanks for this>'
        assert t == []


class TestIncompleteStream:
    '''스트림이 중간에 끊긴 경우 — flush 동작.'''

    def test_unclosed_thinking_block_on_flush(self):
        '''<think>만 있고 </think> 없이 스트림 종료 — 이미 방출된 thought는 유지, end 이벤트는 안 쏨.'''
        p, a, t, e = _collect()
        p.feed('<think>끝나지 않은')
        p.flush()
        # 내부 처리: </think> 못 만났으니 end 이벤트 없음
        assert e == []
        # 이미 흘러간 thought 토큰은 콜백에 전달됨
        assert ''.join(t) == '끝나지 않은'

    def test_trailing_open_tag_prefix_is_not_swallowed(self):
        '''끝에 <th 만 남고 끝나면, flush 시 answer로 fall-through.'''
        p, a, t, e = _collect()
        p.feed('답변 끝 <th')
        p.flush()
        assert ''.join(a) == '답변 끝 <th'


class TestAccumulated:
    '''parser.accumulated 는 answer 부분만 축적 — session_messages content와 1:1.'''

    def test_accumulated_excludes_thought(self):
        p, a, t, e = _collect()
        p.feed('앞')
        p.feed('<think>비밀 사고</think>')
        p.feed('뒤')
        p.flush()
        assert p.accumulated == '앞뒤'

    def test_accumulated_no_thinking(self):
        p, a, t, e = _collect()
        p.feed('그냥 답변')
        p.flush()
        assert p.accumulated == '그냥 답변'


class TestEndEventMetadata:
    '''on_thought_end 이벤트의 metadata — duration과 token 카운트.'''

    def test_end_reports_positive_duration(self):
        import time
        p, a, t, ends = _collect()
        p.feed('<think>')
        time.sleep(0.01)
        p.feed('생각</think>')
        p.flush()
        # ends를 딕셔너리 대신 (text, duration, tokens) 튜플로 별도 수집 필요
        # 위 _collect는 tokens만 담으므로 여기선 독자 수집
        seen = []

        def on_end(text, duration, tokens):
            seen.append({'d': duration, 'tk': tokens})
        p2 = _ThinkingParser(on_thought_end=on_end)
        p2.feed('<think>')
        time.sleep(0.01)
        p2.feed('생각</think>')
        p2.flush()
        assert len(seen) == 1
        assert seen[0]['d'] > 0  # 실측 경과
        assert seen[0]['tk'] >= 1  # 최소 1토큰

    def test_end_token_count_roughly_char_based(self):
        '''토큰 수는 대략 문자수/4 (Claude/Ollama 추정치).'''
        seen = []
        p = _ThinkingParser(on_thought_end=lambda text, d, tk: seen.append(tk))
        long_thought = '가' * 400  # 400자 → ~100 tokens
        p.feed('<think>')
        p.feed(long_thought)
        p.feed('</think>')
        p.flush()
        assert seen[0] >= 50  # 관대한 하한
        assert seen[0] <= 200  # 상한


class TestStoredThinkingsList:
    '''parser._thinkings — 완료된 사고 블록 리스트.'''

    def test_stores_completed_blocks(self):
        p, a, t, e = _collect()
        p.feed('<think>A</think>x<think>B</think>y')
        p.flush()
        assert len(p._thinkings) == 2
        assert p._thinkings[0]['text'] == 'A'
        assert p._thinkings[1]['text'] == 'B'

    def test_does_not_store_unclosed_block(self):
        p, a, t, e = _collect()
        p.feed('<think>미종료')
        p.flush()
        assert p._thinkings == []
