"""gibson/apps/zvm/zvm_session.py

z/VM CP/CMS simulator for Gibson TN3270 sessions.

Screen flow mirrors mock-lpar/mock-zvm.js from the web3270 bridge, translated
into Gibson's ScreenBuffer API and wired into GibsonState for security-event
and SMF logging.

    CP Logon screen
        │  ENTER (userid / password)
        ▼
    CP Ready prompt
        │  IPL CMS / CMS / IPL 190   → CMS Ready
        │  CP Q <x>                   → CP Query response
        │  HELP                       → CP Help response
        │  LOGOFF / DISC              → disconnect (returns None)
        ▼
    CMS Ready prompt
        │  FILELIST / FL              → FILELIST screen
        │  RDRLIST  / RL              → RDRLIST screen
        │  XEDIT <fn ft fm>           → XEDIT screen
        │  CP                         → back to CP Ready
        │  #CP LOGOFF / LOGOFF        → disconnect (returns None)

handle() returns a ScreenBuffer to send, or None to signal disconnect.
"""

from __future__ import annotations

import datetime
from typing import Optional, TYPE_CHECKING

from gibson.render.screen3270 import ScreenBuffer
from gibson.render import colors
from gibson.apps.zvm.cms import cms_command
from gibson.apps.zvm.cp_directory import (
    CpDirectory, CP_CLASS_DESC, parse_cp_command, is_authorized,
)

if TYPE_CHECKING:
    from gibson.core.state import GibsonState

# ── AID bytes used by z/VM ────────────────────────────────────────────────────
AID_ENTER = 0x7D
AID_CLEAR = 0x6D
AID_PF3   = 0xF3
AID_PF7   = 0xF7
AID_PF8   = 0xF8
AID_PF12  = 0xFB

# ── Internal screen-state names ───────────────────────────────────────────────
_LOGON    = "LOGON"
_LOGON_PW = "LOGON_PW"
_CP       = "CP"
_CPQUERY  = "CPQUERY"
_CMS      = "CMS"
_FILELIST = "FILELIST"
_RDRLIST  = "RDRLIST"
_XEDIT    = "XEDIT"

SYSNAME = "ZVMPROD"
VMID    = "ZVMSYS1"
SYSVER  = "7.4.0"
SYSLVL  = "2501"     # CP service level (RSU), for QUERY CPLEVEL

# Sample virtual-machine directory (shown by Q NAMES / Q USERS)
_VM_USERS = ["MAINT", "TCPIP", "OPERATOR", "RACFVM", "DIRMAINT", "SYSADMIN"]

# Sample CMS minidisk file listing
_FILELIST_ROWS = [
    "      PROFILE   EXEC      A1  V        80       42       1  2024-01-15 09:12:44",
    "      DEMO      REXX      A1  V        80      123       2  2024-03-10 14:22:01",
    "      MYJOB     JCL       A1  V        80       18       1  2024-04-01 11:05:33",
    "      NOTES     MEMO      A1  V        80       55       1  2024-04-20 08:44:17",
    "      CMSLIB    MACLIB    A1  F       400      200      50  2023-12-01 00:00:00",
    "      USER      DIRECT    A2  V        80       10       1  2024-02-14 16:30:00",
    "      BACKUP    EXEC      A1  V        80       30       1  2024-03-28 10:10:10",
    "      AUTOEXEC  EXEC      A1  V        80       15       1  2024-01-01 00:00:00",
]

_RDRLIST_ROWS_TMPL = [
    "      MYJOB     JOB       RDR  {uid:<8}  04/27/24 09:14:02  250  A    1",
    "      REPORT    DATA      RDR  SYSTEM    04/26/24 22:00:11  512  A    2",
    "      SYSLOG    OUTPUT    RDR  SYSTEM    04/26/24 23:59:59 1024  A    5",
]

_XEDIT_CONTENT = [
    "       |...+....1....+....2....+....3....+....4....+....5....+....6....+....7...|",
    "00000 * * * Top of File * * *",
    "00001 /* DEMO REXX EXEC */",
    "00002 say 'Hello from z/VM CMS!'",
    f"00003 say 'Running on {SYSNAME}'",
    "00004 do i = 1 to 5",
    "00005   say 'Iteration' i",
    "00006 end",
    "00007 exit 0",
    "00000 * * * End of File * * *",
]


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _time_str() -> str:
    return _now().strftime("%H:%M:%S")


def _date_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _us_date() -> str:
    return _now().strftime("%m/%d/%y")


