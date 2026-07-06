from pathlib import Path
import socket
import tempfile
import time

from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.uss_server import serve_uss


def make_state() -> GibsonState:
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root / 'f', commands_dir=root / 'f' / 'commands', gacf_path=root / 'GACF.DB', host='127.0.0.1', uss_port=0)
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\nGUEST:guest:NONE:NOOMVS\n', encoding='utf-8')
    state = GibsonState.create(cfg)
    state.datasets.allocate('IBMUSER', 'IBMUSER.TEST.DATA')
    state.datasets.write('IBMUSER', 'IBMUSER.TEST.DATA', 'LINE1\nLINE2\n')
    return state


def test_oget_oput_and_tso_bridge():
    state = make_state()
    shell = OmvsShellSession(state, 'IBMUSER', TsoCommandProcessor(state, 'IBMUSER'))
    assert shell.execute("oput IBMUSER.TEST.DATA '/u/ibmuser/sample.txt'").startswith('IBMUSER.TEST.DATA copied')
    assert 'LINE1' in shell.execute("cat '/u/ibmuser/sample.txt'")
    assert 'USER=IBMUSER' in shell.execute('tso LISTUSER IBMUSER')
    shell.execute("python3 -c \"from pathlib import Path; Path('note.txt').write_text('FROM USS')\"")
    assert shell.execute("oget note.txt IBMUSER.TEST.OUT").endswith('IBMUSER.TEST.OUT')
    assert state.datasets.read('IBMUSER', 'IBMUSER.TEST.OUT') == 'FROM USS'


def test_shell_network_commands_and_tso_oget_oput():
    state = make_state()
    proc = TsoCommandProcessor(state, 'IBMUSER')
    assert 'COPIED TO /u/ibmuser/from_tso.txt' in proc.run("OPUT IBMUSER.TEST.DATA '/u/ibmuser/from_tso.txt'")
    assert 'COPIED TO IBMUSER.TEST.COPY' in proc.run("OGET '/u/ibmuser/from_tso.txt' IBMUSER.TEST.COPY")
    assert state.datasets.read('IBMUSER', 'IBMUSER.TEST.COPY').startswith('LINE1')
    shell = OmvsShellSession(state, 'IBMUSER', proc)
    assert 'NETSTAT command complete' in shell.execute('netstat HOME')
    ping_out = shell.execute('ping localhost')
    assert 'Pinging host' in ping_out and 'localhost' in ping_out and 'packets received' in ping_out
    tr_out = shell.execute('traceroute localhost')
    assert 'Traceroute to' in tr_out and 'localhost' in tr_out


def test_extattr_and_ls_E():
    state = make_state()
    shell = OmvsShellSession(state, 'IBMUSER', TsoCommandProcessor(state, 'IBMUSER'))
    shell.execute("python3 -c \"from pathlib import Path; Path('tool.sh').write_text('#!/bin/sh\\necho ok\\n')\"")
    assert shell.execute('extattr +ap tool.sh').endswith('+Eap') or shell.execute('extattr tool.sh').endswith('+Eap')
    listing = shell.execute('ls -E')
    assert 'tool.sh' in listing
    assert '+Eap' in listing or '+Epa' in listing


def test_uss_listener_on_configured_port():
    state = make_state()
    server = serve_uss(state)
    try:
        port = server.server_address[1]
        with socket.create_connection(('127.0.0.1', port), timeout=3) as sock:
            time.sleep(0.1)
            _ = sock.recv(4096)
            sock.sendall(b'IBMUSER\r\n')
            time.sleep(0.1)
            _ = sock.recv(4096)
            sock.sendall(b'pass\r\n')
            time.sleep(0.2)
            banner = sock.recv(8192).decode('utf-8', errors='ignore')
            assert 'GIBSON z/OS UNIX System Services' in banner
            sock.sendall(b'pwd\r\n')
            time.sleep(0.2)
            out = sock.recv(8192).decode('utf-8', errors='ignore')
            assert '/u/ibmuser' in out
    finally:
        server.shutdown()
        server.server_close()


