from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.omvs import OmvsShellSession
from gibson.render.input import InputResult, panel_input_value, SocketInputDriver
from gibson.render.aid_keys import extract_text_function_key, strip_known_control_text


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


def test_terminal_key_caret_sequences_are_logical_events():
    assert extract_text_function_key("^[OR") == "F3"
    assert extract_text_function_key("^[[18~") == "F7"
    assert extract_text_function_key("^[[19~") == "F8"
    assert extract_text_function_key("^[[24~") == "F12"
    r = panel_input_value(InputResult("^[OR"), context="ISPF")
    assert r.key == "F3"
    assert r.command == "END"
    assert r.text == ""
    assert strip_known_control_text("^[OR ^[[18~ ^[[19~").strip() == ""


def test_socket_driver_control_maps_cover_pf_keys():
    assert SocketInputDriver.control_sequence_to_key("^[OR") == "F3"
    assert SocketInputDriver.control_sequence_to_key("^[[18~") == "F7"
    assert SocketInputDriver.control_sequence_to_key("^[[19~") == "F8"
    assert SocketInputDriver.control_sequence_to_key("\x1b[24~") == "F12"


def test_zsec_events_and_rare_are_distinct_after_racfds_hash_flow():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    tso.run("RACFDB POLICY LEGACY ALL")
    tso.run("ADDUSER ZEV001 PASSWORD(SUMMER25) DFLTGRP(SYS1)")
    omvs = OmvsShellSession(st, "IBMUSER")
    omvs.execute("racf2john SYS1.RACFDS > IBMUSER.RACF.HASHES")
    omvs.execute("john --wordlist=GIBSON.WORDLIST IBMUSER.RACF.HASHES")
    events = tso.run("ZSEC EVENTS")
    rare = tso.run("ZSEC RARE")
    assert "ZSECURE SECURITY EVENT REVIEW" in events
    assert "ZSECURE RARE / HIGH-RISK EVENT REVIEW" in rare
    assert events != rare
    assert "RACFDS" in rare or "JOHN" in rare.upper()


def test_zsec_offlinehash_treats_legacy_des_sim_as_crackable():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    tso.run("RACFDB SEED LEGACY")
    out = tso.run("ZSEC OFFLINEHASH")
    assert "ZSECURE OFFLINE RACF HASH REVIEW" in out
    assert "CRACKABLE" in out
    assert "PROTECTED" in out


def test_smf_populated_after_indfile_and_zsec_indfile():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    st.datasets.write("IBMUSER", "IBMUSER.TEST.TEXT", "hello\n")
    out = tso.run("IND$FILE GET DSN(IBMUSER.TEST.TEXT) LOCAL(test-out.txt) MODE(ASCII) EXIST(REPLACE)")
    assert "TRANSFER COMPLETE" in out
    smf = tso.run("SMF LIST")
    assert "NO STRUCTURED SMF" not in smf
    assert "80" in smf and "119" in smf
    z = tso.run("ZSEC IND$FILE")
    assert "ZSECURE IND$FILE TRANSFER REVIEW" in z
    assert "IBMUSER.TEST.TEXT" in z


def test_security_period_summaries_are_distinct():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    tso.run("RACFDB SEED LEGACY")
    tso.run("IND$FILE GET DSN(SYS1.RACFDS) LOCAL(racfds.txt) MODE(ASCII) EXIST(REPLACE)")
    rare = tso.run("D SECURITY,RARE")
    daily = tso.run("D SECURITY,DAILY")
    weekly = tso.run("D SECURITY,WEEKLY")
    monthly = tso.run("D SECURITY,MONTHLY")
    assert "RARE" in rare
    assert "DAILY" in daily
    assert "WEEKLY" in weekly
    assert "MONTHLY" in monthly
    assert len({rare, daily, weekly, monthly}) == 4


def test_indfile_diagnostics_do_not_claim_native_transfer():
    st = make_state()
    tso = TsoCommandProcessor(st, "IBMUSER")
    out = tso.run("D IND$FILE,STATUS")
    assert "COMMAND-MODE IND$FILE" in out
    assert "NATIVE X3270/C3270 TRANSFER ===> NOT CLAIMED" in out


def test_s3270_validation_assets_exist():
    root = Path(__file__).resolve().parents[1]
    for name in [
        "s3270_indfile_get.scr",
        "s3270_indfile_put.scr",
        "s3270_indfile_roundtrip.scr",
        "s3270_indfile_sensitive_dataset.scr",
        "run_s3270_indfile_validation.sh",
    ]:
        assert (root / "manual_validation" / name).exists()
