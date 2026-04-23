'''슬래시 핸들러 — main.py에서 분리(Phase 3.1-F-3).

handle_slash 는 '/cmd arg...' 형태 입력을 받아 세 경로로 분기한다:
  1. _CORE_DELEGATED_SLASHES 화이트리스트(/clear, /undo, /cd, /init 등)는
     harness_core.dispatch로 위임하고 결과를 Rich 로 렌더
  2. /compact, /cloop, /evolve, /history, /restore, /commit, /push, /pull,
     /claude, /mode, /help 는 이 파일에서 직접 처리
  3. 매칭 실패 시 "알 수 없는 명령어" 메시지 출력

run_agent / run_agent_ephemeral / ask_claude / confirm_execute 는 main()이
가진 nested 클로저를 DI로 주입받는다(harness_core.SlashContext로 포장).

tests/test_handle_slash.py 가 `main.handle_slash`를 호출하므로 main.py는
이 심볼을 re-export 유지.
'''
import agent
import config
import harness_core
import evolution

from rich.prompt import Confirm
from rich.table import Table
from rich import box

from session.compactor import compact
from tools.improve import list_backups, restore_backup

from cli.render import (
    console,
    _render_core_notice,
    _render_sessions_table,
    _render_files_tree,
    _print_help,
)
from cli.callbacks import (
    on_token,
    on_tool,
    confirm_write,
)
from cli.claude import _run_claude_cli, do_claude_loop


# harness_core로 위임할 슬래시. /help는 _print_help의 풍성한 표를 유지하기 위해 제외.
_CORE_DELEGATED_SLASHES = {
    '/clear', '/undo', '/cd', '/init', '/save', '/resume',
    '/sessions', '/files', '/index', '/plan', '/cplan', '/improve', '/learn',
}


