'''cli.tui — Textual TUI 기본 구동 검증.

Textual Pilot 을 사용해 실제로 앱이 mount 되고 위젯이 생성되는지 확인.
agent/network 호출은 일어나지 않는 초기 상태만 테스트.
'''
import asyncio
import pytest

from cli.tui import HarnessApp, _TUIStream


class _Args:
    '''main.py argparse 대체 — Pilot 테스트용.'''
    resume = False
    tui = True
    one_shot = None
    extra = None


class TestAppComposition:
    '''compose + on_mount 가 정상 완료되고 핵심 위젯이 존재하는지.'''

    async def test_app_mounts_and_widgets_exist(self, tmp_path):
        app = HarnessApp(working_dir=str(tmp_path), profile={}, args=_Args())
        async with app.run_test() as pilot:
            await pilot.pause()
            # 핵심 위젯 세 개가 DOM 에 존재
            assert app.query_one('#output') is not None
            assert app.query_one('#status-bar') is not None
            assert app.query_one('#input-box') is not None
            assert app.query_one('#prompt-label') is not None

    async def test_redirects_installed_on_mount_and_restored_on_unmount(self, tmp_path):
        from cli import render as _render
        from cli import callbacks as _cb
        import rich.prompt

        orig_file = _render.console.file
        orig_on_token = _cb.on_token
        orig_confirm = rich.prompt.Confirm.ask

        app = HarnessApp(working_dir=str(tmp_path), profile={}, args=_Args())
        async with app.run_test() as pilot:
            await pilot.pause()
            # TUI 모드 진입 후에는 교체되어 있어야 함
            assert _render.console.file is not orig_file
            assert _cb.on_token is not orig_on_token
            assert rich.prompt.Confirm.ask is not orig_confirm

        # 종료 후 원복
        assert _render.console.file is orig_file
        assert _cb.on_token is orig_on_token
        assert rich.prompt.Confirm.ask is orig_confirm

    async def test_input_submit_echoes_and_clears(self, tmp_path):
        '''입력 후 에코와 버퍼 클리어 — agent 호출은 타임아웃/네트워크 없으면
        스레드만 시작됐다가 즉시 실패(실제 ollama 없어도 무방).'''
        app = HarnessApp(working_dir=str(tmp_path), profile={}, args=_Args())
        async with app.run_test() as pilot:
            await pilot.pause()
            inp = app.query_one('#input-box')
            inp.value = '/help'
            await pilot.press('enter')
            await pilot.pause()
            # value 는 즉시 비워짐
            assert inp.value == ''


class TestTUIStream:
    '''rich Console.file 대체 버퍼링 동작.'''

    def test_buffers_until_newline(self, tmp_path):
        flushed = []

        class _FakeApp:
            def call_from_thread(self, fn, *a, **kw):
                # 동기 호출로 단순화 — Pilot 없이 검증
                fn()

        class _FakeRL:
            def __init__(self):
                self.writes = []
                self.scroll_y = 0
                self.max_scroll_y = 0

            def write(self, obj, scroll_end=False):
                self.writes.append(obj)
                flushed.append(obj)

            def scroll_end(self, animate=False):
                pass

        rl = _FakeRL()
        stream = _TUIStream(_FakeApp(), lambda: rl)
        stream.write('abc')
        assert flushed == []  # 아직 flush 안 됨
        stream.write(' def\n')
        assert len(flushed) == 1  # newline 만나서 flush

    def test_explicit_flush(self, tmp_path):
        flushed = []

        class _FakeApp:
            def call_from_thread(self, fn, *a, **kw):
                fn()

        class _FakeRL:
            scroll_y = 0
            max_scroll_y = 0

            def write(self, obj, scroll_end=False):
                flushed.append(obj)

            def scroll_end(self, animate=False):
                pass

        rl = _FakeRL()
        stream = _TUIStream(_FakeApp(), lambda: rl)
        stream.write('partial')
        stream.flush()
        assert len(flushed) == 1
