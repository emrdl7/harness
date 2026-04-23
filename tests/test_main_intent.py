'''main.py 자연어 의도 매처 — CONCERNS §1.4 가드 회귀 방지.

핵심: push와 commit 트리거가 겹치는 입력("커밋하고 푸시")은
push 분기가 commit 부분을 함께 처리하므로 _is_commit_intent는
False를 반환해야 dispatch 순서에 무관하게 안전.
'''
import main


class TestIsCommitIntent:
    def test_commit_only_triggers(self):
        assert main._is_commit_intent('커밋해') is True
        assert main._is_commit_intent('지금 커밋') is True
        assert main._is_commit_intent('변경사항 커밋') is True
        assert main._is_commit_intent('commit해') is True

    def test_push_intent_returns_false_even_if_commit_word_present(self):
        '''§1.4 가드: push 의도가 있으면 commit-only 분류는 안 됨.'''
        assert main._is_commit_intent('커밋하고 푸시') is False
        assert main._is_commit_intent('커밋/푸시') is False
        assert main._is_commit_intent('저장하고 올려') is False

    def test_unrelated_input(self):
        assert main._is_commit_intent('파일 읽어줘') is False
        assert main._is_commit_intent('') is False


class TestIsPushIntent:
    def test_push_triggers(self):
        assert main._is_push_intent('푸시해') is True
        assert main._is_push_intent('push해') is True
        assert main._is_push_intent('올려줘') is True
        assert main._is_push_intent('커밋하고 푸시') is True
        assert main._is_push_intent('커밋/푸시') is True

    def test_commit_only_is_not_push(self):
        assert main._is_push_intent('커밋해') is False
        assert main._is_push_intent('지금 커밋') is False


class TestIsPullIntent:
    def test_pull_triggers(self):
        assert main._is_pull_intent('풀받아') is True
        assert main._is_pull_intent('최신화') is True
        assert main._is_pull_intent('동기화해') is True

    def test_pull_is_not_push_or_commit(self):
        assert main._is_push_intent('풀받아') is False
        assert main._is_commit_intent('풀받아') is False


class TestExtractCommitMsg:
    def test_extracts_text_after_trigger(self):
        assert main._extract_commit_msg('커밋해 버튼 스타일 수정') == '버튼 스타일 수정'
        assert main._extract_commit_msg('지금 커밋 v2 릴리즈') == 'v2 릴리즈'

    def test_returns_empty_when_no_trigger(self):
        assert main._extract_commit_msg('아무 말') == ''

    def test_returns_empty_when_only_trigger(self):
        assert main._extract_commit_msg('커밋해') == ''


class TestNoDoubleRun:
    '''dispatch 순서 fragility 회귀 — push 분기가 commit을 같이 처리하니
    commit 분기에 다시 떨어지면 안 됨.'''

    def test_commit_then_push_phrase_classified_as_push_only(self):
        text = '커밋하고 푸시'
        assert main._is_push_intent(text) is True
        assert main._is_commit_intent(text) is False  # ← 가드 동작 핵심

    def test_short_form_commit_slash_push(self):
        text = '커밋/푸시'
        assert main._is_push_intent(text) is True
        assert main._is_commit_intent(text) is False
