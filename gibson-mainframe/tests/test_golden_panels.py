"""Golden-master 3270 panel capture - regression gate (Phase 0 safety net).

Snapshots the exact ``screen.to_3270()`` bytes of every currently-working 3270
panel so that any *unintended* byte change in a later fix fails loudly.  Panels
are driven through the real input-parsing path (field addresses resolved from
the rendered screen), exactly as a live terminal would, so field-name / routing
regressions are caught too.

Workflow:
  * First run (no fixture) writes the baseline and prints "baseline created".
  * Later runs compare; any panel whose bytes changed is reported as DIFF and
    the run exits non-zero.
  * After an *intended* change, re-baseline with:  GOLDEN_UPDATE=1 python tests/test_golden_panels.py
    (review every DIFF first - that is the whole point).

The clock is frozen so the ISPF primary "Time" field is deterministic.
"""
import datetime as _datetime
import hashlib
import json
import os
from pathlib import Path

# --- freeze time so captures are deterministic ---------------------------
_RealDT = _datetime.datetime


class _FrozenDT(_RealDT):
    @classmethod
    def now(cls, tz=None):
        return _RealDT(2024, 1, 2, 3, 4, 5)


_datetime.datetime = _FrozenDT  # test-only global freeze

from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.net.vtam_frontend import tn3270_vtam_screen

_FIXTURE = Path(__file__).parent / "fixtures" / "golden_panels.json"


def _inbound(screen, key="ENTER", **fieldvals):
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        matches = [x for x in screen.fields if x.name == name]
        if not matches:
            raise KeyError(f"field {name!r} not on screen")
        f = matches[0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _hex(screen) -> str:
    return screen.to_3270().hex()


def _capture_ispf(caps: dict) -> None:
    from gibson.apps.ispf3270.ispf_session import Ispf3270Session
    s = Ispf3270Session(GibsonState.create(), userid="IBMUSER")
    prim = s.initial_screen()
    caps["ispf_primary"] = _hex(prim)
    # each navigation builds a fresh session so captures are independent
    def fresh():
        st = GibsonState.create(); st.racf.load()
        a = Ispf3270Session(st, userid="IBMUSER")
        return a, a.initial_screen()
    a, m = fresh(); caps["ispf_opt0_settings"] = _hex(a.handle(_inbound(m, OPTION="0")))
    a, m = fresh(); caps["ispf_opt3_util"] = _hex(a.handle(_inbound(m, OPTION="3")))
    a, m = fresh(); caps["ispf_opt3_4_dslentry"] = _hex(a.handle(_inbound(m, OPTION="3.4")))
    a, m = fresh(); caps["ispf_opt6_command"] = _hex(a.handle(_inbound(m, OPTION="6")))
    a, m = fresh(); caps["ispf_opt2_dslentry_edit"] = _hex(a.handle(_inbound(m, OPTION="2")))
    a, m = fresh(); caps["ispf_invalid_opt"] = _hex(a.handle(_inbound(m, OPTION="99")))
    a, m = fresh(); caps["ispf_opt8_outlist"] = _hex(a.handle(_inbound(m, OPTION="8")))
    a, m = fresh(); caps["ispf_opt3_2_dsutil"] = _hex(a.handle(_inbound(m, OPTION="3.2")))
    a, m = fresh(); caps["ispf_opt3_3_movecopy"] = _hex(a.handle(_inbound(m, OPTION="3.3")))
    a, m = fresh(); caps["ispf_optR_racf_menu"] = _hex(a.handle(_inbound(m, OPTION="R")))
    a, m = fresh(); caps["ispf_optM_zsec_menu"] = _hex(a.handle(_inbound(m, OPTION="M")))
    a, m = fresh(); caps["ispf_opt4_foreground"] = _hex(a.handle(_inbound(m, OPTION="4")))
    a, m = fresh(); caps["ispf_opt5_batch"] = _hex(a.handle(_inbound(m, OPTION="5")))


def _capture_cics(caps: dict) -> None:
    from gibson.apps.cics3270 import Cics3270Session
    st = GibsonState.create(); st.racf.load(); st.config.realistic_cics_auth = False
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    gm = cs.initial_screen()
    caps["cics_gm"] = _hex(gm)
    ent = cs.handle(_inbound(gm))
    caps["cics_entry"] = _hex(ent)
    caps["cics_cemt_task"] = _hex(cs.handle(_inbound(ent, TRAN="CEMT I TASK")))


def _capture_db2i(caps: dict) -> None:
    from gibson.apps.db2i3270 import Db2i3270Session
    st = GibsonState.create(); st.racf.load()
    db = Db2i3270Session(st, userid="IBMUSER")
    caps["db2i_menu"] = _hex(db.initial_screen())


def _capture_sdsf(caps: dict) -> None:
    from gibson.apps.sdsf3270 import Sdsf3270Session
    st = GibsonState.create(); st.racf.load()
    sd = Sdsf3270Session(st, userid="IBMUSER")
    caps["sdsf_initial"] = _hex(sd.initial_screen())


def _capture_tso(caps: dict) -> None:
    from gibson.apps.tso3270 import Tso3270App
    st = GibsonState.create(); st.racf.load()
    app = Tso3270App(st, peer_addr="203.0.113.9")
    caps["tso_initial"] = _hex(app.initial_screen())


def _capture_vtam(caps: dict) -> None:
    caps["vtam_screen"] = tn3270_vtam_screen(service_port=2023).to_3270().hex()


def capture_all() -> dict:
    caps: dict = {}
    _capture_vtam(caps)
    _capture_tso(caps)
    _capture_ispf(caps)
    _capture_cics(caps)
    _capture_db2i(caps)
    _capture_sdsf(caps)
    return caps


def _load_fixture() -> dict:
    if not _FIXTURE.exists():
        return {}
    return json.loads(_FIXTURE.read_text())


def _save_fixture(caps: dict) -> None:
    _FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    _FIXTURE.write_text(json.dumps(caps, indent=2, sort_keys=True))


def run() -> int:
    caps = capture_all()
    baseline = _load_fixture()
    update = os.environ.get("GOLDEN_UPDATE") == "1"
    if not baseline or update:
        _save_fixture(caps)
        print(f"baseline {'updated' if baseline else 'created'}: {len(caps)} panels")
        return 0
    diffs = []
    missing = sorted(set(baseline) - set(caps))
    new = sorted(set(caps) - set(baseline))
    for name in sorted(caps):
        if name in baseline and caps[name] != baseline[name]:
            diffs.append(name)
    for name in sorted(caps):
        status = "DIFF" if name in diffs else ("NEW " if name in new else "ok  ")
        print(f"  [{status}] {name}")
    for name in missing:
        print(f"  [GONE] {name}")
    if diffs or missing:
        print(f"\nGOLDEN-MASTER MISMATCH: {len(diffs)} changed, {len(missing)} missing.")
        print("If intended, review each then re-baseline: GOLDEN_UPDATE=1 python tests/test_golden_panels.py")
        return 1
    print(f"\nall {len(caps)} panels match golden master"
          + (f" ({len(new)} new captured - re-baseline to record)" if new else ""))
    return 0


# pytest-style entry
def test_golden_panels():
    caps = capture_all()
    baseline = _load_fixture()
    if not baseline:
        _save_fixture(caps)
        return
    changed = [n for n in caps if n in baseline and caps[n] != baseline[n]]
    assert not changed, f"golden-master changed: {changed}"


if __name__ == "__main__":
    raise SystemExit(run())
