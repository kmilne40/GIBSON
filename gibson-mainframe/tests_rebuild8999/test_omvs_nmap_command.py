from gibson.core.state import GibsonState
from gibson.apps.omvs import OmvsShellSession


def shell():
    return OmvsShellSession(GibsonState.create(), 'IBMUSER')


def test_nmap_version_and_allowed_targets():
    sh = shell()
    assert 'nmap-sim.py 2.0.0' in sh.execute('nmap --version')
    assert 'Starting nmap-sim' in sh.execute('nmap 127.0.0.1')
    out = sh.execute('nmap mainframe')
    assert 'Starting nmap-sim' in out


def test_nmap_rejects_external_targets_before_scan():
    sh = shell()
    for cmd in ['nmap 192.168.1.1', 'nmap example.com', 'nmap 10.0.0.0/24', 'nmap 127.0.0.1 example.com']:
        out = sh.execute(cmd)
        assert 'target not permitted' in out or 'multiple targets are not permitted' in out
        assert 'Starting nmap-sim' not in out


def test_nmap_tso_enum_no_transport_failure():
    sh = shell()
    out = sh.execute('nmap -p 2023 mainframe --script tso-enum')
    assert 'IBMUSER' in out
    assert 'CONFIRMED' in out
    assert 'TRANSPORT_FAILURE' not in out


def test_nmap_supported_scripts():
    sh = shell()
    for script in ['tn3270-screen','cics-info','cics-enum','cicspwn']:
        out = sh.execute(f'nmap -p 2023 mainframe --script {script}')
        assert 'PORT     STATE SERVICE' in out
        assert script in out


def test_nmap_output_path_restriction():
    sh = shell()
    assert 'escapes' in sh.execute('nmap mainframe -oN ../../escape.txt') or 'not permitted' in sh.execute('nmap mainframe -oN ../../escape.txt')
    out = sh.execute('nmap mainframe -oN nmap-local.txt -oJ nmap-local.json')
    assert 'Nmap-sim done' in out
    assert sh.env.exists('/u/ibmuser/nmap-local.txt')
    assert sh.env.exists('/u/ibmuser/nmap-local.json')


def test_nmap_help_lists_command():
    sh = shell()
    assert 'nmap' in sh.execute('help').lower()
    assert 'Allowed targets' in sh.execute('help nmap')
