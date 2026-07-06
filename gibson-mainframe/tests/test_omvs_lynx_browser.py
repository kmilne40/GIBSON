from gibson.tools.html_text_browser import render_html
from gibson.apps.omvs_lynx import lynx_command


def test_html_renderer_extracts_text_and_links():
    page=render_html('<html><title>X</title><body><h1>Heading</h1><p>Hello <a href="/a">A</a></p></body></html>', 'https://example.com/base')
    assert 'Heading' in page.text
    assert page.links[0][1] == 'https://example.com/a'


def test_lynx_rejects_file_scheme():
    out=lynx_command(['file:///etc/passwd'])
    assert 'only http/https' in out.lower()


def test_lynx_dump_fetch(monkeypatch):
    monkeypatch.setattr('gibson.tools.html_text_browser.fetch_url', lambda url, **kw: b'<html><title>X</title><body>Dump Text</body></html>')
    out=lynx_command(['-dump','https://example.com'])
    assert 'Dump Text' in out
