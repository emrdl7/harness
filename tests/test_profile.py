'''profile.py — 설정 3단계 merge (defaults → global → project → env).'''
import os
import pytest

import profile as prof


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    '''HOME을 tmp 하위 별도 디렉토리로 격리. working_dir(tmp_path)와 분리.'''
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    # _merge_toml은 호출 시점에 경로 존재만 체크하므로 monkeypatch로 재할당.
    monkeypatch.setattr(prof, 'GLOBAL_CONFIG', str(home / '.harness.toml'))
    # 환경변수 정리
    for k in list(os.environ):
        if k.startswith('HARNESS_'):
            monkeypatch.delenv(k, raising=False)
    return home


class TestLoadDefaults:
    def test_defaults_when_no_config(self, isolated_env):
        config = prof.load(str(isolated_env))
        assert config['language'] == 'korean'
        assert config['confirm_writes'] is True
        assert config['confirm_bash'] is True
        assert config['model'] == ''
        assert config['mcp_servers'] == []


class TestProjectToml:
    def test_project_toml_overrides_defaults(self, isolated_env, tmp_path):
        toml_path = tmp_path / '.harness.toml'
        toml_path.write_text(
            'language = "english"\n'
            'confirm_bash = false\n'
            'model = "llama3:70b"\n'
        )
        config = prof.load(str(tmp_path))
        assert config['language'] == 'english'
        assert config['confirm_bash'] is False
        assert config['model'] == 'llama3:70b'

    def test_mcp_servers_list_merged_not_replaced(self, isolated_env, tmp_path):
        # 전역에 1개, 프로젝트에 1개 → 합산 2개
        global_toml = isolated_env / '.harness.toml'
        global_toml.write_text(
            '[[mcp_servers]]\n'
            'name = "g1"\n'
            'command = ["echo"]\n'
        )
        project_toml = tmp_path / '.harness.toml'
        project_toml.write_text(
            '[[mcp_servers]]\n'
            'name = "p1"\n'
            'command = ["echo"]\n'
        )
        config = prof.load(str(tmp_path))
        names = [s['name'] for s in config['mcp_servers']]
        assert 'g1' in names
        assert 'p1' in names


class TestMalformedToml:
    '''CONCERNS.md §1.19 회귀 방지: 잘못된 TOML은 silently 삼키지 말고
    stderr로 경고 + defaults 유지.'''
    def test_malformed_toml_warns_stderr(self, isolated_env, tmp_path, capsys):
        toml_path = tmp_path / '.harness.toml'
        toml_path.write_text('this is not [valid] = toml = syntax')
        config = prof.load(str(tmp_path))
        # defaults 유지
        assert config['language'] == 'korean'
        # stderr에 경고 출력
        captured = capsys.readouterr()
        assert 'TOML 파싱 실패' in captured.err
        assert str(toml_path) in captured.err


class TestEnvOverride:
    def test_env_overrides_toml(self, isolated_env, tmp_path, monkeypatch):
        toml_path = tmp_path / '.harness.toml'
        toml_path.write_text('language = "english"\n')
        monkeypatch.setenv('HARNESS_LANGUAGE', 'japanese')
        config = prof.load(str(tmp_path))
        assert config['language'] == 'japanese'

    def test_env_bool_parsing(self, isolated_env, tmp_path, monkeypatch):
        monkeypatch.setenv('HARNESS_CONFIRM_BASH', 'false')
        config = prof.load(str(tmp_path))
        assert config['confirm_bash'] is False

        monkeypatch.setenv('HARNESS_CONFIRM_BASH', '1')
        config = prof.load(str(tmp_path))
        assert config['confirm_bash'] is True

    def test_env_int_parsing(self, isolated_env, tmp_path, monkeypatch):
        monkeypatch.setenv('HARNESS_MAX_RETRIES', '7')
        config = prof.load(str(tmp_path))
        assert config['max_retries'] == 7


class TestGuideDiscovery:
    def test_finds_claude_md_in_working_dir(self, isolated_env, tmp_path):
        (tmp_path / 'CLAUDE.md').write_text('# project guide')
        config = prof.load(str(tmp_path))
        assert '# project guide' in config['project_doc']
        assert config['project_doc_path'].endswith('CLAUDE.md')

    def test_no_guide_returns_empty(self, isolated_env, tmp_path):
        config = prof.load(str(tmp_path))
        assert config['project_doc'] == ''
        assert config['project_doc_path'] == ''

    def test_extra_docs_loaded(self, isolated_env, tmp_path):
        (tmp_path / 'README.md').write_text('# readme')
        config = prof.load(str(tmp_path))
        names = [name for name, _ in config['extra_docs']]
        assert 'README.md' in names
