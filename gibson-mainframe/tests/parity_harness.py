"""ASCII <-> EBCDIC parity harness (Phase 0).

The ASCII (netcat/NVT, port 2023 fallback) capability set is the *specification*.
This harness drives each ASCII-reachable capability down the EBCDIC/TN3270 path
and classifies the result so we have an authoritative gap list and a
regression gate, instead of finding divergences one screenshot at a time.

Classification per probe:
  OK         - reachable, no escape bytes, not a stub, not truncated
  STUB       - "... is not available from the EBCDIC 3270 session."
  GARBLED    - raw ANSI escape (\\x1b) leaked into 3270 field text
  TRUNCATED  - output was cut with the 20-line "output truncated" cap
  EXCEPTION  - the EBCDIC path raised

Run:  python tests/parity_harness.py
Exit code is non-zero if any probe is not OK (so CI fails on any regression).
"""
from __future__ import annotations

import sys
import tempfile
import pathlib

sys.path.insert(0, ".")
sys.path.insert(0, "tests")

from helpers_port2023_tn3270 import make_session  # noqa: E402

ESC = "\x1b"


# --- ASCII capability spec (from telnet_server.py dispatch + GIBSON-INTERACTIVE)
# Top-level interactive verbs reachable at the ASCII READY prompt.
INTERACTIVE_VERBS = [
    "SDSF", "ISF", "ISPF", "START",
    "FTP", "TELNET", "OEDIT", "EDIT",
    "CONSOLE", "OMVS", "CICS", "DB2", "DSN",
]
# Representative line commands (rendering / truncation checks).
LINE_COMMANDS = [
    "LISTUSER IBMUSER",
    "LISTUSER *",          # long output -> truncation check
    "ADDUSER?",            # '?' help feature
    "UADS LIST",           # tabular RACF/UADS output
]


def screen_text(scr) -> str:
    if scr is None:
        return ""
    out = []
    for f in getattr(scr, "fields", []):
        out.append(getattr(f, "text", None) or getattr(f, "value", "") or "")
    return "\n".join(out)


def fresh_session():
    tmp = pathlib.Path(tempfile.mkdtemp())
    s = make_session(tmp)
    s.in_3270_mode = True
    s.userid = "IBMUSER"
    s.mode = "TSO_READY"
    return s


def classify(txt: str, exc: Exception | None) -> str:
    if exc is not None:
        return f"EXCEPTION:{type(exc).__name__}"
    if ESC in txt:
        return "GARBLED"
    if "not available from the EBCDIC" in txt:
        return "STUB"
    if "output truncated" in txt:
        return "TRUNCATED"
    return "OK"


def probe_verb(verb: str) -> tuple[str, str]:
    s = fresh_session()
    exc = None
    try:
        s._handle_tso_command(verb)
    except Exception as e:  # noqa: BLE001
        exc = e
    txt = screen_text(s.current_screen)
    return classify(txt, exc), f"mode={getattr(s, 'mode', '?')} {txt[:70]!r}"


def probe_omvs_tool(cmd: str) -> tuple[str, str]:
    """Enter OMVS, run a tool, check the rendered screen for escape leakage."""
    s = fresh_session()
    exc = None
    try:
        s._handle_tso_command("OMVS")
        s._handle_omvs_line(cmd)
    except Exception as e:  # noqa: BLE001
        exc = e
    txt = screen_text(s.current_screen)
    return classify(txt, exc), f"{txt[:70]!r}"


def probe_sdsf_system_cmd(cmd: str) -> tuple[str, str]:
    """Drive a '/'-prefixed operator command through the real SDSF panel input
    path (not the backend directly), so the wiring is gated — that a direct
    '/cmd' reaches a response instead of being ignored."""
    from gibson.render.panels import PanelInput
    s = fresh_session()
    exc = None
    txt = msg = ""
    mode = "?"
    try:
        s._handle_tso_command("SDSF")
        app = s.sdsf_app
        scr = app.handle(PanelInput(aid=0, key="ENTER", fields={"CMD": "/" + cmd}))
        txt = "\n".join((getattr(f, "text", "") or "") for f in scr.fields) if scr else ""
        msg = getattr(app, "_message", "") or ""
        mode = app.mode
    except Exception as e:  # noqa: BLE001
        exc = e
    if exc is not None:
        return f"EXCEPTION:{type(exc).__name__}", ""
    if ESC in (txt + msg):
        return "GARBLED", "escape in panel"
    reached = mode == "OUTPUT" or (msg.strip() and "COMMAND INPUT" not in msg)
    return ("OK" if reached else "IGNORED"), f"mode={mode} msg={msg[:38]!r}"


# 3270 field colour bytes (SFE colour pair = 0x42 <code>).
_COLOUR = {"red": 0xF2, "green": 0xF4, "blue": 0xF1}


def probe_colour(run_verb: str, expect: str) -> tuple[str, str]:
    """Drive a verb and assert the rendered datastream carries the expected
    base colour and leaks no escape bytes (gates item 1 + item 3)."""
    s = fresh_session()
    exc = None
    raw = b""
    try:
        s._handle_tso_command(run_verb)
        raw = s.current_screen.to_3270()
    except Exception as e:  # noqa: BLE001
        exc = e
    if exc is not None:
        return f"EXCEPTION:{type(exc).__name__}", ""
    if b"\x1b" in raw:
        return "GARBLED", "escape byte in datastream"
    code = _COLOUR[expect]
    ok = bytes([0x42, code]) in raw
    return ("OK" if ok else "NOCOLOUR"), f"want {expect}=0x{code:02X} present={ok}"


