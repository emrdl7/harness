'''tools/fs.py — 샌드박스 + read/write/edit/grep/list 동작.'''
import os
import pytest

from tools import fs


@pytest.fixture(autouse=True)
def reset_sandbox():
    '''각 테스트 전후로 샌드박스 off로 복원 — 전역 상태 격리.'''
    fs.set_sandbox(None)
    yield
    fs.set_sandbox(None)


class TestSandbox:
    def test_off_by_default(self, tmp_path):
        ok, resolved = fs._resolve_path(str(tmp_path / 'x'))
        assert ok is True

    def test_relative_resolved_against_root(self, tmp_path):
        fs.set_sandbox(str(tmp_path))
        ok, resolved = fs._resolve_path('foo.txt')
        assert ok is True
        assert resolved == str(tmp_path / 'foo.txt')

    def test_absolute_inside_root_allowed(self, tmp_path):
        fs.set_sandbox(str(tmp_path))
        target = tmp_path / 'a' / 'b.txt'
        ok, resolved = fs._resolve_path(str(target))
        assert ok is True

    def test_absolute_outside_root_blocked(self, tmp_path):
        fs.set_sandbox(str(tmp_path))
        ok, err = fs._resolve_path('/etc/passwd')
        assert ok is False
        assert '샌드박스 밖' in err

    def test_dotdot_escape_blocked(self, tmp_path):
        fs.set_sandbox(str(tmp_path))
        # tmp_path/../something → 샌드박스 외부
        ok, err = fs._resolve_path('../../etc/passwd')
        assert ok is False

    def test_symlink_escape_blocked(self, tmp_path):
        '''샌드박스 내부에 외부를 가리키는 symlink가 있어도 realpath로 차단.'''
        fs.set_sandbox(str(tmp_path))
        outside = tmp_path.parent / 'outside_target.txt'
        outside.write_text('secret')
        link = tmp_path / 'link_to_outside'
        os.symlink(outside, link)
        ok, err = fs._resolve_path('link_to_outside')
        assert ok is False


class TestReadWriteEdit:
    def test_write_and_read_round_trip(self, tmp_path):
        path = tmp_path / 'sample.txt'
        result = fs.write_file(str(path), 'hello\nworld\n')
        assert result['ok'] is True
        result = fs.read_file(str(path))
        assert result['ok'] is True
        assert result['total_lines'] == 2
        assert 'hello' in result['content']
        assert 'world' in result['content']

    def test_read_offset_limit(self, tmp_path):
        path = tmp_path / 'multi.txt'
        path.write_text(''.join(f'line{i}\n' for i in range(10)))
        result = fs.read_file(str(path), offset=3, limit=2)
        assert result['ok'] is True
        assert result['start_line'] == 3
        assert result['end_line'] == 4
        assert 'line2' in result['content']
        assert 'line3' in result['content']
        assert 'line0' not in result['content']

    def test_read_accepts_file_path_alias(self, tmp_path):
        '''profile/legacy 호환: file_path 인자도 받아야 함.'''
        path = tmp_path / 'a.txt'
        path.write_text('x')
        result = fs.read_file(file_path=str(path))
        assert result['ok'] is True

    def test_edit_single_occurrence(self, tmp_path):
        path = tmp_path / 'edit.txt'
        path.write_text('foo bar baz')
        result = fs.edit_file(str(path), 'bar', 'BAR')
        assert result['ok'] is True
        assert path.read_text() == 'foo BAR baz'

    def test_edit_missing_string(self, tmp_path):
        path = tmp_path / 'edit.txt'
        path.write_text('foo bar')
        result = fs.edit_file(str(path), 'NOT_THERE', 'X')
        assert result['ok'] is False
        assert '찾을 수 없음' in result['error']

    def test_edit_multiple_occurrence_requires_replace_all(self, tmp_path):
        path = tmp_path / 'edit.txt'
        path.write_text('foo foo foo')
        result = fs.edit_file(str(path), 'foo', 'X')
        assert result['ok'] is False
        assert 'replace_all' in result['error']

    def test_edit_replace_all(self, tmp_path):
        path = tmp_path / 'edit.txt'
        path.write_text('foo foo foo')
        result = fs.edit_file(str(path), 'foo', 'X', replace_all=True)
        assert result['ok'] is True
        assert result['replaced'] == 3
        assert path.read_text() == 'X X X'


class TestFileChangeDiff:
    '''Feature A — write_file/edit_file 결과의 diff/신규파일 필드 회귀 방지.

    UI-RENDER-PLAN.md V1 Feature A: AR-01 FileEditBlock 이 이 필드들을 보고
    신규파일/diff/실패 분기를 결정한다. 필드 누락 시 fallback 표시로 떨어짐.
    '''

    def test_write_new_file_marks_is_new_file(self, tmp_path):
        path = tmp_path / 'new.txt'
        result = fs.write_file(str(path), 'hello\nworld\n')
        assert result['ok'] is True
        assert result.get('is_new_file') is True
        assert result.get('new_content') == 'hello\nworld\n'
        assert result.get('path') == str(path)

    def test_write_overwrite_returns_unified_diff(self, tmp_path):
        path = tmp_path / 'over.txt'
        path.write_text('a\nb\nc\n')
        result = fs.write_file(str(path), 'a\nB\nc\n')
        assert result['ok'] is True
        assert result.get('is_new_file') is None  # 덮어쓰기엔 키 없음
        diff = result.get('file_diff', '')
        assert '-b' in diff and '+B' in diff

    def test_edit_returns_unified_diff(self, tmp_path):
        path = tmp_path / 'edit.txt'
        path.write_text('foo bar baz\n')
        result = fs.edit_file(str(path), 'bar', 'BAR')
        assert result['ok'] is True
        diff = result.get('file_diff', '')
        assert '-foo bar baz' in diff
        assert '+foo BAR baz' in diff
        assert result.get('path') == str(path)


class TestGrepAndList:
    def test_grep_finds_matches(self, tmp_path):
        (tmp_path / 'a.txt').write_text('hello world\nfoo bar\n')
        (tmp_path / 'b.txt').write_text('nothing here\n')
        result = fs.grep_search('hello', path=str(tmp_path))
        assert result['ok'] is True
        assert result['total_matches'] == 1

    def test_grep_invalid_regex(self, tmp_path):
        result = fs.grep_search('[unclosed', path=str(tmp_path))
        assert result['ok'] is False
        assert '정규식' in result['error']

    def test_list_files_glob(self, tmp_path):
        (tmp_path / 'a.py').touch()
        (tmp_path / 'b.py').touch()
        (tmp_path / 'c.txt').touch()
        result = fs.list_files(pattern=str(tmp_path / '*.py'))
        assert result['ok'] is True
        assert len(result['files']) == 2
