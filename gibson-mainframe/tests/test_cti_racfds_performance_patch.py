from pathlib import Path
import tempfile, time, os, base64
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.welcome.routes import render_page
from gibson.apps import cti_rss
from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor


def state():
    root=Path(tempfile.mkdtemp())
    return GibsonState.create(GibsonConfig(sim_root=root, files_root=root/'files', gacf_path=root/'GACF.DB'))


def test_rss_page_cache_first_and_job_status():
    st=state()
    t0=time.time(); code, ctype, body=render_page('/cti/rss?refresh=1', st); dt=time.time()-t0
    assert code == 200 and dt < 1.0
    assert 'Refresh job started' in body or 'Refresh Jobs' in body
    code, ctype, js=render_page('/cti/rss/status', st)
    assert code == 200 and 'jobs' in js


def test_rss_single_feed_and_security_guardrails():
    st=state()
    cti_rss.ensure_rss_datasets(st,'IBMUSER')
    cti_rss.save_feeds(st,[{'name':'GOOD','title':'Good','url':'https://example.com/feed'},{'name':'BAD','title':'Bad','url':'http://127.0.0.1/feed'}])
    assert not cti_rss.validate_feed_url('http://127.0.0.1/feed')[0]
    calls=[]
    def fetcher(url):
        calls.append(url); return b'<rss><channel><item><title>One</title><link>https://example.com/1</link></item></channel></rss>'
    items, status=cti_rss.fetch_all(st,'IBMUSER',fetcher=fetcher,live=True,feed_name='GOOD')
    assert len(calls) == 1 and 'example.com' in calls[0]


def test_cti_auth_and_management_routes(monkeypatch):
    st=state()
    monkeypatch.setenv('GIBSON_CTI_AUTH_ENABLED','1')
    code,_,body=render_page('/cti/api-keys', st)
    assert code == 401
    token=base64.b64encode(b'ctiadmin:gibson').decode()
    code,_,body=render_page('/cti/api-keys?action=save&provider=VirusTotal&key=SECRET1234', st, headers={'Authorization':'Basic '+token})
    assert code == 200 and 'SECRET1234' not in body and '****1234' in body
    code,_,body=render_page('/cti/actors?action=add&name=TestActor&aliases=TA&motivation=Training&regions=GB&confidence=High&severity=high&tags=test', st, headers={'Authorization':'Basic '+token})
    assert code == 200 and 'TestActor' in body


def test_racfds_seed_verify_and_john_enrichment():
    st=state()
    tso=TsoCommandProcessor(st,'IBMUSER')
    out=tso.run('RACFDB SEED LEGACY')
    assert 'LEGACY-DES RACF HASH LAB USERS SEEDED' in out
    out=tso.run('RACFDB VERIFY HASHES')
    assert 'JOHN-COMPATIBLE EXPORT: YES' in out
    racfds=st.datasets.read('IBMUSER','SYS1.RACFDS(DATABASE)')
    assert 'ALG=LEGACY-DES' in racfds and 'FIREID1' in racfds
    omvs=OmvsShellSession(st,'IBMUSER')
    out=omvs.execute('racf2john --summary SYS1.RACFDS')
    assert 'JOHN-COMPATIBLE(YES)' in out
    out=omvs.execute('racf2john SYS1.RACFDS > IBMUSER.RACF.HASHES')
    assert 'RACF2JOHN005I FORMAT JOHN-RACF-COMPATIBLE' in out or 'LEGACY DES HASHES EXTRACTED' in out
    out=omvs.execute('john --wordlist=GIBSON.WORDLIST IBMUSER.RACF.HASHES')
    assert 'JOHN003I' in out and 'HASHES CRACKED' in out
    assert any('SMF030I PROGRAM EXECUTION' in e[1] for e in st.console_events)