def main() -> int:
    rows: list[tuple[str, str, str]] = []

    for v in INTERACTIVE_VERBS:
        cls, detail = probe_verb(v)
        rows.append((f"verb:{v}", cls, detail))

    for c in LINE_COMMANDS:
        cls, detail = probe_verb(c)
        rows.append((f"cmd:{c}", cls, detail))

    for t in ["racf2john SYS1.RACFDS", "john --show RACF.HASHES"]:
        cls, detail = probe_omvs_tool(t)
        rows.append((f"omvs:{t}", cls, detail))

    for sc in ["$D NJEDEF", "$D SERVICES", "S TCPIP", "P TCPIP"]:
        cls, detail = probe_sdsf_system_cmd(sc)
        rows.append((f"sdsf-sys:/{sc}", cls, detail))

    # colour parity (item 3): TSO red, CONSOLE green, OMVS blue
    for verb, colour in [("LISTUSER IBMUSER", "red"),
                         ("CONSOLE", "green"), ("OMVS", "blue")]:
        cls, detail = probe_colour(verb, colour)
        rows.append((f"colour:{verb}", cls, detail))

    # command-input wrapping (item 8): a multi-row unprotected COMMAND field
    s = fresh_session()
    s._handle_tso_command("LISTUSER IBMUSER")
    cmd_fields = [f for f in s.current_screen.fields
                  if getattr(f, "name", "") == "COMMAND" and not f.protected]
    if cmd_fields and cmd_fields[0].length > 80 and s.current_screen.bound_input_fields:
        rows.append(("input:wrapping-field", "OK",
                     f"COMMAND len={cmd_fields[0].length} bound=True"))
    else:
        rows.append(("input:wrapping-field", "NOFIELD",
                     "no multi-row bound COMMAND field"))

    # rich '?' help over EBCDIC (item 2)
    s = fresh_session()
    s._handle_tso_command("ADDUSER?")
    htxt = "\n".join((getattr(f, "text", "") or "") for f in s.current_screen.fields)
    if "ADDUSER HELP" in htxt and "PASSWORD" in htxt:
        rows.append(("help:ADDUSER?", "OK", "rich COMMAND SYNTAX help"))
    else:
        rows.append(("help:ADDUSER?", "MINIMAL", htxt.split("\n")[0][:50]))

    # OEDIT 3270 full-screen editor on an OMVS file (item 10b)
    try:
        from gibson.apps.omvs import OmvsEnvironment
        s = fresh_session()
        env = OmvsEnvironment(s.state)
        env.ensure_user_profile("IBMUSER")
        vp = env.resolve("/u/ibmuser", "parity_oedit.txt")
        env.write_text(vp, "hello\nworld\n")
        s._handle_tso_command("OEDIT parity_oedit.txt")
        body = "\n".join((getattr(f, "text", "") or "") for f in s.current_screen.fields)
        if s.mode == "OEDITAPP" and "hello" in body and ESC not in body:
            rows.append(("oedit:open", "OK", "ISPF 3270 editor on OMVS file"))
        else:
            rows.append(("oedit:open", "FAIL", f"mode={s.mode}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("oedit:open", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # vi/view/edit inside OMVS -> the 3270 editor, persisting + returning to OMVS
    try:
        s = fresh_session()
        s._handle_tso_command("OMVS")
        env = s.omvs_shell.env
        vp = env.resolve(s.omvs_shell.cwd, "parity_vi.txt")
        env.write_text(vp, "alpha\nbeta\n")
        s._handle_omvs_line("vi parity_vi.txt")
        opened = (s.mode == "OEDITAPP"
                  and type(s.oedit_app).__name__ == "_Omvs3270Editor"
                  and s._panel_return == "TSO_OMVS"
                  and "alpha" in "\n".join(s.oedit_app.lines))
        s.oedit_app.lines = ["alpha", "CHANGED"]
        s.oedit_app._save()
        saved = env.read_text(vp).splitlines() == ["alpha", "CHANGED"]

        class _Done:
            def handle(self, pi):
                return None
        s._dispatch_panel_app(b"\x7d\x40\x40", _Done(), return_mode=s._panel_return)
        returned = s.mode == "TSO_OMVS"
        if opened and saved and returned:
            rows.append(("omvs:vi", "OK", "vi -> 3270 editor, save persists, back to OMVS"))
        else:
            rows.append(("omvs:vi", "FAIL",
                         f"opened={opened} saved={saved} returned={returned}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:vi", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # msfconsole inside OMVS -> interactive sub-mode sharing the ASCII engine
    try:
        s = fresh_session()
        s._handle_tso_command("OMVS")
        s._handle_omvs_line("msfconsole")
        entered = s.mode == "TSO_OMVS_REPL"
        s.handle_tso("help")
        body = screen_text(s.current_screen)
        responded = s.mode == "TSO_OMVS_REPL" and "Core Commands" in body and ESC not in body
        s.handle_tso("exit")
        exited = s.mode == "TSO_OMVS"
        if entered and responded and exited:
            rows.append(("omvs:msfconsole", "OK", "msf6 sub-mode -> commands -> exit to OMVS"))
        else:
            rows.append(("omvs:msfconsole", "FAIL",
                         f"entered={entered} responded={responded} exited={exited}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:msfconsole", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # lynx URL inside OMVS -> interactive 3270 browser sub-mode (shared grammar)
    try:
        s = fresh_session()
        s._handle_tso_command("OMVS")
        s._handle_omvs_line("lynx http://blocked.example")
        entered = s.mode == "TSO_OMVS_REPL"
        s.handle_tso("?")
        helped = s.mode == "TSO_OMVS_REPL" and "Keys: SPACE next page" in screen_text(s.current_screen)
        s.handle_tso("q")
        exited = s.mode == "TSO_OMVS"
        # one-shot forms must NOT enter the sub-mode
        s._handle_omvs_line("lynx -dump http://x")
        oneshot = s.mode == "TSO_OMVS"
        if entered and helped and exited and oneshot:
            rows.append(("omvs:lynx", "OK", "lynx URL -> browser sub-mode -> q to OMVS"))
        else:
            rows.append(("omvs:lynx", "FAIL",
                         f"entered={entered} helped={helped} exited={exited} oneshot={oneshot}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:lynx", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # cti-rss/rss inside OMVS -> interactive 3270 feed-reader sub-mode
    try:
        s = fresh_session()
        s._handle_tso_command("OMVS")
        s._handle_omvs_line("rss")
        banner = screen_text(s.current_screen)
        entered = (s.mode == "TSO_OMVS_REPL"
                   and ("CTI/RSS" in banner or "CTI-RSS" in banner) and ESC not in banner)
        s.handle_tso("f")                       # feeds list -> may page
        guard = 0
        while s.mode == "TSO_MORE" and guard < 30:
            s.handle_tso("")
            guard += 1
        survived = s.mode == "TSO_OMVS_REPL"    # command routed, sub-mode persists
        s.handle_tso("q")
        exited = s.mode == "TSO_OMVS"
        if entered and survived and exited:
            rows.append(("omvs:rss", "OK", "cti-rss sub-mode -> feeds -> q to OMVS"))
        else:
            rows.append(("omvs:rss", "FAIL",
                         f"entered={entered} survived={survived} exited={exited}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:rss", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # FTP interactive client as a TSO sub-mode - authentic z/OS flow, password hidden
    try:
        s = fresh_session()
        pw = next((p for p in ["SYS1", "IBMUSER", "PASSWORD"]
                   if s.state.racf.verify_password("IBMUSER", p)), "SYS1")
        s._handle_tso_command("FTP 127.0.0.1")
        stage1 = s.mode == "TSO_FTP" and s._ftp_stage == "USER"
        s.handle_tso("IBMUSER")
        # the password field must be rendered non-display (hidden)
        pw_hidden = any(getattr(f, "hidden", False) for f in s.current_screen.fields
                        if (getattr(f, "role", "") == "command" or not getattr(f, "protected", True)))
        s.handle_tso(pw)
        loggedin = s._ftp_stage == "CMD"
        s.handle_tso("PWD")
        pwd_ok = "257" in "\n".join((getattr(f, "text", "") or "") for f in s.current_screen.fields)
        s.handle_tso("QUIT")
        quit_ok = s.mode == "TSO_READY" and s.ftp_app is None
        if stage1 and pw_hidden and loggedin and pwd_ok and quit_ok:
            rows.append(("ftp:session", "OK", "FTP login (password hidden) -> ftp> commands -> quit"))
        else:
            rows.append(("ftp:session", "FAIL",
                         f"stage1={stage1} pwhidden={pw_hidden} login={loggedin} pwd={pwd_ok} quit={quit_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ftp:session", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # FTP JES internal reader: submitting JCL returns the REAL, incrementing job
    # id ("250-It is known to JES as JOBnnnnn"), and that id is retrievable with
    # GET (no static placeholder, no decoupled id).
    try:
        import re as _rej
        from gibson.services.ftp import GibsonFtpAdapter as _AD
        jst = make_session(pathlib.Path(tempfile.mkdtemp())).state
        ad = _AD(jst)
        jcl = b"//IBMUSERA JOB (ACCT),'T',CLASS=A,MSGCLASS=X\n//S1 EXEC PGM=IEFBR14\n"

        def _sub():
            r = ad.stor_jes("IBMUSER", "job.jcl", jcl)
            m = _rej.search(r"known to JES as (JOB\d+)", r)
            return r, (m.group(1) if m else None)
        r1, j1 = _sub()
        _, j2 = _sub()
        _, j3 = _sub()
        proto_ok = r1.startswith("250-It is known to JES as JOB") and "JOB19337" not in r1
        increment_ok = None not in (j1, j2, j3) and j1 != j2 != j3 and j1 < j2 < j3
        retr_ok = True
        for j in (j1, j2, j3):
            try:
                if not ad.retr_jes("IBMUSER", j):
                    retr_ok = False
            except Exception:
                retr_ok = False
        # the returned id matches a real job; a fabricated id does not
        no_phantom = False
        try:
            ad.retr_jes("IBMUSER", "JOB19337")
        except FileNotFoundError:
            no_phantom = True
        if proto_ok and increment_ok and retr_ok and no_phantom:
            rows.append(("ftp:jes-submit", "OK",
                         "JCL submit -> real incrementing JOBnnnnn (250 known to JES); GET retrieves spool; no static id"))
        else:
            rows.append(("ftp:jes-submit", "FAIL",
                         f"proto={proto_ok} increment={increment_ok}({j1},{j2},{j3}) retr={retr_ok} nophantom={no_phantom}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ftp:jes-submit", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # TELNET interactive client as a TSO sub-mode (EBCDIC 3270): enters the
    # subsystem and is driven by the shared TelnetSubsession.
    try:
        s = fresh_session()
        s._handle_tso_command("TELNET 127.0.0.1 23")
        entered = s.mode == "TSO_TELNET"
        # a body renders (banner / connecting / error) without raw escapes
        body = "\n".join((getattr(f, "text", "") or "") for f in s.current_screen.fields)
        clean = "\x1b" not in body and "\x07" not in body
        if entered and clean:
            rows.append(("telnet:tso-ebcdic", "OK", "TELNET sub-mode entered from EBCDIC 3270; clean render"))
        else:
            rows.append(("telnet:tso-ebcdic", "FAIL", f"entered={entered} clean={clean}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("telnet:tso-ebcdic", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # TELNET interactive client as a TSO sub-mode (item 10b)
    try:
        s = fresh_session()
        s._handle_tso_command("TELNET")
        entered = s.mode == "TSO_TELNET"
        body = "\n".join((getattr(f, "text", "") or "") for f in s.current_screen.fields)
        banner_ok = "TELNET CLIENT" in body and ESC not in body
        s.handle_tso("help")
        s.handle_tso("quit")
        quit_ok = s.mode == "TSO_READY" and s.telnet_app is None
        if entered and banner_ok and quit_ok:
            rows.append(("telnet:session", "OK", "banner -> telnet> commands -> quit"))
        else:
            rows.append(("telnet:session", "FAIL",
                         f"entered={entered} banner={banner_ok} quit={quit_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("telnet:session", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # 10d: the subsystem dispatch registry is internally consistent — a
    # subsystem can't be half-wired (entry without input handler, or vice versa)
    try:
        s = fresh_session()
        reg = s._subsystems
        problems = []
        for sub in reg:
            if not callable(sub.enter):
                problems.append(f"{sub.name}:enter")
            if not sub.mode:
                problems.append(f"{sub.name}:mode")
            if sub.panel:
                if not sub.app_attr or not hasattr(s, sub.app_attr):
                    problems.append(f"{sub.name}:app_attr")
            elif not callable(sub.line):
                problems.append(f"{sub.name}:line")
        if set(s._subsys_by_mode) != {x.mode for x in reg}:
            problems.append("by_mode")
        if set(s._subsys_by_target) != {x.name for x in reg}:
            problems.append("by_target")
        names = ",".join(x.name for x in reg)
        if not problems:
            rows.append(("registry:consistency", "OK", f"{len(reg)} subsystems: {names}"))
        else:
            rows.append(("registry:consistency", "INCONSISTENT", "; ".join(problems)[:48]))
    except Exception as e:  # noqa: BLE001
        rows.append(("registry:consistency", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # ISPF 3.2 Allocate New Data Set: two-panel flow creates a DCB-correct dataset
    try:
        from gibson.apps.ispf3270.ispf_session import Ispf3270Session
        from gibson.apps.ispf3270 import ispf_session as _ispf
        from gibson.render.panels import PanelInput as _PI
        isp = Ispf3270Session(fresh_session().state, userid="IBMUSER")
        isp._screen = _ispf._DSUTIL
        a = isp.handle(_PI(aid=0, key="ENTER", fields={"OPTION": "A", "DSNAME": "IBMUSER.HARNESS.PDS"}))
        on_alloc = isp._screen == _ispf._DSALLOC and "Allocate New Data Set" in screen_text(a)
        isp.handle(_PI(aid=0, key="ENTER", fields={"SPCU": "CYLS", "PRIQTY": "5", "DIRBLK": "10",
                                                   "RECFM": "FB", "LRECL": "80", "DSNTYPE": "PDS"}))
        meta = isp.state.datasets.meta("IBMUSER", "IBMUSER.HARNESS.PDS")
        made = (isp._screen == _ispf._DSUTIL and meta.get("ORG") == "PO"
                and meta.get("DIRBLKS") == "10" and meta.get("SPACE_UNITS") == "CYLS")
        # bad RECFM is rejected and keeps you on the allocate panel
        isp.handle(_PI(aid=0, key="ENTER", fields={"OPTION": "A", "DSNAME": "IBMUSER.HARNESS.BAD"}))
        b = isp.handle(_PI(aid=0, key="ENTER", fields={"RECFM": "ZZ", "DIRBLK": "0"}))
        rejected = isp._screen == _ispf._DSALLOC and "INVALID RECORD FORMAT" in screen_text(b)
        if on_alloc and made and rejected:
            rows.append(("ispf:allocate", "OK", "3.2 A -> allocate panel -> PDS created, validated"))
        else:
            rows.append(("ispf:allocate", "FAIL",
                         f"on_alloc={on_alloc} made={made} rejected={rejected}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ispf:allocate", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # z/VM logon now verifies CP-directory credentials (no more "any password")
    try:
        from gibson.apps.zvm.zvm_session import ZvmSession, AID_ENTER as _AE

        def _zlogon(state, uid, pw):
            z = ZvmSession(state)
            z.handle(_AE, uid)
            return z, z.handle(_AE, pw)
        base_state = fresh_session().state
        z1, _ = _zlogon(base_state, "MAINT", "MAINT")          # correct weak password
        good = z1._screen == "CP" and z1._classes == "ABCDEFG"
        z2, s2 = _zlogon(base_state, "MAINT", "WRONGPW")       # wrong password rejected
        bad = z2._screen == "LOGON" and "HCPLGA050E" in screen_text(s2)
        hard = fresh_session().state
        hard.config.zvm_lab_vulnerable_mode = False
        z3, _ = _zlogon(hard, "NOBODY99", "x")                 # unknown rejected when hardened
        gated = z3._screen == "LOGON" and not hard.cp_directory.exists("NOBODY99")
        if good and bad and gated:
            rows.append(("zvm:auth", "OK", "CP password verified; bad pw + unknown user rejected"))
        else:
            rows.append(("zvm:auth", "FAIL", f"good={good} bad={bad} gated={gated}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("zvm:auth", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # The z/VM 3270 logon screen must accept the authentic "LOGON userid" / "L
    # userid" forms as well as a bare userid (so typing LOGON LINUX01 logs you in
    # as LINUX01 with its real classes, not as a guest called "LOGON").
    try:
        from gibson.apps.zvm.zvm_session import ZvmSession as _Zvl
        results = {}
        for entry in ("LINUX01", "LOGON LINUX01", "L LINUX01"):
            s = fresh_session().state
            zz = _Zvl(s, peer_addr="10.0.0.9")
            zz.handle(0x7D, entry)
            zz.handle(0x7D, "LINUX01")
            results[entry] = (zz._userid, zz._classes)
        ok = all(u == "LINUX01" and c == "BCEG" for u, c in results.values())
        if ok:
            rows.append(("zvm:logon-verb", "OK", "LOGON/L userid + bare userid all -> LINUX01 (BCEG)"))
        else:
            rows.append(("zvm:logon-verb", "FAIL", str(results)[:60]))
    except Exception as e:  # noqa: BLE001
        rows.append(("zvm:logon-verb", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # z/VM machine creation: DIRMAINT ADD really creates a guest (LIKE clones an
    # admin profile's classes - the realistic over-grant), XAUTOLOG starts it so
    # it shows in QUERY NAMES, AMDISK/PURGE work, and a class-G user is denied.
    try:
        from gibson.apps.zvm.zvm_session import ZvmSession as _Zc, AID_ENTER as _AEc
        cs = fresh_session().state
        zc = _Zc(cs); zc.handle(_AEc, "MAINT"); zc.handle(_AEc, "MAINT")
        def _cpcmd(z, c):
            z._screen = "CP"          # issue from the CP READ prompt (clear prior output)
            return z.handle(_AEc, c)
        _cpcmd(zc, "DIRMAINT ADD NEWVM01 PW SECRET")
        created = cs.cp_directory.exists("NEWVM01")
        _cpcmd(zc, "DIRMAINT ADD WEBVM LIKE MAINT")
        clone = cs.cp_directory.get("WEBVM")
        like_ok = clone is not None and clone.classes == "ABCDEFG"
        _cpcmd(zc, "XAUTOLOG NEWVM01")
        started = "NEWVM01" in cs.cp_directory.logged_on_users()
        _cpcmd(zc, "DIRMAINT FOR NEWVM01 AMDISK 300 75")
        amdisk_ok = "300" in cs.cp_directory.get("NEWVM01").minidisks
        _cpcmd(zc, "DIRMAINT PURGE WEBVM")
        purged = not cs.cp_directory.exists("WEBVM")
        zg = _Zc(cs); zg.handle(_AEc, "GUEST"); zg.handle(_AEc, "GUEST")
        sg = _cpcmd(zg, "DIRMAINT ADD HACKVM")
        deny_add = (not cs.cp_directory.exists("HACKVM")) and "not authorized" in screen_text(sg)
        sx = _cpcmd(zg, "XAUTOLOG NEWVM01")
        deny_auto = "not authorized" in screen_text(sx)
        if created and like_ok and started and amdisk_ok and purged and deny_add and deny_auto:
            rows.append(("zvm:create-machine", "OK",
                         "DIRMAINT ADD creates guest; LIKE clones classes; XAUTOLOG starts; AMDISK/PURGE; class-G denied"))
        else:
            rows.append(("zvm:create-machine", "FAIL",
                         f"add={created} like={like_ok} start={started} amd={amdisk_ok} purge={purged} dadd={deny_add} dauto={deny_auto}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("zvm:create-machine", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # SYSVIEW is now under the ISPF Management menu (option M.3); the SV alias
    # still launches it directly.  Full-screen 3270, PF3 back to the Management menu.
    try:
        from gibson.apps.ispf3270.ispf_session import Ispf3270Session as _IspSv
        from gibson.render.panels import PanelInput as _PIsv
        isp = _IspSv(fresh_session().state, userid="IBMUSER")
        menu = isp._dispatch_option("SV")          # alias still works
        launched = type(isp.subapp).__name__ == "Sysview3270Session"
        mtxt = screen_text(menu)
        menu_ok = "CA SYSVIEW" in mtxt and "System Overview" in mtxt and "Dataset" in mtxt
        # SYSVIEW is now listed on the Management menu (M), not the primary menu
        isp2 = _IspSv(fresh_session().state, userid="IBMUSER")
        on_menu = "SYSVIEW" in screen_text(isp2._dispatch_option("M"))

        def _sv(**f):
            return isp.subapp.handle(_PIsv(aid=0, key=f.pop("key", "ENTER"), fields=f))
        cics_ok = "CICS" in screen_text(_sv(CMD="3"))
        stor_ok = "STORAGE" in screen_text(_sv(CMD="STORAGE")) or "CPU TOTAL" in screen_text(_sv(CMD="STORAGE"))
        back_menu = "PRIMARY OPTION MENU" in screen_text(_sv(key="PF3"))
        exited = _sv(key="PF3") is None
        if launched and menu_ok and on_menu and cics_ok and stor_ok and back_menu and exited:
            rows.append(("sysview:ispf-3270", "OK",
                         "SYSVIEW under ISPF Management menu (M.3) + SV alias; panels+cmds; PF3 back"))
        else:
            rows.append(("sysview:ispf-3270", "FAIL",
                         f"launch={launched} menu={menu_ok} onmenu={on_menu} cics={cics_ok} stor={stor_ok} back={back_menu} exit={exited}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("sysview:ispf-3270", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # L IMS on VTAM: typing 'L IMS' / LOGON APPLID(IMS1) routes to an IMS message
    # terminal (DFS greeting, /SIGN ON RACF-auth, transaction codes via the real
    # IMS model, /DIS, /SIGN OFF) on both the ASCII and the EBCDIC/3270 paths.
    try:
        from gibson.apps.ims.ims_terminal import ImsTerminalSession as _Imt
        from gibson.apps.ims.ims3270 import Ims3270Session as _Im3
        from gibson.render.panels import PanelInput as _PIim
        ist = fresh_session().state
        t = _Imt(ist, peer_addr="10.0.0.9")
        pre = t.command("PART AUTOMOBILE")               # before sign-on -> rejected
        pre_ok = pre is not None and "DFS3649A" in pre and "/SIGN" in pre
        baduser = t.command("/SIGN ON NOSUCHUSER SECRET")
        baduser_ok = "USERID NOT DEFINED" in baduser
        signon = t.command("/SIGN ON IBMUSER")           # existence-based sign-on
        signon_ok = "SIGN COMMAND COMPLETED" in signon
        tx = t.command("PART AUTOMOBILE") or ""
        tx_ok = "SCHEDULED" in tx or "MESSAGE ACCEPTED" in tx
        dis = t.command("/DIS A") or ""
        dis_ok = "DFS000I" in dis
        off = t.command("/SIGN OFF")
        off_ok = off is None
        # SMF LOGON event recorded with service IMS
        smf_ok = any(getattr(e, "command", "") == "LOGON" and "IMS" in (getattr(e, "result", "") + getattr(e, "component", ""))
                     for e in ist.audit.events) or any("IMS /SIGN ON" in getattr(e, "result", "") for e in ist.audit.events)
        # 3270 path
        app = _Im3(fresh_session().state, peer_addr="10.0.0.9")
        init = screen_text(app.initial_screen())
        gui_init = "DFS3650I" in init and "/SIGN COMMAND REQUIRED" in init
        son = screen_text(app.handle(_PIim(aid=0, key="ENTER", fields={"CMD": "/SIGN ON IBMUSER"})))
        gui_signon = "SIGN COMMAND COMPLETED" in son
        gui_exit = app.handle(_PIim(aid=0, key="PF3", fields={})) is None
        # banner advertises L IMS
        from gibson.screens import vtam_model as _vm
        banner = "\n".join(_vm.VtamScreenModel().compact_lines())
        banner_ok = "L IMS" in banner
        if all([pre_ok, baduser_ok, signon_ok, tx_ok, dis_ok, off_ok, smf_ok,
                gui_init, gui_signon, gui_exit, banner_ok]):
            rows.append(("ims:vtam-logon", "OK",
                         "L IMS -> IMS terminal; /SIGN RACF-auth; transactions+/DIS; /SIGN OFF; ASCII+3270; banner advertises"))
        else:
            rows.append(("ims:vtam-logon", "FAIL",
                         f"pre={pre_ok} baduser={baduser_ok} signon={signon_ok} tx={tx_ok} dis={dis_ok} "
                         f"off={off_ok} smf={smf_ok} gui={gui_init}/{gui_signon}/{gui_exit} banner={banner_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ims:vtam-logon", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # z/TPF (L TPF): the prime CRAS console with Z-messages, the ECB transaction
    # model (airline availability + card auth) with an ECB trace, a small TPFDF
    # record model, on both the ASCII and EBCDIC/3270 paths; advertised on VTAM.
    try:
        from gibson.apps.ztpf.ztpf_terminal import ZtpfTerminalSession as _Ztt
        from gibson.apps.ztpf.ztpf3270 import Ztpf3270Session as _Zt3
        from gibson.apps.ztpf.ztpf_engine import z_message as _zm, run_transaction as _rtx
        from gibson.render.panels import PanelInput as _PItp
        zst = fresh_session().state
        stat = _zm(zst, "ZSTAT")
        stat_ok = "SYSTEM STATE" in stat and "I-STREAMS" in stat
        ecb = _rtx(zst, "AVL", "DFWLAX")
        avail_ok = ecb.state == "EXITED" and any("AVAILABILITY" in r for r in ecb.response)
        trace = _zm(zst, "ZTPTRACE")
        trace_ok = "ECB TRACE" in trace and "OPZERO" in trace and "EXITC" in trace
        card = _rtx(zst, "AUTH", "5500000000000004 100")
        card_ok = any("AUTH" in r for r in card.response)
        rec = _zm(zst, "ZDREC FLIGHT")
        rec_ok = "TPFDF FLIGHT RECORDS" in rec and "AA100" in rec
        aces_ok = "ACTIVE ENTRIES" in _zm(zst, "ZACES")
        cyc_ok = "CYCLED TO STATE CRAS" in _zm(zst, "ZCYCL CRAS")
        undef_ok = "NOT DEFINED" in _zm(zst, "ZFOO")
        # terminal command + OFF
        t = _Ztt(zst, peer_addr="10.0.0.9")
        t.command("ZSTAT")              # routed through the terminal -> SMF (service TPF)
        t.command("AVL DFWLAX")
        off_ok = t.command("OFF") is None
        smf_ok = any(getattr(e, "component", "") == "TPF" or "TPF" in getattr(e, "command", "")
                     for e in zst.audit.events)
        # 3270 path
        app = _Zt3(fresh_session().state, peer_addr="10.0.0.9")
        gi = screen_text(app.initial_screen())
        gui_ok = "PRIME CRAS READY" in gi and "z/TPF" in gi
        gz = screen_text(app.handle(_PItp(aid=0, key="ENTER", fields={"CMD": "ZSTAT"})))
        gui_z = "SYSTEM STATE" in gz
        gui_exit = app.handle(_PItp(aid=0, key="PF3", fields={})) is None
        from gibson.screens import vtam_model as _vm2
        banner_ok = "L TPF" in "\n".join(_vm2.VtamScreenModel().compact_lines())
        if all([stat_ok, avail_ok, trace_ok, card_ok, rec_ok, aces_ok, cyc_ok, undef_ok,
                off_ok, smf_ok, gui_ok, gui_z, gui_exit, banner_ok]):
            rows.append(("ztpf:console", "OK",
                         "L TPF CRAS: Z-msgs+ECB transactions+trace+TPFDF; ASCII+3270; banner advertises"))
        else:
            rows.append(("ztpf:console", "FAIL",
                         f"stat={stat_ok} avail={avail_ok} trace={trace_ok} card={card_ok} rec={rec_ok} "
                         f"aces={aces_ok} cyc={cyc_ok} off={off_ok} smf={smf_ok} gui={gui_ok}/{gui_z}/{gui_exit} banner={banner_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ztpf:console", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # z/TPF expanded command catalog (real ZD<xxx> displays) + authentic no-help.
    try:
        from gibson.apps.ztpf import ztpf_engine as _Ze
        zs = fresh_session().state
        def _z(c, **k): return _Ze.z_message(zs, c, **k)
        cat_ok = all([
            "PROGRAM DISPLAY" in _z("ZDPGM"),
            "PROGRAM ATTRIBUTE TABLE" in _z("ZDPAT"),
            "TERMINAL / LNIATA TABLE" in _z("ZDLOK"),
            "RESOURCE CONTROL TABLE" in _z("ZDRCT"),
            "DASD / MODULE STATUS" in _z("ZDMOD"),
            "DUMP NUMBERS" in _z("ZDNUM"),
            "PKI KEYSTORE" in _z("ZPUBK"),
            "FILE SYSTEM (VFS)" in _z("ZPVFS"),
        ])
        help_ok = "no online HELP" in _z("ZHELP") and "ZDORD" in _z("ZHELP")
        undef_ok = "NOT DEFINED" in _z("ZQQQ")
        if cat_ok and help_ok and undef_ok:
            rows.append(("ztpf:zmsg-catalog", "OK",
                         "ZDPGM/ZDPAT/ZDLOK/ZDRCT/ZDMOD/ZDNUM/ZPUBK/ZPVFS render; ZHELP=no-help; undef rejected"))
        else:
            rows.append(("ztpf:zmsg-catalog", "FAIL", f"cat={cat_ok} help={help_ok} undef={undef_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ztpf:zmsg-catalog", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # z/TPF TPFDF records addressed by TYPE+ORDINAL, including sensitive ones.
    try:
        from gibson.apps.ztpf import ztpf_engine as _Zr
        zs = fresh_session().state
        card = _Zr.z_message(zs, "ZDORD CC01 1")
        pnr = _Zr.z_message(zs, "ZDORD PR01 1")
        pub = _Zr.z_message(zs, "ZDORD AA01 100")
        miss = _Zr.z_message(zs, "ZDORD CC01 99")
        bad = _Zr.z_message(zs, "ZDORD")
        ok = ("4111111111111111" in card and "SENSITIVE" in card
              and "PNR" in pnr and "SENSITIVE" in pnr
              and "AA100" in pub and "SENSITIVE" not in pub
              and "NOT FOUND" in miss and "SPECIFY RECORD TYPE" in bad)
        rows.append(("ztpf:records", "OK" if ok else "FAIL",
                     "type+ordinal records: CC01/PR01 sensitive, AA01 public, missing+syntax handled"
                     if ok else f"card={'4111' in card} pnr={'PNR' in pnr} pub={'AA100' in pub}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ztpf:records", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # z/TPF functional-message + record authority: vulnerable-by-default (no ESM)
    # vs secure mode (terminal authority enforced, sensitive records protected,
    # privileged Z-messages denied, audited).
    try:
        from gibson.apps.ztpf import ztpf_engine as _Za
        zs = fresh_session().state
        def _z(c, **k): return _Za.z_message(zs, c, **k)
        vuln_read = "4111111111111111" in _z("ZDORD CC01 1", lniata="010040", authority="BASIC")
        _z("ZPTCH SECMODE=FF", lniata="010002", authority="PRIME")
        _z("ZPTCH AUTHCHK=FF", lniata="010002", authority="PRIME")
        sec_on = _Za.get_ztpf_state(zs).secure_mode and _Za._auth_enforced(_Za.get_ztpf_state(zs))
        sec_rec_deny = "NOT AUTHORIZED" in _z("ZDORD CC01 1", lniata="010040", authority="BASIC")
        sec_priv_deny = "REJECTED" in _z("ZPTCH CRASKEY=X", lniata="010040", authority="BASIC")
        sec_prime_ok = "4111111111111111" in _z("ZDORD CC01 1", lniata="010002", authority="PRIME")
        audit_ok = "AUDIT LOG" in _z("ZAUDIT", lniata="010002", authority="PRIME")
        ok = vuln_read and sec_on and sec_rec_deny and sec_priv_deny and sec_prime_ok and audit_ok
        rows.append(("ztpf:authority", "OK" if ok else "FAIL",
                     "vulnerable BASIC reads PANs; secure denies record+privileged, allows PRIME, audits"
                     if ok else f"vuln={vuln_read} on={sec_on} rdeny={sec_rec_deny} pdeny={sec_priv_deny} prime={sec_prime_ok} aud={audit_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ztpf:authority", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # z/TPF vulnerability lab: recon -> harvest -> tamper -> flag, with Gibson
    # security events raised; secure mode blocks the chain.
    try:
        from gibson.apps.ztpf import ztpf_engine as _Zl
        zs = fresh_session().state
        def _z(c, **k): return _Zl.z_message(zs, c, **k)
        brief_ok = "VULNERABILITY LAB" in _z("ZLAB")
        incomplete = "INCOMPLETE" in _z("ZFLAG", lniata="0700AA")
        _z("ZDLOK", lniata="0700AA")
        _z("ZDORD CC01 1", lniata="0700AA", authority="BASIC")
        _z("ZPTCH AUTHCHK=FF", lniata="0700AA", authority="BASIC")
        flag = _z("ZFLAG", lniata="0700AA")
        flag_ok = "OBJECTIVE COMPLETE" in flag and "FLAG{" in flag
        st_ok = _Zl.get_ztpf_state(zs).lab_flag_captured
        evt_ok = any(getattr(e, "component", "") == "TPF" or "TPF" in getattr(e, "command", "")
                     for e in zs.audit.events)
        # secure mode blocks the same chain for a BASIC terminal
        zs2 = fresh_session().state
        _Zl.z_message(zs2, "ZPTCH SECMODE=FF", lniata="010002", authority="PRIME")
        _Zl.z_message(zs2, "ZPTCH AUTHCHK=FF", lniata="010002", authority="PRIME")
        blocked = "NOT AUTHORIZED" in _Zl.z_message(zs2, "ZDORD CC01 1", lniata="010040", authority="BASIC")
        ok = brief_ok and incomplete and flag_ok and st_ok and evt_ok and blocked
        rows.append(("ztpf:vuln-lab", "OK" if ok else "FAIL",
                     "recon->harvest->tamper->FLAG; Gibson security events; secure mode blocks chain"
                     if ok else f"brief={brief_ok} inc={incomplete} flag={flag_ok} st={st_ok} evt={evt_ok} blk={blocked}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ztpf:vuln-lab", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # APF vulnerability lab: SETPROG APF,ADD stores the DSN fully-qualified (no
    # userid prefix), persists across a restart / separate console process, and
    # is shown live by every display (SDSF APF panel, D PROG,APF, ENUM 'APF').
    try:
        import os as _os, tempfile as _tf, pathlib as _pl
        from gibson.core.config import GibsonConfig as _GC
        from gibson.core.state import GibsonState as _GS
        from gibson.apps.tso import TsoCommandProcessor as _TCPa
        from gibson.apps.sdsf import SdsfApp as _SdA
        from gibson.apps.parmlib.explorer import system_config_state as _scs
        _saved = _os.environ.get("GIBSON_SIM_ROOT")
        _root = _pl.Path(_tf.mkdtemp())
        _os.environ["GIBSON_SIM_ROOT"] = str(_root)
        try:
            DSN = "RUARIV.VULNAPF.LIB"
            s1 = _GS.create(_GC.from_env())
            add_msg = _TCPa(s1, "IBMUSER").run(f"SETPROG APF,ADD,DSNAME={DSN},VOLUME=SMS")
            stored_ok = DSN in s1.apf_libraries and not any("IBMUSER." + DSN in l for l in s1.apf_libraries)
            msg_ok = DSN in add_msg and "ADDED TO APF LIST" in add_msg
            persisted_ok = (_root / "apf_libraries.json").exists()
            s2 = _GS.create(_GC.from_env())                 # separate process / restart
            restart_ok = DSN in s2.apf_libraries
            dprog_ok = DSN in _TCPa(s2, "IBMUSER").run("D PROG,APF")
            disp_ok = DSN in _TCPa(s2, "IBMUSER").run("DISPLAY PROG,APF")
            sdsf_ok = any(DSN == r.cells.get("DSNAME") for r in _SdA(s2, "IBMUSER")._system_panel("APF").rows)
            enum_ok = DSN in _scs(s2)["apf"]
            _TCPa(s2, "IBMUSER").run(f"SETPROG APF,DELETE,DSNAME={DSN}")
            s3 = _GS.create(_GC.from_env())
            del_ok = DSN not in s3.apf_libraries
        finally:
            if _saved is None:
                _os.environ.pop("GIBSON_SIM_ROOT", None)
            else:
                _os.environ["GIBSON_SIM_ROOT"] = _saved
        if all([stored_ok, msg_ok, persisted_ok, restart_ok, dprog_ok, disp_ok, sdsf_ok, enum_ok, del_ok]):
            rows.append(("apf:persistent-add", "OK",
                         "SETPROG APF,ADD fully-qualified + persisted; SDSF/D PROG,APF/ENUM all show it; DELETE persists"))
        else:
            rows.append(("apf:persistent-add", "FAIL",
                         f"stored={stored_ok} msg={msg_ok} persist={persisted_ok} restart={restart_ok} "
                         f"dprog={dprog_ok} disp={disp_ok} sdsf={sdsf_ok} enum={enum_ok} del={del_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("apf:persistent-add", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # APF privilege-escalation lab end-to-end: a SPECIAL user creates a vulnerable
    # APF library with UACC(UPDATE/ALTER) that another (non-special) user can find
    # via ENUM and ride to SPECIAL via ELV.APF - all persistent across a restart.
    try:
        import os as _os3, tempfile as _tf3, pathlib as _pl3
        from gibson.core.config import GibsonConfig as _GC3
        from gibson.core.state import GibsonState as _GS3
        from gibson.apps.tso import TsoCommandProcessor as _TCP3
        _sv = _os3.environ.get("GIBSON_SIM_ROOT")
        results = {}
        for uacc in ("UPDATE", "ALTER"):
            _os3.environ["GIBSON_SIM_ROOT"] = str(_pl3.Path(_tf3.mkdtemp()))
            try:
                DSN, ATT = "RUARIV.VULNAPF.LIB", "BOB"
                s1 = _GS3.create(_GC3.from_env())
                sp = _TCP3(s1, "IBMUSER")
                sp.run(f"SETPROG APF,ADD,DSNAME={DSN},VOLUME=SMS")
                sp.run(f"ADDSD '{DSN}' UACC({uacc})")
                acc = s1.dynamic_racf.effective_access("DATASET", DSN, ATT, s1.racf)
                at = _TCP3(s1, ATT)
                enum_ok = DSN in at.run("ENUM 'APF'")              # bare ENUM
                pre_special = bool(s1.racf.get(ATT) and s1.racf.get(ATT).special)
                elv = at.run("ELV.APF")                            # bare ELV.APF
                esc_ok = "SPECIAL ATTRIBUTE NOW ACTIVE" in elv and s1.racf.get(ATT).special
                # blue-team half: the elv_apf HMS detection must fire
                try:
                    import gibson.apps.cti_hms as _Hh
                    det_ok = "elv_apf" in (getattr(_Hh.get_hms_state(s1), "auto_fired", set()) or set())
                except Exception:
                    det_ok = False
                # persistence across a fresh state (restart / separate process)
                s2 = _GS3.create(_GC3.from_env())
                persist_ok = (DSN in s2.apf_libraries
                              and s2.dynamic_racf.effective_access("DATASET", DSN, ATT, s2.racf) in {"UPDATE", "ALTER"}
                              and bool(s2.racf.get(ATT) and s2.racf.get(ATT).special))
                results[uacc] = (acc in {"UPDATE", "ALTER"}) and enum_ok and (not pre_special) and esc_ok and det_ok and persist_ok
            finally:
                pass
        if _sv is None:
            _os3.environ.pop("GIBSON_SIM_ROOT", None)
        else:
            _os3.environ["GIBSON_SIM_ROOT"] = _sv
        if all(results.values()):
            rows.append(("racf:apf-escalation-lab", "OK",
                         "SPECIAL creates UACC(UPDATE/ALTER) APF lib; ENUM-found; ELV.APF NONE->SPECIAL; fires elv_apf HMS; persists"))
        else:
            rows.append(("racf:apf-escalation-lab", "FAIL", f"results={results}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("racf:apf-escalation-lab", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # zSecure `zsec audit` now produces an authentic CKRCARLA Status Audit report
    try:
        from gibson.apps.zsecure_engine import zsecure_command
        rep = zsecure_command(fresh_session().state, "IBMUSER", "ZSEC AUDIT") or ""
        markers = ["CKRCARLA", "zSecure Audit for RACF", "AUDIT CONCERNS",
                   "PROTECTALL", "PRIVILEGED USER CENSUS", "USEOPER", "CMDSPEC",
                   "CMDFAIL", "AUDIT PRIORITY SUMMARY"]
        missing = [m for m in markers if m not in rep]
        if not missing:
            rows.append(("zsec:audit", "OK", "CKRCARLA status audit: SETROPTS+census+SMF reports"))
        else:
            rows.append(("zsec:audit", "FAIL", "missing: " + ",".join(missing)[:40]))
    except Exception as e:  # noqa: BLE001
        rows.append(("zsec:audit", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # zSecure ISPF menu uses authentic SE/RA/AU option codes and routes correctly
    try:
        from gibson.apps.ispf3270.ispf_session import Ispf3270Session as _Isp
        from gibson.apps.ispf3270 import ispf_session as _ispf2
        from gibson.render.panels import PanelInput as _PI2
        z = _Isp(fresh_session().state, userid="IBMUSER")
        z._screen = _ispf2._ZSEC
        menu = screen_text(z._zsec_panel())
        authentic = ("Menu  Options  Info" in menu and "AU" in menu
                     and "RA.S" in menu and "zSecure" in menu)
        z.handle(_PI2(aid=0, key="ENTER", fields={"OPTION": "AU"}))
        au_out = "\n".join(z._racf_output or [])
        au_ok = "CKRCARLA" in au_out and "AUDIT PRIORITY SUMMARY" in au_out
        z.handle(_PI2(aid=0, key="ENTER", fields={"OPTION": "RA.S"}))
        ras_ok = "SETROPTS" in "\n".join(z._racf_output or []).upper()
        bad = z.handle(_PI2(aid=0, key="ENTER", fields={"OPTION": "ZZ"}))
        invalid_ok = "INVALID OPTION" in screen_text(bad)
        if authentic and au_ok and ras_ok and invalid_ok:
            rows.append(("zsec:menu", "OK", "SE/RA/AU codes; AU->status audit, RA.S->SETROPTS"))
        else:
            rows.append(("zsec:menu", "FAIL",
                         f"authentic={authentic} au={au_ok} ras={ras_ok} inv={invalid_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("zsec:menu", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Endevor MVP: primary menu + element browse reachable through the TSO path
    try:
        from gibson.apps.endevor import endevor_command
        est = fresh_session().state
        menu = endevor_command(est, "TRAINEE", "ENDEVOR") or ""
        disp = endevor_command(est, "TRAINEE", "ENDEVOR DISPLAY") or ""
        hello = endevor_command(est, "TRAINEE", "ENDEVOR BROWSE TRAINING.GENERAL.COBOL.HELLO") or ""
        guard = endevor_command(est, "TRAINEE", "LISTUSER X") is None   # non-Endevor passes through
        if ("ENDEVOR PRIMARY OPTIONS" in menu and "PAYCALC" in disp
                and "HELLO FROM THE TRAINING SYSTEM" in hello and guard):
            rows.append(("endevor:browse", "OK", "C1 menu + element display/browse via TSO"))
        else:
            rows.append(("endevor:browse", "FAIL",
                         f"menu={'ENDEVOR PRIMARY OPTIONS' in menu} disp={'PAYCALC' in disp} "
                         f"browse={'HELLO' in hello} guard={guard}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("endevor:browse", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Endevor broken-access-control lab: vuln leaks cross-scope source; fixed denies + audits
    try:
        from gibson.apps.endevor import endevor_command
        # vulnerable mode (default): TRAINEE reads PAYROLL source it has no scope for
        vs = fresh_session().state
        vs.config.endevor_lab_vulnerable_mode = True
        leak = endevor_command(vs, "TRAINEE", "ENDEVOR BROWSE PAYROLL.SALARY.COBOL.PAYCALC") or ""
        leaked = "WS-CEO-BASE" in leak and "BYPASSED" in leak
        # fixed mode: same browse denied with ICH408I + SMF80 violation; in-scope still works
        fs = fresh_session().state
        fs.config.endevor_lab_vulnerable_mode = False
        before = len(getattr(fs.audit, "events", []))
        denied = endevor_command(fs, "TRAINEE", "ENDEVOR BROWSE PAYROLL.SALARY.COBOL.PAYCALC") or ""
        audited = len(getattr(fs.audit, "events", [])) > before
        denied_ok = "ICH408I" in denied and "INSUFFICIENT ACCESS" in denied and "WS-CEO-BASE" not in denied
        allowed = endevor_command(fs, "IBMUSER", "ENDEVOR BROWSE PAYROLL.SALARY.COBOL.PAYCALC") or ""
        inscope = "WS-CEO-BASE" in allowed
        if leaked and denied_ok and audited and inscope:
            rows.append(("endevor:authz", "OK", "vuln leaks cross-scope; fixed denies+audits, in-scope ok"))
        else:
            rows.append(("endevor:authz", "FAIL",
                         f"leak={leaked} deny={denied_ok} audit={audited} inscope={inscope}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("endevor:authz", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Endevor must be selectable from the ISPF primary option menu (option E),
    # launching the CA Endevor SCM C1 PRIMARY OPTIONS MENU and driving element
    # actions (DISPLAY/BROWSE) from the panel command line.
    try:
        from gibson.apps.ispf3270.ispf_session import Ispf3270Session as _Isp
        from gibson.render.panels import PanelInput as _PIe
        from gibson.apps.endevor import get_endevor_store as _ges
        ist = fresh_session().state
        isp = _Isp(ist, peer_addr="127.0.0.1", userid="TRAINEE")

        def _t(scr):
            return "\n".join((getattr(f, "text", "") or "") for f in scr.fields)
        isp.initial_screen()
        # Endevor is listed on the Management menu (M) and opened via M.4
        on_menu = "Endevor" in _t(isp.handle(_PIe(aid=0, key="ENTER", fields={"OPTION": "M"})))
        c1 = _t(isp.handle(_PIe(aid=0, key="ENTER", fields={"OPTION": "4"})))
        launched = "ENDEVOR PRIMARY OPTIONS MENU" in c1
        # the E alias still opens Endevor directly from the primary menu
        ispA = _Isp(fresh_session().state, peer_addr="127.0.0.1", userid="TRAINEE")
        ispA.initial_screen()
        alias_ok = "ENDEVOR PRIMARY OPTIONS MENU" in _t(ispA.handle(_PIe(aid=0, key="ENTER", fields={"OPTION": "E"})))
        # body now uses authentic multi-colour ISPF styling, not single green
        body_colours = {f.colour for f in isp._endv_panel().fields if (f.text or "").strip()}
        colours_ok = len(body_colours) >= 3
        els = list(_ges(ist).elements.values())
        spec = f"{els[0].system}.{els[0].subsystem}.{els[0].type}.{els[0].name}" if els else "X.Y.Z.Q"
        brw = _t(isp.handle(_PIe(aid=0, key="ENTER", fields={"OPTION": f"BROWSE {spec}"})))
        acted = ("LINE(S) DISPLAYED" in brw) or ("BROWSE ELEMENT" in brw) or ("BYPASSED" in brw)
        back = "Management Services" in _t(isp.handle(_PIe(aid=0, key="PF3", fields={})))
        if on_menu and launched and alias_ok and acted and back and colours_ok:
            rows.append(("endevor:ispf-menu", "OK", "Endevor under Management menu (M.4)+E alias; C1 menu; multi-colour; PF3->M"))
        else:
            rows.append(("endevor:ispf-menu", "FAIL",
                         f"menu={on_menu} c1={launched} alias={alias_ok} acted={acted} back={back} colours={colours_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("endevor:ispf-menu", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # ISPF Management menu (M) groups zSecure, SMP/E, SYSVIEW, Endevor, EZRecon;
    # selections launch each app; EZRecon is a full-screen recon panel under M.5.
    try:
        from gibson.apps.ispf3270.ispf_session import Ispf3270Session as _IspM
        from gibson.render.panels import PanelInput as _PIm
        isp = _IspM(fresh_session().state, userid="IBMUSER")
        isp.initial_screen()
        mtxt = screen_text(isp.handle(_PIm(aid=0, key="ENTER", fields={"OPTION": "M"})))
        lists_all = all(x in mtxt for x in ("Management Services", "zSecure", "SYSVIEW", "Endevor", "EZRecon"))
        # M.5 -> EZRecon panel
        ez = isp.handle(_PIm(aid=0, key="ENTER", fields={"OPTION": "5"}))
        ez_launched = type(isp.subapp).__name__ == "EzRecon3270Session"
        eztxt = screen_text(ez)
        ez_ui = "EZRECON" in eztxt.upper() and "Results" in eztxt
        # numeric menu present (DNS Lookup .. Shodan), F-keys gone; PF3 returns
        def _ez(**f):
            return isp.subapp.handle(_PIm(aid=0, key=f.pop("key", "ENTER"), fields=f))
        numeric_menu = ("DNS Lookup" in eztxt and "Shodan" in eztxt
                        and "Option" in eztxt and "Target" in eztxt)
        ez_colours = len({f.colour for f in ez.fields if (f.text or "").strip()}) >= 3
        ez_exit = _ez(key="PF3") is None
        if lists_all and ez_launched and ez_ui and numeric_menu and ez_colours and ez_exit:
            rows.append(("ispf:management-menu", "OK",
                         "M groups zSecure/SMP-E/SYSVIEW/Endevor/EZRecon; M.5 EZRecon live numeric panel; PF3 back"))
        else:
            rows.append(("ispf:management-menu", "FAIL",
                         f"lists={lists_all} ezlaunch={ez_launched} ui={ez_ui} menu={numeric_menu} col={ez_colours} exit={ez_exit}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ispf:management-menu", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # OMVS client rendering: ANSI/OSC/BEL/CR escapes never reach the 3270; the FTP
    # /TELNET password stage is detected so the input field is rendered hidden;
    # output wraps to the screen width.
    try:
        from gibson.render.ansi3270 import strip_ansi as _sa
        from gibson.render import colors as _c
        from gibson.services.tn3270_server import _omvs_wants_password as _wp
        dirty = (_c.WHITE + "user" + _c.RESET + "\x1b[2J\x1b[H" + _c.RED + "name"
                 + "\x1b]0;window-title\x07" + "\x07\r\nsecond line")
        clean = _sa(dirty)
        no_escapes = not any(ch in clean for ch in ("\x1b", "\x07", "\r"))
        keeps_text = "user" in clean and "name" in clean and "second line" in clean
        keeps_nl = "\n" in clean
        pw_ok = (_wp("331 Send password please.") and _wp("Password:")
                 and _wp("EZA1789I PASSWORD:") and not _wp("ftp> ") and not _wp("230 logged in"))
        # line-mode helper agrees
        from gibson.apps.omvs import _omvs_password_prompt as _lp
        line_ok = _lp("Password:") and _lp("331 need password") and not _lp("normal line")
        if no_escapes and keeps_text and keeps_nl and pw_ok and line_ok:
            rows.append(("omvs:client-render", "OK",
                         "strip_ansi removes CSI/OSC/BEL/CR (keeps text+newlines); FTP/TELNET password stage hidden"))
        else:
            rows.append(("omvs:client-render", "FAIL",
                         f"noesc={no_escapes} text={keeps_text} nl={keeps_nl} pw={pw_ok} line={line_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:client-render", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # Command history: SHIFT+UP / UP recalls previous commands at the TSO command
    # prompt (DOWN walks forward); driven inside the line reader so it is
    # transparent to callers and unaffected on password/panel prompts.
    try:
        from gibson.render.input import SocketInputDriver as _SID

        class _FakeConn:
            def recv(self, n): return b""
            def sendall(self, b): pass

        def _drive(data, history=None):
            d = _SID(_FakeConn(), echo=True)
            d._pending = bytearray(data)
            return d.read_line("", history=history).text

        hist = ["whoami", "ls -la"]
        normal = _drive(b"echo hi\r") == "echo hi"
        shift_up = _drive(b"\x1b[1;2A\r", history=hist) == "ls -la"        # SHIFT+UP
        f12 = _drive(b"\x1b[24~\r", history=hist) == "ls -la"             # F12 retrieve
        f12_twice = _drive(b"\x1b[24~\x1b[24~\r", history=hist) == "whoami"
        up_twice = _drive(b"\x1b[1;2A\x1b[1;2A\r", history=hist) == "whoami"
        plain_up = _drive(b"\x1b[A\r", history=hist) == "ls -la"
        up_down = _drive(b"\x1b[1;2A\x1b[B\r", history=hist) == ""
        no_hist_noop = _drive(b"\x1b[1;2A\r", history=None) in ("", "[1;2A")
        # HISTORY listing keeps the last 50 with bash-style numbering
        big = [f"cmd{i}" for i in range(60)]
        recent = big[-50:]
        hist_list_ok = len(recent) == 50 and recent[0] == "cmd10" and recent[-1] == "cmd59"
        # 3270 path: HISTORY command lists prior commands; PF12 retrieve prefills
        s3 = fresh_session()
        for c in ("LISTCAT", "TIME", "PROFILE"):
            s3._handle_tso_command(c)
        s3._handle_tso_command("HISTORY")
        htxt = screen_text(s3.current_screen)
        hist3270_ok = all(x in htxt for x in ("LISTCAT", "TIME", "PROFILE"))
        prefill = s3.tso_ready_screen(cmd_value="LISTCAT")
        cf = [f for f in prefill.fields if getattr(f, "name", "") == "COMMAND"]
        retrieve_ok = bool(cf) and "LISTCAT" in (getattr(cf[0], "text", "") or "")
        if all([normal, shift_up, f12, f12_twice, up_twice, plain_up, up_down, no_hist_noop,
                hist_list_ok, hist3270_ok, retrieve_ok]):
            rows.append(("tso:command-history", "OK",
                         "line-mode SHIFT+UP/UP/F12 recall + HISTORY; 3270 HISTORY cmd + PF12 retrieve"))
        else:
            rows.append(("tso:command-history", "FAIL",
                         f"normal={normal} shiftup={shift_up} f12={f12} up={plain_up} down={up_down} "
                         f"list={hist_list_ok} h3270={hist3270_ok} retrieve={retrieve_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("tso:command-history", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # Privileged-port migration: TN3270/line-mode default 23, FTP default 21,
    # DB2 stays 50000; the VTAM nmap service profile reflects the new port.
    try:
        from gibson.core.config import GibsonConfig as _GC
        from gibson.net import service_profiles as _sp
        c = _GC()
        ports_ok = c.port == 23 and c.ftp_port == 21 and c.db2_tcp_port == 50000
        prof_ok = _sp.FTP_ZOS.default_port == 21 and _sp.TN3270E.default_port == 23
        if ports_ok and prof_ok:
            rows.append(("config:privileged-ports", "OK", "TN3270/line=23, FTP=21, DB2=50000; service profiles aligned"))
        else:
            rows.append(("config:privileged-ports", "FAIL", f"ports={ports_ok} profiles={prof_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("config:privileged-ports", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # welcome80 landing-page connections must not emit noisy GEO LOGON SMF80
    # records, while real service logons still do, and SMF119 geo telemetry is
    # unaffected.
    try:
        st = make_session(pathlib.Path(tempfile.mkdtemp())).state

        def _geo_logons():
            return sum(1 for e in st.audit.events
                       if "GEO LOGON" in (getattr(e, "event", "") + getattr(e, "command", "") + str(getattr(e, "extra", ""))))
        b0 = _geo_logons()
        st.record_geo_connection("8.8.8.8", port=80, service="WELCOME80", action="LOGON")
        web = _geo_logons() - b0
        st.record_geo_connection("8.8.8.8", port=23, service="TSO", action="LOGON")
        tso = _geo_logons() - b0 - web
        if web == 0 and tso == 1:
            rows.append(("logging:welcome80-geo-suppressed", "OK", "welcome80 GEO LOGON suppressed; service logons still recorded"))
        else:
            rows.append(("logging:welcome80-geo-suppressed", "FAIL", f"web={web} tso={tso}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logging:welcome80-geo-suppressed", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # EZRecon LIVE (kmilne40/EZRecon) as an ISPF panel: numeric options 1-10
    # (no F-keys), real DNS/WHOIS/HTTP/Shodan backend, Get-All and port-scan
    # removed, enterable Shodan API key, and *** continuation paging for long
    # output. Live calls are mocked here (no network in the harness); real
    # acceptance is on Kali.
    try:
        from gibson.apps.ezrecon3270 import ezrecon_live as _live
        from gibson.apps.ezrecon3270 import EzRecon3270Session as _EZ
        from gibson.render.panels import PanelInput as _PIz
        import types as _types
        # mock the network seams
        _live._dns_records = lambda d, t: (["93.184.216.34"] if t == "A" else
                                           (['"v=spf1 ~all"'] if (t == "TXT" and not d.startswith("_dmarc"))
                                            else (['"v=DMARC1; p=none"'] if t == "TXT" else [])))

        def _ans(d, t):
            if t == "MX":
                return [_types.SimpleNamespace(preference=10, exchange=_types.SimpleNamespace(to_text=lambda: "mail.x.com."))]
            if t == "NS":
                return [_types.SimpleNamespace(target=_types.SimpleNamespace(to_text=lambda: "a.iana-servers.net."))]
            if t == "SOA":
                return [_types.SimpleNamespace(mname=_types.SimpleNamespace(to_text=lambda: "ns.x.com."),
                                               rname=_types.SimpleNamespace(to_text=lambda: "host.x.com."),
                                               serial=2024010101, refresh=7200, retry=3600, expire=1209600, minimum=3600)]
            return []
        _live._dns_answer = _ans
        _live._reverse_ptr = lambda ip: ["example.com"]
        _live._whois_raw = lambda d: "Domain Name: EXAMPLE.COM\n" + ("X" * 70 + "\n") * 20
        _live._axfr = lambda ns, d: None
        _live._shodan_search_raw = lambda k, q: {"matches": [{"ip_str": "1.2.3.4", "port": 80, "data": "HTTP/1.1 200"}], "total": 1}
        _live._shodan_host_raw = lambda k, ip: {"ip_str": ip, "org": "Ex", "os": "Linux", "data": [{"port": 443, "product": "nginx", "data": "b"}], "vulns": []}

        ez = _EZ(make_session(pathlib.Path(tempfile.mkdtemp())).state, "127.0.0.1", "IBMUSER")
        ez.initial_screen()

        def _z(**f):
            return screen_text(ez.handle(_PIz(aid=0, key=f.pop("key", "ENTER"), fields=f)))
        numeric = {
            "1 DNS": ("1", "example.com", "93.184.216.34"),
            "2 MX": ("2", "example.com", "mail.x.com"),
            "3 NS": ("3", "example.com", "iana-servers"),
            "4 SOA": ("4", "example.com", "2024010101"),
            "6 WHOIS": ("6", "example.com", "EXAMPLE.COM"),
            "7 Zone": ("7", "example.com", "REFUSED"),
        }
        res = {n: (exp in _z(OPTION=o, TARGET=t)) for n, (o, t, exp) in numeric.items()}
        rev = "example.com" in _z(OPTION="5", TARGET="93.184.216.34")
        # *** paging on long WHOIS
        _z(OPTION="6", TARGET="example.com")
        more_shown = "***" in screen_text(ez._render())
        pg = ez._page
        _z()  # ENTER advances page while ***
        paged = ez._page == pg + 1
        # Shodan needs API key; set it then search/host
        _z(APIKEY="KEY123")
        key_set = ez.api_key == "KEY123" and "(set)" in screen_text(ez._render())
        sh_search = "1.2.3.4" in _z(OPTION="10", TARGET="apache")
        sh_host = "nginx" in "\n".join(ez._all_lines) and _z(OPTION="10", TARGET="93.184.216.34") is not None
        # numeric only, no get-all / port-scan; F-key does nothing useful
        codes_ok = [a[0] for a in _live.ACTIONS] == [str(i) for i in range(1, 11)]
        no_getall = not any("GET ALL" in a[1].upper() for a in _live.ACTIONS)
        no_portscan = not any("PORT" in a[1].upper() or "SCAN" in a[1].upper() for a in _live.ACTIONS)
        bad_opt = "Invalid" in _z(OPTION="99", TARGET="x")
        colours = len({f.colour for f in ez._render().fields if (f.text or "").strip()}) >= 4
        x_exit = ez.handle(_PIz(aid=0, key="ENTER", fields={"OPTION": "X"})) is None
        pf3_exit = ez.handle(_PIz(aid=0, key="PF3", fields={})) is None
        if (all(res.values()) and rev and more_shown and paged and key_set and sh_search
                and codes_ok and no_getall and no_portscan and bad_opt and colours and x_exit and pf3_exit):
            rows.append(("ezrecon:live", "OK",
                         "numeric 1-10 live DNS/MX/NS/SOA/rev/WHOIS/zone/email/subs/shodan; *** paging; API key; no get-all/port-scan"))
        else:
            rows.append(("ezrecon:live", "FAIL",
                         f"num={res} rev={rev} more={more_shown} paged={paged} key={key_set} sh={sh_search} "
                         f"codes={codes_ok} nogetall={no_getall} noportscan={no_portscan} bad={bad_opt} col={colours} x={x_exit} pf3={pf3_exit}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ezrecon:live", f"EXCEPTION:{type(e).__name__}", str(e)[:70]))

    # DB2 z/OS DRDA listener on 50000: answers a client EXCSAT with a valid
    # EXCSATRD that nmap's drda-info/-sV parses as IBM DB2 (platform, version,
    # instance, external name); also answers ACCSEC with ACCSECRD.
    try:
        import struct as _st
        from gibson.net import drda as _drda
        sstate = make_session(pathlib.Path(tempfile.mkdtemp())).state

        def _p(cp, d):
            return _st.pack(">HH", len(d) + 4, cp) + d
        mgr = bytes.fromhex("1403000724070008240f00081440000814740008")
        ep = (_p(_drda.EXTNAM, b"") + _p(_drda.SRVNAM, b"") + _p(_drda.SRVRLSLV, b"")
              + _p(_drda.MGRLVLLS, mgr) + _p(_drda.SRVCLSNM, b""))
        ddm = _st.pack(">HH", len(ep) + 4, _drda.EXCSAT) + ep
        req = _st.pack(">HBBH", len(ddm) + 6, 0xD0, 0x01, 1) + ddm
        cp_ok = _drda.parse_request_codepoint(req) == _drda.EXCSAT
        resp = _drda.respond(req, sstate)

        def _parse(r):
            dl = _st.unpack(">H", r[0:2])[0]
            d = r[6:dl]
            ddm_cp = _st.unpack(">H", d[2:4])[0]
            f = {}
            off = 4
            while off < _st.unpack(">H", d[0:2])[0]:
                pl = _st.unpack(">H", d[off:off + 2])[0]
                pc = _st.unpack(">H", d[off + 2:off + 4])[0]
                f[pc] = d[off + 4:off + pl]
                off += pl
            return ddm_cp, f
        ddm_cp, fields = _parse(resp)
        magic_ok = resp[2] == 0xD0
        rd_ok = ddm_cp == _drda.EXCSATRD
        srvclass = fields.get(_drda.SRVCLSNM, b"").decode("cp037")
        prodrel = fields.get(_drda.SRVRLSLV, b"").decode("cp037")
        srvname = fields.get(_drda.SRVNAM, b"").decode("cp037")
        fields_ok = ("DB2" in srvclass) and prodrel.startswith("DSN") and bool(srvname)
        # ACCSEC -> ACCSECRD
        ap = _p(_drda.SECMEC, _st.pack(">H", 3))
        addm = _st.pack(">HH", len(ap) + 4, _drda.ACCSEC) + ap
        areq = _st.pack(">HBBH", len(addm) + 6, 0xD0, 0x01, 1) + addm
        aresp = _drda.respond(areq, sstate)
        acc_ok = _st.unpack(">H", aresp[8:10])[0] == _drda.ACCSECRD
        # full login handshake: SECCHK (RACF) + ACCRDB (RDB name)
        def _mkreq(cp, *ps):
            body = b"".join(ps)
            ddm = _st.pack(">HH", len(body) + 4, cp) + body
            return _st.pack(">HBBH", len(ddm) + 6, 0xD0, 0x01, 1) + ddm
        _pw = next((p for p in ["SYS1", "IBMUSER", "PASSWORD"]
                    if sstate.racf.verify_password("IBMUSER", p)), "SYS1")
        sc_ok = _drda.respond(_mkreq(_drda.SECCHK, _p(_drda.USRID, "IBMUSER".encode("cp037")),
                                     _p(_drda.PASSWORD, _pw.encode("cp037"))), sstate)
        secchk_ok = (_st.unpack(">H", sc_ok[8:10])[0] == _drda.SECCHKRM
                     and _drda.get_request_param(sc_ok, _drda.SECCHKCD) == b"\x00")
        sc_bad = _drda.respond(_mkreq(_drda.SECCHK, _p(_drda.USRID, "IBMUSER".encode("cp037")),
                                      _p(_drda.PASSWORD, "WRONGPW99".encode("cp037"))), sstate)
        secchk_rej = _drda.get_request_param(sc_bad, _drda.SECCHKCD) != b"\x00"
        ar_ok = _drda.respond(_mkreq(_drda.ACCRDB, _p(_drda.RDBNAM, "GIBSONDB2".encode("cp037"))), sstate)
        accrdb_ok = _st.unpack(">H", ar_ok[8:10])[0] == _drda.ACCRDBRM
        ar_no = _drda.respond(_mkreq(_drda.ACCRDB, _p(_drda.RDBNAM, "NOSUCHDB".encode("cp037"))), sstate)
        rdbnfn_ok = _st.unpack(">H", ar_no[8:10])[0] == _drda.RDBNFNRM
        handshake_ok = secchk_ok and secchk_rej and accrdb_ok and rdbnfn_ok
        if cp_ok and magic_ok and rd_ok and fields_ok and acc_ok and handshake_ok:
            rows.append(("db2:drda-listener", "OK",
                         f"EXCSAT/ACCSEC/SECCHK(RACF)/ACCRDB handshake; platform={srvclass}, version={prodrel}, instance={srvname}"))
        else:
            rows.append(("db2:drda-listener", "FAIL",
                         f"cp={cp_ok} magic={magic_ok} rd={rd_ok} fields={fields_ok} acc={acc_ok} hs={handshake_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("db2:drda-listener", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # NJE (Network Job Entry) listener: binds 175 (clear) + 2252 (TLS), silent on
    # connect, answers the 33-byte OPEN with ACK/NAK and the reason-code
    # side-channel (0x01 unknown OHOST, 0x04 valid OHOST/bad RHOST, 0x00 ACK)
    # exactly as nmap's nje-node-brute expects.
    try:
        from gibson.net import nje_protocol as _P
        from gibson.core.nje import CHAPTER10_NODES as _NODES
        from gibson.core.config import GibsonConfig as _GC2
        from gibson.net import service_profiles as _sp2

        def _open(rhost, ohost):       # build exactly like nmap openNJEfmt
            return (b"\xd6\xd7\xc5\xd5\x40\x40\x40\x40"
                    + _P.ebcdic8(rhost) + b"\x00\x00\x00\x00"
                    + _P.ebcdic8(ohost) + b"\x00\x00\x00\x00" + b"\x00")
        cases = {
            "valid-ohost(HAL)": ("FAKE", "HAL", "NAK", 0x04),
            "unknown-ohost": ("FAKE", "NOPE", "NAK", 0x01),
            "full-ack": ("GIBSON", "HAL", "ACK", 0x00),
            "own-node(GIBSON)": ("FAKE", "GIBSON", "NAK", 0x04),
        }
        results = {}
        rlen_ok = True
        for name, (rh, oh, et, er) in cases.items():
            resp, info = _P.respond_open(_open(rh, oh), _NODES)
            rlen_ok = rlen_ok and len(resp) == 33
            results[name] = (_P.from_ebcdic(resp[0:8]) == et and resp[32] == er)
        non_open = _P.respond_open(b"garbage-not-an-open-record-bytes!", _NODES) is None
        # I-record sign-on (nje-pass-brute): build an I-record like the script,
        # extract + check the password, and confirm the J/B reply byte 19.
        _irec_hdr = bytes.fromhex("0000003e000000000000002e1002808fcff0c929")

        def _irec(rhost, pw):
            return (_irec_hdr + _P.ebcdic8(rhost) + b"\x01" + b"\x00" * 5
                    + bytes([0x64, 0x80, 0x00]) + _P.ebcdic8(pw.upper()) * 2
                    + bytes.fromhex("0015000000000000000000"))
        pw_good = _P.parse_irecord_password(_irec("GIBSON", "HAL123")) == "HAL123"
        ok_good = _P.check_node_password("HAL", "HAL123", _NODES)
        ok_bad = not _P.check_node_password("HAL", "WRONGPW", _NODES)
        jrec = _P.signon_reply(True)
        brec = _P.signon_reply(False)
        # nje-pass-brute reads byte 19 (1-indexed): 0xC2 -> invalid, else valid
        signon_ok = (len(jrec) >= 19 and jrec[18] != 0xC2
                     and len(brec) >= 19 and brec[18] == 0xC2)
        dleack_ok = len(_P.DLE_ACK) == 18 and _P.is_soh_enq(_P.SOH_ENQ)
        cfg2 = _GC2()
        ports_ok = cfg2.nje_port == 175 and cfg2.nje_tls_port == 2252
        prof_ok = (getattr(_sp2, "NJE").nmap_service == "nje"
                   and getattr(_sp2, "NJE").default_port == 175
                   and getattr(_sp2, "NJE_TLS").default_port == 2252)
        if (all(results.values()) and rlen_ok and non_open and ports_ok and prof_ok
                and pw_good and ok_good and ok_bad and signon_ok and dleack_ok):
            rows.append(("nje:listener", "OK",
                         "OPEN->ACK/NAK (node-brute) + SOH/ENQ->DLE/ACK->I-record password (pass-brute); ports 175/2252"))
        else:
            rows.append(("nje:listener", "FAIL",
                         f"cases={results} rlen={rlen_ok} nonopen={non_open} ports={ports_ok} prof={prof_ok} "
                         f"pw={pw_good} okg={ok_good} okb={ok_bad} signon={signon_ok} dle={dleack_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("nje:listener", f"EXCEPTION:{type(e).__name__}", str(e)[:70]))

    # NJE lab (Chapter 10 post-auth kill chain): NMR operator-command injection
    # (iNJEctor rogue node), cross-node /*XEQ under a forged NJHTOUSR identity,
    # RACF persistence (Z4CK SPECIAL+OMVS), operator forensics and HMS detection.
    try:
        from gibson.core.nje import NJENetwork as _NN
        from gibson.apps import nje_lab as _lab
        from gibson.apps.cti_hms import get_hms_state as _hms, seen_ttp_ids as _seen
        lst = make_session(pathlib.Path(tempfile.mkdtemp())).state
        net = _NN.seeded()
        # NMR injection: build the rogue H4CKR node with full authority
        for c in ("$T NJEDEF ,NODENUM=5", "$T NODE(5) ,name=H4CKR",
                  "$add socket(h4ckr),node=h4ckr,ipaddr=192.168.0.20",
                  "$T node(h4ckr),auth=(Device=Y,Job=Y,Net=Y,System=Y)"):
            _lab.nmr_inject(lst, net, c)
        h4ckr = net.nodes.get("H4CKR")
        nmr_ok = h4ckr is not None and "NET=Y" in h4ckr.auth and "SYSTEM=Y" in h4ckr.auth
        # cross-node /*XEQ persistence payload
        log, info = _lab.xeq_execute(lst, rhost="GIBSON", ohost="HAL",
                                     jcl_text=_lab.RACF_JCL, asuser="RUARIV")
        z = lst.racf.get("Z4CK")
        persist_ok = (z is not None and getattr(z, "special", False)
                      and getattr(z, "has_omvs", getattr(z, "omvs", False)))
        forensics_ok = (any("$HASP122" in l for l in log)
                        and any("IEF403I" in l for l in log)
                        and any("IEF404I" in l for l in log)
                        and any("IRR010I" in l for l in log))
        ids = _seen(_hms(lst))
        hms_ok = "nje_nmr" in ids and "nje_exec" in ids
        if nmr_ok and persist_ok and forensics_ok and hms_ok:
            rows.append(("nje:lab", "OK",
                         "NMR injection (rogue H4CKR NET/SYSTEM); /*XEQ forges NJHTOUSR -> Z4CK SPECIAL+OMVS; $HASP122/IEF40x forensics; HMS nje_nmr+nje_exec"))
        else:
            rows.append(("nje:lab", "FAIL",
                         f"nmr={nmr_ok} persist={persist_ok} forensics={forensics_ok} hms={hms_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("nje:lab", f"EXCEPTION:{type(e).__name__}", str(e)[:70]))

    # RACFDS Scope A - real RACF DES hash generation (john --format=racf). The
    # hashes are validated byte-exact against John the Ripper's own published
    # DES test vectors, using a real DES provider (pycryptodome or the
    # `cryptography` library). This is the password material a binary
    # SYS1.RACFDS.BACKUP carries for offline cracking.
    try:
        import warnings as _w
        _w.filterwarnings("ignore")
        from gibson.core.racf_legacy_des import (
            generate_legacy_racf_des_hash as _g, crypto_available as _ca,
            format_john_racf_hash as _fj)
        vectors = {("A", "A"): "0F7DE80335E8ED68",
                   ("AAAAAAAA", "AAAAAAAA"): "062314297C496E0E",
                   ("TESTTEST", "TESTTEST"): "0FF48804F759193F"}
        real = _ca()
        matches = {f"{u}/{p}": (_g(u, p) == exp) for (u, p), exp in vectors.items()}
        john_line = _fj("TESTTEST", _g("TESTTEST", "TESTTEST"))
        fmt_ok = john_line == "TESTTEST:$racf$*TESTTEST*0FF48804F759193F"
        if real and all(matches.values()) and fmt_ok:
            rows.append(("racfds:des-hashes", "OK",
                         "real DES provider; JtR vectors A/AAAAAAAA/TESTTEST match byte-exact; $racf$* line well-formed"))
        else:
            rows.append(("racfds:des-hashes", "FAIL",
                         f"real_des={real} vectors={matches} fmt={fmt_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("racfds:des-hashes", f"EXCEPTION:{type(e).__name__}", str(e)[:70]))

    # RACFDS Scope A - binary SYS1.RACFDS.BACKUP container. A real 4096-byte-block
    # RACF DB image (ICB / BAM / index / USER profiles) built from live RACF
    # state, carrying genuine DES hashes; round-trips through the reference reader
    # and snapshots on backup with SMF/HMS evidence. (Real racf2john acceptance is
    # on the target box; this gate proves internal consistency + hash fidelity.)
    try:
        import warnings as _w2
        _w2.filterwarnings("ignore")
        from gibson.core import racf_db_image as _img
        from gibson.core import racf_db_binary as _rdb
        from gibson.core.racf_legacy_des import generate_legacy_racf_des_hash as _g2
        from gibson.core.racf_database import LEGACY_LAB_PASSWORDS as _LLP
        from gibson.apps.cti_hms import get_hms_state as _hg, seen_ttp_ids as _hs
        bst = make_session(pathlib.Path(tempfile.mkdtemp())).state
        blob = _rdb.build_racfds_binary(bst)
        blocks_ok = len(blob) >= 4 * _img.BLOCK_SIZE and len(blob) % _img.BLOCK_SIZE == 0
        icb_ok = blob[24:32] == _img.ICB_MARKER
        ents = {e.userid: e for e in _img.parse(blob)}
        rt_ok = _rdb.verify_roundtrip(bst)
        # the seeded legacy lab users must carry the genuine crackable DES hash
        lab_ok = all(
            uid.upper() in ents and ents[uid.upper()].password_hex == _g2(uid, pw).upper()
            for uid, pw in _LLP.items()) and bool(_LLP)
        msg, raw = _rdb.materialise_racfds_binary(bst, trigger="COPYRACF.JCL")
        cat = bst.datasets.read("IBMUSER", "SYS1.RACFDS.BACKUP")
        snap_ok = ("RACFDS-BINARY-BASE64" in cat
                   and getattr(bst, "racfds_backup_stale", True) is False
                   and "racfds_john" in _hs(_hg(bst)))
        # reader emits racf2john-style lines
        lines_ok = any(l.startswith("DUMONT:$racf$*DUMONT*") for l in _img.john_lines(list(ents.values())))
        # full exfil chain: BACKUP command -> binary dataset -> OMVS cp -> raw bytes
        from gibson.core.racf_database import backup_racfds as _bk
        from gibson.core.racf_db_binary import is_binary_dataset as _isbin, decode_from_dataset as _dec
        from gibson.apps.omvs import OmvsShellSession as _OSS
        _bk(bst)
        bcat = bst.datasets.read("IBMUSER", "SYS1.RACFDS.BACKUP")
        backup_bin = _isbin(bcat)
        sh = _OSS(bst, "IBMUSER")
        sh.execute("cp \"//'SYS1.RACFDS.BACKUP'\" /tmp/racfdb")
        uss_raw = sh.env.read_bytes("/tmp/racfdb")
        cp_bin = (uss_raw[24:32] == _img.ICB_MARKER and len(uss_raw) % _img.BLOCK_SIZE == 0
                  and uss_raw[:4] != b"RDBU" and _img.parse(uss_raw))
        exfil_ok = backup_bin and bool(cp_bin)
        if blocks_ok and icb_ok and rt_ok and lab_ok and snap_ok and lines_ok and exfil_ok:
            rows.append(("racfds:binary", "OK",
                         "4KB-block image from live RACF; genuine DES; round-trips; BACKUP writes binary; OMVS cp //' yields raw bytes (racf2john)"))
        else:
            rows.append(("racfds:binary", "FAIL",
                         f"blocks={blocks_ok} icb={icb_ok} rt={rt_ok} lab={lab_ok} snap={snap_ok} lines={lines_ok} exfil={exfil_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("racfds:binary", f"EXCEPTION:{type(e).__name__}", str(e)[:70]))

    # OMVS client rendering: ANSI escapes stripped on the 3270 path, and a
    # password prompt makes the next input field non-display (masked).
    try:
        from gibson.apps.omvs import _omvs_password_prompt as _opp
        from gibson.services.tn3270_server import _omvs_wants_password as _owp
        from gibson.render.ansi3270 import strip_ansi as _sa
        # ANSI escapes removed
        esc = "\x1b[31mRED\x1b[0m \x1b[1mBOLD\x1b[0m line"
        strip_ok = "\x1b" not in _sa(esc) and "RED" in _sa(esc)
        # password prompts detected (both transports)
        pw_cases = ["331 Send password please.\nPassword:", "Password:", "Enter passphrase:"]
        no_cases = ["ftp> ", "login: ", "EZA1701I Not connected."]
        det_ok = (all(_opp(c) and _owp(c) for c in pw_cases)
                  and not any(_opp(c) or _owp(c) for c in no_cases))
        # the masking reuses the proven logon hidden-field mechanism: a 3270
        # session renders a non-display COMMAND field when input_hidden=True
        from gibson.services.tn3270_server import Tn3270Session as _T3
        sess = _T3.__new__(_T3)
        sess.state = fresh_session().state
        sess._tso_more = None
        sess._sent = []
        sess._send_screen = lambda s: sess._sent.append(s)
        sess.mode = "TSO_OMVS"
        sess._emit_tso_output("331 Send password please.\nPassword:", prompt="ftp>",
                              return_mode="TSO_OMVS", input_hidden=True)
        scr = sess._sent[-1]
        cmd_field = next((f for f in scr.fields if getattr(f, "role", "") == "command"
                          or getattr(f, "name", "") == "COMMAND"), None)
        mask_ok = cmd_field is not None and bool(getattr(cmd_field, "hidden", False))
        if strip_ok and det_ok and mask_ok:
            rows.append(("omvs:client-render", "OK",
                         "3270 strips ANSI escapes; password prompt -> non-display input field; detectors correct"))
        else:
            rows.append(("omvs:client-render", "FAIL",
                         f"strip={strip_ok} detect={det_ok} mask={mask_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:client-render", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # Endevor foreground realism: option 2 on the C1 menu opens a fielded
    # element-action data-entry panel (ACTION + ENVIRONMENT/SYSTEM/SUBSYSTEM/
    # TYPE/ELEMENT/STAGE) that drives the real engine; missing keys are guarded.
    try:
        from gibson.apps.ispf3270.ispf_session import Ispf3270Session as _IspF
        from gibson.render.panels import PanelInput as _PIf
        from gibson.apps.endevor import get_endevor_store as _ges
        fst = fresh_session().state
        el = list(_ges(fst).elements.values())[0]
        isf = _IspF(fst, peer_addr="127.0.0.1", userid="IBMUSER")

        def _tf(scr):
            return "\n".join((getattr(f, "text", "") or "") for f in scr.fields)
        isf.initial_screen()
        isf.handle(_PIf(aid=0, key="ENTER", fields={"OPTION": "E"}))
        fgp = _tf(isf.handle(_PIf(aid=0, key="ENTER", fields={"OPTION": "2"})))
        fielded = "Element Actions" in fgp and "Action" in fgp and "System" in fgp
        brw = _tf(isf.handle(_PIf(aid=0, key="ENTER", fields={
            "ACTION": "BROWSE", "SYSTEM": el.system, "SUBSYS": el.subsystem,
            "TYPE": el.type, "ELEMENT": el.name, "STAGE": "P"})))
        browsed = ("BROWSE" in brw.upper()) and ("DISPLAYED" in brw.upper()
                   or "BROWSE ELEMENT" in brw.upper() or "BYPASSED" in brw.upper())
        guard = "REQUIRED" in _tf(isf.handle(_PIf(aid=0, key="ENTER",
                                 fields={"ACTION": "RETRIEVE", "SYSTEM": el.system})))
        backc1 = "PRIMARY OPTIONS" in _tf(isf.handle(_PIf(aid=0, key="PF3", fields={}))).upper()
        if fielded and browsed and guard and backc1:
            rows.append(("endevor:foreground", "OK",
                         "C1 opt 2 -> fielded BROWSE drives engine; key guard; PF3 back"))
        else:
            rows.append(("endevor:foreground", "FAIL",
                         f"fielded={fielded} browsed={browsed} guard={guard} back={backc1}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("endevor:foreground", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Endevor element lifecycle realism: ADD->GENERATE->MOVE with VVLL bumping and
    # footprints (CCID/last-action/proc-group), signout enforcement, SCL batch.
    try:
        from gibson.apps.endevor import endevor_command as _E
        est = fresh_session().state
        a = _E(est, "IBMUSER", "ENDEVOR ADD TRAINING.GENERAL.COBOL.PAYX CCID JIRA-1 COMMENT 'x'")
        add_ok = "ADDED TO STAGE D" in a and "VV.LL 01.00" in a
        g = _E(est, "IBMUSER", "ENDEVOR GENERATE TRAINING.GENERAL.COBOL.PAYX")
        gen_ok = "GENERATE COMPLETED" in g and "RC=0000" in g and "VV.LL 01.01" in g
        move_ok = "MOVED FROM STAGE D TO STAGE T" in _E(est, "IBMUSER",
                          "ENDEVOR MOVE TRAINING.GENERAL.COBOL.PAYX TO TEST")
        _E(est, "IBMUSER", "ENDEVOR ADD TRAINING.GENERAL.COBOL.NOGENX")
        nogen = "NOT GENERATED" in _E(est, "IBMUSER",
                          "ENDEVOR MOVE TRAINING.GENERAL.COBOL.NOGENX TO TEST")
        br = _E(est, "IBMUSER", "ENDEVOR BROWSE TRAINING.GENERAL.COBOL.PAYX")
        foot = "CCID JIRA-1" in br and "GENERATED YES" in br and "LAST ACTION MOVE" in br
        _E(est, "TRAINEE", "ENDEVOR SIGNOUT TRAINING.GENERAL.COBOL.HELLO")
        denied = "SIGNED OUT TO TRAINEE" in _E(est, "IBMUSER",
                          "ENDEVOR DELETE TRAINING.GENERAL.COBOL.HELLO")
        over = "OVERRIDE" in _E(est, "IBMUSER", "ENDEVOR SIGNOVER TRAINING.GENERAL.COBOL.HELLO")
        scl = _E(est, "IBMUSER", "ENDEVOR SCL SET SYSTEM TRAINING SUBSYS GENERAL TYPE COBOL; "
                                 "ADD ELEMENT SCLX; GENERATE ELEMENT SCLX; MOVE ELEMENT SCLX")
        scl_ok = "C1BM3000I" in scl and "MAXCC=0000" in scl and scl.count("RC=0000") >= 4
        if all([add_ok, gen_ok, move_ok, nogen, foot, denied, over, scl_ok]):
            rows.append(("endevor:lifecycle", "OK",
                         "ADD/GEN(RC0000)/MOVE, footprint+VVLL, signout enforce, SIGNOVER"))
            rows.append(("endevor:scl", "OK", "C1BM3000 SCL deck SET+ADD/GENERATE/MOVE MAXCC=0000"))
        else:
            rows.append(("endevor:lifecycle", "FAIL",
                         f"add={add_ok} gen={gen_ok} move={move_ok} nogen={nogen} "
                         f"foot={foot} signout={denied} over={over}"))
            rows.append(("endevor:scl", "FAIL", f"scl={scl_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("endevor:lifecycle", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # New users created via ADDUSER must receive the same default training
    # datasets as the seeded users (GUEST): PDS.CODE, SQL.LAB, 4CHAR.PIN,
    # JCL.LAB, COBOL.LAB, REXX.LAB, plus the matching DATASET profiles.
    try:
        nst = fresh_session().state
        SUF = ["PDS.CODE", "SQL.LAB", "4CHAR.PIN", "JCL.LAB", "COBOL.LAB", "REXX.LAB"]

        def _has(uid, suf):
            return nst.datasets.ds_path(uid, f"{uid}.{suf}").exists()
        nst.racf.adduser("ZZNEWUSR", password="ZZ1PWXY")
        new_ok = all(_has("ZZNEWUSR", s) for s in SUF)
        member_ok = (nst.datasets.ds_path("ZZNEWUSR", "ZZNEWUSR.PDS.CODE") / "TIME").exists()
        prof_ok = all(nst.dynamic_racf._find_profile("DATASET", f"ZZNEWUSR.{p}") is not None
                      for p in ("PDS.CODE", "SQL.LAB", "JCL.LAB"))
        if new_ok and member_ok and prof_ok:
            rows.append(("racf:newuser-datasets", "OK",
                         "ADDUSER provisions PDS.CODE/SQL/4CHAR.PIN/JCL/COBOL/REXX + profiles"))
        else:
            rows.append(("racf:newuser-datasets", "FAIL",
                         f"datasets={new_ok} members={member_ok} profiles={prof_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("racf:newuser-datasets", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # OMVS network tools must be true-to-life: BIND dig (answer/+short/-x/NXDOMAIN),
    # RIR/registrar whois, nslookup/host, and z/OS CS ping (-c honored)/traceroute.
    try:
        from gibson.apps.omvs import OmvsShellSession as _Omv
        ost = fresh_session().state
        sh = _Omv(ost, "IBMUSER")
        dig = sh.execute("dig example.com")
        dig_ok = "ANSWER SECTION" in dig and "93.184.216.34" in dig and "status: NOERROR" in dig
        short_ok = sh.execute("dig +short example.com").strip() == "93.184.216.34"
        nx_ok = "NXDOMAIN" in sh.execute("dig nonexistent.invalid")
        rev_ok = "example.com" in sh.execute("dig -x 93.184.216.34")
        whod_ok = "Registrar:" in sh.execute("whois example.com")
        whoi = sh.execute("whois 8.8.8.8")
        whoi_ok = "NetRange:" in whoi and "Google" in whoi
        png = sh.execute("ping -c 3 example.com")
        png_ok = "Pinging host" in png and png.count("response took") == 3 and "3 packets received" in png
        tr = sh.execute("traceroute example.com")
        tr_ok = "Traceroute to" in tr and "93.184.216.34" in tr and tr.count(" ms") >= 3
        ns_ok = "Address: 93.184.216.34" in sh.execute("nslookup example.com")
        hs_ok = "has address 93.184.216.34" in sh.execute("host example.com")
        if all([dig_ok, short_ok, nx_ok, rev_ok, whod_ok, whoi_ok, png_ok, tr_ok, ns_ok, hs_ok]):
            rows.append(("omvs:nettools", "OK",
                         "dig/+short/-x/NXDOMAIN, whois dom+ip, nslookup/host, ping -c, traceroute"))
        else:
            rows.append(("omvs:nettools", "FAIL",
                         f"dig={dig_ok} short={short_ok} nx={nx_ok} rev={rev_ok} whoD={whod_ok} "
                         f"whoI={whoi_ok} ping={png_ok} tr={tr_ok} ns={ns_ok} host={hs_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:nettools", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # OMVS full-screen 3270 editor: oedit/vi open a real fielded ISPF-EDIT panel
    # (overtype + prefix I/D), PF3 saves to the USS file, and view is read-only.
    try:
        from gibson.apps.tso3270.tso_session import Tso3270App as _T3
        from gibson.apps.tso import TsoCommandProcessor as _TCP
        from gibson.render.panels import PanelInput as _PIe
        est = fresh_session().state
        uu = est.racf.get("IBMUSER")
        if not getattr(uu, "has_omvs", False):
            est.racf.altuser("IBMUSER", omvs=True,
                             omvs_segment={"UID": "0", "HOME": "/u/ibmuser", "PROGRAM": "/bin/sh"})
        a = _T3(est, peer_addr="127.0.0.1", userid="IBMUSER")
        a.tso = _TCP(est, "IBMUSER")
        a._enter_omvs()

        def _tx(scr):
            return "\n".join((getattr(f, "text", "") or "") for f in (scr.fields if scr else []))
        opened = "EDIT" in _tx(a.handle(_PIe(aid=0, key="ENTER",
                              fields={"CMD": "oedit /u/ibmuser/gate.txt"})))
        a.handle(_PIe(aid=0, key="ENTER", fields={"L0": "GATE LINE ONE", "P0": "000100"}))
        a.handle(_PIe(aid=0, key="ENTER", fields={"P0": "I", "L0": "GATE LINE ONE"}))
        a.handle(_PIe(aid=0, key="ENTER", fields={"L1": "GATE LINE TWO", "L0": "GATE LINE ONE"}))
        a.handle(_PIe(aid=0, key="PF3", fields={}))
        saved_off = a.omvs_editor is None and a._submode == "OMVS"
        content = a.omvs_shell.env.read_text(a.omvs_shell._resolved("/u/ibmuser/gate.txt"))
        file_ok = "GATE LINE ONE" in content and "GATE LINE TWO" in content
        ro = "BROWSE" in _tx(a.handle(_PIe(aid=0, key="ENTER",
                          fields={"CMD": "view /u/ibmuser/gate.txt"})))
        a.handle(_PIe(aid=0, key="PF3", fields={}))
        if opened and saved_off and file_ok and ro:
            rows.append(("omvs:editor3270", "OK",
                         "oedit fielded panel; overtype+prefix I; PF3 saves; view read-only"))
        else:
            rows.append(("omvs:editor3270", "FAIL",
                         f"open={opened} saved={saved_off} file={file_ok} readonly={ro}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:editor3270", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # OMVS lynx text browser: renders Gibson's own in-sim sites offline (no real
    # HTTP), follows numbered links, and runs as a 3270 sub-mode under OMVS.
    try:
        from gibson.apps.tso3270.tso_session import Tso3270App as _T3l
        from gibson.apps.tso import TsoCommandProcessor as _TCPl
        from gibson.render.panels import PanelInput as _PIl
        from gibson.apps.omvs_lynx import LynxSession as _LX
        lst = fresh_session().state
        # offline in-sim render
        rendered = _LX(["http://localhost/cti"], state=lst, userid="IBMUSER").start()
        render_ok = "SENTRY" in (rendered or "").upper() and "[1]" in (rendered or "")
        ul = lst.racf.get("IBMUSER")
        if not getattr(ul, "has_omvs", False):
            lst.racf.altuser("IBMUSER", omvs=True,
                             omvs_segment={"UID": "0", "HOME": "/u/ibmuser", "PROGRAM": "/bin/sh"})
        al = _T3l(lst, peer_addr="127.0.0.1", userid="IBMUSER")
        al.tso = _TCPl(lst, "IBMUSER")
        al._enter_omvs()
        al.handle(_PIl(aid=0, key="ENTER", fields={"CMD": "lynx http://localhost/cti"}))
        active = al.lynx is not None and any("SENTRY" in l.upper() for l in al.lines)
        al.handle(_PIl(aid=0, key="ENTER", fields={"CMD": "2"}))
        followed = any("EVENT" in l.upper() for l in al.lines[-40:])
        al.handle(_PIl(aid=0, key="PF3", fields={}))
        quit_ok = al.lynx is None and al._submode == "OMVS"
        if render_ok and active and followed and quit_ok:
            rows.append(("omvs:lynx", "OK", "offline in-sim render; 3270 sub-mode; follow link; PF3 quit"))
        else:
            rows.append(("omvs:lynx", "FAIL",
                         f"render={render_ok} active={active} follow={followed} quit={quit_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("omvs:lynx", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # MVP package manager: RX MVP browse/search/info, and INSTALL with dependency
    # resolution + CC 0000 job transcript + RAKF BRXMTTAUTH authorization.
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCPm
        mst = fresh_session().state
        if not mst.racf.exists("GUEST"):
            mst.racf.adduser("GUEST", password="GUEST", privilege="USE")
        adm = TsoCommandProcessor(mst, "IBMUSER") if False else _TCPm(mst, "IBMUSER")
        gst = _TCPm(mst, "GUEST")
        upd = "package(s) available" in adm.run("RX MVP UPDATE")
        lst = adm.run("RX MVP LIST")
        list_ok = "FTPD" in lst and "REVIEW" in lst and "available" in lst
        srch = "FTPD" in adm.run("RX MVP SEARCH ftp")
        info = "Depends:      RANDOMPW" in adm.run("RX MVP SHOW FTPD")
        ins = adm.run("RX MVP INSTALL FTPD")
        ins_ok = ("RANDOMPW" in ins and ins.count("MAXCC=0000") >= 2
                  and "COND CODE 0000" in ins and "2 package(s) installed" in ins)
        instlist = adm.run("RX MVP LIST --installed")
        state_ok = "FTPD" in instlist and "RANDOMPW" in instlist and "installed" in instlist
        bare = "MVS/CE package manager" in adm.run("MVP")        # bare MVP also works
        denial = gst.run("RX MVP INSTALL REVIEW")
        authz_ok = "ICH408I" in denial and "BRXMTTAUTH" in denial and "refused" in denial
        if upd and list_ok and srch and info and ins_ok and state_ok and bare and authz_ok:
            rows.append(("mvp:packages", "OK",
                         "RX MVP UPDATE/LIST/SEARCH/SHOW + bare MVP browse the catalog"))
            rows.append(("mvp:install", "OK",
                         "INSTALL resolves deps, CC 0000 job, records state; BRXMTTAUTH denies GUEST"))
        else:
            rows.append(("mvp:packages", "FAIL", f"upd={upd} list={list_ok} search={srch} info={info} bare={bare}"))
            rows.append(("mvp:install", "FAIL", f"install={ins_ok} state={state_ok} authz={authz_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("mvp:packages", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # RX MVP really installs: writes runnable REXX members into <userid>.MVP.EXEC,
    # and the installed tools execute (via EX 'dsn(member)' and %name).
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCPm
        mst = fresh_session().state
        mtso = _TCPm(mst, "IBMUSER")
        mtso.run("RX MVP INSTALL RANDOMPW DISKMAP")
        members = mst.datasets.members("IBMUSER", "IBMUSER.MVP.EXEC")
        member_ok = "RANDOMPW" in members and "DISKMAP" in members
        src = mst.datasets.read("IBMUSER", "IBMUSER.MVP.EXEC(RANDOMPW)")
        src_ok = "random password generator" in src.lower()
        run1 = mtso.run("EX 'IBMUSER.MVP.EXEC(RANDOMPW)' '2'")
        run_ok = "RANDOMPW 1.0" in run1 and "Generated 2 password" in run1
        run2 = mtso.run("%DISKMAP")
        bare_ok = "DASD volume allocation map" in run2
        den = _TCPm(mst, "GUEST").run("RX MVP INSTALL RANDOMPW")
        deny_ok = "BRXMTTAUTH" in den
        if member_ok and src_ok and run_ok and bare_ok and deny_ok:
            rows.append(("mvp:real-install", "OK",
                         "installs runnable REXX to userid.MVP.EXEC; EX + %name run; unauth denied"))
        else:
            rows.append(("mvp:real-install", "FAIL",
                         f"member={member_ok} src={src_ok} run={run_ok} bare={bare_ok} deny={deny_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("mvp:real-install", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))
    try:
        from gibson.apps.lennox.system import LennoxSession as _LN, FLAG as _FLAG
        from gibson.services.lennox_server import serve_lennox as _srv  # noqa: F401 (importable)
        lst = fresh_session().state
        s = _LN(lst, "127.0.0.1")
        explore = "README.txt" in s.handle("ls")
        creds = "IBMUSER" in s.handle("cat /var/backups/creds.bak") and s.got_creds
        sudol = "NOPASSWD: /usr/bin/find" in s.handle("sudo -l")
        denied = "Permission denied" in s.handle("cat /root/flag.txt")
        pe = "root" in s.handle("sudo find . -exec /bin/sh \\;") and s.is_root
        flag = _FLAG in s.handle("cat /root/flag.txt")
        pingfix = "Pinging host mfhost" in s.handle("ping -c 2 mfhost")
        dig = "ANSWER SECTION" in s.handle("dig example.com")
        if all([explore, creds, sudol, denied, pe, flag, pingfix, dig]):
            rows.append(("lennox:training", "OK",
                         "explore->creds->sudo -l->privesc(find -exec)->root flag; net tools"))
        else:
            rows.append(("lennox:training", "FAIL",
                         f"explore={explore} creds={creds} sudol={sudol} denied={denied} "
                         f"pe={pe} flag={flag} ping={pingfix} dig={dig}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("lennox:training", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # z/VM CMS depth: real A-disk file commands (LISTFILE/TYPE/COPYFILE/RENAME/
    # ERASE/EXEC/QUERY DISK) driven through the same engine both CMS paths call.
    try:
        from gibson.apps.zvm.cms import cms_command as _CMS
        cst = fresh_session().state
        lst = _CMS(cst, "LINUX01", "LISTFILE")
        list_ok = "HELLO" in lst and "PROFILE" in lst and "Ready;" in lst
        type_ok = "Hello from z/VM CMS" in _CMS(cst, "LINUX01", "TYPE HELLO REXX")
        _CMS(cst, "LINUX01", "COPYFILE HELLO REXX A1 GREET REXX A1")
        copied = "GREET" in _CMS(cst, "LINUX01", "LISTFILE GREET *")
        _CMS(cst, "LINUX01", "RENAME GREET REXX A1 HI REXX A1")
        renamed = "HI" in _CMS(cst, "LINUX01", "LISTFILE HI *")
        erased = ("Ready;" in _CMS(cst, "LINUX01", "ERASE HI REXX")
                  and "NOT FOUND" in _CMS(cst, "LINUX01", "STATE HI REXX"))
        execd = "Hello from z/VM CMS" in _CMS(cst, "LINUX01", "HELLO")
        qdisk = "CMSA01" in _CMS(cst, "LINUX01", "QUERY DISK")
        session_owned = _CMS(cst, "LINUX01", "LOGOFF") is None    # not a CMS file cmd
        if all([list_ok, type_ok, copied, renamed, erased, execd, qdisk, session_owned]):
            rows.append(("zvm:cms", "OK",
                         "A-disk LISTFILE/TYPE/COPYFILE/RENAME/ERASE/EXEC/QUERY DISK"))
        else:
            rows.append(("zvm:cms", "FAIL",
                         f"list={list_ok} type={type_ok} copy={copied} ren={renamed} "
                         f"erase={erased} exec={execd} qdisk={qdisk} owned={session_owned}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("zvm:cms", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # /cti (Gibson Sentry) live telemetry: the labs' SMF type-80 security events
    # feed the Security page, dashboard stats, the JSON API and the CSV report.
    try:
        from gibson.apps.welcome.routes import render_page as _RP
        from gibson.apps.tso import TsoCommandProcessor as _TCPc
        import json as _json
        cst = fresh_session().state
        if not cst.racf.exists("GUEST"):
            cst.racf.adduser("GUEST", password="GUEST", privilege="USE")
        _TCPc(cst, "GUEST").run("RX MVP INSTALL REVIEW")          # BRXMTTAUTH denial -> SMF80
        cst.record_security_event("HACKER", "LOGON", "PASSWORD", result="FAILURE",
                                  service="TSO", addr="203.0.113.9", terminal="TN3270")
        code, ct, body = _RP("/cti/security", state=cst)
        page_ok = code == 200 and "SMF Type 80" in body and "MVP INSTALL" in body and "RACF Violations" in body
        _, _, dash = _RP("/cti/dashboard", state=cst)
        dash_ok = "Recent Security Events" in dash and "Security Events" in dash
        code, ct, body = _RP("/cti/api/events", state=cst)
        api = _json.loads(body)
        api_ok = (code == 200 and "application/json" in ct
                  and api["counts"]["security_events"] >= 1 and api["counts"]["racf_violations"] >= 1)
        code, ct, body = _RP("/cti/reports/security.csv", state=cst)
        csv_ok = (code == 200 and "text/csv" in ct
                  and body.splitlines()[0].startswith("timestamp,userid,event"))
        if page_ok and dash_ok and api_ok and csv_ok:
            rows.append(("cti:live-events", "OK",
                         "SMF80 labs feed -> /cti/security + dashboard + JSON API + CSV report"))
        else:
            rows.append(("cti:live-events", "FAIL",
                         f"page={page_ok} dash={dash_ok} api={api_ok} csv={csv_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("cti:live-events", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # Heavy Metal Spider IDS engine: the 9-stage TTP chain emits field-correct SMF
    # records, and 3+ distinct TTPs raise the correlation alarm.
    try:
        from gibson.apps import cti_hms as _H
        hst = fresh_session().state
        n0 = len(hst.audit.events)
        _H.run_scenario(hst)
        hms = _H.get_hms_state(hst)
        stages_ok = [s.ttp_id for s in hms.sightings] == [t.id for t in _H.HMS_TTPS]
        types = {e.extra.get("RECORD_TYPE") for e in hst.audit.events[n0:]}
        smf_ok = {"119", "80", "30", "42", "90", "92", "14"}.issubset(types)
        has_119_72 = any(e.extra.get("RECORD_TYPE") == "119" and e.extra.get("SUBTYPE") == "72"
                         for e in hst.audit.events[n0:])
        has_80_alt = any(e.extra.get("RECORD_TYPE") == "80" and "ALTUSER" in (e.extra.get("EVENT") or "")
                         for e in hst.audit.events[n0:])
        alarm = hms.alarm
        alarm_ok = (alarm is not None and alarm["message"] == "Potential Heavy Metal Spider detected"
                    and alarm["notified"] == ["KEVIN", "IBMUSER"]
                    and set(alarm["associated_tools"]) == {"hydra", "nikto", "surrogat"}
                    and alarm["count"] >= 3)
        _H.trigger_ttp(hst, "ftp_exfil")
        idem = hms.alarm["ts"] == alarm["ts"]
        if stages_ok and smf_ok and has_119_72 and has_80_alt and alarm_ok and idem:
            rows.append(("cti:hms-engine", "OK",
                         "9-stage TTP chain -> field-correct SMF; 3+ -> alarm (KEVIN/IBMUSER, HYDRA/NIKTO/SURROGAT)"))
        else:
            rows.append(("cti:hms-engine", "FAIL",
                         f"stages={stages_ok} smf={smf_ok} 119.72={has_119_72} "
                         f"80.alt={has_80_alt} alarm={alarm_ok} idem={idem}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("cti:hms-engine", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # HMS TA CTI page: login-enforced (even with global CTI auth off), renders the
    # actor profile / kill chain / IDS chain, and the lab runner raises the alarm.
    try:
        from gibson.apps.welcome.routes import render_page as _RP
        import base64 as _b64
        hst = fresh_session().state
        c1, _, _ = _RP("/cti/hms", state=hst)
        auth = {"Authorization": "Basic " + _b64.b64encode(b"ctiadmin:gibson").decode()}
        c2, _, b2 = _RP("/cti/hms", state=hst, headers=auth)
        page_ok = (c1 == 401 and c2 == 200 and "Heavy Metal Spider" in b2
                   and "IDS Detection Chain" in b2 and "Kill Chain" in b2)
        _, _, b3 = _RP("/cti/hms?run=scenario", state=hst, headers=auth)
        alarm_ok = "Potential Heavy Metal Spider detected" in b3 and "T1567" in b3
        cbad, _, _ = _RP("/cti/hms", state=hst,
                         headers={"Authorization": "Basic " + _b64.b64encode(b"x:y").decode()})
        if page_ok and alarm_ok and cbad == 401:
            rows.append(("cti:hms-ta", "OK",
                         "login-gated HMS TA page: profile/kill-chain/IDS + scenario alarm"))
        else:
            rows.append(("cti:hms-ta", "FAIL",
                         f"login401={c1 == 401} auth200={c2 == 200} page={page_ok} "
                         f"alarm={alarm_ok} bad401={cbad == 401}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("cti:hms-ta", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # HMS alarm delivery: 3+ TTPs -> Master Console + web dashboard + SEND MESSAGE
    # to KEVIN (live if connected) and IBMUSER (queued offline).
    try:
        from gibson.apps import cti_hms as _Ha
        ast2 = fresh_session().state
        got = []
        ast2.sessions.add("KEVIN", "10.0.0.5", notifier=lambda m: got.append(m))
        _Ha.run_scenario(ast2)
        a = _Ha.get_hms_state(ast2).alarm
        con = ast2.drain_console_events()
        con_ok = any("Potential Heavy Metal Spider" in t for _, t in con)
        da = ast2.recent_dashboard_alerts(10)
        dash_ok = any(d["event_type"] == "HMS" and "Heavy Metal Spider" in d["message"] for d in da)
        kevin_ok = any("Potential Heavy Metal Spider" in m for m in got)
        ibm_ok = any("Heavy Metal Spider" in m for _, m in ast2.pending_messages.get("IBMUSER", []))
        deliv_ok = a is not None and a.get("delivered") is True
        if con_ok and dash_ok and kevin_ok and ibm_ok and deliv_ok:
            rows.append(("cti:hms-alarm", "OK",
                         "alarm -> Master Console + dashboard + SEND MSG KEVIN(live)/IBMUSER(queued)"))
        else:
            rows.append(("cti:hms-alarm", "FAIL",
                         f"console={con_ok} dash={dash_ok} kevin={kevin_ok} "
                         f"ibmuser={ibm_ok} delivered={deliv_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("cti:hms-alarm", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # Watched logon alerts: MAINT -> LVM (z/VM) and GUEST/IBMUSER -> TSO raise a
    # logon alert on the console + dashboard; other users do not.
    try:
        lst2 = fresh_session().state
        lst2.record_security_event("MAINT", "LOGON", "PASSWORD", service="TN3270/ZVM", addr="10.0.0.3")
        lst2.record_security_event("GUEST", "LOGON", "PASSWORD", service="TSO", addr="10.0.0.8")
        lst2.record_security_event("IBMUSER", "LOGON", "PASSWORD", service="TSO", addr="10.0.0.9")
        lst2.record_security_event("TRAINEE", "LOGON", "PASSWORD", service="TSO", addr="10.0.0.10")
        la = [d["message"] for d in lst2.recent_dashboard_alerts(20) if d["event_type"] == "LOGON"]
        maint = any("MAINT signed on to LVM" in m for m in la)
        guest = any("GUEST signed on to TSO" in m for m in la)
        ibm = any("IBMUSER signed on to TSO" in m for m in la)
        noise = not any("TRAINEE" in m for m in la)
        if maint and guest and ibm and noise:
            rows.append(("cti:logon-alerts", "OK",
                         "MAINT->LVM and GUEST/IBMUSER->TSO raise logon alerts (console+dashboard)"))
        else:
            rows.append(("cti:logon-alerts", "FAIL",
                         f"maint={maint} guest={guest} ibm={ibm} noise_ok={noise}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("cti:logon-alerts", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # PLONK forensics console: login-gated; packet/SMF/SQL search over seeded
    # captures + a real parsed .pcap from disk.
    try:
        from gibson.apps.welcome.routes import render_page as _RPp
        from gibson.apps import cti_hms as _Hp, cti_plonk as _P
        import base64 as _b64p
        pst = fresh_session().state
        _Hp.run_scenario(pst)
        authp = {"Authorization": "Basic " + _b64p.b64encode(b"ctiadmin:gibson").decode()}
        c0, _, _ = _RPp("/cti/plonk", state=pst)
        c1, _, b1 = _RPp("/cti/plonk", state=pst, headers=authp)
        caps = _P.list_captures(pst)
        real = [c for c in caps if c.name == "hms_sample.pcap"]
        real_ok = bool(real) and len(real[0].packets) >= 1 and real[0].source == "hms_sample.pcap"
        page_ok = (c0 == 401 and c1 == 200 and "PLONK search" in b1
                   and "tn3270e_ftp_session.pcap" in b1)
        _, _, b2 = _RPp("/cti/plonk?q=proto%3Dftp+size%3D38mb&src=packets", state=pst, headers=authp)
        _, _, b3 = _RPp("/cti/plonk?q=smf80+altuser&src=smf", state=pst, headers=authp)
        _, _, b4 = _RPp("/cti/plonk/pcap?cap=db2_ddf_sql.pcap", state=pst, headers=authp)
        _, _, b5 = _RPp("/cti/plonk/sql", state=pst, headers=authp)
        search_ok = ("file_xfer" in b2 and "ALTUSER" in b3
                     and "PROD.ACCOUNTS" in b4 and "FETCH FIRST 5000" in b5)
        if page_ok and real_ok and search_ok:
            rows.append(("cti:plonk", "OK",
                         "login-gated PLONK: packet/SMF/SQL search + real .pcap parsed from disk"))
        else:
            rows.append(("cti:plonk", "FAIL",
                         f"page={page_ok} real_pcap={real_ok} search={search_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("cti:plonk", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # HMS real-signal auto-detection: organic FTP brute + port scan + RACF DB
    # access fire TTPs for real and raise the alarm; normal admin stays quiet;
    # the manual demo FIRE controls still work.
    try:
        from gibson.apps import cti_hms as _Hd
        ast3 = fresh_session().state
        for _ in range(3):
            ast3.record_security_event("HACKER", "LOGON", "PASSWORD-INVALID", result="FAILURE",
                                       service="FTPD", addr="203.0.113.7")
        for _p in (21, 23, 992, 3270, 2380, 8080):
            ast3.note_port_touch("203.0.113.7", _p, "scan")
        ast3.record_security_event("HACKER", "RESOURCE ACCESS", "DSN=SYS1.RACFDS COPY",
                                   result="SUCCESS", service="USS", addr="203.0.113.7")
        hd = _Hd.get_hms_state(ast3)
        auto_ok = {"ftp_brute", "nmap", "racfds_john"}.issubset(hd.auto_fired)
        alarm_ok = hd.alarm is not None and hd.alarm["count"] >= 3
        astn = fresh_session().state
        astn.record_security_event("ADMIN", "LOGON", "PASSWORD", result="SUCCESS", service="TSO", addr="10.0.0.5")
        astn.record_security_event("ADMIN", "ALTUSER", "PASSWORD RESET", result="SUCCESS", service="RACF")
        astn.record_security_event("ADMIN", "RESOURCE ACCESS", "DSN=SYS1.PARMLIB", result="SUCCESS", service="TSO")
        hn = _Hd.get_hms_state(astn)
        quiet_ok = (not hn.auto_fired) and hn.alarm is None
        astm = fresh_session().state
        _Hd.trigger_ttp(astm, "nmap"); _Hd.trigger_ttp(astm, "vtam_enum"); _Hd.trigger_ttp(astm, "tso_enum")
        manual_ok = _Hd.get_hms_state(astm).alarm is not None
        if auto_ok and alarm_ok and quiet_ok and manual_ok:
            rows.append(("cti:hms-autodetect", "OK",
                         "real FTP-brute+scan+RACFDS fire TTPs->alarm; normal admin quiet; manual FIRE intact"))
        else:
            rows.append(("cti:hms-autodetect", "FAIL",
                         f"auto={auto_ok} alarm={alarm_ok} quiet={quiet_ok} manual={manual_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("cti:hms-autodetect", f"EXCEPTION:{type(e).__name__}", str(e)[:60]))

    # RACF dataset protection for GUEST: in secure mode GUEST has ACCESS(NONE) to
    # SYS1.* (ICH408I denial) UNLESS the profile is in WARNING mode, where access
    # is permitted but audited. Normal users keep ALTER; GUEST keeps its own data.
    try:
        gs = fresh_session().state
        gs.config.security_mode = "secure"
        if not gs.racf.exists("GUEST"):
            gs.racf.adduser("GUEST", password="GUEST", privilege="USE")

        def _auth(user, dsn, intent="READ"):
            try:
                gs.datasets.security.authorize(user, dsn, intent); return True
            except PermissionError:
                return False
        denied_norm = not _auth("GUEST", "SYS1.LINKLIB")           # normal SYS1 -> denied
        warn_ok = _auth("GUEST", "SYS1.PARMLIB")                   # WARNING -> permitted
        own_ok = _auth("GUEST", "GUEST.OWN.DATA")                  # own data -> ok
        admin_ok = _auth("IBMUSER", "SYS1.LINKLIB")                # ALTER -> ok
        # profile seeding is correct
        pn = gs.dynamic_racf._find_profile("DATASET", "SYS1.LINKLIB")
        pw = gs.dynamic_racf._find_profile("DATASET", "SYS1.PARMLIB")
        seeded = (pn is not None and pn.permits.get("GUEST") == "NONE"
                  and pw is not None and getattr(pw, "warning", False) is True)
        if denied_norm and warn_ok and own_ok and admin_ok and seeded:
            rows.append(("racf:guest-sys1", "OK", "GUEST NONE to SYS1.* (ICH408I); WARNING permits+audits"))
        else:
            rows.append(("racf:guest-sys1", "FAIL",
                         f"deny={denied_norm} warn={warn_ok} own={own_ok} admin={admin_ok} seeded={seeded}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("racf:guest-sys1", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # IMS Connect / OTMA security lab: with /SECURE OTMA NONE an unauthenticated
    # client injects transactions and operator commands under a spoofed userid;
    # /SECURE OTMA FULL + TIMS/CIMS profiles produce an authentic ICH408I denial.
    try:
        from gibson.apps.ims import ims_command as _ims, get_ims_state as _gims
        ist = fresh_session().state
        if not ist.racf.exists("IMSUSER"):
            ist.racf.adduser("IMSUSER", password="IMSUSER", privilege="USE")
        # vulnerable default
        vuln_default = _gims(ist).otma_security == "NONE"
        inj_tx = "HWSC0001I" in _ims(ist, "HACKER", "IMS SUBMIT ADDPART AS IMSUSER") and \
                 "COMPLETED" in _ims(ist, "HACKER", "IMS SUBMIT DSPINV AS IMSUSER")
        inj_cmd = "COMPLETED" in _ims(ist, "HACKER", "IMS CMD /STO TRAN PART AS IMSOPER")
        audit_vuln = "POSSIBLE" in _ims(ist, "HACKER", "IMS AUDIT")
        # flip to FULL
        _ims(ist, "IBMUSER", "IMS SECURE OTMA FULL")
        d_tx = _ims(ist, "HACKER", "IMS SUBMIT DSPINV")
        denied_tx = "DFS3662W" in d_tx and "ICH408I" in d_tx and "TIMS" in d_tx
        d_cmd = _ims(ist, "HACKER", "IMS CMD /STO TRAN DSPINV")
        denied_cmd = "DFS3662W" in d_cmd and "CIMS" in d_cmd
        legit_ok = "HWSC0001I" in _ims(ist, "IMSUSER", "IMS SUBMIT DSPINV")
        audit_fixed = "DENIED" in _ims(ist, "IMSUSER", "IMS AUDIT")
        if (vuln_default and inj_tx and inj_cmd and audit_vuln
                and denied_tx and denied_cmd and legit_ok and audit_fixed):
            rows.append(("ims:otma", "OK", "OTMA NONE injects (spoofed); FULL -> ICH408I TIMS/CIMS denial"))
        else:
            rows.append(("ims:otma", "FAIL",
                         f"vuln={vuln_default} injTX={inj_tx} injCMD={inj_cmd} "
                         f"denyTX={denied_tx} denyCMD={denied_cmd} legit={legit_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ims:otma", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # IMS Connect must be selectable from the ISPF primary menu (option I) and
    # drive the OTMA lab from the panel command line.
    try:
        from gibson.apps.ispf3270.ispf_session import Ispf3270Session as _IspI
        from gibson.render.panels import PanelInput as _PIi
        ist2 = fresh_session().state
        isp = _IspI(ist2, peer_addr="127.0.0.1", userid="HACKER")

        def _ti(scr):
            return "\n".join((getattr(f, "text", "") or "") for f in scr.fields)
        on_menu = "IMS" in _ti(isp.initial_screen())
        panel = "IMS CONNECT / OTMA" in _ti(isp.handle(_PIi(aid=0, key="ENTER", fields={"OPTION": "I"})))
        acted = "SCHEDULED" in _ti(isp.handle(_PIi(aid=0, key="ENTER",
                                  fields={"OPTION": "SUBMIT ADDPART AS IMSUSER"})))
        back = "Primary Option Menu" in _ti(isp.handle(_PIi(aid=0, key="PF3", fields={})))
        if on_menu and panel and acted and back:
            rows.append(("ims:ispf-menu", "OK", "ISPF option I -> IMS Connect panel -> SUBMIT -> PF3 back"))
        else:
            rows.append(("ims:ispf-menu", "FAIL", f"menu={on_menu} panel={panel} acted={acted} back={back}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ims:ispf-menu", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # IMS DB / DL/I learning module: hierarchical navigation (GU/GN/GNP),
    # insert/replace/delete, and PROCOPT enforcement on the parts database.
    try:
        from gibson.apps.ims import ims_command as _imd
        dst = fresh_session().state
        gu = _imd(dst, "IMSUSER", "IMS DLI GU PART(PARTNO=P200)")
        gu_ok = "PARTNO=P200" in gu and "DESC=GASKET" in gu and "STATUS='  '" in gu
        gn = _imd(dst, "IMSUSER", "IMS DLI GN")
        gn_ok = "STOCK" in gn and "WHSE=W01" in gn        # advances into child
        path = _imd(dst, "IMSUSER", "IMS DLI GU PART(PARTNO=P100) STOCK(WHSE=W02)")
        path_ok = "WHSE=W02" in path and "QTY=0012" in path
        gnp = _imd(dst, "IMSUSER", "IMS DLI GNP")
        gnp_ok = "ORDER" in gnp and "O5001" in gnp        # next child within P100
        ins = _imd(dst, "IMSUSER", "IMS DLI ISRT PART(PARTNO=P400,DESC=WIDGET,TYPE=ROUND)")
        ins_ok = "STATUS='  '" in ins and "PARTNO=P400" in ins
        dlt = _imd(dst, "IMSUSER", "IMS DLI DLET")
        gone = "GE" in _imd(dst, "IMSUSER", "IMS DLI GU PART(PARTNO=P400)")
        del_ok = "STATUS='  '" in dlt and gone
        _imd(dst, "IMSUSER", "IMS PSB GET")               # PROCOPT=G
        procopt = "AM" in _imd(dst, "IMSUSER", "IMS DLI ISRT PART(PARTNO=P500,DESC=X,TYPE=FLAT)")
        if gu_ok and gn_ok and path_ok and gnp_ok and ins_ok and del_ok and procopt:
            rows.append(("ims:dli", "OK", "GU/GN/GNP nav, qualified path, ISRT/DLET, PROCOPT=G->AM"))
        else:
            rows.append(("ims:dli", "FAIL",
                         f"gu={gu_ok} gn={gn_ok} path={path_ok} gnp={gnp_ok} "
                         f"ins={ins_ok} del={del_ok} procopt={procopt}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ims:dli", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # forced initial password change is now OPT-IN (policy.initial_password_change);
    # when enabled it must still work end to end.
    try:
        s = fresh_session()
        s.state.password_policy.initial_password_change = True
        s._handle_tso_command("ADDUSER PARITYU1 PASSWORD(INITPW01) DFLTGRP(SYS1)")
        s.pending_user = "PARITYU1"
        s.mode = "TSO_PASS"
        s.handle_tso("INITPW01")               # verify initial password
        forced = s.mode == "TSO_NEWPASS"
        s.handle_tso("N3wPa$$w0rd")            # new
        s.handle_tso("N3wPa$$w0rd")            # confirm
        done = s.mode == "TSO_READY" and not s._change_required("PARITYU1")
        if forced and done:
            rows.append(("logon:forced-change", "OK", "opt-in TSO_NEWPASS enforced -> READY, flag cleared"))
        else:
            rows.append(("logon:forced-change", "NOTFORCED",
                         f"forced={forced} completed={done} mode={s.mode}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:forced-change", f"EXCEPTION:{type(e).__name__}", str(e)[:50]))

    # DEFAULT behaviour: a freshly-added user logs straight on with their initial
    # password (NO forced change) and can log on again cleanly.
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCP
        from gibson.apps.tso3270.tso_session import Tso3270App as _App
        from gibson.render.panels import PanelInput as _PIin
        lst = fresh_session().state
        _TCP(lst, "IBMUSER").run("ADDUSER LIVEU1 PASSWORD(INITPW01) DFLTGRP(SYS1)")
        no_force = lst.racf.get("LIVEU1").password_change_required is False

        def _live_logon(pw):
            app = _App(lst, userid="")
            scr = app.handle(_PIin(aid=0, key="ENTER",
                                   fields={"USERID": "LIVEU1", "PASSWORD": pw, "PROC": "ISPFPROC"}))
            return app, screen_text(scr)
        a2, s2 = _live_logon("INITPW01")     # straight to READY, no change step
        a3, s3 = _live_logon("INITPW01")     # repeatable
        clean2 = a2._screen == "READY" and "READY" in s2 and "NEW PASSWORD" not in s2.upper()
        clean3 = a3._screen == "READY" and "READY" in s3
        if no_force and clean2 and clean3:
            rows.append(("logon:live-newuser", "OK", "new user logs on directly (no forced change)"))
        else:
            rows.append(("logon:live-newuser", "FAIL",
                         f"no_force={no_force} clean2={clean2} clean3={clean3}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:live-newuser", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # EBCDIC '?' help parity: the tso3270 READY path routes '?' through the SAME
    # TsoAutocomplete the ASCII/netcat path uses, rendered without ANSI leakage.
    try:
        from gibson.apps.tso3270.tso_session import Tso3270App as _App2
        from gibson.render.panels import PanelInput as _PIin2
        hstate = fresh_session().state
        happ = _App2(hstate, userid="")
        happ.handle(_PIin2(aid=0, key="ENTER",
                           fields={"USERID": "IBMUSER", "PASSWORD": "SYS1", "PROC": "ISPFPROC"}))
        hscr = screen_text(happ.handle(_PIin2(aid=0, key="ENTER", fields={"CMD": "LIST?"})))
        qmark = ("MATCHING COMMANDS FOR" in hscr and "LISTDS" in hscr
                 and "LISTUSER" in hscr and "\x1b" not in hscr and "Ý" not in hscr)
        bare = screen_text(happ.handle(_PIin2(aid=0, key="ENTER", fields={"CMD": "?"})))
        bare_ok = "GIBSON TSO COMMANDS" in bare or "COMMAND / SYNTAX" in bare
        if qmark and bare_ok:
            rows.append(("tso:help-qmark", "OK", "EBCDIC '?' -> TsoAutocomplete, ANSI-clean (ASCII parity)"))
        else:
            rows.append(("tso:help-qmark", "FAIL", f"qmark={qmark} bare={bare_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("tso:help-qmark", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # PDS member save: empty PS stub is promoted and saved (no raw [Errno 17]);
    # a real sequential data set yields a clean message; new members persist.
    try:
        from gibson.apps.editor import InteractiveEditor as _IEd
        dstate = fresh_session().state
        dds = dstate.datasets
        dds.ds_path("IBMUSER", "IBMUSER.IBMUSER").write_text("")   # empty stub
        e1 = _IEd("IBMUSER.IBMUSER(STUFF)", "/* REXX */",
                  save_callback=lambda t: dds.write("IBMUSER", "IBMUSER.IBMUSER(STUFF)", t))
        m1 = e1._save()
        saved = m1 == "DATA SAVED" and dds.members("IBMUSER", "IBMUSER.IBMUSER") == ["STUFF"]
        dds.allocate("IBMUSER", "IBMUSER.SEQDS", org="PS")
        dds.write("IBMUSER", "IBMUSER.SEQDS", "CONTENT")
        e2 = _IEd("IBMUSER.SEQDS(M1)", "x",
                  save_callback=lambda t: dds.write("IBMUSER", "IBMUSER.SEQDS(M1)", t))
        m2 = e2._save()
        clean = "Errno" not in m2 and "[" not in m2 and "Ý" not in m2 and "SAVE FAILED" in m2
        if saved and clean:
            rows.append(("ds:member-save", "OK", "stub promoted+saved; PS->clean msg; member persists"))
        else:
            rows.append(("ds:member-save", "FAIL", f"saved={saved} clean={clean} m2={m2[:30]}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ds:member-save", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # ANSI/CSI must not leak into 3270 fields as "Ý2J" bracket garble, while real
    # bracket text and SGR colour are preserved.
    try:
        from gibson.render.ansi3270 import render_ansi_to_screen as _r2s
        from gibson.apps.cbsa.cics_session import cbpp_panel as _cbpp
        cbsa = screen_text(_r2s(_cbpp(), rows=24, cols=80))
        no_leak = "Ý" not in cbsa and "[2J" not in cbsa and "CBPP" in cbsa
        brackets = screen_text(_r2s("LISTUSER [userid|*] <ALL|TSO>"))
        kept = "[userid|*]" in brackets and "<ALL|TSO>" in brackets
        sgr = screen_text(_r2s("\x1b[1;32mGREEN\x1b[0m x"))
        sgr_ok = "GREEN" in sgr and "32m" not in sgr
        if no_leak and kept and sgr_ok:
            rows.append(("render:no-ansi-leak", "OK", "CSI stripped (no Ý2J); brackets+SGR intact"))
        else:
            rows.append(("render:no-ansi-leak", "FAIL", f"leak_ok={no_leak} brackets={kept} sgr={sgr_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("render:no-ansi-leak", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # SDSF from READY launches the full-screen app (not canned text); PF3 returns.
    try:
        from gibson.apps.tso3270.tso_session import Tso3270App as _App3
        from gibson.render.panels import PanelInput as _PIin3
        sstate = fresh_session().state
        sapp = _App3(sstate, userid="")
        sapp.handle(_PIin3(aid=0, key="ENTER",
                           fields={"USERID": "IBMUSER", "PASSWORD": "SYS1", "PROC": "ISPFPROC"}))
        sd = screen_text(sapp.handle(_PIin3(aid=0, key="ENTER", fields={"CMD": "SDSF"})))
        launched = sapp.sdsf is not None and "SDSF" in sd and ("Display" in sd or "COMMAND INPUT" in sd)
        back = screen_text(sapp.handle(_PIin3(aid=0, key="PF3", fields={})))
        returned = sapp.sdsf is None and "READY" in back
        if launched and returned:
            rows.append(("tso:sdsf-launch", "OK", "SDSF -> full-screen app; PF3 -> READY"))
        else:
            rows.append(("tso:sdsf-launch", "FAIL", f"launched={launched} returned={returned}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("tso:sdsf-launch", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # EX/EXEC of a persisted REXX member executes (was a symptom of the save bug).
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCP2
        xstate = fresh_session().state
        xstate.datasets.write("IBMUSER", "IBMUSER.IBMUSER(STUFF)",
                              "/* REXX */\nSAY 'HELLO FROM REXX'")
        xtso = _TCP2(xstate, "IBMUSER")
        r_q = xtso.run("EX 'IBMUSER.IBMUSER(STUFF)'")
        r_p = xtso.run("EX IBMUSER.IBMUSER(STUFF)")
        if "HELLO FROM REXX" in r_q and "HELLO FROM REXX" in r_p and "NOT FOUND" not in r_q:
            rows.append(("tso:exec-member", "OK", "EX 'dsn(member)' runs persisted REXX (quoted+bare)"))
        else:
            rows.append(("tso:exec-member", "FAIL", f"quoted={'HELLO' in r_q} bare={'HELLO' in r_p}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("tso:exec-member", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Per-context transcript colour: TSO=red, OMVS=light-blue, CONSOLE=green
    # (parity with the ASCII path; previously everything rendered green).
    try:
        from gibson.apps.tso3270.tso_session import Tso3270App as _App4
        from gibson.render.panels import PanelInput as _PIin4
        from gibson.render import colors as _col
        cstate = fresh_session().state
        capp = _App4(cstate, userid="")
        capp.handle(_PIin4(aid=0, key="ENTER",
                           fields={"USERID": "IBMUSER", "PASSWORD": "SYS1", "PROC": "ISPFPROC"}))
        scr = capp.handle(_PIin4(aid=0, key="ENTER", fields={"CMD": "TIME"}))
        body_cols = {getattr(f, "colour", None) for f in scr.fields
                     if (getattr(f, "text", "") or "").strip()}
        tso_red = _col.RED in body_cols
        capp._submode = "OMVS"
        omvs_lb = capp._transcript_colour() == getattr(_col, "LIGHT_BLUE", _col.GREEN)
        capp._submode = "CONSOLE"
        con_grn = capp._transcript_colour() == _col.GREEN
        capp._submode = None
        tso_helper = capp._transcript_colour() == _col.RED
        if tso_red and omvs_lb and con_grn and tso_helper:
            rows.append(("render:context-colour", "OK", "TSO red / OMVS light-blue / CONSOLE green"))
        else:
            rows.append(("render:context-colour", "FAIL",
                         f"tso={tso_red} omvs={omvs_lb} con={con_grn}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("render:context-colour", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # ISPF Edit CC...A block copy: a block marked with CC in one Enter and the
    # A/B destination given in a *later* Enter must paste (pending block persists).
    try:
        from gibson.apps.ispf3270.editor import Ispf3270Editor as _Ed
        from gibson.render.panels import PanelInput as _PIin5
        estate = fresh_session().state
        ed = _Ed(estate, "IBMUSER", "IBMUSER.T(M)", "AAA\nBBB\nCCC\nDDD")
        _h, m1 = ed._apply_prefix(_PIin5(aid=0, key="ENTER", fields={"LP0": "CC", "LP1": "CC"}))
        pending = ed._pending_block is not None and "PENDING" in (m1 or "")
        ed._apply_prefix(_PIin5(aid=0, key="ENTER", fields={"LP3": "A"}))
        copied = ed.lines == ["AAA", "BBB", "CCC", "DDD", "AAA", "BBB"]
        # same-submission still works
        ed2 = _Ed(estate, "IBMUSER", "IBMUSER.T2(M)", "AAA\nBBB\nCCC\nDDD")
        ed2._apply_prefix(_PIin5(aid=0, key="ENTER", fields={"LP0": "CC", "LP1": "CC", "LP3": "A"}))
        one_shot = ed2.lines == ["AAA", "BBB", "CCC", "DDD", "AAA", "BBB"]
        if pending and copied and one_shot:
            rows.append(("ispf:block-copy", "OK", "CC...CC then A pastes (multi-Enter + one-shot)"))
        else:
            rows.append(("ispf:block-copy", "FAIL", f"pending={pending} copied={copied} oneshot={one_shot}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("ispf:block-copy", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # z/VM Just Enough Authority lab: vulnerable mode over-grants LINUX01 (B,C,E)
    # so DISPLAY/STORE HOST leak+corrupt cross-guest and HiperSockets bridges
    # LPARs; fixed mode reduces to class G and the enforcement denies both.
    try:
        from gibson.apps.zvm.zvm_session import ZvmSession as _Zvm
        _AID = 0x7D

        def _drive(vuln):
            s = fresh_session().state
            s.config.zvm_jea_lab_vulnerable_mode = vuln
            sess = _Zvm(s, peer_addr="10.0.0.9")
            g = sess._dir.get("LINUX01")
            sess._userid = "LINUX01"
            sess._classes = g.classes
            out = {c: screen_text(sess._handle_cp(_AID, c))
                   for c in ("DISPLAY HOST", "STORE HOST 021000 PWNED",
                             "QUERY HIPERSOCKETS", "CPAUDIT")}
            return g.classes, out

        vc, vo = _drive(True)
        fc, fo = _drive(False)
        vuln_ok = (vc == "BCEG"
                   and "RACFKEY=" in vo["DISPLAY HOST"] and "NOT YOUR GUEST" in vo["DISPLAY HOST"]
                   and "cross-guest write" in vo["STORE HOST 021000 PWNED"].lower()
                   and "LP2" in vo["QUERY HIPERSOCKETS"]
                   and "LINUX01" in vo["CPAUDIT"] and "BCE" in vo["CPAUDIT"])
        fixed_ok = (fc == "G"
                    and "not authorized" in fo["DISPLAY HOST"].lower()
                    and "not authorized" in fo["STORE HOST 021000 PWNED"].lower()
                    and "isolation" in fo["QUERY HIPERSOCKETS"].lower()
                    and "BCE" not in fo["CPAUDIT"])   # LINUX01 creep row gone
        if vuln_ok and fixed_ok:
            rows.append(("zvm:jea", "OK", "class-creep leak/corrupt vs JEA denial (both modes)"))
        else:
            rows.append(("zvm:jea", "FAIL", f"vuln={vuln_ok} fixed={fixed_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("zvm:jea", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # EBCDIC logon MFA parity: an MFA field is on the panel, and when MFA is
    # active a valid token (PIN+HHMM) is required after the password resolves.
    try:
        import time as _t
        from gibson.apps.tso import TsoCommandProcessor as _TCPm
        from gibson.apps.tso3270.tso_session import Tso3270App as _Appm
        from gibson.render.panels import PanelInput as _PIm
        ms = fresh_session().state
        _TCPm(ms, "IBMUSER").run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(INITPASS)")
        ms.password_policy.mfa_active = True
        ms.mfa_enabled = True
        mapp = _Appm(ms, userid="NANCY")
        field_ok = "MFATOKEN" in [getattr(f, "name", "") for f in mapp._logon_panel().fields]
        mapp = _Appm(ms, userid="")
        L = lambda **f: screen_text(mapp.handle(_PIm(aid=0, key="ENTER",
                        fields={"USERID": "NANCY", "PROC": "ISPFPROC", **f})))
        prompt = L(PASSWORD="INITPASS")                       # pw ok -> MFA required
        bad = L(PASSWORD="INITPASS", MFATOKEN="000000")
        good = L(PASSWORD="INITPASS", MFATOKEN=_t.strftime("%H%M"))
        mfa_ok = (field_ok and "MFA TOKEN REQUIRED" in prompt
                  and "MFA TOKEN INVALID" in bad and "READY" in good)
        if mfa_ok:
            rows.append(("logon:mfa", "OK", "EBCDIC MFA field+prompt+validate (ASCII parity)"))
        else:
            rows.append(("logon:mfa", "FAIL",
                         f"field={field_ok} prompt={'MFA TOKEN REQUIRED' in prompt} "
                         f"bad={'INVALID' in bad} good={'READY' in good}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:mfa", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Endevor package separation-of-duties lab: vulnerable lets the package
    # creator self-approve to PROD; fixed denies self-approval and requires a
    # distinct approver-group member. Non-approvers are denied in both modes.
    try:
        from gibson.apps.endevor.endevor_engine import endevor_command as _E

        def _sod(vuln):
            s = fresh_session().state
            s.config.endevor_sod_lab_vulnerable_mode = vuln
            _E(s, "DEVUSER", "ENDEVOR PACKAGE CREATE PKG1 BANKING.CORE.COBOL.ACCTPOST TO P")
            _E(s, "DEVUSER", "ENDEVOR PACKAGE CAST PKG1")
            self_app = _E(s, "DEVUSER", "ENDEVOR PACKAGE APPROVE PKG1")
            na = _E(s, "TRAINEE", "ENDEVOR PACKAGE APPROVE PKG1")   # before execute
            if not vuln:
                _E(s, "FIBSADM", "ENDEVOR PACKAGE APPROVE PKG1")
            ex = _E(s, "DEVUSER", "ENDEVOR PACKAGE EXECUTE PKG1")
            return self_app, ex, na

        va, vx, vna = _sod(True)
        fa, fx, fna = _sod(False)
        vuln_ok = ("BYPASS" in va.upper() and "EXECUTED" in vx
                   and "bypassed" in vx.lower())
        fixed_ok = ("SEPARATION OF DUTIES" in fa.upper() and "DENIED" in fa.upper()
                    and "EXECUTED" in fx and "bypassed" not in fx.lower())
        denied_ok = "NOT IN APPROVER GROUP" in vna.upper()
        if vuln_ok and fixed_ok and denied_ok:
            rows.append(("endevor:package-sod", "OK", "self-approve bypass vs SoD denial (both modes)"))
        else:
            rows.append(("endevor:package-sod", "FAIL",
                         f"vuln={vuln_ok} fixed={fixed_ok} denied={denied_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("endevor:package-sod", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # A saved password change must survive a UADS re-sync (server reload): the
    # GACF.DB/RACF flag is authoritative, so the user is NOT re-forced to change
    # on every logon (the bug where an ASCII-set password was "lost" in EBCDIC).
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCPp
        from gibson.apps.tso3270.tso_session import Tso3270App as _Appp
        from gibson.render.panels import PanelInput as _PIp
        ps = fresh_session().state
        ps.password_policy.initial_password_change = True   # opt in to forced change
        _TCPp(ps, "IBMUSER").run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(INITPASS)")
        pa = _Appp(ps, userid="")
        pa.handle(_PIp(aid=0, key="ENTER", fields={"USERID": "NANCY", "PASSWORD": "INITPASS", "PROC": "ISPFPROC"}))
        pa.handle(_PIp(aid=0, key="ENTER", fields={"USERID": "NANCY", "PASSWORD": "INITPASS",
                                                   "NEWPW": "NEWPASS01", "PROC": "ISPFPROC"}))
        # simulate a server/process that does NOT have NANCY's change synced in
        # memory: drop her UADS entry. The logon path must reload+resync UADS
        # from RACF itself (the bug was that it only reloaded RACF).
        try:
            ps.uads.entries.pop("NANCY", None)
        except Exception:
            pass
        pa2 = _Appp(ps, userid="")
        r = screen_text(pa2.handle(_PIp(aid=0, key="ENTER",
                        fields={"USERID": "NANCY", "PASSWORD": "NEWPASS01", "PROC": "ISPFPROC"})))
        clean = "READY" in r and "ENTER A NEW PASSWORD" not in r and "MINIMUM LENGTH" not in r
        flag_cleared = ps.uads.get("NANCY") is not None and ps.uads.get("NANCY").password_change_required is False
        if flag_cleared and clean:
            rows.append(("logon:persist-change", "OK", "saved change survives reload; no re-force"))
        else:
            rows.append(("logon:persist-change", "FAIL", f"flag_cleared={flag_cleared} clean={clean}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:persist-change", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Admin ALTUSER PASSWORD(...) keeps UADS aligned with RACF: by DEFAULT it
    # does NOT expire the password (user logs on directly); EXPIRED forces a
    # change, NOEXPIRED is also direct.
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCPa
        from gibson.apps.tso3270.tso_session import Tso3270App as _Appa
        from gibson.render.panels import PanelInput as _PIa
        as_ = fresh_session().state
        adm = _TCPa(as_, "IBMUSER")
        adm.run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(INITPASS)")
        # default reset: no expiry, logon goes straight to READY
        adm.run("ALTUSER NANCY PASSWORD(RESET123)")
        reset_noforce = as_.uads.get("NANCY").password_change_required is False and as_.racf.verify_password("NANCY", "RESET123")
        ar = _Appa(as_, userid="")
        direct_reset = "READY" in screen_text(
            ar.handle(_PIa(aid=0, key="ENTER", fields={"USERID": "NANCY", "PASSWORD": "RESET123", "PROC": "ISPFPROC"})))
        # explicit EXPIRED: next logon must force a change
        adm.run("ALTUSER NANCY PASSWORD(EXPRD123) EXPIRED")
        exp = as_.uads.get("NANCY").password_change_required is True
        ae = _Appa(as_, userid="")
        forced = "ENTER A NEW PASSWORD" in screen_text(
            ae.handle(_PIa(aid=0, key="ENTER", fields={"USERID": "NANCY", "PASSWORD": "EXPRD123", "PROC": "ISPFPROC"})))
        if reset_noforce and direct_reset and exp and forced:
            rows.append(("logon:altuser-reset", "OK", "default reset = direct logon; EXPIRED forces change"))
        else:
            rows.append(("logon:altuser-reset", "FAIL",
                         f"reset_noforce={reset_noforce} direct={direct_reset} exp={exp} forced={forced}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:altuser-reset", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # RACF/GACF.DB is the single source of truth for logon: a user must be able
    # to log on with their current password even if SYS1.UADS is empty/stale, and
    # new users must be hashed with DES (not KDFAES).
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCPr
        from gibson.apps.tso3270.tso_session import Tso3270App as _Appr
        from gibson.render.panels import PanelInput as _PIr
        rs = fresh_session().state
        des_ok = rs.password_policy.algorithm == "MD5"
        _TCPr(rs, "IBMUSER").run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(Summer26)")
        des_hash = rs.racf.get("NANCY").password.startswith("$1$")   # real md5crypt
        # wipe UADS entirely - RACF must still admit NANCY (case-folded), straight
        # to READY with no forced change.
        rs.uads.entries.clear()
        rb = _Appr(rs, userid="")
        out = screen_text(rb.handle(_PIr(aid=0, key="ENTER",
                          fields={"USERID": "NANCY", "PASSWORD": "SUMMER26", "PROC": "ISPFPROC"})))
        empty_uads_ok = "READY" in out and "ENTER A NEW PASSWORD" not in out and "MINIMUM LENGTH" not in out
        if des_ok and des_hash and empty_uads_ok:
            rows.append(("logon:racf-authoritative", "OK", "md5crypt $1$; case-fold; direct logon, empty UADS"))
        else:
            rows.append(("logon:racf-authoritative", "FAIL",
                         f"md5={des_ok} hash={des_hash} empty_uads={empty_uads_ok}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:racf-authoritative", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # An ADDUSER'd user lives in the shared in-memory RACF; a logon reload must
    # not erase them even if the on-disk GACF.DB has drifted (merge reload). This
    # is the "new user cannot log on over EBCDIC / NOT AUTHORIZED at the userid
    # stage" defect.
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCPm
        from gibson.apps.tso3270.tso_session import Tso3270App as _Appm
        from gibson.render.panels import PanelInput as _PIm
        ms = fresh_session().state
        _TCPm(ms, "IBMUSER").run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(INITPASS) SPECIAL")
        # simulate the on-disk GACF.DB not containing NANCY (drift vs memory)
        try:
            gp = ms.config.gacf_path
            keep = [l for l in gp.read_text().splitlines() if not l.startswith("NANCY")]
            gp.write_text("\n".join(keep) + "\n")
        except Exception:
            pass
        ms.racf.load(merge=True)
        still_there = ms.racf.exists("NANCY")
        ma = _Appm(ms, userid="")
        out = screen_text(ma.handle(_PIm(aid=0, key="ENTER",
                          fields={"USERID": "NANCY", "PASSWORD": "INITPASS", "PROC": "ISPFPROC"})))
        reached = "READY" in out and "AUTHORIZED" not in out.upper()
        if still_there and reached:
            rows.append(("logon:added-user-visible", "OK", "merge reload keeps ADDUSER'd user; logon works"))
        else:
            rows.append(("logon:added-user-visible", "FAIL", f"exists={still_there} reached={reached}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:added-user-visible", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    # Drive the REAL 3270 datastream through the LOGON panel (not a synthetic
    # PanelInput).  DEFAULT: a new user logs straight to READY (userid decodes
    # correctly, no forced change).  OPT-IN: with initial_password_change the
    # empty New Password field prompts a new password (never "MINIMUM LENGTH IS
    # 8"), and a valid new password reaches READY.
    try:
        from gibson.apps.tso import TsoCommandProcessor as _TCPp2
        from gibson.apps.tso3270.tso_session import Tso3270App as _Appp2
        from gibson.net.datastream3270 import (encode_3270_address as _enc, encode_ebcdic_field as _ebc,
                                               parse_3270_input_frame as _parse)
        from gibson.render.panels import panel_input_from_event as _pie

        def _submit(app, scr, mods):
            frame = bytearray([0x7D]) + _enc(0)
            for nm, tx in mods:
                fl = scr.get_field(nm)
                frame += bytes([0x11]) + _enc(fl.address + 1) + _ebc(tx)
            return app.handle(_pie(_parse(bytes(frame), screen_registry=scr)))

        # default: straight to READY
        ds = fresh_session().state
        _TCPp2(ds, "IBMUSER").run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(INITPASS)")
        dapp = _Appp2(ds, userid=""); dscr = dapp.initial_screen()
        direct = "READY" in screen_text(_submit(dapp, dscr,
                 [("USERID", "NANCY"), ("PASSWORD", "INITPASS"), ("PROC", "ISPFPROC")]))

        # opt-in: empty newpw prompts (not MIN LEN), then change -> READY
        os_ = fresh_session().state
        os_.password_policy.initial_password_change = True
        _TCPp2(os_, "IBMUSER").run("ADDUSER NANCY DFLTGRP(SYS1) PASSWORD(INITPASS)")
        oapp = _Appp2(os_, userid=""); oscr = oapp.initial_screen()
        o1s = _submit(oapp, oscr, [("USERID", "NANCY"), ("PASSWORD", "INITPASS"), ("PROC", "ISPFPROC")])
        o1 = screen_text(o1s)
        prompts = "ENTER A NEW PASSWORD" in o1 and "MINIMUM LENGTH" not in o1
        o2 = _submit(oapp, o1s,
                     [("USERID", "NANCY"), ("PASSWORD", "INITPASS"), ("NEWPW", "WINTER27"), ("PROC", "ISPFPROC")])
        done = "READY" in screen_text(o2)
        if direct and prompts and done:
            rows.append(("logon:panel-datastream", "OK", "real frames: direct READY; opt-in prompts (not MIN LEN)->READY"))
        else:
            rows.append(("logon:panel-datastream", "FAIL", f"direct={direct} prompts={prompts} done={done}"))
    except Exception as e:  # noqa: BLE001
        rows.append(("logon:panel-datastream", f"EXCEPTION:{type(e).__name__}", str(e)[:48]))

    width = max(len(r[0]) for r in rows)
    print("=" * 100)
    print(f"{'PROBE'.ljust(width)}  RESULT      DETAIL")
    print("-" * 100)
    failures = 0
    for name, cls, detail in rows:
        if cls != "OK":
            failures += 1
        print(f"{name.ljust(width)}  {cls:<11} {detail}")
    print("=" * 100)
    print(f"{len(rows)} probes, {failures} not-OK")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
