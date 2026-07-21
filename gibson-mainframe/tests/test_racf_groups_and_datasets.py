from pathlib import Path

import pytest

from gibson.apps.ispf import IspfApp
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.input import InputResult


class StubDriver:
    def __init__(self, responses):
        self.responses = list(responses)

    def read_line(self, prompt: str = "", hidden: bool = False, mask: bool = False):
        if not self.responses:
            raise AssertionError("no more responses")
        value = self.responses.pop(0)
        return value if isinstance(value, InputResult) else InputResult(str(value))

    def read_line_at(self, row: int, col: int, hidden: bool = False):
        return self.read_line(hidden=hidden)


def build_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands", gacf_path=tmp_path / "GACF.DB")
    cfg.gacf_path.write_text(
        "IBMUSER:SYS1:SPECIAL:OMVS:SYS1\n"
        "GUEST:GUEST:NONE:NOOMVS:STUDENT\n",
        encoding="utf-8",
    )
    return GibsonState.create(cfg)


def test_adduser_dfltgrp_persists_and_connects(tmp_path: Path):
    state = build_state(tmp_path)
    admin = TsoCommandProcessor(state, "IBMUSER")
    assert "GROUP LAB DEFINED" in admin.run("ADDGROUP LAB")
    out = admin.run("ADDUSER ALICE PASS(TEST123) NOOMVS DFLTGRP(LAB)")
    assert "ICH01003I USERID ALICE DEFINED" in out
    assert state.racf.get("ALICE").default_group == "LAB"
    assert state.dynamic_racf.groups["LAB"].users["ALICE"] == "USE"

    reloaded = GibsonState.create(state.config)
    assert reloaded.racf.get("ALICE").default_group == "LAB"
    assert "ALICE" in reloaded.dynamic_racf.groups["LAB"].users


def test_altuser_dfltgrp_requires_existing_connect(tmp_path: Path):
    state = build_state(tmp_path)
    admin = TsoCommandProcessor(state, "IBMUSER")
    assert "GROUP LAB DEFINED" in admin.run("ADDGROUP LAB")
    out = admin.run("ALTUSER GUEST DFLTGRP(LAB)")
    assert "NOT CONNECTED TO GROUP LAB" in out
    assert "CONNECTED TO GROUP LAB" in admin.run("CONNECT GUEST GROUP(LAB) AUTHORITY(USE)")
    out = admin.run("ALTUSER GUEST DFLTGRP(LAB)")
    assert "ICH01006I USERID GUEST ALTERED" in out
    assert state.racf.get("GUEST").default_group == "LAB"


def test_group_permit_controls_dataset_read_vs_update(tmp_path: Path):
    state = build_state(tmp_path)
    admin = TsoCommandProcessor(state, "IBMUSER")
    admin.run("ADDGROUP LAB")
    admin.run("CONNECT GUEST GROUP(LAB) AUTHORITY(USE)")
    state.datasets.allocate("IBMUSER", "IBMUSER.SECRET.DATA")
    state.datasets.write("IBMUSER", "IBMUSER.SECRET.DATA", "SECRET")
    admin.run("PERMIT IBMUSER.SECRET.DATA CLASS(DATASET) ID(LAB) ACCESS(READ)")

    assert state.datasets.read("GUEST", "IBMUSER.SECRET.DATA") == "SECRET"
    with pytest.raises(PermissionError):
        state.datasets.write("GUEST", "IBMUSER.SECRET.DATA", "CHANGED")


def test_noomvs_user_cannot_use_omvs_transfer_commands(tmp_path: Path):
    state = build_state(tmp_path)
    guest = TsoCommandProcessor(state, "GUEST")
    assert "OMVS segment" in guest.run("OGET '/u/guest/file.txt' GUEST.TEST.DATA")
    assert "OMVS segment" in guest.run("OPUT GUEST.TEST.DATA '/u/guest/file.txt'")


def test_ispf_32_allocates_under_user_prefix_and_flat_space(tmp_path: Path):
    state = build_state(tmp_path)
    app = IspfApp(state, "IBMUSER", lambda c: "OK")
    sent = []
    driver = StubDriver(["TEST.NEW.DATA", "", "0", "FB", "80"])
    app._allocate_panel(driver, sent.append)
    assert app.message == "DATA SET ALLOCATED AS PS"
    assert state.datasets.ds_path("IBMUSER", "IBMUSER.TEST.NEW.DATA") == tmp_path / "f" / "IBMUSER" / "TEST" / "NEW" / "DATA"
    assert any(r.name == "IBMUSER.TEST.NEW.DATA" for r in state.datasets.listcat("IBMUSER"))


def test_appl_access_can_be_group_controlled(tmp_path: Path):
    state = build_state(tmp_path)
    admin = TsoCommandProcessor(state, "IBMUSER")
    admin.run("RALTER APPL CICS UACC(NONE)")
    admin.run("PERMIT CICS CLASS(APPL) ID(STUDENT) ACCESS(READ)")
    guest = TsoCommandProcessor(state, "GUEST")
    assert guest.can_access_appl("CICS") is True
    admin.run("ADDUSER ALICE PASS(TEST123) NOOMVS DFLTGRP(SYS1)")
    alice = TsoCommandProcessor(state, "ALICE")
    assert alice.can_access_appl("CICS") is False


def test_ispf_32_library_type_and_dslist_prefix_behaviour(tmp_path: Path):
    state = build_state(tmp_path)
    app = IspfApp(state, "IBMUSER", lambda c: "OK")
    sent = []

    # Explicit LIBRARY allocation should create one PO data set entry, not a
    # phantom intermediate qualifier directory.
    driver = StubDriver(["TRAIN.CODE", "LIBRARY", "0", "FB", "80"])
    app._allocate_panel(driver, sent.append)
    assert app.message == "DATA SET ALLOCATED AS PDSE/LIBRARY"
    rows = state.datasets.listcat("IBMUSER")
    names = [r.name for r in rows]
    assert "IBMUSER.TRAIN.CODE" in names
    assert "IBMUSER.TRAIN" not in names

    # ISPF 3.4 Dsname Level must behave like an HLQ/prefix list field rather
    # than auto-qualifying the value with the current TSO prefix.
    state.datasets.allocate("IBMUSER", "IBMUSER.KEV.TEST.DATA")
    state.datasets.allocate("IBMUSER", "KEV.OTHER.DATA")
    state.datasets.allocate("IBMUSER", "SYS1.TEST.DATA")
    captured = {}
    app.dslist_loop = lambda _d, _s, prefix: captured.setdefault("prefix", prefix)
    driver = StubDriver(["KEV"])
    app.panel_34(driver, sent.append)
    assert captured["prefix"] == "KEV"
    kev_names = [r.name for r in state.datasets.listcat("IBMUSER", "KEV")]
    assert "KEV.OTHER.DATA" in kev_names
    assert all(not name.startswith("IBMUSER.KEV") for name in kev_names)