class _FakeKeyDriver:
    def __init__(self, commands, keys):
        self.commands = list(commands)
        self.keys = list(keys)

    def read_line(self, prompt: str = "", hidden: bool = False, mask: bool = False):
        if self.commands:
            return self.commands.pop(0)
        from gibson.render.input import InputResult
        return InputResult("", "EOF")

    def read_key(self):
        if self.keys:
            return self.keys.pop(0)
        from gibson.render.input import InputResult
        return InputResult("", "EOF")


def test_omvs_oedit_stays_in_gibson_and_saves_file():
    from gibson.render.input import InputResult

    state = make_state()
    shell = OmvsShellSession(state, 'IBMUSER', TsoCommandProcessor(state, 'IBMUSER'))
    writes = []
    driver = _FakeKeyDriver(
        commands=[InputResult('oedit note.txt'), InputResult('', 'EOF')],
        keys=[
            InputResult('H'), InputResult('I'), InputResult('', 'ENTER'),
            InputResult('~'),
            InputResult('S'), InputResult('A'), InputResult('V'), InputResult('E'), InputResult('', 'ENTER'),
            InputResult('E'), InputResult('N'), InputResult('D'), InputResult('', 'ENTER'),
        ],
    )

    shell.run_interactive(driver, lambda s: writes.append(s))

    assert shell.env.read_text('/u/ibmuser/note.txt').startswith('HI')
    assert not any('interactive editor unavailable' in chunk for chunk in writes)


def test_line_only_omvs_oedit_fails_gracefully_instead_of_crashing():
    state = make_state()
    shell = OmvsShellSession(state, 'IBMUSER', TsoCommandProcessor(state, 'IBMUSER'))
    outputs = []

    def reader(prompt: str, hidden: bool = False):
        from gibson.render.input import InputResult
        if not hasattr(reader, 'done'):
            reader.done = True
            return InputResult('oedit note.txt')
        return InputResult('', 'EOF')

    shell.run_interactive(reader, lambda s: outputs.append(s))

    assert any('interactive editor unavailable' in chunk for chunk in outputs)


def test_cat_and_cp_support_dataset_operands():
    state = make_state()
    shell = OmvsShellSession(state, 'IBMUSER', TsoCommandProcessor(state, 'IBMUSER'))

    assert 'LINE1' in shell.execute("cat \"//'IBMUSER.TEST.DATA'\"")

    out = shell.execute("cp \"//'IBMUSER.TEST.DATA'\" sample_from_ds.txt")
    assert out == ''
    assert 'LINE1' in shell.execute('cat sample_from_ds.txt')

    shell.execute("python3 -c \"from pathlib import Path; Path('from_uss.txt').write_text('USS CONTENT')\"")
    out = shell.execute("cp from_uss.txt \"//'IBMUSER.TEST.CATCOPY'\"")
    assert out == ''
    assert state.datasets.read('IBMUSER', 'IBMUSER.TEST.CATCOPY') == 'USS CONTENT'


def test_cp_supports_dataset_members():
    state = make_state()
    state.datasets.allocate('IBMUSER', 'IBMUSER.PDS.CODE', org='PO')
    state.datasets.write('IBMUSER', 'IBMUSER.PDS.CODE(TIME)', 'SAY HELLO\n')
    shell = OmvsShellSession(state, 'IBMUSER', TsoCommandProcessor(state, 'IBMUSER'))

    out = shell.execute("cp \"//'IBMUSER.PDS.CODE(TIME)'\" member.txt")
    assert out == ''
    assert 'SAY HELLO' in shell.execute('cat member.txt')

    shell.execute("python3 -c \"from pathlib import Path; Path('new_member.txt').write_text('NEW MEMBER')\"")
    out = shell.execute("cp new_member.txt \"//'IBMUSER.PDS.CODE(NEWONE)'\"")
    assert out == ''
    assert state.datasets.read('IBMUSER', 'IBMUSER.PDS.CODE(NEWONE)') == 'NEW MEMBER'
