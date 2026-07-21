from pathlib import Path
import tempfile

from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', gacf_path=root/'GACF.DB')
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\nGUEST:guest:NONE:NOOMVS\n', encoding='utf-8')
    st = GibsonState.create(cfg)
    st.datasets.allocate('IBMUSER','IBMUSER.TEST.DATA')
    st.datasets.write('IBMUSER','IBMUSER.TEST.DATA','b\na\na\nhello\n')
    return st


def shell():
    st = make_state()
    return st, OmvsShellSession(st, 'IBMUSER', TsoCommandProcessor(st,'IBMUSER'))


def test_all_requested_uss_commands_registered_and_helpful():
    st, sh = shell()
    commands = [
        'pwd','ls','cd','mkdir','rmdir','touch','cat','more','head','tail','cp','mv','rm','chmod','chown','chgrp','id','whoami','uname','date','echo','grep','find','wc','sort','uniq','cut','tr','df','du','ps','kill','env','export','set','umask','ln','tar','gzip','gunzip','od','hexdump','iconv','chtag','man','help','OPUT','OGET','OCOPY'
    ]
    supported = {c.lower() for c in sh.supported_commands()}
    for cmd in commands:
        assert cmd.lower() in supported
        out = sh.execute(f'{cmd} HELP')
        assert 'not found' not in out.lower()
        assert out.strip()


def test_uss_text_and_filesystem_commands_work():
    st, sh = shell()
    assert sh.execute('touch .hidden') == ''
    assert '.hidden' not in sh.execute('ls')
    assert '.hidden' in sh.execute('ls -a')
    assert '.hidden' in sh.execute('ls -la')
    assert sh.execute('mkdir work') == ''
    assert sh.execute('cd work') == ''
    sh.execute('touch sample.txt')
    sh.env.write_text('/u/ibmuser/work/sample.txt', 'b\na\na\nhello\n')
    assert 'b' in sh.execute('cat sample.txt')
    assert sh.execute('head -n 2 sample.txt').splitlines() == ['b','a']
    assert sh.execute('tail -n 1 sample.txt').strip() == 'hello'
    assert '4:hello' in sh.execute('grep -n hello sample.txt')
    assert sh.execute('sort sample.txt').splitlines()[0] == 'a'
    assert sh.execute('uniq sample.txt').splitlines() == ['b','a','hello']
    assert 'sample.txt' in sh.execute('wc sample.txt')
    assert '/u/ibmuser/work/sample.txt' in sh.execute('find . -name sample.txt')
    assert sh.execute('cut -c 1 sample.txt').splitlines()[0] == 'b'
    assert 'B' in sh.execute('tr b B sample.txt')
    assert 'attributes updated' in sh.execute('chmod 755 sample.txt')
    assert 'attributes updated' in sh.execute('chown IBMUSER sample.txt')
    assert 'attributes updated' in sh.execute('chgrp SYS1 sample.txt')
    assert 'TAG=' in sh.execute('chtag -c 1047 sample.txt')
    assert '00000000' in sh.execute('hexdump sample.txt')
    assert '# iconv simulated' in sh.execute('iconv -f IBM-1047 -t ISO8859-1 sample.txt')
    assert sh.execute('ln -s sample.txt link.txt') == ''
    assert 'SYMLINK' in sh.execute('cat link.txt')
    assert sh.execute('tar -cf arc.tar sample.txt') == ''
    assert 'sample.txt' in sh.execute('tar -tf arc.tar')
    assert 'compressed' in sh.execute('gzip sample.txt')
    assert 'expanded' in sh.execute('gunzip sample.txt.gz')
    assert 'simulated process' in sh.execute('kill 100')
    assert sh.execute('rmdir empty') == 'rmdir: empty: No such directory'


def test_oput_oget_ocopy_and_cp_dataset_quoting_variants():
    st, sh = shell()
    assert 'copied to /u/ibmuser/fromds.txt' in sh.execute("OPUT -t IBMUSER.TEST.DATA /u/ibmuser/fromds.txt")
    assert 'hello' in sh.execute('cat /u/ibmuser/fromds.txt')
    assert 'copied to IBMUSER.TEST.OUT' in sh.execute('OGET -b /u/ibmuser/fromds.txt IBMUSER.TEST.OUT')
    assert 'hello' in st.datasets.read('IBMUSER','IBMUSER.TEST.OUT')
    assert sh.execute("cp \"//'IBMUSER.TEST.DATA'\" /u/ibmuser/copy1.txt") == ''
    assert sh.execute("cp //'IBMUSER.TEST.DATA' /u/ibmuser/copy2.txt") == ''
    assert 'hello' in sh.execute('cat /u/ibmuser/copy1.txt')
    assert 'hello' in sh.execute('cat /u/ibmuser/copy2.txt')
    assert 'copied to IBMUSER.TEST.OCOPY' in sh.execute('OCOPY INPATH(/u/ibmuser/fromds.txt) OUTDATASET(IBMUSER.TEST.OCOPY)')
    assert 'hello' in st.datasets.read('IBMUSER','IBMUSER.TEST.OCOPY')
