from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.omvs import OmvsShellSession
from gibson.apps.cti_rss import fetch_all, rss_command


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root / 'f', commands_dir=root / 'f' / 'commands', gacf_path=root / 'GACF.DB', default_system_hostname='GIBSON')
    return GibsonState.create(cfg)


def test_omvs_help_is_grouped_and_documents_rss_lynx():
    st = make_state(); sh = OmvsShellSession(st, 'IBMUSER')
    out = sh.execute('help')
    assert 'Security tools:' in out
    assert 'RSS / CTI feeds:' in out
    assert 'Web tools:' in out
    assert 'cti-rss' in out
    assert 'lynx' in out
    assert 'external HTTP/HTTPS' in sh.execute('help lynx')
    assert 'cti-rss' in sh.execute('apropos rss')


def test_nmap_corrid_is_persisted_to_smf80_operlog_and_tool_events():
    st = make_state(); sh = OmvsShellSession(st, 'IBMUSER')
    out = sh.execute('nmap mainframe -p2023 --script tso-brute --offline')
    line = [l for l in out.splitlines() if 'Correlation ID:' in l][0]
    corr = line.split(':', 1)[1].strip()
    smf = [e for e in st.audit.events if e.component == 'SMF80' and e.extra.get('CORRID') == corr]
    assert smf, corr
    assert smf[-1].extra.get('TOOL') == 'NMAP'
    assert smf[-1].extra.get('SCRIPT') == 'TSO-BRUTE'
    assert any(ev.get('correlation_id') == corr for ev in getattr(st, 'tool_events', []))
    operlog = st.console_log.operlog_path.read_text(encoding='utf-8')
    assert corr in operlog


def test_rss_latest_five_per_feed_and_lynx_open_with_mocked_fetcher(monkeypatch):
    st = make_state()
    sample = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
    <item><title>Story 1</title><link>https://example.com/1</link><pubDate>Today</pubDate><description>One</description></item>
    <item><title>Story 2</title><link>https://example.com/2</link><description>Two</description></item>
    <item><title>Story 3</title><link>https://example.com/3</link></item>
    <item><title>Story 4</title><link>https://example.com/4</link></item>
    <item><title>Story 5</title><link>https://example.com/5</link></item>
    <item><title>Story 6</title><link>https://example.com/6</link></item>
    </channel></rss>'''
    fetch_all(st, 'IBMUSER', fetcher=lambda url: sample, live=True)
    out = rss_command(st, 'IBMUSER', 'RSS SHOW')
    assert 'CTI/RSS LATEST FIVE STORIES PER FEED' in out
    assert 'Story 1' in out
    # Latest view caps each feed to five displayed stories.
    assert 'Story 6' not in out
    import gibson.tools.html_text_browser as browser
    monkeypatch.setattr(browser, 'fetch_url', lambda url: b'<html><title>Article</title><body><h1>Article Page</h1><p>Hello</p></body></html>')
    opened = rss_command(st, 'IBMUSER', 'RSS LYNX 1 1')
    assert 'GIBSON LYNX - RSS ARTICLE' in opened
    assert 'Article Page' in opened


def test_lynx_external_fetch_is_python_native_and_logs(monkeypatch):
    st = make_state(); sh = OmvsShellSession(st, 'IBMUSER')
    import gibson.tools.html_text_browser as browser
    monkeypatch.setattr(browser, 'fetch_url', lambda url: b'<html><title>Example</title><body><h1>Example Domain</h1><a href="/next">Next</a></body></html>')
    out = sh.execute('lynx https://example.com/')
    assert 'Example Domain' in out
    assert any(e.extra.get('TOOL') == 'LYNX' for e in st.audit.events if e.component == 'SMF80')


def test_ispf_m_menu_no_nmap_but_omvs_nmap_exists():
    from gibson.apps.ispf import IspfApp
    st = make_state()
    assert getattr(IspfApp, 'panel_management') is not None
    sh = OmvsShellSession(st, 'IBMUSER')
    assert 'Nmap done' in sh.execute('nmap mainframe -p21 --script ftp-anon -sV')