def handle_slash(cmd: str, session_msgs: list, working_dir: str, profile: dict, undo_count: int = 0,
                 run_agent=None, run_agent_ephemeral=None,
                 ask_claude=None, confirm_execute=None) -> tuple[list, str, int]:
    '''run_agent / run_agent_ephemeral / ask_claude / confirm_execute:
    main()의 nested 함수들을 DI로 받아 harness_core.SlashContext로 포장해 dispatch에 전달.'''
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0]

    # 공통 핸들러는 harness_core에 위임 (점진 마이그레이션 화이트리스트)
    if name in _CORE_DELEGATED_SLASHES:
        core_state = harness_core.SlashState(
            messages=session_msgs,
            working_dir=working_dir,
            profile=profile,
            undo_count=undo_count,
        )
        core_ctx = harness_core.SlashContext(
            run_agent=run_agent,
            run_agent_ephemeral=run_agent_ephemeral,
            ask_claude=ask_claude,
            confirm_execute=confirm_execute,
        )
        result = harness_core.dispatch(cmd, core_state, core_ctx)
        if result.handled:
            # 추가 데이터 렌더 (notice로 표현 안 되는 것)
            if name == '/sessions':
                _render_sessions_table(result.data.get('sessions', []))
            elif name == '/files':
                _render_files_tree(result.data.get('tree', {}))
            elif name == '/index':
                console.print(
                    f'  [tool.ok]✓[/tool.ok] 인덱싱 완료  '
                    f'[bold]{result.data.get("indexed", 0)}[/bold]개 청크  '
                    f'[dim](건너뜀 {result.data.get("skipped", 0)}개)[/dim]\n'
                )
            elif name == '/improve':
                backup = result.data.get('backup', '')
                if backup:
                    console.print(f'  [tool.ok]✓[/tool.ok] 백업  [dim]{backup}[/dim]')
                for v in result.data.get('validation', []):
                    if v['ok']:
                        console.print(f'  [tool.ok]✓[/tool.ok] {v["file"]}')
                    else:
                        console.print(f'  [tool.fail]✗[/tool.fail] {v["file"]}  [dim]{v["error"]}[/dim]')
                if result.notice:
                    _render_core_notice(result.notice, result.level)
                console.print()
            elif result.notice:
                _render_core_notice(result.notice, result.level)
            return (result.state.messages, result.state.working_dir, result.state.undo_count)

    if name == '/compact':
        non_sys = [m for m in session_msgs if m['role'] != 'system']
        if len(non_sys) < 4:
            console.print('  [dim]압축할 대화가 충분하지 않습니다[/dim]')
        else:
            console.print('  [dim]세션 압축 중...[/dim]')
            new_msgs, dropped = compact(session_msgs)
            session_msgs = new_msgs
            console.print(f'  [tool.ok]✓[/tool.ok] 압축 완료 — 메시지 {dropped}개 요약됨')
        return session_msgs, working_dir, undo_count

    if name == '/cloop':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            console.print('  [warn]사용법:[/warn] /cloop <작업 내용>')
            return session_msgs, working_dir, undo_count
        session_msgs = do_claude_loop(query, session_msgs, working_dir, profile)
        return session_msgs, working_dir, undo_count

    if name == '/evolve':
        sub = parts[1] if len(parts) > 1 else ''

        if sub == 'proposals':
            # 제안서 목록 표시
            from evolution.proposer import load_pending, load_all
            pending = load_pending('pending')
            if not pending:
                console.print('  [dim]대기 중인 제안서가 없습니다[/dim]')
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('우선순위', no_wrap=True)
                t.add_column('타입')
                t.add_column('근거')
                t.add_column('증거', justify='right')
                t.add_column('상태')
                for p in pending:
                    color = 'red' if p['priority'] == 'high' else 'yellow'
                    evidence_count = len(p.get('evidence', []))
                    evidence_str = f'[cyan]{evidence_count}[/cyan]' if evidence_count >= 3 else f'[dim]{evidence_count}[/dim]'
                    t.add_row(
                        f'[{color}]{p["priority"]}[/{color}]',
                        p['type'],
                        p['rationale'][:60],
                        evidence_str,
                        p.get('status', 'pending'),
                    )
                console.print(t)
                console.print('  [dim]증거 수 = 해당 패턴이 관찰된 세션 수 (많을수록 신뢰도 높음)[/dim]')
            return session_msgs, working_dir, undo_count

        if sub == 'run':
            # 제안서 즉시 실행
            from evolution.executor import execute_pending
            console.print('  [dim]자율 개선 실행 중...[/dim]')
            results = execute_pending(force=True, console=console)
            if not results:
                console.print('  [dim]실행할 제안서 없음[/dim]')
            for r in results:
                icon = '[tool.ok]✓[/tool.ok]' if r['ok'] else '[tool.fail]✗[/tool.fail]'
                console.print(f'  {icon} {r["key"]}')
            return session_msgs, working_dir, undo_count

        if sub == 'changelog':
            from evolution.executor import load_changelog
            entries = load_changelog(15)
            if not entries:
                console.print('  [dim]변경 이력이 없습니다[/dim]')
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('시간', style='dim', no_wrap=True)
                t.add_column('키')
                t.add_column('결과', no_wrap=True)
                t.add_column('근거')
                t.add_column('파일')
                for e in entries:
                    status_str = '[tool.ok]적용[/tool.ok]' if e['status'] == 'applied' else '[tool.fail]실패[/tool.fail]'
                    files_str = ', '.join(e.get('changed_files', [])) or '-'
                    rationale = e.get('rationale', '') or e.get('error', '')
                    t.add_row(e['ts'][:16], e['key'][:30], status_str, rationale[:45], files_str[:40])
                console.print(t)
            return session_msgs, working_dir, undo_count

        # 기본: 진화 엔진 실행
        evolution.run(
            session_msgs=session_msgs,
            working_dir=working_dir,
            profile=profile,
            console=console,
            agent_run=agent.run,
            on_token=on_token,
            on_tool=on_tool,
            confirm_write=confirm_write,
            undo_count=undo_count,
        )
        return session_msgs, working_dir, undo_count

    if name == '/history':
        from evolution.history import recent as hist_recent, avg_score
        from evolution.scorer import grade
        entries = hist_recent(20)
        if not entries:
            console.print('  [dim]진화 이력이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
        t.add_column('시간', style='dim', no_wrap=True)
        t.add_column('이벤트')
        t.add_column('품질', justify='right')
        for e in entries[-10:]:
            sc = e.get('score')
            if sc is not None:
                letter, color = grade(sc)
                score_str = f'[{color}]{letter} {sc:.2f}[/{color}]'
            else:
                score_str = '[dim]—[/dim]'
            t.add_row(e['ts'][:16], e.get('event', ''), score_str)
        avg = avg_score(10)
        console.print(t)
        console.print(f'  평균 품질 [bold]{avg:.2f}[/bold] (최근 10세션)\n')
        return session_msgs, working_dir, undo_count

    if name == '/restore':
        backups = list_backups()
        if not backups:
            console.print('  [dim]백업이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=False)
        for i, b in enumerate(backups[:5]):
            t.add_row(f'[dim]{i}[/dim]', b)
        console.print(t)
        idx_str = parts[1] if len(parts) > 1 else '0'
        try:
            target = backups[int(idx_str)]
        except (ValueError, IndexError):
            target = backups[0]
        if Confirm.ask(f'  [warn]{target}[/warn] 으로 복원할까요?'):
            r = restore_backup(target)
            if r['ok']:
                console.print('  [tool.ok]✓[/tool.ok] 복원 완료 — 하네스를 재시작하세요')
            else:
                console.print(f'  [tool.fail]✗[/tool.fail] {r["error"]}')
        return session_msgs, working_dir, undo_count

    if name == '/commit':
        import subprocess as _sp
        msg = parts[1].strip() if len(parts) > 1 else ''
        if not msg:
            console.print('  [warn]사용법:[/warn] /commit <메시지>')
            return session_msgs, working_dir, undo_count
        # 변경 파일 확인
        status = _sp.run(['git', 'status', '--short'], cwd=working_dir, capture_output=True, text=True)
        if not status.stdout.strip():
            console.print('  [dim]커밋할 변경 사항이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        # 변경 목록 표시
        for line in status.stdout.strip().splitlines():
            console.print(f'  [dim]{line}[/dim]')
        if not Confirm.ask('  위 파일을 커밋할까요?', default=True):
            return session_msgs, working_dir, undo_count
        add = _sp.run(['git', 'add', '-A'], cwd=working_dir, capture_output=True, text=True)
        commit = _sp.run(['git', 'commit', '-m', msg], cwd=working_dir, capture_output=True, text=True)
        if commit.returncode == 0:
            # 커밋 해시 추출
            first_line = commit.stdout.strip().splitlines()[0] if commit.stdout.strip() else ''
            console.print(f'  [tool.ok]✓[/tool.ok] {first_line}')
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] {commit.stderr.strip()}')
        return session_msgs, working_dir, undo_count

    if name == '/push':
        import subprocess as _sp
        console.print('  [dim]git push...[/dim]')
        r = _sp.run(['git', 'push'], cwd=working_dir, capture_output=True, text=True)
        if r.returncode == 0:
            out = r.stdout.strip() or r.stderr.strip() or '완료'
            console.print(f'  [tool.ok]✓[/tool.ok] {out}')
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] {r.stderr.strip()}')
        return session_msgs, working_dir, undo_count

    if name == '/pull':
        import subprocess as _sp
        console.print('  [dim]git pull...[/dim]')
        r = _sp.run(['git', 'pull'], cwd=working_dir, capture_output=True, text=True)
        if r.returncode == 0:
            out = r.stdout.strip() or '완료'
            console.print(f'  [tool.ok]✓[/tool.ok] {out}')
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] {r.stderr.strip()}')
        return session_msgs, working_dir, undo_count

    if name == '/claude':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            console.print('  [warn]사용법:[/warn] /claude <질문>')
            return session_msgs, working_dir, undo_count
        _run_claude_cli(query, session_msgs=session_msgs, working_dir=working_dir, model=profile.get('claude_model') or None)
        return session_msgs, working_dir, undo_count

    if name == '/agents':
        from tools import external_ai
        agents = external_ai.list_all()
        if not agents:
            console.print('  [dim]등록된 외부 에이전트가 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
        t.add_column('키', style='bold magenta', no_wrap=True)
        t.add_column('이름', no_wrap=True)
        t.add_column('상태', no_wrap=True)
        t.add_column('설명', style='dim')
        for a in agents:
            status = '[tool.ok]사용 가능[/tool.ok]' if a.is_available() else '[tool.fail]미설치[/tool.fail]'
            t.add_row(a.key, a.name, status, a.description)
        console.print(t)
        console.print('  [dim]다른 에이전트를 붙이려면 tools/external_ai.py 참조[/dim]\n')
        return session_msgs, working_dir, undo_count

    if name == '/think':
        # 마지막 assistant 메시지의 _thinking 필드 펼치기.
        # 세션 저장/복원 시에도 JSON 그대로 보존되므로 /resume 후에도 동작.
        last_think = None
        for m in reversed(session_msgs):
            if m.get('role') == 'assistant':
                last_think = m.get('_thinking')
                break
        if not last_think:
            console.print('  [dim]마지막 응답에 사고 블록이 없습니다 (reasoning 모델이 아닐 수 있음)[/dim]')
            return session_msgs, working_dir, undo_count
        duration = last_think.get('duration', 0)
        tokens = last_think.get('tokens', 0)
        text = last_think.get('text', '').strip()
        console.print(
            f'\n  [dim]▸ {duration:.1f}초 동안 생각함 · {tokens} 토큰[/dim]'
        )
        # 사고 본문은 들여쓰기 + dim italic. 원문 개행 유지.
        for line in text.splitlines() or ['(내용 없음)']:
            console.print(f'    [dim italic]{line}[/dim italic]')
        console.print()
        return session_msgs, working_dir, undo_count

    if name == '/mode':
        mode = parts[1].strip() if len(parts) > 1 else ''
        valid = ('suggest', 'auto-edit', 'full-auto')
        if mode not in valid:
            console.print(f'  [warn]사용법:[/warn] /mode suggest | auto-edit | full-auto')
            console.print(f'  현재: [bold]{config.APPROVAL_MODE}[/bold]')
        else:
            config.APPROVAL_MODE = mode
            console.print(f'  [tool.ok]✓[/tool.ok] approval_mode → [bold]{mode}[/bold]')
        return session_msgs, working_dir, undo_count

    if name == '/help':
        _print_help()
        return session_msgs, working_dir, undo_count

    console.print(f'  [tool.fail]✗[/tool.fail] 알 수 없는 명령어: [bold]{name}[/bold]  '
                  f'[dim]/ 입력 후 Tab[/dim]')
    return session_msgs, working_dir, undo_count
