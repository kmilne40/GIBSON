from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.omvs import OmvsShellSession
from gibson.core.transfers import get_transfer_manager


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(
        sim_root=root,
        files_root=root / "files",
        gacf_path=root / "GACF.DB",
        transfer_root=root / "transfers",
        security_mode="vuln",
    )
    return GibsonState.create(cfg)


def test_adduser_legacy_all_materialises_and_john_cracks():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    assert "LEGACY-ALL" in tso.run("RACFDB POLICY LEGACY ALL")
    out = tso.run("ADDUSER ZZZ001 PASSWORD(SUMMER25) DFLTGRP(SYS1)")
    assert "ZZZ001" in out
    racfds = st.datasets.read("IBMUSER", "SYS1.RACFDS(DATABASE)")
    assert "USERID=ZZZ001" in racfds
    assert "ALG=LEGACY-DES" in [l for l in racfds.splitlines() if "USERID=ZZZ001" in l][0]
    omvs = OmvsShellSession(st, "IBMUSER")
    out = omvs.execute("racf2john SYS1.RACFDS > IBMUSER.RACF.HASHES")
    assert "LEGACY DES HASHES EXTRACTED" in out
    hashes = st.datasets.read("IBMUSER", "IBMUSER.RACF.HASHES")
    assert "ZZZ001:$racf$*ZZZ001*" in hashes
    out = omvs.execute("john --wordlist=GIBSON.WORDLIST IBMUSER.RACF.HASHES")
    assert "ZZZ001:SUMMER25" in out


def test_altuser_updates_hash_and_backup_stale_then_backup_current():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    tso.run("RACFDB POLICY LEGACY ALL")
    tso.run("ADDUSER ZZZ002 PASSWORD(SUMMER25) DFLTGRP(SYS1)")
    tso.run("RACFDB BACKUP")
    status = tso.run("RACFDB STATUS")
    assert "STALE=NO" in status
    tso.run("ALTUSER ZZZ002 PASSWORD(WELCOME1)")
    status = tso.run("RACFDB STATUS")
    assert "STALE=YES" in status
    tso.run("RACFDB BACKUP")
    status = tso.run("RACFDB STATUS")
    assert "STALE=NO" in status
    omvs = OmvsShellSession(st, "IBMUSER")
    omvs.execute("racf2john SYS1.RACFDS > IBMUSER.RACF.HASHES")
    out = omvs.execute("john --wordlist=GIBSON.WORDLIST IBMUSER.RACF.HASHES")
    assert "ZZZ002:WELCOME1" in out


def test_secure_policy_keeps_new_user_protected():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    tso.run("RACFDB POLICY PROTECTED")
    tso.run("ADDUSER ZZZ003 PASSWORD(SUMMER25) DFLTGRP(SYS1)")
    line = [l for l in st.datasets.read("IBMUSER", "SYS1.RACFDS(DATABASE)").splitlines() if "USERID=ZZZ003" in l][0]
    assert "ALG=KDFAES" in line
    assert "HASH=*PROTECTED*" in line


def test_indfile_command_get_put_member_and_evidence():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    st.datasets.write("IBMUSER", "IBMUSER.DATA.TEXT", "hello\nworld\n")
    out = tso.run("IND$FILE GET DSN(IBMUSER.DATA.TEXT) LOCAL(out.txt) MODE(ASCII)")
    assert "IND$FILE004I TRANSFER COMPLETE" in out
    assert (st.config.transfer_root / "out.txt").exists()
    (st.config.transfer_root / "in.txt").write_text("uploaded\n", encoding="utf-8")
    out = tso.run("IND$FILE PUT LOCAL(in.txt) DSN(IBMUSER.PDS(M1)) MODE(ASCII) EXIST(REPLACE)")
    assert "IND$FILE004I TRANSFER COMPLETE" in out
    assert "uploaded" in st.datasets.read("IBMUSER", "IBMUSER.PDS(M1)")
    types = {str(r.header.record_type) for r in getattr(st, "smf_records", [])}
    assert {"80", "92", "119"}.issubset(types)


def test_indfile_sensitive_transfer_alert_and_zsec():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    tso.run("RACFDB SEED LEGACY")
    out = tso.run("IND$FILE GET DSN(SYS1.RACFDS) LOCAL(racfds.txt) MODE(ASCII)")
    assert "TRANSFER COMPLETE" in out
    assert any("GIBSSEC4A" in text for _sev, text in st.console_events)
    z = tso.run("ZSEC IND$FILE")
    assert "ZSECURE IND$FILE TRANSFER REVIEW" in z
    assert "SYS1.RACFDS" in z


def test_indfile_rejects_unsafe_local_paths():
    st = make_state()
    mgr = get_transfer_manager(st)
    try:
        mgr.write_local("../../bad", b"x")
        assert False
    except ValueError:
        pass
