#!/usr/bin/env python3
"""Self-contained logon diagnostic.

Run this with the SAME python that starts your server, e.g.:

    .venv/bin/python verify_logon.py          # if you use the venv
    python3 verify_logon.py                    # if you run system python

It imports the gibson code that is ACTUALLY installed/running, creates a brand
new user in a throwaway state, and drives the EBCDIC TSO/E LOGON panel through
real 3270 datastream frames - exactly what your 3270 emulator sends.  It prints
where the code was loaded from and whether a new user can log on.

If this prints ALL-OK, the running code is correct and any remaining failure is
environmental (stale duplicate install, wrong GACF.DB path, etc).  If it prints
a FAIL, the running code is missing a fix - clean the install and reinstall.
"""
import sys, tempfile, pathlib

def main() -> int:
    import gibson
    print("gibson loaded from :", gibson.__file__)
    from gibson.core.config import GibsonConfig
    from gibson.core.state import GibsonState
    from gibson.apps.tso import TsoCommandProcessor
    from gibson.apps.tso3270 import Tso3270App
    from gibson.net.datastream3270 import encode_3270_address, encode_ebcdic_field
    from gibson.render.panels import panel_input_from_event, PanelInput
    from gibson.net.datastream3270 import parse_3270_input_frame

    tmp = pathlib.Path(tempfile.mkdtemp())
    gacf = tmp / "GACF.DB"
    gacf.write_text("IBMUSER:SYS1:SPECIAL:OMVS\n", encoding="utf-8")
    cfg = GibsonConfig(host="127.0.0.1", port=0, tn3270_port=0, sim_root=tmp,
                       files_root=tmp / "f", commands_dir=tmp / "f" / "commands",
                       gacf_path=gacf)
    cfg.ensure()
    st = GibsonState.create(cfg)

    # 1) create a brand new user (initial password)
    TsoCommandProcessor(st, "IBMUSER").run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(INITPASS)")
    ok_exists = st.racf.exists("NANCY")
    ok_verify = st.racf.verify_password("NANCY", "INITPASS")
    print("new user exists in RACF :", ok_exists)
    print("password verifies       :", ok_verify)

    # 2) drive the TSO/E LOGON panel via REAL datastream frames
    app = Tso3270App(st, userid="")
    scr = app.initial_screen()

    def submit(scr, mods):
        frame = bytearray([0x7D]) + encode_3270_address(0)
        for name, text in mods:
            fld = scr.get_field(name)
            frame += bytes([0x11]) + encode_3270_address(fld.address + 1) + encode_ebcdic_field(text)
        ev = parse_3270_input_frame(bytes(frame), screen_registry=scr)
        return app.handle(panel_input_from_event(ev))

    def text_of(s):
        return "\n".join((getattr(f, "text", "") or "") for f in s.fields) if s else ""

    s1 = submit(scr, [("USERID", "NANCY"), ("PASSWORD", "INITPASS"), ("PROC", "ISPFPROC")])
    t1 = text_of(s1)
    minlen_bug = "MINIMUM LENGTH" in t1
    forced = "ENTER A NEW PASSWORD" in t1 or "NEW PASSWORD" in t1
    reached_ready = "READY" in t1
    print("step1 says MIN LENGTH    :", minlen_bug, "  (should be False)")
    print("step1 forces a change    :", forced, "  (should be False - no forced change)")
    print("step1 reaches READY      :", reached_ready, "  (should be True - direct logon)")

    all_ok = ok_exists and ok_verify and not minlen_bug and not forced and reached_ready
    print("\nRESULT:", "ALL-OK (running code is correct: new user logs straight on)" if all_ok
          else "FAIL (running code is missing a fix - clean install + reinstall)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
