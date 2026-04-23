'''자연어 입력 → 슬래시 명령 의도 매처.

main.py에서 분리(Phase 3.1-A). main은 이 모듈을 re-export해 외부 호출자
호환을 유지한다. CONCERNS §3.5는 "더 정확한 LLM 분류"를 권하지만 현재는
간단한 substring + push 가드(§1.4) 조합 유지.

테스트: tests/test_main_intent.py — main에서 re-export하는 심볼을 그대로 검증.
'''

# ── git 의도 ─────────────────────────────────────────────────────
_COMMIT_TRIGGERS = [
    '커밋해', '커밋 해', '커밋하자', '커밋해줘', '커밋해주세요',
    '저장해', '저장하자', '저장해줘', 'commit해', 'commit 해',
    '변경사항 저장', '변경사항 커밋', '지금 커밋', '그냥 커밋',
]
_PUSH_TRIGGERS = [
    '푸시해', '푸시 해', '푸시하자', '푸시해줘', 'push해', 'push 해',
    '올려줘', '올리자', '원격에 올려', '커밋/푸시', '커밋 푸시',
    '커밋하고 푸시', '저장하고 올려',
]
_PULL_TRIGGERS = [
    '풀받아', '풀 받아', '풀받자', '풀해줘', 'pull해', 'pull 해',
    '최신 받아', '최신화', '동기화해', '받아와',
]


def _is_push_intent(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _PUSH_TRIGGERS)


def _is_commit_intent(text: str) -> bool:
    '''CONCERNS §1.4: push 의도와 겹치면 False — push 분기가 commit 부분을
    같이 처리하므로, 여기서 True를 반환하면 dispatch 순서에 따라 commit이
    두 번 실행될 fragility가 생긴다. push 우선 분류로 명시 차단.
    '''
    if _is_push_intent(text):
        return False
    lower = text.lower()
    return any(t in lower for t in _COMMIT_TRIGGERS)


def _is_pull_intent(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _PULL_TRIGGERS)


def _extract_commit_msg(text: str) -> str:
    '''트리거 이후 텍스트를 커밋 메시지로 추출. 없으면 빈 문자열.'''
    lower = text.lower()
    for t in _COMMIT_TRIGGERS:
        idx = lower.find(t)
        if idx != -1:
            after = text[idx + len(t):].strip(' ,.:;줘')
            if after:
                return after
    return ''


# ── /cplan 의도 ──────────────────────────────────────────────────
_CPLAN_TRIGGERS = [
    '클로드로 계획', '클로드가 계획', '클로드로 플랜', '클로드가 플랜',
    '클로드한테 계획', '클로드한테 플랜', '클로드가 설계', '클로드로 설계',
    'claude로 계획', 'claude가 계획', 'claude로 플랜', 'claude가 플랜',
    '클로드가 짜줘', '클로드로 짜줘', '클로드가 작성', '클로드가 먼저',
]


def _is_cplan_intent(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _CPLAN_TRIGGERS)


def _extract_cplan_task(text: str) -> str:
    lower = text.lower()
    for t in _CPLAN_TRIGGERS:
        idx = lower.find(t)
        if idx != -1:
            after = text[idx + len(t):].strip(' ,.:;줘')
            if after:
                return after
    return text