class ZvmSession:
    """Stateful z/VM CP/CMS session attached to a single TN3270 connection.

    Instantiate once per TN3270 client connection (mirror of CicsSimulator).
    Call handle(aid, text) for each input frame; it returns the next
    ScreenBuffer to send or None when the session should be torn down.
    """

    def __init__(self, state: "GibsonState", peer_addr: str = "") -> None:
        self.state = state
        self.peer_addr = peer_addr
        self._screen   = _LOGON
        self._userid   = ""
        self._pending  = ""      # userid waiting for password
        self._last_msg = ""      # last CP/CMS output line
        self._xedit_file = "DEMO REXX A"
        # z/VM CP directory is shared on the GibsonState so Q NAMES reflects
        # every logged-on guest across connections.
        self._dir: CpDirectory = getattr(self.state, "cp_directory", None) or CpDirectory()
        try:
            self.state.cp_directory = self._dir
        except Exception:
            pass
        # Phase-2 JEA lab: set the Linux guest's privilege classes for the mode
        # (vulnerable -> over-granted B,C,E; fixed -> Just Enough Authority G).
        try:
            from gibson.apps.zvm.jea_lab import apply_remediation
            apply_remediation(
                self._dir,
                vulnerable=getattr(self.state.config, "zvm_jea_lab_vulnerable_mode", True))
        except Exception:
            pass
        self._classes = "G"      # privilege classes held by the logged-on guest

    # ── Public entry points ───────────────────────────────────────────────────

    def logon_screen(self) -> ScreenBuffer:
        return self._screen_logon()

    def run_terminal(self, input_driver, send) -> None:
        """ASCII/telnet text-mode z/VM CP/CMS session."""
        from gibson.render import colors
        send(colors.CLEAR)
        send(f"z/VM  Version {SYSVER}  Service Level {VMID}\n")
        send(f"{SYSNAME} AT {VMID}  {_date_str()}  {_time_str()}\n\n")
        res = input_driver.read_line("USERID  ==> ")
        if res.key == "EOF":
            return
        userid = (res.text.strip().upper() or "DEMO")[:8]
        self._pending = userid
        res = input_driver.read_line("PASSWORD==> ")
        if res.key == "EOF":
            return
        if not res.text.strip():
            send("LOGON REJECTED\n")
            return
        pw = res.text.strip()
        vuln = getattr(self.state.config, "zvm_lab_vulnerable_mode", True)
        known = self._dir.exists(userid)
        if (known and not self._dir.verify_password(userid, pw)) or (not known and not vuln):
            self._emit_logon_fail(userid)
            send("HCPLGA050E LOGON unsuccessful--incorrect password\n")
            return
        guest = self._dir.logon(userid, allow_create=vuln)
        if guest is None:
            self._emit_logon_fail(userid)
            send("HCPLGA050E LOGON unsuccessful--incorrect password\n")
            return
        self._classes = guest.classes
        self._userid = userid
        self._pending = ""
        self._emit_logon_event(userid)
        send(f"\nLOGON AT {_time_str()} {_date_str()}\n")
        send(f"z/VM Version {SYSVER}\n")
        send("Your IPL directory entry will be used to IPL CMS.\n")
        send(f"Ready; T=0.01/0.01 {_time_str()}\n\n")
        in_cms = False
        while True:
            prompt = f"{userid} CMS\n===> " if in_cms else f"{userid} CP\n===> "
            res = input_driver.read_line(prompt)
            if res.key == "EOF":
                return
            raw = (res.text or "").strip()
            cmd = raw.upper()
            if not cmd:
                continue
            if not in_cms:
                if cmd in ("IPL CMS", "CMS", "IPL 190", "IPL 191"):
                    in_cms = True
                    send(f"z/VM CMS Level {SYSVER}  {SYSNAME}\n")
                    send(f"Ready; T=0.01/0.01 {_time_str()}\n\n")
                elif cmd.startswith("Q ") or cmd.startswith("QUERY ") or cmd in ("Q", "QUERY"):
                    send(self._cp_query(cmd) + f"\nReady; T=0.01/0.01 {_time_str()}\n\n")
                elif cmd == "HELP":
                    send(
                        "CP COMMANDS:\n"
                        "  IPL CMS       Load CMS\n"
                        "  QUERY TIME    Display time\n"
                        "  QUERY NAMES   List logged-on users\n"
                        "  QUERY STORAGE Display storage allocation\n"
                        "  LOGOFF        Logoff from z/VM\n"
                        f"Ready; T=0.01/0.01 {_time_str()}\n\n"
                    )
                elif cmd in ("LOGOFF", "LOG", "DISC", "DISCONNECT"):
                    send(f"LOGOFF AT {_time_str()}\n")
                    return
                else:
                    send(f"HCPCMD003E Unknown CP command: {cmd}\nReady(00003); T=0.01/0.01 {_time_str()}\n\n")
            else:
                if cmd in ("IPL CMS", "CMS", "IPL 190", "IPL 191"):
                    send(f"z/VM CMS Level {SYSVER}  {SYSNAME}\n")
                    send(f"Ready; T=0.01/0.01 {_time_str()}\n\n")
                elif cmd in ("FILELIST", "FL"):
                    send("Cmd   Filename  Filetype  Fm  Format  Lrecl  Records  Blocks  Date      Time\n")
                    send("-" * 79 + "\n")
                    for row in _FILELIST_ROWS:
                        send(row + "\n")
                    send(f"\nReady; T=0.01/0.01 {_time_str()}\n\n")
                elif cmd in ("RDRLIST", "RL"):
                    send("Cmd   Filename  Filetype  Fm  Origid   Date      Time     Recs  Class Pri Hold\n")
                    send("-" * 79 + "\n")
                    for tmpl in _RDRLIST_ROWS_TMPL:
                        send(tmpl.format(uid=userid) + "\n")
                    send(f"\nReady; T=0.01/0.01 {_time_str()}\n\n")
                elif cmd.startswith("XEDIT ") or cmd.startswith("X "):
                    send("Full-screen XEDIT requires TN3270 mode.\n\n")
                elif cmd == "CP":
                    in_cms = False
                    send(f"Ready; T=0.01/0.01 {_time_str()}\n\n")
                elif cmd in ("#CP LOGOFF", "LOGOFF"):
                    send(f"LOGOFF AT {_time_str()}\n")
                    return
                else:
                    cms_out = cms_command(self.state, userid, raw)
                    if cms_out is not None:
                        send(cms_out + "\n\n")
                    else:
                        send(f"DMSEXT002S Command not found: {raw}\nReady(00002); T=0.01/0.01 {_time_str()}\n\n")

    def handle(self, aid: int, text: str) -> Optional[ScreenBuffer]:
        """Process one AID+text frame.  Returns None to signal disconnect."""
        uc = (text or "").strip().upper()

        if self._screen == _LOGON:
            return self._handle_logon(aid, text)
        if self._screen == _LOGON_PW:
            return self._handle_logon_pw(aid, text)
        if self._screen == _CP:
            return self._handle_cp(aid, uc)
        if self._screen == _CPQUERY:
            return self._handle_cpquery(aid)
        if self._screen == _CMS:
            return self._handle_cms(aid, uc, text)
        if self._screen in (_FILELIST, _RDRLIST):
            return self._handle_list(aid)
        if self._screen == _XEDIT:
            return self._handle_xedit(aid)
        return self._screen_logon()

    # ── Logon flow ────────────────────────────────────────────────────────────

    def _handle_logon(self, aid: int, text: str) -> Optional[ScreenBuffer]:
        if aid == AID_PF3:
            return None  # disconnect
        if aid != AID_ENTER:
            return self._screen_logon()
        # Extract userid: accept the authentic "LOGON userid" / "L userid" as
        # well as a bare userid (the first token after any leading logon verb).
        toks = text.split()
        if toks and toks[0].upper() in ("LOGON", "LOG", "L") and len(toks) > 1:
            toks = toks[1:]
        userid = (toks[0] if toks else "").upper()[:8] or "DEMO"
        self._pending = userid
        self._screen = _LOGON_PW
        return self._screen_logon_pw(userid)

    def _handle_logon_pw(self, aid: int, text: str) -> Optional[ScreenBuffer]:
        if aid == AID_PF3:
            self._screen = _LOGON
            return self._screen_logon()
        if aid != AID_ENTER:
            return self._screen_logon_pw(self._pending)
        pw = text.strip()
        userid = self._pending or "DEMO"
        if not pw:
            return self._screen_logon_pw(userid, "ENTER PASSWORD")
        vuln = getattr(self.state.config, "zvm_lab_vulnerable_mode", True)
        known = self._dir.exists(userid)
        # Real credential check: a known userid must supply the correct password;
        # unknown userids are admitted only in lab-vulnerable mode (transient G).
        if (known and not self._dir.verify_password(userid, pw)) or (not known and not vuln):
            self._screen = _LOGON
            self._pending = ""
            self._emit_logon_fail(userid)
            return self._screen_logon("HCPLGA050E LOGON unsuccessful--incorrect password")
        guest = self._dir.logon(userid, allow_create=vuln)
        if guest is None:
            self._screen = _LOGON
            self._pending = ""
            self._emit_logon_fail(userid)
            return self._screen_logon("HCPLGA050E LOGON unsuccessful--incorrect password")
        self._userid = userid
        self._pending = ""
        self._screen = _CP
        self._last_msg = ""
        self._classes = guest.classes
        self._emit_logon_event(userid)
        return self._screen_cp()

    def _emit_logon_event(self, userid: str) -> None:
        try:
            self.state.record_security_event(
                userid, "LOGON", "PASSWORD",
                service="TN3270/ZVM", addr=self.peer_addr, terminal="3270",
            )
        except Exception:
            pass

    def _emit_logon_fail(self, userid: str) -> None:
        try:
            self.state.record_security_event(
                userid, "LOGON_FAIL", "PASSWORD",
                service="TN3270/ZVM", addr=self.peer_addr, terminal="3270",
            )
        except Exception:
            pass

    # ── CP mode ───────────────────────────────────────────────────────────────

    def _handle_cp(self, aid: int, cmd: str) -> Optional[ScreenBuffer]:
        if aid == AID_PF3:
            return None  # logoff
        if aid != AID_ENTER or not cmd:
            return self._screen_cp()

        # ---- z2: privilege-class enforcement -----------------------------
        verb, required = parse_cp_command(cmd)
        if not is_authorized(self._classes, required):
            self._emit_priv_event(verb, required, authorized=False)
            msg = (
                f"HCPCFC026E Operand missing or invalid\n"
                f"HCPCMD003E You are not authorized to issue CP command {verb}.\n"
                f"   {verb} requires privilege class {required}; "
                f"you hold class {self._classes or 'G'}.\n"
                f"Ready(00045); T=0.01/0.01 {_time_str()}"
            )
            self._last_msg = msg
            self._screen = _CPQUERY
            return self._screen_cpquery(msg)

        # ---- z3: privileged lifecycle commands ---------------------------
        if verb == "FORCE":
            return self._cp_force(cmd)
        if verb == "SHUTDOWN":
            self._emit_priv_event("SHUTDOWN", "A", authorized=True)
            msg = (f"HCPSHU960I System shutdown may be delayed for up to 0 seconds\n"
                   f"SYSTEM SHUTDOWN STARTED BY {self._userid}\n"
                   f"Ready; T=0.01/0.01 {_time_str()}")
            self._last_msg = msg
            self._screen = _CPQUERY
            return self._screen_cpquery(msg)

        # ---- z4-z7: minidisk, spool, service machines, networking -------
        if verb == "STORE":
            return self._cp_store_host(cmd)
        if verb in ("DISPLAY", "DUMP"):
            return self._cp_display_host(cmd)
        if verb == "LINK":
            return self._cp_link(cmd)
        if verb == "DETACH":
            return self._cp_detach(cmd)
        if verb in ("DEFINE VSWITCH", "SET VSWITCH"):
            return self._cp_vswitch(verb, cmd)
        if verb in ("DIRMAINT", "DIRM"):
            return self._cp_dirmaint(cmd)
        if verb in ("XAUTOLOG", "AUTOLOG", "XAUTO"):
            return self._cp_xautolog(cmd)
        if verb == "RAC":
            return self._cp_rac(cmd)
        if verb in ("PURGE", "TRANSFER", "ORDER", "CLOSE"):
            return self._cp_spool(verb, cmd)

        if cmd in ("IPL CMS", "CMS", "IPL 190", "IPL 191"):
            self._screen = _CMS
            self._last_msg = f"IPL CMS\nz/VM CMS Level {SYSVER}  {SYSNAME}\nReady; T=0.01/0.01 {_time_str()}"
            return self._screen_cms()

        up_cmd = cmd.upper().strip()
        if up_cmd in ("Q HIPERSOCKETS", "QUERY HIPERSOCKETS", "Q HIPERSOCKET", "QUERY HIPERSOCKET"):
            from gibson.apps.zvm.jea_lab import hipersockets_status
            vuln = getattr(self.state.config, "zvm_jea_lab_vulnerable_mode", True)
            result = hipersockets_status(self._dir, vulnerable=vuln) + f"\nReady; T=0.01/0.01 {_time_str()}"
            self._last_msg = result
            self._screen = _CPQUERY
            return self._screen_cpquery(result)
        if up_cmd in ("Q PRIVCLASS ALL", "QUERY PRIVCLASS ALL", "Q PRIVCLASS *",
                      "QUERY PRIVCLASS *", "CPAUDIT", "AUDIT PRIVCLASS"):
            from gibson.apps.zvm.jea_lab import audit_report
            result = audit_report(self._dir) + f"\nReady; T=0.01/0.01 {_time_str()}"
            self._last_msg = result
            self._screen = _CPQUERY
            return self._screen_cpquery(result)

        if cmd.startswith("Q ") or cmd.startswith("QUERY ") or cmd in ("Q", "QUERY"):
            result = self._cp_query(cmd)
            self._last_msg = result
            self._screen = _CPQUERY
            return self._screen_cpquery(result)

        if cmd == "HELP":
            result = (
                "CP COMMANDS:\n"
                "  IPL CMS         Load CMS\n"
                "  QUERY TIME      Display time\n"
                "  QUERY NAMES     List logged-on users\n"
                "  QUERY PRIVCLASS Display your privilege classes\n"
                "  QUERY STORAGE   Display storage allocation\n"
                "  QUERY DASD      Display DASD volumes\n"
                "  FORCE  userid   (class A) log another user off\n"
                "  SHUTDOWN        (class A) shut the system down\n"
                "  DISCONNECT      Disconnect, leaving the VM running\n"
                "  LOGOFF          Logoff from z/VM\n"
                f"Ready; T=0.01/0.01 {_time_str()}"
            )
            self._last_msg = result
            self._screen = _CPQUERY
            return self._screen_cpquery(result)

        if verb in ("DISCONNECT", "DISC"):
            self._dir.disconnect(self._userid)
            return None
        if cmd in ("LOGOFF", "LOG"):
            self._dir.logoff(self._userid)
            return None

        self._last_msg = f"HCPCMD003E Unknown CP command: {cmd}\nReady(00003); T=0.01/0.01 {_time_str()}"
        return self._screen_cp(self._last_msg)

    def _cp_store_host(self, cmd: str) -> ScreenBuffer:
        """STORE HOST addr value - alter host real storage (class C).  The class
        check has already passed; the lab shows the cross-guest blast radius."""
        from gibson.apps.zvm.jea_lab import alter_host
        text, cross = alter_host(self.state, self._userid, cmd)
        self._emit_priv_event("STORE HOST", "C", authorized=True,
                              target="CROSS-GUEST-WRITE" if cross else "")
        return self._cp_out(text + f"\nReady; T=0.01/0.01 {_time_str()}")

    def _cp_display_host(self, cmd: str) -> ScreenBuffer:
        """DISPLAY/DUMP HOST [addr] - examine host real storage (class E)."""
        from gibson.apps.zvm.jea_lab import examine_host
        text, leak = examine_host(self.state, self._userid, cmd)
        self._emit_priv_event("DISPLAY HOST", "E", authorized=True,
                              target="CROSS-GUEST-READ" if leak else "")
        return self._cp_out(text + f"\nReady; T=0.01/0.01 {_time_str()}")

    def _cp_force(self, cmd: str) -> ScreenBuffer:
        """Class-A FORCE: log another guest off the system."""
        parts = cmd.split()
        target = (parts[1].upper() if len(parts) > 1 else "")
        if not target:
            msg = f"HCPCFC026E Operand missing or invalid\nReady(00026); T=0.01/0.01 {_time_str()}"
        elif not self._dir.exists(target) or not self._dir.get(target).logged_on:
            msg = f"HCPFRC045E {target} not logged on\nReady(00045); T=0.01/0.01 {_time_str()}"
        else:
            self._dir.logoff(target)
            self._emit_priv_event("FORCE", "A", authorized=True, target=target)
            msg = (f"USER {target} LOGOFF AS OF {_time_str()} BY {self._userid}\n"
                   f"HCPFRC045I {target} forced off the system\n"
                   f"Ready; T=0.01/0.01 {_time_str()}")
        self._last_msg = msg
        self._screen = _CPQUERY
        return self._screen_cpquery(msg)

    def _cp_out(self, msg: str) -> ScreenBuffer:
        self._last_msg = msg
        self._screen = _CPQUERY
        return self._screen_cpquery(msg)

    # ---- z4: minidisk LINK / DETACH ------------------------------------
    def _cp_link(self, cmd: str) -> ScreenBuffer:
        toks = [p for p in cmd.split()[1:] if p.upper() not in ("TO", "AS", "PASS=")]
        if len(toks) < 3:
            return self._cp_out(f"HCPLNM020E Userid missing or invalid\n"
                                f"Ready(00020); T=0.01/0.01 {_time_str()}")
        owner, oaddr, myaddr = toks[0].upper(), toks[1].upper(), toks[2].upper()
        mode = (toks[3].upper() if len(toks) > 3 else "RR")
        pw = (toks[4] if len(toks) > 4 else "")
        if owner == self._userid:                      # linking your own disk
            self._dir.get(self._userid).links.append((owner, oaddr, myaddr, mode))
            return self._cp_out(f"{owner} {oaddr} LINKED AS {myaddr} {mode}\n"
                                f"Ready; T=0.01/0.01 {_time_str()}")
        if not self._dir.exists(owner):
            return self._cp_out(f"HCPLNM053E {owner} not in CP directory\n"
                                f"Ready(00053); T=0.01/0.01 {_time_str()}")
        md = self._dir.minidisk(owner, oaddr)
        if md is None:
            return self._cp_out(f"HCPLNM040E Device {oaddr} does not exist for {owner}\n"
                                f"Ready(00040); T=0.01/0.01 {_time_str()}")
        want_write = mode in ("RW", "W", "MR", "M", "MW")
        needed = md.write_pw if want_write else md.read_pw
        ok = False
        if needed == "ALL":
            ok = True
        elif needed == "":
            denied = "no link permitted in this mode"
        elif pw.upper() == needed.upper():
            ok = True
        else:
            denied = "password incorrect"
        if not ok:
            self._emit_link_event(owner, oaddr, mode, authorized=False)
            return self._cp_out(
                f"HCPLNM298E {owner} {oaddr} not linked; {denied}\n"
                f"Ready(00298); T=0.01/0.01 {_time_str()}")
        self._dir.get(self._userid).links.append((owner, oaddr, myaddr, mode))
        self._emit_link_event(owner, oaddr, mode, authorized=True)
        warn = "" if want_write else "  (R/O exposure)" if md.read_pw == "ALL" else ""
        return self._cp_out(
            f"{owner} {oaddr} LINKED AS {myaddr} {mode}{warn}\n"
            f"Ready; T=0.01/0.01 {_time_str()}")

    def _cp_detach(self, cmd: str) -> ScreenBuffer:
        parts = cmd.split()
        addr = (parts[1].upper() if len(parts) > 1 else "")
        g = self._dir.get(self._userid)
        before = len(g.links)
        g.links = [l for l in g.links if l[2] != addr]
        if len(g.links) < before:
            return self._cp_out(f"{addr} DETACHED\nReady; T=0.01/0.01 {_time_str()}")
        return self._cp_out(f"{addr} DETACHED\nReady; T=0.01/0.01 {_time_str()}")

    def _emit_link_event(self, owner: str, addr: str, mode: str, authorized: bool) -> None:
        try:
            self.state.record_security_event(
                self._userid, "CP MINIDISK LINK" if authorized else "CP MINIDISK LINK DENIED",
                f"LINK {owner} {addr} MODE={mode}", service="TN3270/ZVM",
                addr=self.peer_addr, terminal="3270",
                result="SUCCESS" if authorized else "DENIED")
        except Exception:
            pass

    # ---- z5: spool ------------------------------------------------------
    def _cp_spool(self, verb: str, cmd: str) -> ScreenBuffer:
        parts = cmd.upper().split()
        ids = [p for p in parts[1:] if p.isdigit() or (len(p) == 4 and p.isdigit())]
        spoolid = (ids[0] if ids else "")
        if verb == "CLOSE":
            return self._cp_out(f"CONSOLE FILE SPOOLED TO {self._userid}\n"
                                f"RDR FILE 0200 SENT FROM {self._userid}\n"
                                f"Ready; T=0.01/0.01 {_time_str()}")
        if not spoolid:
            return self._cp_out(f"HCPCMD003E Spool id missing\nReady(00003); T=0.01/0.01 {_time_str()}")
        sf = self._dir.find_spool(spoolid)
        if sf is None:
            return self._cp_out(f"HCPSPL003E File {spoolid} not found\nReady(00003); T=0.01/0.01 {_time_str()}")
        # other users' spool requires class D
        if sf.owner != self._userid and "D" not in (self._classes or ""):
            self._emit_priv_event(f"{verb} (spool of {sf.owner})", "D", authorized=False)
            return self._cp_out(
                f"HCPSPL003E You are not authorized to {verb} spool file of {sf.owner}\n"
                f"   (requires privilege class D; you hold class {self._classes or 'G'}.)\n"
                f"Ready(00045); T=0.01/0.01 {_time_str()}")
        if sf.owner != self._userid:
            self._emit_priv_event(f"{verb} (spool of {sf.owner})", "D", authorized=True)
        if verb == "PURGE":
            self._dir.purge_spool(spoolid)
            return self._cp_out(f"{spoolid} PURGED\nReady; T=0.01/0.01 {_time_str()}")
        if verb == "TRANSFER":
            tgt = parts[parts.index("TO") + 1] if "TO" in parts else (parts[-1] if len(parts) > 2 else "")
            self._dir.transfer_spool(spoolid, tgt)
            return self._cp_out(f"{spoolid} TRANSFERRED TO {tgt}\nReady; T=0.01/0.01 {_time_str()}")
        if verb == "ORDER":
            return self._cp_out(f"RDR REORDERED\nReady; T=0.01/0.01 {_time_str()}")
        return self._cp_out(f"Ready; T=0.01/0.01 {_time_str()}")

    # ---- z6: DirMaint / RACFVM -----------------------------------------
    def _cp_dirmaint(self, cmd: str) -> ScreenBuffer:
        from gibson.apps.zvm.cp_directory import DIRMAINT_AUTH
        sub = cmd.split(None, 1)[1].strip() if len(cmd.split(None, 1)) > 1 else ""
        if self._userid not in DIRMAINT_AUTH and "B" not in (self._classes or ""):
            self._emit_priv_event("DIRMAINT", "B", authorized=False)
            return self._cp_out(
                f"DVH002E You are not authorized to issue DirMaint commands.\n"
                f"   (DirMaint authority requires class B or directory authorization.)\n"
                f"Ready(00002); T=0.01/0.01 {_time_str()}")
        toks = sub.split()
        # optional  FOR <target>  prefix
        target = None
        if toks and toks[0].upper() == "FOR" and len(toks) >= 2:
            target = toks[1].upper()
            toks = toks[2:]
        verb2 = toks[0].upper() if toks else ""
        rest = toks[1:]
        self._emit_priv_event(f"DIRMAINT {verb2}", "B", authorized=True)

        # ---- ADD: actually create a new virtual machine -----------------------
        if verb2 == "ADD":
            newid = (target or (rest[0] if rest else "")).upper()
            args = rest if target else rest[1:]
            like = None
            pw = "LBYONLY"
            cls = "G"
            i = 0
            while i < len(args):
                a = args[i].upper()
                if a in ("LIKE", "PROTO") and i + 1 < len(args):
                    like = args[i + 1]; i += 2; continue
                if a in ("PW", "PASS", "PASSWORD") and i + 1 < len(args):
                    pw = args[i + 1].upper(); i += 2; continue
                if a in ("CLASS", "CL") and i + 1 < len(args):
                    cls = args[i + 1].upper(); i += 2; continue
                i += 1
            g, status = self._dir.define_guest(newid, classes=cls, password=pw, like=like)
            if status == "badid":
                return self._cp_out(
                    f"DVHADD3211E The userid specified is not valid; ADD failed.\n"
                    f"Ready(00024); T=0.01/0.01 {_time_str()}")
            if status == "exists":
                return self._cp_out(
                    f"DVHADD3211E User {newid} already in directory; ADD failed.\n"
                    f"Ready(00024); T=0.01/0.01 {_time_str()}")
            like_txt = f" (LIKE {like.upper()}, classes {g.classes})" if like else f" (class {g.classes})"
            self.state.record_security_event(self._userid, "DIRMAINT ADD",
                                             f"NEWID={newid}{like_txt}", service="ZVM",
                                             terminal="LVM") if hasattr(self.state, "record_security_event") else None
            return self._cp_out(
                f"DVHXMT1191I Your ADD request for {newid} has been sent for processing.\n"
                f"DVHREQ2288I Your ADD request for {newid} at * has been accepted.\n"
                f"DVHBIU3450I The source for directory entry {newid} has been updated.\n"
                f"DVHBIU3456I The next ONLINE refresh will use the new directory.\n"
                f"DVHRLA3891I Directory entry {newid}{like_txt} created and brought online.\n"
                f"DVHREQ2289I Your ADD request for {newid} has completed; cc=0.\n"
                f"   (XAUTOLOG {newid} to start it, or LOGON {newid} / PW {g.password})\n"
                f"Ready; T=0.01/0.01 {_time_str()}")

        # ---- AMDISK: add a minidisk to an existing guest ----------------------
        if verb2 == "AMDISK":
            who = (target or (rest[0] if rest else self._userid)).upper()
            margs = rest if target else rest[1:]
            addr = (margs[0] if margs else "200").upper()
            cyls = 50
            for a in margs[1:]:
                if a.isdigit():
                    cyls = int(a); break
            ok = self._dir.add_minidisk(who, addr, cyls=cyls)
            if not ok:
                return self._cp_out(
                    f"DVHDRC3343E User {who} not found; AMDISK failed.\n"
                    f"Ready(00024); T=0.01/0.01 {_time_str()}")
            return self._cp_out(
                f"DVHXMT1191I Your AMDISK request for {who} has been sent for processing.\n"
                f"DVHDRC3344I Minidisk {addr.upper()} ({cyls} CYL) added to {who}.\n"
                f"DVHREQ2289I Your AMDISK request for {who} has completed; cc=0.\n"
                f"Ready; T=0.01/0.01 {_time_str()}")

        # ---- PURGE: delete a guest -------------------------------------------
        if verb2 == "PURGE":
            who = (target or (rest[0] if rest else "")).upper()
            ok = self._dir.delete_guest(who)
            if not ok:
                return self._cp_out(
                    f"DVHPRG3402E User {who} cannot be purged (not found or protected).\n"
                    f"Ready(00024); T=0.01/0.01 {_time_str()}")
            return self._cp_out(
                f"DVHXMT1191I Your PURGE request for {who} has been sent for processing.\n"
                f"DVHPRG3344I Directory entry {who} has been purged.\n"
                f"DVHREQ2289I Your PURGE request for {who} has completed; cc=0.\n"
                f"Ready; T=0.01/0.01 {_time_str()}")

        # ---- other verbs: realistic acknowledgement --------------------------
        ok = {"DMDISK": "DVHDRC3343I", "FORWARD": "DVHWAI2140I",
              "REVIEW": "DVHREV3425I", "CHANGE": "DVHREQ2289I"}.get(verb2, "DVHREQ2289I")
        return self._cp_out(
            f"DVHXMT1191I Your DIRMAINT {verb2} request has been sent for processing.\n"
            f"{ok} Request for {self._userid} completed; directory updated.\n"
            f"Ready; T=0.01/0.01 {_time_str()}")

    def _cp_xautolog(self, cmd: str) -> ScreenBuffer:
        """XAUTOLOG/AUTOLOG - start (log on) another virtual machine.  Requires
        class A or B (or DirMaint authority); the target must exist."""
        from gibson.apps.zvm.cp_directory import DIRMAINT_AUTH
        parts = cmd.split()
        who = parts[1].upper() if len(parts) > 1 else ""
        authed = ("A" in (self._classes or "") or "B" in (self._classes or "")
                  or self._userid in DIRMAINT_AUTH)
        if not authed:
            self._emit_priv_event(f"XAUTOLOG {who}", "B", authorized=False)
            return self._cp_out(
                f"HCPCFC003E XAUTOLOG {who} not authorized - requires class A or B.\n"
                f"Ready(00045); T=0.01/0.01 {_time_str()}")
        if not self._dir.exists(who):
            return self._cp_out(
                f"HCPLGA361E LOGON userid {who} not in CP directory.\n"
                f"Ready(00045); T=0.01/0.01 {_time_str()}")
        self._dir.logon(who, allow_create=False)
        self._emit_priv_event(f"XAUTOLOG {who}", "B", authorized=True, target=who)
        n = len(self._dir.logged_on_users())
        return self._cp_out(
            f"AUTO LOGON  ***  {who}     USERS = {n}\n"
            f"HCPCLS6056I XAUTOLOG information for {who}: The IPL command is verified by the IPL command processor.\n"
            f"Ready; T=0.01/0.01 {_time_str()}")

    def _cp_rac(self, cmd: str) -> ScreenBuffer:
        """RAC: run a RACF command via RACFVM (same engine the ISPF panels use)."""
        racf_cmd = cmd.split(None, 1)[1].strip() if len(cmd.split(None, 1)) > 1 else ""
        if not racf_cmd:
            return self._cp_out(f"RAC requires a RACF command operand\nReady; T=0.01/0.01 {_time_str()}")
        try:
            from gibson.apps.tso import TsoCommandProcessor
            out = TsoCommandProcessor(self.state, self._userid).run(racf_cmd)
        except Exception as exc:
            out = f"RAC FAILED: {exc}"
        return self._cp_out(f"{out}\nReady; T=0.01/0.01 {_time_str()}")

    # ---- z7: VSWITCH + security dashboard ------------------------------
    def _cp_vswitch(self, verb: str, cmd: str) -> ScreenBuffer:
        parts = cmd.upper().split()
        if verb == "DEFINE VSWITCH":
            name = parts[2] if len(parts) > 2 else "VSW0"
            self._dir.vswitches[name] = {"owner": self._userid, "grants": set()}
            self._emit_priv_event(f"DEFINE VSWITCH {name}", "B", authorized=True)
            return self._cp_out(f"VSWITCH {name} DEFINED\nReady; T=0.01/0.01 {_time_str()}")
        # SET VSWITCH name GRANT|REVOKE userid
        name = parts[2] if len(parts) > 2 else ""
        action = parts[3] if len(parts) > 3 else ""
        who = parts[4] if len(parts) > 4 else ""
        vsw = self._dir.vswitches.get(name)
        if vsw is None:
            return self._cp_out(f"HCPSWC2835E VSWITCH {name} does not exist\nReady(02835); T=0.01/0.01 {_time_str()}")
        if action == "GRANT":
            vsw["grants"].add(who)
        elif action == "REVOKE":
            vsw["grants"].discard(who)
        self._emit_priv_event(f"SET VSWITCH {name} {action} {who}", "B", authorized=True)
        return self._cp_out(f"VSWITCH {name} {action} {who} COMPLETE\nReady; T=0.01/0.01 {_time_str()}")

    def _security_dashboard(self) -> str:
        d = self._dir
        priv = [f"{u}({g.classes})" for u, g in sorted(d.guests.items()) if g.classes != "G"]
        exposed = [f"{u} {a}" for u, g in sorted(d.guests.items())
                   for a, md in g.minidisks.items() if md.read_pw == "ALL"]
        grants = [f"{n}->{','.join(sorted(v['grants'])) or 'none'}" for n, v in sorted(d.vswitches.items())]
        return "\n".join([
            f"z/VM SECURITY POSTURE  {SYSNAME}",
            "-" * 60,
            f"PRIVILEGED GUESTS ({len(priv)}): " + ", ".join(priv),
            f"MINIDISKS LINKABLE BY ALL ({len(exposed)}): " + ", ".join(exposed),
            f"SPOOL FILES IN SYSTEM     : {len(d.spool)}",
            f"VSWITCH GRANTS            : " + "; ".join(grants),
            f"LOGGED ON                 : " + ", ".join(d.logged_on_users()),
        ])

    def _emit_priv_event(self, verb: str, required: str, authorized: bool,
                         target: str = "") -> None:
        try:
            detail = f"CP {verb}"
            if target:
                detail += f" {target}"
            detail += f" CLASS={required or 'G'} HELD={self._classes or 'G'}"
            self.state.record_security_event(
                self._userid,
                "CP PRIVILEGED COMMAND" if authorized else "CP COMMAND DENIED",
                detail, service="TN3270/ZVM", addr=self.peer_addr, terminal="3270",
                result="SUCCESS" if authorized else "DENIED",
            )
        except Exception:
            pass

    def _handle_cpquery(self, aid: int) -> ScreenBuffer:
        if aid in (AID_ENTER, AID_PF3, AID_CLEAR):
            self._screen = _CP
            self._last_msg = ""
            return self._screen_cp()
        return self._screen_cpquery(self._last_msg)

    def _cp_query(self, cmd: str) -> str:
        uc = cmd.upper()
        t = _time_str()
        if "TIME" in uc:
            return (
                f"TIME IS {t}  DATE IS {_us_date()}\n"
                f"CPU TIME = 00:00:00.12  CONNECT TIME = 00:05:37"
            )
        if "PRIVCLASS" in uc or "PRIV" in uc:
            held = self._classes or "G"
            lines = [f"PRIVCLASSES FOR {self._userid}: {held}"]
            for c in held:
                if c in CP_CLASS_DESC:
                    lines.append(f"  {c}  {CP_CLASS_DESC[c]}")
            return "\n".join(lines)
        if "SECURITY" in uc or "POSTURE" in uc:
            return self._security_dashboard()
        if "LINK" in uc:
            g = self._dir.get(self._userid)
            if not g or not g.links:
                return "NO MINIDISKS LINKED"
            rows = [f"{ow} {oa} LINKED AS {ma} {md}" for ow, oa, ma, md in g.links]
            return "\n".join(rows)
        if "VSWITCH" in uc or "VSW" in uc:
            rows = [f"VSWITCH {n}  OWNER {v['owner']}  GRANTED: {', '.join(sorted(v['grants'])) or 'NONE'}"
                    for n, v in sorted(self._dir.vswitches.items())]
            return "\n".join(rows) if rows else "NO VSWITCHES DEFINED"
        if "RDR" in uc or "READER" in uc or "SPOOL" in uc:
            files = self._dir.reader_files(self._userid)
            if not files:
                return f"NO RDR FILES FOR {self._userid}"
            rows = [f"ORIGINID FILE  CLASS RECORDS NAME     TYPE"]
            for s in files:
                rows.append(f"{s.origin:<8} {s.spoolid}  A     {s.records:<7} {s.name:<8} {s.ftype}")
            return "\n".join(rows)
        if "MDISK" in uc:
            g = self._dir.get(self._userid)
            disks = g.minidisks if g else {}
            if not disks:
                return f"NO MINIDISKS OWNED BY {self._userid}"
            return "\n".join(f"MDISK {a}  LABEL {md.label}  CYLS {md.cyls}  "
                             f"READ={md.read_pw or 'NONE'} WRITE={md.write_pw or 'NONE'}"
                             for a, md in sorted(disks.items()))
        if "CPLEVEL" in uc or "CPDATA" in uc:
            rel = SYSVER.split(".")
            return (
                f"z/VM Version {rel[0]} Release {'.'.join(rel[1:])}, "
                f"service level {SYSLVL} (64-bit)\n"
                f"Generated at {_us_date()} {t} UTC\n"
                f"IPL at {_us_date()} {t} UTC"
            )
        if "USERID" in uc:
            return f"{self._userid or 'DEMO'} AT {SYSNAME}"
        if "CPUS" in uc or "PROCESSORS" in uc or uc.strip() in ("Q CPU", "QUERY CPU"):
            return ("CPU 00  ID  FF00012345  CPC  MASTER  CPVID NONE\n"
                    "CPU 01  ID  FF00012345  CPC  ALTERNATE")
        if "NAME" in uc or "USER" in uc:
            logged = self._dir.logged_on_users()
            if self._userid and self._userid not in logged:
                logged = [self._userid] + logged
            rows = "  ".join(f"{u} - DSC" if (self._dir.get(u) and self._dir.get(u).disconnected)
                              else f"{u} - 3270" for u in logged)
            return (f"{rows}\n"
                    f"TOTAL USERS LOGGED ON = {len(logged)}")
        if "STOR" in uc:
            return "STORAGE = 2G"
        if "VIRTUAL" in uc or " V " in f" {uc} ":
            return (
                "VIRTUAL STORAGE = 512M\n"
                "CORE 0 SIZE = 1G\n"
                "EXPANDED STORAGE = 2G"
            )
        if "DASD" in uc or "DISK" in uc:
            return (
                "DASD 191 3390 MFT191  R/W  CYL 3339  BLK 555  EXT 1  LABEL SPOOL\n"
                "DASD 192 3390 MFT192  R/O  CYL 1669  BLK 0    EXT 1  LABEL WORK\n"
                "DASD 193 3390 MFT193  R/W  CYL 6669  BLK 0    EXT 1  LABEL PAGE"
            )
        token = cmd.split()[-1] if cmd.split() else ""
        return f"HCPCQV003E Invalid option - {token}\nReady(00003); T=0.01/0.01 {t}"

    # ── CMS mode ──────────────────────────────────────────────────────────────

    def _handle_cms(self, aid: int, cmd: str, raw: str) -> Optional[ScreenBuffer]:
        if aid == AID_PF3:
            self._screen = _CP
            self._last_msg = "Returned to CP from CMS."
            return self._screen_cp(self._last_msg)
        if aid != AID_ENTER or not cmd:
            return self._screen_cms()

        if cmd in ("FILELIST", "FL"):
            self._screen = _FILELIST
            return self._screen_filelist()

        if cmd in ("RDRLIST", "RL"):
            self._screen = _RDRLIST
            return self._screen_rdrlist()

        if cmd.startswith("XEDIT ") or cmd.startswith("X "):
            parts = raw.strip().split(None, 1)
            self._xedit_file = (parts[1] if len(parts) > 1 else "DEMO REXX A").upper()
            self._screen = _XEDIT
            return self._screen_xedit()

        if cmd == "CP":
            self._screen = _CP
            self._last_msg = "CP entered."
            return self._screen_cp(self._last_msg)

        if cmd == "CMS":
            self._last_msg = f"Already in CMS.  Ready; T=0.01/0.01 {_time_str()}"
            return self._screen_cms(self._last_msg)

        if cmd in ("#CP LOGOFF", "LOGOFF"):
            return None

        cms_out = cms_command(self.state, self._userid, raw.strip())
        if cms_out is not None:
            self._last_msg = cms_out
            return self._screen_cms(self._last_msg)
        self._last_msg = f"DMSEXT002S Command not found: {raw.strip()}\nReady(00002); T=0.01/0.01 {_time_str()}"
        return self._screen_cms(self._last_msg)

    # ── FILELIST / RDRLIST navigation ─────────────────────────────────────────

    def _handle_list(self, aid: int) -> ScreenBuffer:
        if aid in (AID_PF3, AID_ENTER, AID_CLEAR):
            self._screen = _CMS
            self._last_msg = f"Ready; T=0.01/0.01 {_time_str()}"
            return self._screen_cms(self._last_msg)
        if self._screen == _FILELIST:
            return self._screen_filelist()
        return self._screen_rdrlist()

    # ── XEDIT navigation ──────────────────────────────────────────────────────

    def _handle_xedit(self, aid: int) -> ScreenBuffer:
        if aid == AID_PF3:
            self._screen = _CMS
            self._last_msg = f"File saved: {self._xedit_file}\nReady; T=0.01/0.01 {_time_str()}"
            return self._screen_cms(self._last_msg)
        return self._screen_xedit()

    # ── Screen builders ───────────────────────────────────────────────────────

    def _oia_bar(self, s: ScreenBuffer, pfkeys: str) -> None:
        """Operator information area — bottom two rows."""
        s.put(23, 1, "-" * 79, colors.BLUE)
        s.put(24, 1, f"RUNNING   {SYSNAME}", colors.WHITE)
        s.put(24, 20, pfkeys, colors.GREEN)

    def _screen_logon(self, message: str = "") -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, f"z/VM  Version {SYSVER}  Service Level {VMID}", colors.WHITE)
        s.put(2, 1, f"{SYSNAME} AT {VMID}", colors.GREEN)
        s.put(3, 1, f"{_date_str()}  {_time_str()}", colors.GREEN)
        s.put(4, 1, "IBM Confidential OCO Source Materials", colors.GREEN)
        s.put(5, 1, "(c) Copyright IBM Corp. 1981, 2023", colors.GREEN)
        s.put(6, 1, "Licensed Material - Program Property of IBM", colors.GREEN)
        s.put(8, 1, "LOGON", colors.WHITE)
        if message:
            s.put(18, 2, message, colors.YELLOW)
        s.put(10, 2, "USERID  ==>", colors.GREEN)
        s.add_field("USERID", 10, 14, 8, protected=False, role="input")
        s.put(11, 2, "PASSWORD==>", colors.GREEN)
        s.add_field("PASSWORD", 11, 14, 8, protected=False, hidden=True, role="input")
        s.put(13, 2, "Command ==>", colors.GREEN)
        s.add_field("COMMAND", 13, 14, 40, protected=False, role="input")
        s.put(15, 2, "Enter LOGON to connect to z/VM.", colors.GREEN)
        s.put(16, 2, "Enter DIAL  to connect to a virtual machine.", colors.GREEN)
        s.put(24, 1, f"RUNNING   {SYSNAME}", colors.WHITE)
        s.put(24, 20, "PF3=Quit", colors.GREEN)
        s.set_cursor(10, 14)
        return s

    def _screen_logon_pw(self, userid: str, message: str = "") -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, f"z/VM  Version {SYSVER}  Service Level {VMID}", colors.WHITE)
        s.put(2, 1, f"{SYSNAME} AT {VMID}", colors.GREEN)
        if message:
            s.put(4, 2, message, colors.YELLOW)
        s.put(6, 2, f"USERID:  {userid}", colors.GREEN)
        s.put(7, 2, "ENTER PASSWORD:", colors.GREEN)
        s.add_field("PASSWORD", 7, 18, 8, protected=False, hidden=True, role="input")
        s.put(24, 1, f"RUNNING   {SYSNAME}", colors.WHITE)
        s.put(24, 20, "PF3=Cancel", colors.GREEN)
        s.set_cursor(7, 18)
        return s

    def _screen_cp(self, message: str = "") -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        uid = self._userid
        s.put(1, 1, f"z/VM CP  {SYSNAME}      {uid:<8} Logged On", colors.WHITE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        lines = [
            f"LOGON AT {_time_str()} {_date_str()}",
            f"z/VM Version {SYSVER}",
            "Your IPL directory entry will be used to IPL CMS.",
            f"Ready; T=0.01/0.01 {_time_str()}",
        ]
        if message:
            lines += [""] + message.split("\n")
        for i, line in enumerate(lines[:16], start=3):
            s.put(i, 2, line[:77], colors.GREEN)
        s.put(21, 1, "-" * 79, colors.BLUE)
        s.put(22, 2, uid, colors.WHITE)
        s.put(22, 11, "CP", colors.GREEN)
        s.add_field("INPUT", 22, 14, 60, protected=False, role="command")
        self._oia_bar(s, "PF3=Logoff  PF12=Retrieve  Enter=Submit")
        s.set_cursor(22, 14)
        return s

    def _screen_cpquery(self, result: str) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, f"CP QUERY RESPONSE  {SYSNAME}", colors.WHITE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        for i, line in enumerate(result.split("\n")[:18], start=3):
            s.put(i, 2, line[:77], colors.GREEN)
        s.put(22, 2, self._userid, colors.WHITE)
        s.put(22, 11, "CP", colors.GREEN)
        s.add_field("INPUT", 22, 14, 60, protected=False, role="command")
        self._oia_bar(s, "Enter=Continue  PF3=CP Ready")
        s.set_cursor(22, 14)
        return s

    def _screen_cms(self, message: str = "") -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        uid = self._userid
        s.put(1, 1, f"z/VM CMS  {SYSNAME}      {uid:<8}", colors.WHITE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        lines = [
            f"IPL CMS",
            f"z/VM CMS Level {SYSVER}  {SYSNAME}",
            f"Ready; T=0.01/0.01 {_time_str()}",
        ]
        if message:
            lines += [""] + message.split("\n")
        for i, line in enumerate(lines[:16], start=3):
            s.put(i, 2, line[:77], colors.GREEN)
        s.put(21, 1, "-" * 79, colors.BLUE)
        s.put(22, 2, uid, colors.WHITE)
        s.put(22, 11, "CMS", colors.GREEN)
        s.add_field("INPUT", 22, 15, 59, protected=False, role="command")
        self._oia_bar(s, "PF3=CP Mode  PF12=Retrieve  Enter=Submit")
        s.set_cursor(22, 15)
        return s

    def _screen_filelist(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        uid = self._userid
        s.put(1, 1, "FILELIST  A0  V 169  Trunc=169 Size=8  Line=1 Col=1 Alt=0", colors.WHITE)
        s.put(2, 1, "Cmd   Filename  Filetype  Fm  Format  Lrecl  Records  Blocks  Date      Time", colors.GREEN)
        s.put(3, 1, "-" * 79, colors.BLUE)
        for i, row in enumerate(_FILELIST_ROWS, start=4):
            s.put(i, 1, row[:79], colors.GREEN)
        s.put(20, 1, "1= Help  2= Refresh  3= Quit  4= Sort(type)  5= Sort(date)  6= Sort(size)", colors.BLUE)
        s.put(21, 1, "-" * 79, colors.BLUE)
        s.put(22, 2, uid, colors.WHITE)
        s.put(22, 11, "FILELIST", colors.GREEN)
        s.add_field("INPUT", 22, 20, 54, protected=False, role="command")
        self._oia_bar(s, "PF3=Quit  PF7=Bkwd  PF8=Fwd  PF12=Cursor")
        s.set_cursor(22, 20)
        return s

    def _screen_rdrlist(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        uid = self._userid
        s.put(1, 1, "RDRLIST   A0  V 108  Trunc=108 Size=3  Line=1 Col=1 Alt=0", colors.WHITE)
        s.put(2, 1, "Cmd   Filename  Filetype  Fm  Origid   Date      Time     Recs  Class Pri Hold", colors.GREEN)
        s.put(3, 1, "-" * 79, colors.BLUE)
        for i, tmpl in enumerate(_RDRLIST_ROWS_TMPL, start=4):
            s.put(i, 1, tmpl.format(uid=uid)[:79], colors.GREEN)
        s.put(20, 1, "1= Help  2= Refresh  3= Quit  4= View  5= Print  6= Receive  9= Purge", colors.BLUE)
        s.put(21, 1, "-" * 79, colors.BLUE)
        s.put(22, 2, uid, colors.WHITE)
        s.put(22, 11, "RDRLIST", colors.GREEN)
        s.add_field("INPUT", 22, 19, 55, protected=False, role="command")
        self._oia_bar(s, "PF3=Quit  PF7=Bkwd  PF8=Fwd")
        s.set_cursor(22, 19)
        return s

    def _screen_xedit(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        fname = self._xedit_file
        s.put(1, 1, f"{fname:<24} V 80  Trunc=80 Size=10 Line=0 Col=1 Alt=0", colors.WHITE)
        s.put(2, 1, "====>", colors.GREEN)
        s.add_field("CMDLINE", 2, 7, 66, protected=False, role="command")
        for i, line in enumerate(_XEDIT_CONTENT, start=3):
            s.put(i, 2, line[:77], colors.GREEN)
        s.put(21, 1, "1= Help  2= Add  3= Quit  4= Tab  5= Cchar  6= ?  7= Bkwd  8= Fwd  9= Repeat", colors.BLUE)
        s.put(22, 1, "10= Rgtleft  11= Spltjoin  12= Power input", colors.BLUE)
        s.put(23, 1, f"XEDIT     {SYSNAME}", colors.WHITE)
        s.put(23, 20, "PF3=Quit  PF7=Bkwd  PF8=Fwd", colors.GREEN)
        s.set_cursor(2, 7)
        return s
