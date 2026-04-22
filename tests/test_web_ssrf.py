'''tools/web._is_safe_url — §2.7 SSRF 방어 회귀 테스트.'''
from tools.web import _is_safe_url


class TestSchemeFilter:
    def test_http_ok(self):
        ok, _ = _is_safe_url('http://example.com/foo')
        assert ok

    def test_https_ok(self):
        ok, _ = _is_safe_url('https://example.com/foo')
        assert ok

    def test_file_blocked(self):
        ok, err = _is_safe_url('file:///etc/passwd')
        assert not ok
        assert 'scheme' in err

    def test_ftp_blocked(self):
        ok, err = _is_safe_url('ftp://example.com/')
        assert not ok

    def test_data_blocked(self):
        ok, err = _is_safe_url('data:text/html,<h1>x</h1>')
        assert not ok


class TestInternalHosts:
    def test_loopback_blocked(self):
        ok, err = _is_safe_url('http://127.0.0.1:8080/')
        assert not ok
        assert '내부' in err

    def test_localhost_blocked(self):
        ok, err = _is_safe_url('http://localhost/')
        assert not ok

    def test_rfc1918_blocked_10(self):
        ok, _ = _is_safe_url('http://10.0.0.1/')
        assert not ok

    def test_rfc1918_blocked_192(self):
        ok, _ = _is_safe_url('http://192.168.1.1/')
        assert not ok

    def test_link_local_blocked(self):
        ok, _ = _is_safe_url('http://169.254.169.254/latest/meta-data/')
        assert not ok

    def test_ipv6_loopback_blocked(self):
        ok, _ = _is_safe_url('http://[::1]/')
        assert not ok


class TestMalformed:
    def test_missing_hostname(self):
        ok, err = _is_safe_url('http:///path')
        assert not ok
        assert 'hostname' in err or 'DNS' in err
