'''자기 진화 엔진 — 세션 종료 시 자동 실행'''
import os
import uuid
from datetime import datetime

from evolution.scorer import score, grade
from evolution.tracker import record, get_recurring, dismiss_all
from evolution.history import snapshot, avg_score, recent
from evolution.proposer import analyze as analyze_proposals, record_tool_sequence
from session.analyzer import summarize_session, build_learn_prompt
from tools.improve import (
    backup_sources, validate_python, read_sources,
    HARNESS_DIR, EDITABLE_FILES
)

GLOBAL_DOC = os.path.join(HARNESS_DIR, 'HARNESS.md')

TRACKED_DOCS = [
    GLOBAL_DOC,
]

AUTO_IMPROVE_THRESHOLD = 3   # N세션 이상 반복 패턴이면 소스 개선 자동 실행
SCORE_LEARN_THRESHOLD = 0.95  # 이 점수 미만이면 항상 학습


def run(
    session_msgs: list,
    working_dir: str,
    profile: dict,
    console,
    agent_run,
    on_token,
    on_tool,
    confirm_write,
    undo_count: int = 0,
    unknown_tools: list = None,
    tool_call_sequence: list = None,
):
    '''세션 종료 후 자동 진화 사이클 실행'''

    summary = summarize_session(session_msgs)
    summary['undo_count'] = undo_count
    summary['total_tool_calls'] = _count_tool_calls(session_msgs)

    if summary['turn_count'] < 1:
        return

    session_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]
    # 툴 시퀀스 기록 (proposer용) — CONCERNS.md §1.20 대응:
    # 기존엔 session_id='' 빈 버킷에 먼저 기록한 뒤 실제 id로 다시 기록해
    # sequence store에 쓰레기 데이터가 누적됐음. 한 번만 기록.
    if tool_call_sequence:
        record_tool_sequence(tool_call_sequence, session_id)
    quality = score(summary)
    letter, color = grade(quality)

    def _print(msg):
        if console is not None:
            console.print(msg)

    _print(f'\n[dim]── 진화 엔진 ────────────────────────────[/dim]')
    _print(f'  세션 품질  [{color}]{letter}[/{color}]  [dim]{quality:.2f}[/dim]')

    # ── 1. 패턴 누적 기록
    if summary['failures']:
        record(summary['failures'], session_id)

    project_doc_path = os.path.join(working_dir, 'HARNESS.md')
    project_doc = profile.get('project_doc', '')

    # ── 2. 자동 학습 (점수가 낮거나 실패가 있으면)
    if quality < SCORE_LEARN_THRESHOLD or summary['failures']:
        _print('  [dim]학습 중...[/dim]')
        _run_learn(
            summary, profile.get('global_doc', ''), project_doc,
            working_dir, project_doc_path,
            agent_run, on_token, on_tool, confirm_write
        )
        _print('  [green]✓ 완료[/green]')

    # ── 3. 반복 패턴 감지 → 소스 자동 개선
    recurring = get_recurring(threshold=AUTO_IMPROVE_THRESHOLD)
    if recurring:
        patterns_str = '\n'.join(f'- {r["pattern"]} ({r["count"]}회)' for r in recurring[:5])
        _print(f'  [yellow]반복 실패 패턴 {len(recurring)}개 감지[/yellow]')
        _print(f'  [dim]{patterns_str}[/dim]')
        _print('  [dim]소스 자동 개선 중...[/dim]')
        _run_source_improve(recurring, agent_run, on_token, on_tool, confirm_write, working_dir)
        dismiss_all()
        _print('  [green]✓ 완료[/green]')

    # ── 4. 기능 개선 제안서 생성 (auto_evolve 활성 시)
    if profile.get('auto_evolve', False):
        proposals = analyze_proposals(
            unknown_tools=unknown_tools or [],
            session_id=session_id,
        )
        if proposals:
            _print(f'  [dim]개선 제안 {len(proposals)}개 생성됨[/dim]')
            for p in proposals[:3]:
                _print(f'  [dim]  • [{p["priority"]}] {p["rationale"][:60]}[/dim]')

    # ── 5. 이력 기록
    docs_to_track = [GLOBAL_DOC, project_doc_path]
    snapshot(docs_to_track, 'session_end', quality, session_id)

    # ── 6. 트렌드 출력
    trend = avg_score(10)
    trend_icon = '↑' if trend > quality else ('→' if abs(trend - quality) < 0.05 else '↓')
    _print(f'  최근 10세션 평균  [dim]{trend:.2f} {trend_icon}[/dim]')
    _print('[dim]────────────────────────────────────────[/dim]\n')


def _run_learn(summary, global_doc, project_doc, working_dir, project_doc_path, agent_run, on_token, on_tool, confirm_write):
    learn_prompt = build_learn_prompt(summary, global_doc, project_doc, working_dir)
    learn_system = [{'role': 'system', 'content': _LEARN_SYSTEM}]
    agent_run(
        learn_prompt,
        session_messages=learn_system,
        working_dir=working_dir,
        profile={},
        on_token=lambda t: None,  # 조용히 실행
        on_tool=on_tool,
        confirm_write=confirm_write,
    )


def _run_source_improve(recurring, agent_run, on_token, on_tool, confirm_write, working_dir):
    patterns_str = '\n'.join(f'- {r["pattern"]} ({r["count"]}회, 마지막: {r.get("last_seen","?")})'
                              for r in recurring[:5])
    backup_sources()
    sources = read_sources()

    improve_prompt = f'''다음 실패 패턴이 여러 세션에 걸쳐 반복 발생했습니다:

{patterns_str}

하네스 소스를 분석해 근본 원인을 찾고 수정하세요:
- 툴 description이 부정확해 모델이 인자를 잘못 전달하는 경우 → tools/__init__.py 수정
- 에러 처리가 부족한 경우 → 해당 tool 파일 수정
- 시스템 프롬프트가 불명확한 경우 → agent.py 수정

소스 코드:
{sources[:10000]}

수정 후 python3 -m py_compile <파일> 으로 검증하세요.
'''
    improve_session = [{'role': 'system', 'content': _IMPROVE_SYSTEM + f'\nHARNESS_DIR: {HARNESS_DIR}'}]
    agent_run(
        improve_prompt,
        session_messages=improve_session,
        working_dir=HARNESS_DIR,
        profile={},
        on_token=lambda t: None,
        on_tool=on_tool,
        confirm_write=confirm_write,
    )


def _count_tool_calls(messages: list) -> int:
    return sum(1 for m in messages if m.get('role') == 'tool')


_LEARN_SYSTEM = '''당신은 하네스의 자기학습 에이전트입니다.
세션 분석 결과를 바탕으로 HARNESS.md 파일만 개선하세요.
- 기존 내용 read_file로 확인 후 수정
- 중복 추가 금지
- 변경 없으면 파일 건드리지 말 것
- 출력 최소화'''

_IMPROVE_SYSTEM = '''당신은 하네스의 자기 개선 에이전트입니다.
반복되는 실패 패턴의 근본 원인을 소스에서 찾아 수정하세요.
수정 후 반드시 py_compile로 검증하세요. 출력 최소화.'''
