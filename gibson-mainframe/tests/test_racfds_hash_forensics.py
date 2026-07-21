from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.omvs import OmvsShellSession
from gibson.core.racf_legacy_des import generate_legacy_racf_des_hash, verify_legacy_racf_des_hash, format_john_racf_hash


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root / "files", gacf_path=root / "GACF.DB")
    return GibsonState.create(cfg)


def test_sys1_catalog_contains_racfds_and_manx():
    st = make_state()
    names = {x.name for x in st.datasets.listcat("IBMUSER", prefix="SYS1.")}
    assert "SYS1.RACFDS" in names
    assert "SYS1.RACFDS.BACKUP" in names
    assert {"SYS1.MANA", "SYS1.MANB", "SYS1.MANC"}.issubset(names)
    smfprm = st.datasets.read("IBMUSER", "SYS1.PARMLIB(SMFPRM00)")
    assert "RECORDING(DATASET)" in smfprm
    assert "SYS1.MANA" in smfprm


def test_legacy_des_simulator_is_deterministic_and_verifiable():
    h1 = generate_legacy_racf_des_hash("FIREID1", "viper1")
    h2 = generate_legacy_racf_des_hash("fireid1", "VIPER1")
    assert h1 == h2
    assert verify_legacy_racf_des_hash("FIREID1", "VIPER1", h1)
    assert not verify_legacy_racf_des_hash("FIREID1", "WRONG", h1)
    assert format_john_racf_hash("FIREID1", h1).startswith("FIREID1:$racf$*FIREID1*")


def test_racfdb_status_sync_backup_and_irrdbu00():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    out = tso.run("RACFDB STATUS")
    assert "SYS1.RACFDS" in out
    assert "LEGACY-DES RECORDS" in out
    out = tso.run("RACFDB BACKUP")
    assert "BACKUP" in out
    out = tso.run("RACFDB EXPORT IRRDBU00")
    assert "PASSWORD HASH MATERIAL SUPPRESSED" in out
    unload = st.datasets.read("IBMUSER", "IBMUSER.IRRDBU00.UNLOAD")
    # Real IRRDBU00 record types: 0100 groups, 0200 users, 0500 general resources.
    assert any(l.startswith("0200 ") for l in unload.splitlines())  # user basic data (USBD)
    assert any(l.startswith("0100 ") for l in unload.splitlines())  # group basic data (GPBD)
    assert "$racf$" not in unload


def test_omvs_racf2john_and_john_emit_smf_console_and_zsecure():
    st = make_state()
    omvs = OmvsShellSession(st, "IBMUSER")
    out = omvs.execute("racf2john SYS1.RACFDS > IBMUSER.RACF.HASHES")
    assert "LEGACY DES HASHES EXTRACTED" in out
    hashes = st.datasets.read("IBMUSER", "IBMUSER.RACF.HASHES")
    assert "$racf$" in hashes
    out = omvs.execute("john IBMUSER.RACF.HASHES")
    assert "JOHN001I" in out
    assert "HASHES CRACKED" in out
    shown = omvs.execute("john --show IBMUSER.RACF.HASHES")
    assert "FIREID1" in shown or "DUMONT" in shown
    # Structured SMF types exist for dataset access, program execution, and USS activity.
    types = {str(r.header.record_type) for r in getattr(st, "smf_records", [])}
    assert {"80", "30", "92"}.issubset(types)
    assert any("RACF HASH EXTRACTION" in text for sev, text in st.console_events)
    zsec = TsoCommandProcessor(st, "IBMUSER").run("ZSEC OFFLINEHASH")
    assert "OFFLINE RACF HASH REVIEW" in zsec
    assert "MF-TTP08" in zsec


def test_smf_recording_modes_and_manx_dump():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    out = tso.run("D SMF,DS")
    assert "RECORDING(DATASET)" in out
    assert "SYS1.MANA" in out
    out = tso.run("SMF SWITCH")
    assert "SMF SWITCH COMPLETE" in out
    out = tso.run("SMF DUMP MAN(SYS1.MANA)")
    assert "IFASMFDP" in out
    out = tso.run("SMF RECORDING(LOGSTREAM)")
    assert "RECORDING(LOGSTREAM)" in out
    out = tso.run("SMF DUMP LOGSTREAM(IFASMF.RACF.LOG)")
    assert "IFASMFDL" in out


def test_adduser_and_altuser_materialise_racfds():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    out = tso.run("ADDUSER NEWUSR PASS(SECRETS1) DFLTGRP(SYS1)")
    assert "NEWUSR" in out
    racfds = st.datasets.read("IBMUSER", "SYS1.RACFDS(DATABASE)")
    assert "USERID=NEWUSR" in racfds
    out = tso.run("ALTUSER NEWUSR PASSWORD(CHANGED1)")
    assert "NEWUSR" in out
    racfds = st.datasets.read("IBMUSER", "SYS1.RACFDS(DATABASE)")
    assert "USERID=NEWUSR" in racfds
