from pathlib import Path

from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState


def build_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands", gacf_path=tmp_path / "GACF.DB")
    cfg.gacf_path.write_text(
        "IBMUSER:SYS1:SPECIAL:OMVS:SYS1\n"
        "GUEST:GUEST:NONE:NOOMVS:STUDENT\n",
        encoding="utf-8",
    )
    return GibsonState.create(cfg)


def test_switch_between_racf_and_acf2_modes(tmp_path: Path):
    state = build_state(tmp_path)
    tso = TsoCommandProcessor(state, "IBMUSER")

    out = tso.run("ACF2")
    assert "ACF2 MODE ACTIVE" in out
    assert "IBMUSER NAME(IBMUSER)" in tso.run("LIST IBMUSER")
    assert "ACF2 DATABASE DATA SET NAMES IN EFFECT" in tso.run("SHOW DDSN")

    out = tso.run("RACF")
    assert out == "RACF MODE ACTIVE"
    assert "USER=IBMUSER" in tso.run("LISTUSER IBMUSER")


def test_acf2_lid_insert_change_and_delete(tmp_path: Path):
    state = build_state(tmp_path)
    tso = TsoCommandProcessor(state, "IBMUSER")

    tso.run("ACF2")
    assert "LOGONID ALICE DEFINED" in tso.run("INSERT ALICE PASSWORD(TEST123) SECURITY GROUP(LAB) UID(2001)")
    listed = tso.run("LIST ALICE")
    assert "ALICE NAME(ALICE)" in listed
    assert "SECURITY" in listed
    assert "UID(2001)" in listed

    changed = tso.run("CHANGE ALICE NOSECURITY NOGROUP(LAB) GROUP(SYS1) NO-OMVS")
    assert "LOGONID ALICE ALTERED" in changed
    relisted = tso.run("LIST ALICE")
    assert "NOSECURITY" in relisted
    assert "NO-OMVS" in relisted

    deleted = tso.run("DELETE ALICE")
    assert "LOGONID ALICE DELETED" in deleted
    assert "NOT FOUND" in tso.run("LIST ALICE")


def test_acf2_group_profile_and_roles_compat(tmp_path: Path):
    state = build_state(tmp_path)
    tso = TsoCommandProcessor(state, "IBMUSER")

    tso.run("ACF2")
    assert "PROFILE(GROUP) DIV(OMVS) SETTING ACTIVE" in tso.run("SET PROFILE(GROUP) DIV(OMVS)")
    assert "GROUP PROFILE LAB STORED" in tso.run("INSERT LAB GID(3001)")
    assert "GID(3001)" in tso.run("LIST LAB")

    tso.run("SET LID")
    tso.run("INSERT ALICE PASSWORD(TEST123) GROUP(LAB) UID(2001)")
    assert "ALICE ROLE(LAB)" in tso.run("ROLES ALICE")
    tso.run("CHANGE ALICE NOGROUP(LAB) GROUP(SYS1)")
    assert "LAB" not in tso.run("ROLES ALICE")


def test_acf2_dataset_rule_resource_rule_and_access_checks(tmp_path: Path):
    state = build_state(tmp_path)
    admin = TsoCommandProcessor(state, "IBMUSER")
    admin.run("ACF2")
    admin.run("SET LID")
    admin.run("INSERT ALICE PASSWORD(TEST123) GROUP(SYS1) UID(2001)")

    assert "RULE SETTING ACTIVE" in admin.run("SET RULE")
    assert "RULE SET IBMUSER.SECRET.DATA STORED" in admin.run("INSERT IBMUSER.SECRET.DATA")
    grant = admin.run("RECKEY IBMUSER ADD( SECRET.DATA UID(ALICE) SERVICE(READ) ALLOW )")
    assert "RULE LINE STORED" in grant
    assert "$KEY(IBMUSER)" in admin.run("LIST IBMUSER.SECRET.DATA")
    assert "UID(ALICE) SERVICE(READ) ALLOW" in admin.run("ACCESS DSNAME('IBMUSER.SECRET.DATA')")
    assert "ALLOW" in admin.run("TEST DSNAME('IBMUSER.SECRET.DATA') LID(ALICE) SERVICE(READ)")

    assert "RESOURCE(SUR) SETTING ACTIVE" in admin.run("SET RESOURCE(SUR)")
    grant = admin.run("RECKEY IBMUSER ADD( IBMUSER.SUBMIT UID(ALICE) SERVICE(READ) ALLOW )")
    assert "RESOURCE SUR RULE LINE STORED" in grant
    rlist = admin.run("LIST IBMUSER.SUBMIT")
    assert "TYPE(SUR)" in rlist
    assert "UID(ALICE)" in rlist


def test_acf2_admin_commands_require_special_but_self_list_allowed(tmp_path: Path):
    state = build_state(tmp_path)
    guest = TsoCommandProcessor(state, "GUEST")
    guest.run("ACF2")
    assert "GUEST NAME(GUEST)" in guest.run("LIST GUEST")
    assert "NOT AUTHORIZED" in guest.run("SHOW TSO")
    assert "NOT AUTHORIZED" in guest.run("INSERT AL1 PASSWORD(TEST)")
