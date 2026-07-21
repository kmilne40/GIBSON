#!/usr/bin/env python3
"""Simulation-population diagnostic.

Run with the SAME python that starts your server:

    .venv/bin/python diagnose_sims.py        # if you use the venv
    python3 diagnose_sims.py                  # otherwise

It reports WHERE the gibson code is loaded from and whether the CICS region and
the other simulations are populated.  If this prints POPULATED but your live
3270 session shows empty menus, the running server is a different/older copy
than the code you installed (clean the install and reinstall).
"""
import sys, tempfile, pathlib


def main() -> int:
    import gibson
    print("gibson loaded from :", gibson.__file__)
    from gibson.core.config import GibsonConfig
    from gibson.core.state import GibsonState

    tmp = pathlib.Path(tempfile.mkdtemp())
    gacf = tmp / "GACF.DB"; gacf.write_text("IBMUSER:SYS1:SPECIAL:OMVS\n")
    cfg = GibsonConfig(host="127.0.0.1", port=0, tn3270_port=0, sim_root=tmp,
                       files_root=tmp / "f", commands_dir=tmp / "f" / "commands",
                       gacf_path=gacf)
    cfg.ensure()
    st = GibsonState.create(cfg)

    # CICS region (shared, always seeded in __init__._seed)
    from gibson.apps.cics import get_cics_region
    reg = get_cics_region(st)
    nt, npr, nf = len(reg.transactions), len(reg.programs), len(reg.files)
    print(f"CICS transactions  : {nt}")
    print(f"CICS programs      : {npr}")
    print(f"CICS files         : {nf}")
    sample = ", ".join(sorted(reg.transactions)[:12])
    print(f"  sample txns      : {sample}")

    # Drive CEMT and a couple of sim transactions through the real session
    from gibson.apps.cics3270 import Cics3270Session
    from gibson.render.panels import PanelInput

    def drive(txn):
        c = Cics3270Session(st, peer_addr="127.0.0.1")
        c.initial_screen(); c.handle(PanelInput(aid=0, key="CLEAR", fields={}))
        scr = c.handle(PanelInput(aid=0, key="ENTER",
                                  fields={"CMDLINE": txn, "COMMAND": txn, "INPUT": txn}))
        return "\n".join((getattr(f, "text", "") or "") for f in scr.fields).strip() if scr else ""

    cemt = drive("CEMT I TRANSACTION")
    cops = drive("COPS")
    omen = drive("OMEN")
    cemt_ok = "result" in cemt and "ENABLED" in cemt
    cops_ok = "OPERATOR" in cops.upper() and "CEMT" in cops
    omen_ok = len(omen) > 60

    print(f"CEMT I TRANSACTION : {'POPULATED' if cemt_ok else 'EMPTY'}")
    print(f"COPS operator menu : {'POPULATED' if cops_ok else 'EMPTY'}")
    print(f"OMEN (CBSA bank)   : {'POPULATED' if omen_ok else 'EMPTY'}")

    all_ok = nt >= 20 and npr >= 20 and cemt_ok and cops_ok and omen_ok
    print("\nRESULT:", "POPULATED (running code is correct)" if all_ok
          else "EMPTY/REGRESSED (running code is wrong/stale - clean install + reinstall)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
