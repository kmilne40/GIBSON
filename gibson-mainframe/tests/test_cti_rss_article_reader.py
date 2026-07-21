from pathlib import Path
import tempfile, json
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cti_rss import rss_command, CACHE_DSN


def make_state():
    root=Path(tempfile.mkdtemp())
    cfg=GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', gacf_path=root/'GACF.DB')
    cfg.ensure(); cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_rss_open_uses_article_renderer(monkeypatch):
    st=make_state()
    st.datasets.write('IBMUSER', CACHE_DSN, json.dumps({'time':'NOW','items':[{'feed':'TEST','title':'Story','link':'https://example.com/story','published':'','summary':''}], 'status':[] }))
    monkeypatch.setattr('gibson.tools.html_text_browser.fetch_url', lambda url: b'<html><title>T</title><body><h1>Article Title</h1><p>Hello <a href="/x">link</a></p></body></html>')
    out=rss_command(st,'IBMUSER','rss --open 1')
    assert 'CTI RSS ARTICLE VIEW' in out
    assert 'Article Title' in out
    assert 'Links:' in out


def test_rss_open_without_cache_is_clear_error():
    st=make_state()
    out=rss_command(st,'IBMUSER','rss --open 1')
    assert 'ITEM NOT FOUND' in out or 'RUN RSS' in out
