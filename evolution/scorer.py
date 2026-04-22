def score(summary: dict) -> float:
    '''세션 품질 점수 0.0~1.0 반환. 낮을수록 개선이 필요한 세션.'''
    if summary['turn_count'] == 0:
        return 1.0

    total_tool_calls = summary.get('total_tool_calls', 1)
    failure_count = len(summary['failures'])
    reflections = summary['reflections']
    undos = summary.get('undo_count', 0)

    failure_rate = min(failure_count / max(total_tool_calls, 1), 1.0)
    reflection_penalty = min(reflections * 0.15, 0.45)
    undo_penalty = min(undos * 0.2, 0.4)

    score = 1.0 - failure_rate * 0.5 - reflection_penalty - undo_penalty
    return round(max(0.0, score), 3)


def grade(score: float) -> tuple[str, str]:
    '''점수 → 등급, 색상'''
    if score >= 0.85:
        return 'A', 'green'
    if score >= 0.65:
        return 'B', 'yellow'
    if score >= 0.45:
        return 'C', 'dark_orange'
    return 'D', 'red'
