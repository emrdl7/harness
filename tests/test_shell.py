'''tools/shell.py — 위험 명령 분류 + 실제 실행 동작.'''
from tools import shell


class TestClassifyCommand:
    def test_safe_simple_commands(self):
        assert shell.classify_command('ls -la') == 'safe'
        assert shell.classify_command('pwd') == 'safe'
        assert shell.classify_command('echo hello') == 'safe'
        assert shell.classify_command('cat file.txt') == 'safe'

    def test_dangerous_destructive(self):
        assert shell.classify_command('rm file.txt') == 'dangerous'
        assert shell.classify_command('rm -rf /tmp/foo') == 'dangerous'
        assert shell.classify_command('chmod 777 file') == 'dangerous'
        assert shell.classify_command('sudo apt install vim') == 'dangerous'

    def test_dangerous_shell_meta(self):
        assert shell.classify_command('echo a | grep b') == 'dangerous'
        assert shell.classify_command('cat x > /tmp/y') == 'dangerous'
        assert shell.classify_command('a && b') == 'dangerous'
        assert shell.classify_command('echo `whoami`') == 'dangerous'
        assert shell.classify_command('echo $(date)') == 'dangerous'

    def test_dangerous_curl_pipe_sh(self):
        assert shell.classify_command('curl http://x.com | sh') == 'dangerous'
        assert shell.classify_command('wget http://x.com | bash') == 'dangerous'

    def test_dangerous_etc_redirect(self):
        assert shell.classify_command('cat foo > /etc/hosts') == 'dangerous'

    def test_dangerous_find_delete(self):
        assert shell.classify_command('find . -name x -delete') == 'dangerous'
        assert shell.classify_command('find . -exec rm {} \\;') == 'dangerous'


class TestRunCommand:
    def test_safe_command_argv(self):
        '''메타문자 없으면 shell=False + shlex 경로.'''
        result = shell.run_command('echo hello')
        assert result['ok'] is True
        assert result['stdout'].strip() == 'hello'

    def test_command_with_meta_uses_shell(self):
        result = shell.run_command('echo hello | tr a-z A-Z')
        assert result['ok'] is True
        assert 'HELLO' in result['stdout']

    def test_nonzero_exit(self):
        result = shell.run_command('false')
        assert result['ok'] is False
        assert result['returncode'] != 0

    def test_unknown_command(self):
        result = shell.run_command('this_command_definitely_does_not_exist_xyz')
        assert result['ok'] is False
        assert 'error' in result

    def test_cwd_respected(self, tmp_path):
        result = shell.run_command('pwd', cwd=str(tmp_path))
        assert result['ok'] is True
        # macOS는 /private prefix 붙을 수 있음
        assert str(tmp_path) in result['stdout'] or result['stdout'].strip().endswith(tmp_path.name)


class TestRunPython:
    '''§1.6 회귀 방지: 작은 코드는 인라인(python3 -c), 큰 코드는 tempfile.
    둘 다 누수 없이 정리되고 결과가 올바르게 반환되어야 한다.'''
    def test_small_inline(self):
        result = shell.run_python('print("hi")')
        assert result['ok']
        assert 'hi' in result['stdout']

    def test_error_path(self):
        result = shell.run_python('raise ValueError("boom")')
        assert not result['ok']
        assert 'ValueError' in result['stderr']
        assert 'boom' in result['stderr']

    def test_large_code_uses_tempfile(self, tmp_path, monkeypatch):
        # 파일 누수 체크: TMPDIR 격리
        monkeypatch.setenv('TMPDIR', str(tmp_path))
        # inline limit 초과 크기 (약 8KB+)
        big_code = 'x = 1\n' * 2000 + 'print(x)'
        before = list(tmp_path.iterdir())
        result = shell.run_python(big_code)
        assert result['ok']
        assert result['stdout'].strip() == '1'
        # 실행 후 TMPDIR에 tmp*.py 잔재 없음
        after = list(tmp_path.iterdir())
        assert len(after) == len(before), f'임시파일 누수: {after}'
