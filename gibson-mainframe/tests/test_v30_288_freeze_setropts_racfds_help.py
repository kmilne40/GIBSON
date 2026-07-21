from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/"f", commands_dir=tmp_path/"f"/"commands", transfer_root=tmp_path/"transfers", gacf_path=tmp_path/"GACF.DB")
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS:SYS1\nGUEST:SYS1:NONE:NOOMVS:STUDENT\n")
    return GibsonState.create(cfg)


def test_setropts_list_full_not_password_only(tmp_path):
    st = make_state(tmp_path)
    out = TsoCommandProcessor(st, "IBMUSER").run("SETROPTS LIST")
    assert "RACF OPTIONS" in out
    assert "CLASSACT" in out
    assert "RACLIST" in out
    assert "GENERIC" in out
    assert "PASSWORD OPTIONS" in out
    assert "MFA OPTIONS" in out
    assert "CICS SECURITY SUMMARY" in out
    assert out.index("RACF OPTIONS") < out.index("PASSWORD OPTIONS")


def test_setropts_password_options_change_and_take_effect(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    assert "MIXEDCASE        : INACTIVE" in tso.run("SETROPTS LIST")
    assert "UPDATED" in tso.run("SETROPTS PASSWORD(ALGORITHM(KDFAES))")
    assert "UPDATED" in tso.run("SETROPTS PASSWORD(MINLENGTH(12))")
    assert "UPDATED" in tso.run("SETROPTS PASSWORD(HISTORY(5))")
    assert "UPDATED" in tso.run("SETROPTS PASSWORD(REVOKE(5))")
    assert "UPDATED" in tso.run("SETROPTS PASSWORD(INTERVAL(90))")
    assert "UPDATED" in tso.run("SETROPTS PASSWORD(MIXEDCASE)")
    assert "MIXEDCASE        : ACTIVE" in tso.run("SETROPTS LIST")
    assert "UPDATED" in tso.run("SETROPTS PASSWORD(NOMIXEDCASE)")
    listed = tso.run("SETROPTS LIST")
    assert "ALGORITHM        : KDFAES" in listed
    assert "MINLENGTH        : 12" in listed
    assert "HISTORY          : 5" in listed
    assert "REVOKE           : 5" in listed
    assert "INTERVAL         : 90" in listed
    assert "MIXEDCASE        : INACTIVE" in listed


def test_setropts_class_raclist_generic_refresh_help(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    for cmd in ["SETROPTS CLASSACT(DATASET)", "SETROPTS RACLIST(FACILITY)", "SETROPTS GENERIC(DATASET)", "SETROPTS RACLIST(FACILITY) REFRESH", "SETROPTS REFRESH"]:
        out = tso.run(cmd)
        assert "UPDATED" in out or "COMPLETE" in out or "ACTIVE" in out
    assert "SETROPTS HELP" in tso.run("SETROPTS ?")
    assert "SETROPTS PASSWORD HELP" in tso.run("SETROPTS PASSWORD ?")
    assert "SETROPTS PASSWORD HELP" in tso.run("HELP SETROPTS PASSWORD")


def test_setropts_unauthorized_denied(tmp_path):
    st = make_state(tmp_path)
    out = TsoCommandProcessor(st, "GUEST").run("SETROPTS PASSWORD(MINLENGTH(12))")
    assert "INSUFFICIENT" in out or "NOT AUTH" in out


def test_sys1_racfds_catalog_and_protection(tmp_path):
    st = make_state(tmp_path)
    ibm = TsoCommandProcessor(st, "IBMUSER")
    out = ibm.run("LISTCAT LEVEL(SYS1)")
    assert "SYS1.RACFDS" in out
    assert "SYS1.UADS" in out
    out2 = ibm.run("LISTCAT SYS1.*")
    assert "SYS1.RACFDS" in out2
    guest = TsoCommandProcessor(st, "GUEST")
    denied = guest.run("VIEW 'SYS1.RACFDS'")
    assert "ICH408I" in denied or "NOT AUTH" in denied or "ACCESS" in denied


def test_help_for_new_commands_and_scripts():
    root = Path.cwd()
    assert "Install and enable" in (root/"install-gibson.sh").read_text()
    assert "Usage:" in __import__('subprocess').check_output(["bash", "install-gibson.sh", "--help"], text=True)
    assert "Usage:" in __import__('subprocess').check_output(["bash", "web-terminal/bin/gibson-web-terminal.sh", "--help"], text=True)
