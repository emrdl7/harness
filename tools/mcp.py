import json
import os
import subprocess
import threading
from typing import Optional


class StdioMCPClient:
    '''stdio 전송(JSON-RPC 2.0)으로 MCP 서버와 통신하는 클라이언트.'''

    def __init__(self, name: str, command: list[str], env: dict = None):
        self.name = name
        self._command = command
        self._extra_env = env or {}
        self._proc: Optional[subprocess.Popen] = None
        self._req_id = 0
        self._pending: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None
        self.tools: list[dict] = []

    # ── 라이프사이클 ──────────────────────────────────────────────

    def start(self) -> bool:
        '''서버 프로세스를 시작하고 MCP 초기화 핸드셰이크를 수행.'''
        env = {**os.environ, **self._extra_env}
        try:
            self._proc = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f'MCP 서버 실행 실패 ({self.name}): {e}') from e

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        resp = self._request('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'harness', 'version': '1.0'},
        })
        if resp is None or 'error' in resp:
            return False

        self._notify('notifications/initialized', {})

        self.tools = self._fetch_tools()
        return True

    def stop(self):
        if self._proc:
            try:
                self._proc.terminate()
            except OSError:
                pass
            self._proc = None

    # ── 툴 인터페이스 ─────────────────────────────────────────────

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        resp = self._request('tools/call', {'name': tool_name, 'arguments': arguments})
        if resp is None:
            return {'ok': False, 'error': f'MCP 서버 응답 없음 ({self.name})'}
        if 'error' in resp:
            msg = resp['error'].get('message', str(resp['error'])) if isinstance(resp['error'], dict) else str(resp['error'])
            return {'ok': False, 'error': msg}

        result = resp.get('result', {})
        is_error = result.get('isError', False)
        content = result.get('content', [])
        text = '\n'.join(c['text'] for c in content if c.get('type') == 'text')
        return {'ok': not is_error, 'output': text, 'content': content}

    # ── JSON-RPC 내부 ─────────────────────────────────────────────

    def _fetch_tools(self) -> list[dict]:
        resp = self._request('tools/list', {})
        if resp and 'result' in resp:
            return resp['result'].get('tools', [])
        return []

    def _next_id(self) -> int:
        with self._lock:
            self._req_id += 1
            return self._req_id

    def _request(self, method: str, params: dict, timeout: float = 30.0) -> Optional[dict]:
        req_id = self._next_id()
        event = threading.Event()
        with self._lock:
            self._pending[req_id] = {'event': event, 'result': None}

        msg = json.dumps({'jsonrpc': '2.0', 'id': req_id, 'method': method, 'params': params})
        try:
            self._proc.stdin.write(msg + '\n')
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            with self._lock:
                self._pending.pop(req_id, None)
            return None

        if event.wait(timeout):
            with self._lock:
                return self._pending.pop(req_id, {}).get('result')
        with self._lock:
            self._pending.pop(req_id, None)
        return None

    def _notify(self, method: str, params: dict):
        msg = json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params})
        try:
            self._proc.stdin.write(msg + '\n')
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def _read_loop(self):
        '''백그라운드 스레드에서 서버 stdout을 읽고 대기 중인 요청에 응답 주입.'''
        while self._proc:
            try:
                line = self._proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                msg_id = data.get('id')
                if msg_id is not None:
                    with self._lock:
                        entry = self._pending.get(msg_id)
                    if entry:
                        entry['result'] = data
                        entry['event'].set()
            except (json.JSONDecodeError, OSError, ValueError):
                break
