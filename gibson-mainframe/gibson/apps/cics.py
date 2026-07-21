from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional
from collections import deque
import os
import re
from gibson.core.state import GibsonState
from gibson.core.passticket import get_passticket_service
from gibson.render import colors
from gibson.render.input import SocketInputDriver
from gibson.render.screen3270 import ScreenBuffer
from gibson.core.cics_region import get_cics_region, parse_define, REMOVED_CICS_TRANSACTIONS
from gibson.apps.cbsa.cics_session import execute_omen
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.apps.pin_bruteforce import get_active_pin_bruteforce
@dataclass
class CicsResource:
    name: str
    status: str = "ENABLED"
    attrs: Dict[str, str] | None = None
    # Compatibility attributes used by the shared CICS region model.
    # Older CicsSimulator seed records are deliberately still accepted so
    # CEDA INSTALL/CEMT INQUIRE cannot crash when a legacy record is present.
    group: str = "GIBSON"
    rtype: str = "RESOURCE"
    installed: bool = True
    open_state: str = "OPEN"
    def attr(self, key: str, default: str = "") -> str:
        return (self.attrs or {}).get(key, default)
class CicsSimulator:
    """CICS/GICS terminal simulator.
    The original Gibson CICS module was a separate socket routine.  This class
    keeps that transaction style and the uploaded screen assets, but routes it
    through the shared Gibson state and input driver so ``L CICS`` at the VTAM
    logon screen behaves like the old flow again.
    """
    def __init__(self, state: GibsonState, userid: str = "DEFAULT"):
        self.state = state
        self.userid = (userid or "DEFAULT").upper()
        self.signed_on = not state.config.realistic_cics_auth
        self.start_time = datetime.now()
        self.log_path = state.config.sim_root / "cics-simulator.log"
        self.programs: Dict[str, CicsResource] = {
            "DFHWBADX": CicsResource("DFHWBADX", "ENABLED", {"LENGTH": "000184", "USECOUNT": "000000", "RESCOUNT": "000000"}),
            "DFH0XCMN": CicsResource("DFH0XCMN", "ENABLED", {"LENGTH": "004096", "USECOUNT": "000003", "RESCOUNT": "000001"}),
            "MYPROG": CicsResource("MYPROG", "ENABLED", {"LENGTH": "000123", "USECOUNT": "000001", "RESCOUNT": "000000"}),
            "DEMO001": CicsResource("DEMO001", "DISABLED", {"LENGTH": "000456", "USECOUNT": "000000", "RESCOUNT": "000000"}),
        }
        self.files: Dict[str, CicsResource] = {
            "FILEA": CicsResource("FILEA", "OPEN ENABLED", {"DSN": "DATA.FILEA", "TYPE": "KSDS", "READ": "YES", "UPDATE": "YES"}),
            "FILEB": CicsResource("FILEB", "CLOSED ENABLED", {"DSN": "DATA.FILEB", "TYPE": "ESDS", "READ": "YES", "UPDATE": "NO"}),
            "GACFDB": CicsResource("GACFDB", "OPEN ENABLED", {"DSN": "SYS1.RACFDS", "TYPE": "KSDS", "READ": "YES", "UPDATE": "NO"}),
        }
        self.transactions: Dict[str, CicsResource] = {
            "CESN": CicsResource("CESN", "ENABLED", {"PROGRAM": "DFHSNP", "TASKDATALOC": "ANY"}),
            "CESF": CicsResource("CESF", "ENABLED", {"PROGRAM": "DFHSFP", "TASKDATALOC": "ANY"}),
            "CEMT": CicsResource("CEMT", "ENABLED", {"PROGRAM": "DFHEMTP", "TASKDATALOC": "ANY"}),
            "CEDA": CicsResource("CEDA", "ENABLED", {"PROGRAM": "DFHEDAP", "TASKDATALOC": "ANY"}),
            "CECI": CicsResource("CECI", "ENABLED", {"PROGRAM": "DFHECIP", "TASKDATALOC": "ANY"}),
            "CEBR": CicsResource("CEBR", "ENABLED", {"PROGRAM": "DFHBRP", "TASKDATALOC": "BELOW"}),
            "CEDF": CicsResource("CEDF", "ENABLED", {"PROGRAM": "DFHEDF", "TASKDATALOC": "ANY"}),
        }
        self.terminal_resources: Dict[str, CicsResource] = {
            "LU320": CicsResource("LU320", "INSERVICE ACQUIRED", {"NETNAME": "LU320", "USERID": self.userid}),
            "T0001": CicsResource("T0001", "INSERVICE RELEASED", {"NETNAME": "TCP0001", "USERID": ""}),
        }
        self.connections: Dict[str, CicsResource] = {
            "DB2A": CicsResource("DB2A", "INSERVICE", {"NETNAME": "DB2A", "ACCESSMETHOD": "IRC"}),
            "TCPIP": CicsResource("TCPIP", "INSERVICE", {"NETNAME": "TCPIP", "ACCESSMETHOD": "TCPIP"}),
        }
        # Shared CICS region model.  This is additive: existing CicsSimulator
        # attributes remain available, but resource state now persists across
        # simulator instances using the shared Gibson state object.
        self.region = get_cics_region(state)
        self.programs = self.region.programs
        self.files = self.region.files
        self.transactions = self.region.transactions
        self.terminal_resources = self.region.terminals
        self.bank_demo_admin = os.getenv("GIBSON_CICS_BANK_DEMO_ADMIN", "0") in ("1", "true", "TRUE")
        # FIBS/CICSLAB/old GMVB remain removed. DVCA is now reintroduced
        # as a clean source-informed vulnerable CICS training subsystem.
        self.bank_authenticated = False
        self.bank_userid = ""
        self.bank_current = "LOGN"
        self.bank_prev = "LOGN"
        self.bank_status = "BANKING APPS REMOVED FROM GOLDEN BASELINE"
        self.bank_last_item = ""
        self.cbsa_active = False
        self.dvca_active = False
        self.panel_state = ""
        self.panel_breadcrumb = []

        self.bank_items: Dict[str, dict[str, str]] = {
            "00001": {"item_number": "00001", "item_name": "STEEL FASTENER CRATE", "price": "129.99", "shipping_cost": "18.00", "purchasable": "Y", "order_supply": "Y", "comments": "STANDARD INDUSTRIAL STOCK"},
            "00002": {"item_number": "00002", "item_name": "LAB SENSOR ARRAY", "price": "899.00", "shipping_cost": "42.50", "purchasable": "Y", "order_supply": "N", "comments": "EXPORT REVIEW REQUIRED"},
            "04242": {"item_number": "04242", "item_name": "ARCHIVE TRANSIT CASE", "price": "59.95", "shipping_cost": "12.00", "purchasable": "N", "order_supply": "Y", "comments": "INTERNAL USE ONLY"},
        }
        self.bank_orders: list[dict[str, str]] = [
            {"index": "00001", "date": "04/18/26", "name": "STEEL FASTENER CRATE", "price": "129.99", "shipping": "18.00", "item_number": "00001"},
            {"index": "00002", "date": "04/19/26", "name": "LAB SENSOR ARRAY", "price": "899.00", "shipping": "42.50", "item_number": "00002"},
        ]
        self.bank_form_values: dict[str, str] = {}
        self.bank_focus: int = 0
    # ------------------------------------------------------------------
    # Asset / panel helpers
    # ------------------------------------------------------------------
    def _asset(self, name: str, fallback: str = "") -> str:
        text = self.state.templates.render(name, self.userid, "SPECIAL" if self._is_special() else "NONE")
        return text if text is not None else fallback
    def _panel(self, title: str, body: Iterable[str], status: str = "") -> str:
        lines = [colors.CLEAR]
        if status:
            lines.append(f"{status[:79]:<79}\n")
        else:
            lines.append(f"{'':79}\n")
        lines.append(f"{title[:79]:<79}\n")
        lines.append(" " * 79 + "\n")
        for line in body:
            lines.append(f"{line[:79]:<79}\n")
        while len(lines) < 22:
            lines.append(" " * 79 + "\n")
        lines.append("PF 1 HELP       3 END       5 VAR       6 CRSR       9 MSG       12 CNCL\n")
        return "".join(lines)
    def _is_special(self) -> bool:
        user = self.state.racf.get(self.userid)
        return bool(user and user.special)
    def _log(self, message: str) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {self.userid} {message}\n")
        except Exception:
            pass
    # ------------------------------------------------------------------
    # Non-interactive compatibility API used by TSO and tests
    # ------------------------------------------------------------------
    def execute(self, command: str) -> str:
        cmd = (command or "").strip()
        uc = cmd.upper()
        self._log(uc)
        if not uc and not getattr(self, "dvca_active", False) and not getattr(self, "cbsa_active", False):
            return ""
        if uc and uc.split()[0] in {"FIBS", "GMVB", "CICSLAB1", "BLAB", "CICSLAB", "HACK3270"}:
            return "DFHCE3551 COMMAND NOT RECOGNIZED."
        if uc and uc.split()[0] in {"OMEN", "CBSA"}:
            self.dvca_active = False
        if getattr(self, "dvca_active", False) and uc in {"PF3", "F3", "END", "QUIT"}:
            self.dvca_active = False
            return self.help_screen()
        if getattr(self, "dvca_active", False):
            return execute_dvca(self.state, self.userid, cmd)
        if getattr(self, "cbsa_active", False) and uc and uc.split()[0] in {"DVCA", "MCGM", "MCMM", "MCOR", "MCAD", "MCHI", "MCHS", "SCRT", "CEDF", "CECI", "CEBR", "CEMT", "CEDA", "CSMT"}:
            self.cbsa_active = False
        if getattr(self, "cbsa_active", False) and uc in {"PF3", "F3", "END", "MENU"}:
            self.cbsa_active = False
            return self.help_screen()
        if getattr(self, "cbsa_active", False):
            cbsa_cmd = cmd
            if uc and uc.split()[0] in {"OMEN", "CBSA"}:
                cbsa_cmd = cmd.split(maxsplit=1)[1] if len(cmd.split(maxsplit=1)) > 1 else "OMEN"
            out = execute_omen(self.state, self.userid, cbsa_cmd or uc)
            if isinstance(out, str) and out.startswith("GIBSON_CICS_ROUTE:"):
                self.cbsa_active = False
                return self.execute(out.split(":", 1)[1])
            return out
        if self.panel_state:
            panel_out = self._operation_panel(cmd)
            if panel_out is not None:
                return panel_out
        if uc in ("HELP", "?"):
            return self.help_screen()
        if uc in ("F10", "PF10", "INSTRUCTIONS", "INSTR"):
            return self.instructions_screen()
        if uc in {"3", "OPER", "OPERATOR", "CICSOP", "CICS OPERATOR"}:
            self.panel_state = "CICS_OPERATOR_MAIN"
            return self.operator_menu()
        if uc.startswith("SECURITY") or uc.startswith("SMF EVENTS") or uc in {"12", "CICS SMF"}:
            return self.security_smf_events()
        if uc in {"CICS RESOURCE STATUS", "CICS STATUS", "CICS RESOURCES", "RESOURCE STATUS"}:
            return self._cics_resource_status_panel()
        if uc in {"DB2 ACTIVITY", "CICS DB2", "DB2 CONNECTION", "DB2CONN STATUS"}:
            return self._db2_activity_panel()
        if uc in {"13", "DVCA LAB CONTROL"}:
            return self.dvca_lab_control()
        if uc in ("CICS DISPLAY SECURITY", "CICS DISPLAY SIT", "D CICS,SECURITY", "D CICS,SIT"):
            return "\n".join(self.region.security_status_lines())
        if uc in {"CICS RECON", "CICS FINGERPRINT", "CICS HACK3270 RECON", "ESM FINGERPRINT", "CICS ESM"}:
            return self._cics_attack_surface_panel()
        if uc.split()[0] in {"IND$FILE", "INDSFILE", "IND\\$FILE"} or uc.startswith("IND$FILE"):
            return self._indfile_intercept(cmd)
        if uc.startswith("CICS SET SIT"):
            return self._cics_set_sit(cmd)
        if uc == "CICS SECURITY REFRESH":
            self._audit_stage("CICS SECURITY REFRESH", "SECURITY CACHE REFRESHED", transid="CEMT", cls="OPERCMDS")
            return "DFHXS1201 CICS SECURITY REFRESH COMPLETE"
        if uc.startswith("CICS AUTH") or uc.startswith("CICS LOGON") or uc.startswith("CICS PASSWORD") or uc.startswith("CICS SIGNON"):
            arg = uc.split()[-1] if len(uc.split()) >= 3 else "STATUS"
            cur = bool(self.state.config.realistic_cics_auth)
            if arg in ("ON", "YES", "ENABLE", "ENABLED"):
                self.state.config.realistic_cics_auth = True
                self.signed_on = False
                self._audit_stage("CICS SIGNON POLICY", "CICS terminal sign-on requirement ENABLED (password logon ON)", transid="CEMT", cls="OPERCMDS", result="WARNING")
                return "DFHCE3551 CICS SIGN-ON REQUIRED IS NOW ON. NEW SESSIONS MUST CESN BEFORE RUNNING TRANSACTIONS."
            if arg in ("OFF", "NO", "DISABLE", "DISABLED"):
                self.state.config.realistic_cics_auth = False
                self.signed_on = True
                self._audit_stage("CICS SIGNON POLICY", "CICS terminal sign-on requirement DISABLED (password logon OFF)", transid="CEMT", cls="OPERCMDS")
                return "DFHCE3552 CICS SIGN-ON REQUIRED IS NOW OFF. TERMINALS RUN UNDER THE DEFAULT USER."
            return f"DFHCE3550 CICS SIGN-ON REQUIRED IS CURRENTLY {'ON' if cur else 'OFF'}. USE: CICS AUTH ON | CICS AUTH OFF."
        if uc.startswith("CESN"):
            m_pt = re.search(r"USER\(([^)]+)\).*PTKT\(([^)]+)\)(?:.*APPL\(([^)]+)\))?", cmd, re.I)
            if m_pt:
                user = m_pt.group(1).strip().upper()
                ticket = m_pt.group(2).strip().upper()
                appl = (m_pt.group(3) or "CICS").strip().upper()
                result = get_passticket_service(self.state).validate(user, appl, ticket, consumer="CICS-CESN")
                if result.get("ok"):
                    self.userid = user
                    self.signed_on = True
                    self.region.signon(user)
                    return f"DFHCE3548 USERID {user} SIGNED ON SUCCESSFULLY WITH PASSTICKET FOR {appl}."
                self.state.record_security_event(user, "SIGNON", str(result.get('message', 'PASSTICKET REJECTED')), result="FAILURE", service="CICS")
                return f"DFHCE3520 SIGN-ON FAILED: {result.get('message', 'PASSTICKET REJECTED')}"
            self.signed_on = True
            self.region.signon(self.userid)
            return f"DFHCE3548 USERID {self.userid} SIGNED ON SUCCESSFULLY."
        if self.state.config.realistic_cics_auth and not self.signed_on:
            return "DFHCE3549 SIGN-ON REQUIRED. ENTER CESN."
        if uc in ("CESF", "CESF LOGOFF", "LOGOFF", "SIGNOFF", "EXIT"):
            self.signed_on = False
            self.region.signoff(self.userid)
            return self._asset("CESF.txt", "DFHCE3590 Sign-off is complete.")
        if uc == "CEMT":
            ok, msg = self._tx_allowed("CEMT", corrid=self._cics_corrid("CEM"))
            if ok:
                self.panel_state = "CEMT_MAIN"
                return self.cemt_menu()
            return msg
        if uc == "CEDA":
            ok, msg = self._tx_allowed("CEDA", corrid=self._cics_corrid("CED"))
            if ok:
                self.panel_state = "CEDA_MAIN"
                return self.ceda_menu()
            return msg
        if uc == "CECI":
            ok, msg = self._tx_allowed("CECI", corrid=self._cics_corrid("CEC"))
            if ok:
                self.panel_state = "CECI_MAIN"
                return self.ceci_menu()
            return msg
        if uc.startswith("CEMT"):
            ok, msg = self._tx_allowed("CEMT", corrid=self._cics_corrid("CEM"))
            return self._cemt(cmd) if ok else msg
        if uc.startswith("CEDA"):
            ok, msg = self._tx_allowed("CEDA", corrid=self._cics_corrid("CED"))
            return self._ceda(cmd) if ok else msg
        if uc.startswith("CECI"):
            ok, msg = self._tx_allowed("CECI", corrid=self._cics_corrid("CEC"))
            return self._ceci(cmd) if ok else msg
        alias = self.region.alias_target(uc.split()[0]) if uc.split() else ""
        if alias:
            head = uc.split()[0]
            rest = cmd[len(head):].strip()
            routed = f"{alias} {rest}".strip()
            self._audit_stage("CICS RACF BYPASS USE",
                              f"unprotected alias {head} ran {alias} {rest} bypassing transaction security",
                              transid=head, resource=alias, cls="TCICSTRN", result="WARNING")
            self.region.add_log("WARNING", head, self.userid,
                                f"unprotected alias {head} dispatched to {alias} (cicspwn RACF bypass)",
                                corrid=self._cics_corrid("BYP"))
            if alias == "CEMT":
                return self._cemt(routed)
            if alias == "CECI":
                return self._ceci(routed)
            if alias == "CEDA":
                return self._ceda(routed)
            if alias == "CEBR":
                return self.cebr(routed)
            if alias == "CEDF":
                return self._cedf(routed)
        if uc.startswith("CEBR"):
            return self.cebr(cmd)
        if uc.startswith("CEDF"):
            return self._cedf(cmd)
        if uc.startswith("CSMT"):
            return self.csmt(cmd)
        if uc.startswith("CESL") or uc.startswith("CMSG"):
            return self.cesl()
        if uc.startswith("CICSPWN") or uc.startswith("PWNPROBE"):
            return self.cicspwn_report()
        if uc.startswith("PWNSCAN") or uc.startswith("CICS PWNSCAN") or uc.startswith("PWNDETECT"):
            return self.cicspwn_detection()
        if uc.split()[0] in {"DVCA", "MCGM", "MCMM", "MCOR", "MCAD", "MCHI", "MCHS", "SCRT"}:
            self.dvca_active = True
            self.region.start_task("DVCA", "MCSTART", self.userid)
            return execute_dvca(self.state, self.userid, uc.split()[0])
        if uc.split()[0] in {"OMEN", "CBSA"}:
            ok, msg = self._tx_allowed("OMEN", corrid=self._cics_corrid("OMN"))
            if not ok:
                return msg
            self.cbsa_active = True
            self.region.start_task("OMEN", "BNKMENU", self.userid)
            rest = cmd.split(maxsplit=1)[1] if len(cmd.split(maxsplit=1)) > 1 else "OMEN"
            out = execute_omen(self.state, self.userid, rest if rest != "OMEN" else "OMEN")
            if isinstance(out, str) and out.startswith("GIBSON_CICS_ROUTE:"):
                self.cbsa_active = False
                return self.execute(out.split(":", 1)[1])
            if getattr(self.region, "trace_enabled_for", "") in {"OMEN", "*"}:
                self.region.traces["OMEN"] = ["RECEIVE MAP(BNKMENU)", "LINK PROGRAM(BNKMENU)", "SEND MAP(BNKMENU)", "RETURN TRANSID(OMEN)"]
            return out
        if uc.split()[0] in {"FIBS", "GMVB", "CICSLAB1", "BLAB", "CUST", "ACCT", "CUSA", "CUSU", "CUSD", "ACCA", "ACCU", "ACCD", "XFER", "DBCR", "BATCH", "SWFT", "APIM", "HACK3270"}:
            return "DFHCE3551 COMMAND NOT RECOGNIZED."
        if uc in self.transactions:
            return f"DFHAC2206 {uc} TRANSACTION STARTED.  NORMAL COMPLETION."
        return "DFHCE3551 COMMAND NOT RECOGNIZED."
    # ------------------------------------------------------------------
    # Main terminal session for L CICS
    # ------------------------------------------------------------------
    def run_terminal(self, input_driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        banner = self._asset("cics-screen.txt", self._asset("cics-screen.ttx.txt", "WELCOME TO GICS\n"))
        send(colors.CLEAR + colors.BLUE + banner + colors.RESET + "\n")
        # This reproduces the old behaviour: banner first, ENTER to arrive at CICS command line.
        res = input_driver.read_line()
        if res.key == "EOF":
            return
        while True:
            # Active DVCA/OMEN brute-force sessions auto-advance roughly once
            # per second.  Use a bounded input timeout so ENTER is no longer
            # required to progress the animation, while still allowing PF3/PF12
            # or typed commands to interrupt/cancel.
            auto_app = ""
            if getattr(self, "dvca_active", False) and get_active_pin_bruteforce(self.state, self.userid, "DVCA MCAD") is not None:
                auto_app = "DVCA"
            elif getattr(self, "cbsa_active", False) and get_active_pin_bruteforce(self.state, self.userid, "CBSA OMEN") is not None:
                auto_app = "OMEN"
            res = input_driver.read_line("===> ", timeout=1.05 if auto_app else None)
            key = res.key or ""
            cmd = res.text.strip()
            if key == "TIMEOUT" and auto_app:
                key = ""
                cmd = ""
            uc = (key or cmd).upper()
            if uc in ("EXIT", "LOGOFF", "SIGNOFF", "CESF") or (uc in ("F3", "PF3") and not (getattr(self, "dvca_active", False) or getattr(self, "cbsa_active", False) or self.panel_state)):
                send(colors.CLEAR + colors.BLUE + self.execute("CESF") + colors.RESET + "\n")
                return
            if uc in ("F1", "PF1", "HELP", "?"):
                send(colors.CLEAR + colors.BLUE + self.help_screen() + colors.RESET + "\n")
                continue
            if uc in ("F10", "PF10", "INSTRUCTIONS", "INSTR"):
                send(colors.CLEAR + colors.BLUE + self.instructions_screen() + colors.RESET + "\n")
                continue
            effective = key or cmd
            try:
                self.state.audit.record(self.userid, effective, "ENTER", "CICS")
            except Exception:
                pass
            if getattr(self, "dvca_active", False) and key:
                output = execute_dvca(self.state, self.userid, cmd, aid=key, event=res.event)
            elif getattr(self, "cbsa_active", False) and key:
                output = execute_omen(self.state, self.userid, key)
            elif res.event is not None and self.panel_state:
                panel_out = self.handle_terminal_event(res.event)
                output = panel_out if panel_out is not None else self.execute(effective)
            else:
                output = self.execute(effective)
            send(colors.CLEAR + colors.BLUE + output + colors.RESET + "\n")
    # ------------------------------------------------------------------
    # CICS supplied transaction style panels/actions
    # ------------------------------------------------------------------
    def _cics_corrid(self, prefix: str = "CIC") -> str:
        return self.region.corrid(prefix) if hasattr(self, "region") else f"{prefix}-LOCAL"

    def _tx_allowed(self, transid: str, *, access: str = "READ", corrid: str = "") -> tuple[bool, str]:
        if not hasattr(self, "region"):
            return True, ""
        return self.region.check_transaction(self.userid, transid, access=access, corrid=corrid)

    def _file_allowed(self, file_name: str, *, access: str = "READ", transid: str = "", corrid: str = "") -> tuple[bool, str]:
        if not hasattr(self, "region"):
            return True, ""
        return self.region.check_file(self.userid, file_name, access=access, transid=transid, corrid=corrid)

    def _audit_stage(self, event: str, detail: str, *, result: str = "SUCCESS", transid: str = "", resource: str = "", cls: str = "CICS", corrid: str = "") -> None:
        if hasattr(self, "region"):
            self.region.record_security(self.userid, event, detail, result=result, transid=transid, resource=resource, cls=cls, profile=resource or transid or self.region.applid, corrid=corrid)

    def _gmvb_service_execute(self, command: str) -> str:
        # Removed from golden baseline: GMVB/FIBS web-banking service.
        return "DFHCE3551 COMMAND NOT RECOGNIZED."

    def help_screen(self) -> str:
        return self._panel(
            "DFHCE3590 HELP - AVAILABLE GIBSON/CICS TRANSACTIONS",
            [
                "  CESN  - SIGNON TO CICS",
                "  CESF  - SIGNOFF",
                "  CEMT  - MASTER TERMINAL INQUIRE/SET/PERFORM/DISCARD",
                "  CEDA  - RESOURCE DEFINITION ONLINE",
                "  CECI  - COMMAND LEVEL INTERPRETER",
                "  CEBR  - TEMPORARY STORAGE BROWSE",
                "  CEDF  - EXECUTION DIAGNOSTIC FACILITY",
                "  CESL  - GIBSON CICS LOG DISPLAY",
                "  OMEN  - CBSA CICS BANKING SAMPLE APPLICATION",
                "  DVCA  - DAMN VULNERABLE CICS APPLICATION",
                "",
                "  EXAMPLES:",
                "    CEMT I FILE",
                "    CEMT I PROG",
                "    CEMT SET PROGRAM(MYPROG) ENABLED",
                "    CEDA DISPLAY PROGRAM",
                "    CECI SEND TEXT('HELLO')",
            ],
        )

    def instructions_screen(self) -> str:
        return self._panel(
            "CICS INSTRUCTIONS - GIBSON TRAINING GUIDE",
            [
                "DVCA: vulnerable CICS/BMS shopping app. Use HACK ON for field tamper labs.",
                "  HACK ON exposes protected/hidden training fields; BUY/PRICE edits repaint on ENTER.",
                "CBSA/OMEN: banking sample with CBPP pre-authentication and COBOL/CICS flaws.",
                "CBPP: GACF signon panel; PA1/PA3 escape is vulnerable-mode training only.",
                "CEMT/CEDA/CECI/CEDF/CEBR/CSMT: supplied transaction simulations for CICS education.",
                "Vulns: protected field trust, COMMAREA state trust, length mismatch, RECEIVE MAP,",
                "       business logic bypass, debug leakage, sensitive logging and simulated ASRA.",
                "Evidence: CICS log, SDSF/SMF, zSecure, dashboard and master console alerts.",
                "Safety: all behaviours are resettable Gibson simulations; no host exploit is executed.",
                "",
                "PF3/PF12 return. Type HELP for command list.",
            ],
            "PF10 INSTRUCTIONS",
        )

    def build_fielded_panel(self, panel_state: str | None = None) -> ScreenBuffer:
        """Build a field-registered Operation CICS panel for AID/frame tests."""
        state = (panel_state or self.panel_state or "CICS_OPERATOR_MAIN").upper()
        titles = {
            "CICS_OPERATOR_MAIN": "OPERATION CICS - CICS OPERATOR FUNCTIONS",
            "CEMT_MAIN": "CEMT - MASTER TERMINAL",
            "CEMT_INQUIRE": "CEMT INQUIRE",
            "CEMT_SET": "CEMT SET",
            "CEMT_PERFORM": "CEMT PERFORM",
            "CEMT_DISCARD": "CEMT DISCARD",
            "CEDA_MAIN": "CEDA - RESOURCE DEFINITION ONLINE",
            "CEDA_DISPLAY": "CEDA DISPLAY",
            "CEDA_DEFINE": "CEDA DEFINE",
            "CECI_MAIN": "CECI - COMMAND LEVEL INTERPRETER",
            "CEBR_MAIN": "CEBR - TEMPORARY STORAGE BROWSE",
            "CEDF_MAIN": "CEDF - EXECUTION DIAGNOSTIC FACILITY",
            "CSMT_MAIN": "CSMT - MESSAGE LOG",
            "SECURITY_SMF_MAIN": "SECURITY / SMF EVENTS",
            "DB2_SQL_ACTIVITY": "DB2 CONNECTION / SQL ACTIVITY",
            "DVCA_LAB_CONTROL": "DVCA LAB CONTROL",
            "CBSA_OMEN_STATUS": "CBSA / OMEN STATUS",
        }
        options = {
            "CICS_OPERATOR_MAIN": [("1","CEMT Master Terminal"),("2","CEDA Resource Definition"),("3","CECI Command Interpreter"),("4","CEDF Trace Facility"),("5","CEBR TS/TD Queue Browse"),("6","CSMT Message Log"),("7","Security / SMF Events"),("8","DB2 Connection / SQL Activity"),("9","CICS Resource Status"),("10","DVCA Lab Control"),("11","CBSA / OMEN Status")],
            "CEMT_MAIN": [("1","INQUIRE"),("2","SET"),("3","PERFORM"),("4","DISCARD")],
            "CEMT_INQUIRE": [("1","SYSTEM"),("2","TRANSACTION"),("3","PROGRAM"),("4","TASK"),("5","FILE"),("6","CONNECTION"),("7","TERMINAL"),("8","DB2CONN"),("9","TSQUEUE"),("10","TDQUEUE"),("11","SECURITY")],
            "CEMT_SET": [("1","TRANSACTION"),("2","PROGRAM"),("3","FILE"),("4","TASK PURGE"),("5","SECURITY")],
            "CEDA_MAIN": [("1","DISPLAY"),("2","DEFINE"),("3","INSTALL"),("4","CHECK"),("5","DELETE")],
            "CEDA_DISPLAY": [("1","PROGRAM"),("2","FILE"),("3","TRANSACTION")],
            "CEDA_DEFINE": [("1","PROGRAM"),("2","TRANSACTION"),("3","FILE")],
            "CECI_MAIN": [("1","READ FILE"),("2","WRITE FILE"),("3","WRITEQ TS"),("4","READQ TS"),("5","DELETEQ TS"),("6","WRITEQ TD"),("7","READQ TD"),("8","LINK PROGRAM"),("9","XCTL PROGRAM"),("10","SEND TEXT"),("11","ABEND")],
        }.get(state, [])
        s = ScreenBuffer()
        # Emit genuine 3270 field attributes (SFE) so a real terminal (c3270)
        # sees the OPTION field as an actual modifiable field.  Without this the
        # whole screen is one default field and typed options never map back to
        # the OPTION field on ENTER.
        s.extended_attributes = True
        s.bound_input_fields = True
        s.put(1, 1, titles.get(state, state)[:79], colors.BLUE)
        s.put(3, 1, "Option ===>", colors.BLUE)
        s.add_field("OPTION", 3, 13, 12, value="", protected=False, color=colors.RED, role="cics_option", tab_order=1)
        row = 5
        for num, label in options:
            s.put(row, 3, f"{num:>3}  {label}"[:76], colors.TURQUOISE)
            row += 1
        s.put(22, 1, "Direct commands still work: CEMT I CONNECTION, CEMT I TSQUEUE, CECI WRITEQ TS", colors.WHITE)
        s.put(24, 1, "PF3=Back  PF5=Operator Menu  PF7=Up  PF8=Down  ENTER=Submit", colors.BLUE)
        s.set_cursor_field("OPTION")
        return s

    def handle_terminal_event(self, event) -> str | None:
        """Contextual AID/field dispatch for Operation CICS panels."""
        if event is None:
            return None
        if getattr(event, 'is_pf', lambda n: False)(3):
            return self._operation_panel('PF3') if self.panel_state else None
        if getattr(event, 'is_pf', lambda n: False)(5):
            self.panel_state = 'CICS_OPERATOR_MAIN'
            return self.operator_menu()
        fields = getattr(event, 'fields_by_name', {}) or {}
        option = ''
        for k, v in fields.items():
            if k.upper() in {'OPTION','COMMAND'}:
                option = v.strip(); break
        if not option:
            option = getattr(event, 'primary_command', lambda: '')()
        if option and self.panel_state:
            return self._operation_panel(option)
        if option:
            return self.execute(option)
        return None

    def operator_menu(self) -> str:
        return self._panel_menu("OPERATION CICS - CICS OPERATOR FUNCTIONS", [("1","CEMT Master Terminal"),("2","CEDA Resource Definition"),("3","CECI Command Interpreter"),("4","CEDF Trace Facility"),("5","CEBR TS/TD Queue Browse"),("6","CSMT Message Log"),("7","Security / SMF Events"),("8","DB2 CONNECTION / SQL ACTIVITY"),("9","CICS RESOURCE STATUS"),("10","DVCA LAB CONTROL"),("11","CBSA / OMEN STATUS"),("12","Help")], ["Direct commands still work: CEMT INQUIRE SYSTEM, CEMT I CONNECTION, CEMT I TSQUEUE, CECI WRITEQ TS."])


    def _panel_menu(self, title: str, options: list[tuple[str, str]], extra: list[str] | None = None) -> str:
        body = [f"{num:>3}  {label}" for num, label in options]
        body += ["", "Enter option number/name. PF3=BACK PF5=OPERATOR MENU HELP=context help"]
        if extra: body += [""] + extra
        return self._panel(title, body)

    def _operation_panel(self, cmd: str) -> str | None:
        uc = (cmd or "").strip().upper()
        if not self.panel_state:
            return None
        if uc in {"PF3","F3","BACK"}:
            self.panel_state = "CICS_OPERATOR_MAIN"
            return self.operator_menu()
        if uc in {"PF5","F5","MENU"}:
            self.panel_state = "CICS_OPERATOR_MAIN"
            return self.operator_menu()
        maps = {
            "CICS_OPERATOR_MAIN": {"1":"CEMT", "CEMT":"CEMT", "2":"CEDA", "CEDA":"CEDA", "3":"CECI", "CECI":"CECI", "4":"CEDF", "CEDF":"CEDF", "5":"CEBR", "CEBR":"CEBR", "6":"CSMT", "CSMT":"CSMT", "7":"SECURITY", "SECURITY":"SECURITY", "8":"DB2", "DB2":"DB2", "9":"STATUS", "STATUS":"STATUS", "10":"DVCA", "13":"DVCA", "DVCA":"DVCA", "11":"CBSA", "CBSA":"CBSA"},
            "CEMT_MAIN": {"1":"CEMT_INQUIRE","INQUIRE":"CEMT_INQUIRE","I":"CEMT_INQUIRE","2":"CEMT_SET","SET":"CEMT_SET","3":"CEMT_PERFORM","PERFORM":"CEMT_PERFORM","4":"CEMT_DISCARD","DISCARD":"CEMT_DISCARD"},
            "CEMT_INQUIRE": {"1":"CEMT I SYSTEM", "SYSTEM":"CEMT I SYSTEM", "2":"CEMT I TRANSACTION", "TRANSACTION":"CEMT I TRANSACTION", "TRAN":"CEMT I TRANSACTION", "3":"CEMT I PROGRAM", "PROGRAM":"CEMT I PROGRAM", "PROG":"CEMT I PROGRAM", "4":"CEMT I TASK", "TASK":"CEMT I TASK", "5":"CEMT I FILE", "FILE":"CEMT I FILE", "6":"CEMT I CONNECTION", "CONNECTION":"CEMT I CONNECTION", "7":"CEMT I TERMINAL", "TERMINAL":"CEMT I TERMINAL", "8":"CEMT I DB2CONN", "DB2CONN":"CEMT I DB2CONN", "9":"CEMT I TSQUEUE", "TSQUEUE":"CEMT I TSQUEUE", "TSQ":"CEMT I TSQUEUE", "10":"CEMT I TDQUEUE", "TDQUEUE":"CEMT I TDQUEUE", "TDQ":"CEMT I TDQUEUE", "11":"CEMT I SECURITY", "SECURITY":"CEMT I SECURITY"},
            "CEMT_SET": {"1":"CEMT SET TRANSACTION(DVCA) ENABLED", "TRANSACTION":"CEMT SET TRANSACTION(DVCA) ENABLED", "2":"CEMT SET PROGRAM(MYPROG) NEWCOPY", "PROGRAM":"CEMT SET PROGRAM(MYPROG) NEWCOPY", "3":"CEMT SET FILE(FILEA) OPEN", "FILE":"CEMT SET FILE(FILEA) OPEN", "4":"CEMT SET TASK(000001) PURGE", "TASK":"CEMT SET TASK(000001) PURGE", "5":"CEMT SET SECURITY ON", "SECURITY":"CEMT SET SECURITY ON"},
            "CEMT_PERFORM": {"1":"CEMT PERFORM STATISTICS", "STATISTICS":"CEMT PERFORM STATISTICS", "2":"CEMT PERFORM DUMP", "DUMP":"CEMT PERFORM DUMP", "3":"CEMT PERFORM SHUTDOWN", "SHUTDOWN":"CEMT PERFORM SHUTDOWN"},
            "CEMT_DISCARD": {"1":"CEMT DISCARD PROGRAM(MYPROG)", "PROGRAM":"CEMT DISCARD PROGRAM(MYPROG)"},
            "CEDA_MAIN": {"1":"CEDA_DISPLAY", "DISPLAY":"CEDA_DISPLAY", "2":"CEDA_DEFINE", "DEFINE":"CEDA_DEFINE", "3":"CEDA INSTALL GROUP(GIBSON)", "INSTALL":"CEDA INSTALL GROUP(GIBSON)", "4":"CEDA CHECK", "CHECK":"CEDA CHECK", "5":"CEDA DELETE", "DELETE":"CEDA DELETE"},
            "CEDA_DISPLAY": {"1":"CEDA DISPLAY PROGRAM", "PROGRAM":"CEDA DISPLAY PROGRAM", "2":"CEDA DISPLAY FILE", "FILE":"CEDA DISPLAY FILE", "3":"CEDA DISPLAY TRANSACTION", "TRANSACTION":"CEDA DISPLAY TRANSACTION"},
            "CEDA_DEFINE": {"1":"CEDA DEFINE PROGRAM(TESTPGM)", "PROGRAM":"CEDA DEFINE PROGRAM(TESTPGM)", "2":"CEDA DEFINE TRANSACTION(TST1) PROGRAM(TESTPGM)", "TRANSACTION":"CEDA DEFINE TRANSACTION(TST1) PROGRAM(TESTPGM)", "3":"CEDA DEFINE FILE(TESTFILE)", "FILE":"CEDA DEFINE FILE(TESTFILE)"},
            "CECI_MAIN": {"1":"CECI READ FILE(CBSACUST) RIDFLD(1001)", "READ FILE":"CECI READ FILE(CBSACUST) RIDFLD(1001)", "2":"CECI WRITE FILE(CBSAACC)", "WRITE FILE":"CECI WRITE FILE(CBSAACC)", "3":"CECI WRITEQ TS QUEUE(TEST) FROM('HELLO')", "WRITEQ TS":"CECI WRITEQ TS QUEUE(TEST) FROM('HELLO')", "4":"CECI READQ TS QUEUE(TEST)", "READQ TS":"CECI READQ TS QUEUE(TEST)", "5":"CECI DELETEQ TS QUEUE(TEST)", "DELETEQ TS":"CECI DELETEQ TS QUEUE(TEST)", "6":"CECI WRITEQ TD QUEUE(CSMT) FROM('HELLO')", "WRITEQ TD":"CECI WRITEQ TD QUEUE(CSMT) FROM('HELLO')", "7":"CECI READQ TD QUEUE(CSMT)", "READQ TD":"CECI READQ TD QUEUE(CSMT)", "8":"CECI LINK PROGRAM(INQCUST)", "LINK":"CECI LINK PROGRAM(INQCUST)", "9":"CECI XCTL PROGRAM(INQCUST)", "XCTL":"CECI XCTL PROGRAM(INQCUST)", "10":"CECI SEND TEXT('HELLO')", "SEND":"CECI SEND TEXT('HELLO')", "11":"CECI ABEND ABCODE(ASRA)", "ABEND":"CECI ABEND ABCODE(ASRA)"}
        }
        choice = maps.get(self.panel_state, {}).get(uc)
        if not choice:
            return self._panel("OPERATION CICS", [f"INVALID SELECTION {uc}", "Use PF5/MENU to return to Operation CICS main menu."])
        if choice in {"CEMT", "CEDA", "CECI"}:
            self.panel_state = choice + "_MAIN"
            return {"CEMT_MAIN": self.cemt_menu, "CEDA_MAIN": self.ceda_menu, "CECI_MAIN": self.ceci_menu}[self.panel_state]()
        if choice == "SECURITY": return self.security_smf_events()
        if choice == "DB2": return self._db2_activity_panel()
        if choice == "STATUS": return self._cics_resource_status_panel()
        if choice == "DVCA": return self.dvca_lab_control()
        if choice == "CBSA": return self._cbsa_omen_status_panel()
        if choice in {"CEMT_INQUIRE","CEMT_SET","CEMT_PERFORM","CEMT_DISCARD","CEDA_DISPLAY","CEDA_DEFINE"}:
            self.panel_state = choice
            return self._render_panel_state(choice)
        # route concrete command through direct handlers
        old = self.panel_state; self.panel_state = ""
        out = self.execute(choice)
        self.panel_state = old
        return out

    def _render_panel_state(self, state: str) -> str:
        if state == "CEMT_INQUIRE": return self._panel_menu("CEMT INQUIRE", [("1","SYSTEM"),("2","TRANSACTION"),("3","PROGRAM"),("4","TASK"),("5","FILE"),("6","CONNECTION"),("7","TERMINAL"),("8","DB2CONN"),("9","TSQUEUE"),("10","TDQUEUE"),("11","SECURITY")])
        if state == "CEMT_SET": return self._panel_menu("CEMT SET", [("1","TRANSACTION"),("2","PROGRAM"),("3","FILE"),("4","TASK PURGE"),("5","SECURITY")])
        if state == "CEMT_PERFORM": return self._panel_menu("CEMT PERFORM", [("1","STATISTICS"),("2","DUMP"),("3","SHUTDOWN SAFE RESPONSE")])
        if state == "CEMT_DISCARD": return self._panel_menu("CEMT DISCARD", [("1","PROGRAM")])
        if state == "CEDA_DISPLAY": return self._panel_menu("CEDA DISPLAY", [("1","PROGRAM"),("2","FILE"),("3","TRANSACTION")])
        if state == "CEDA_DEFINE": return self._panel_menu("CEDA DEFINE", [("1","PROGRAM"),("2","TRANSACTION"),("3","FILE")])
        return self.operator_menu()

    def _db2_activity_panel(self) -> str:
        return self._panel("DB2 CONNECTION / SQL ACTIVITY", ["DB2CONN DB2A STATUS CONNECTED PLAN(CBSAPLAN)", "Recent tables: CBSA.CUSTOMER CBSA.ACCOUNT CBSA.SQLI_EVENTS CBSA.VULN_EVENTS", "Use CEMT I DB2CONN or DB2 to inspect simulated database resources."])

    def _cics_resource_status_panel(self) -> str:
        return self._panel("CICS RESOURCE STATUS", [f"Transactions: {len(self.transactions)}", f"Programs: {len(self.programs)}", f"Files: {len(self.files)}", f"Tasks: {len(self.region.tasks)}", "Use CEMT INQUIRE submenus for detailed screens."])

    def _cbsa_omen_status_panel(self) -> str:
        return self._panel("CBSA / OMEN STATUS", ["OMEN transaction installed and available", "CBSA service layer active", "Db2 tables: CUSTOMER ACCOUNT PROCTRAN WEB_AUDIT", "Use OMEN or CBSA to start the CICS banking sample."])

    def _cics_attack_surface_panel(self) -> str:
        """The data hack3270's passive attacks consume: ESM fingerprint, LU /
        terminal model + Query Reply features, and IND$FILE availability."""
        r = self.region
        esm = "RACF" if r.racf_active() else "NONE"
        lu = getattr(self, "client_lu_name", None) or r.lu_name
        ttype = getattr(self, "client_terminal_type", None) or "IBM-3278-2-E"
        self._audit_stage("CICS RECON", f"Attack-surface fingerprint read (ESM={esm} LU={lu})",
                          transid="CICS", cls="OPERCMDS", result="WARNING")
        return self._panel("CICS ATTACK SURFACE / ESM FINGERPRINT", [
            f"ESM (External Security Manager): {esm}    SEC={r.security_options.get('SEC','YES')}",
            f"APPLID {r.applid}   SYSID {r.sysid}   CICS {getattr(r,'cics_version','6.1')}",
            f"LU name (client-reported)      : {lu}",
            f"Terminal type (negotiated)     : {ttype}",
            "Query Reply features            : COLOR, EXTD-HILITE, EXTD-ATTR, 3270-DS",
            "  (hack3270 'Query Reply lying' can substitute these features)",
            "IND$FILE transfer transaction   : AVAILABLE (try IND$FILE GET <dsn>)",
            "NOTE: LU name and Query Reply are client-supplied; a MITM (hack3270)",
            "can spoof them. Server-side identity is via RACF (ESM), not the LU.",
        ], status="CICS-RECON-001")

    def _indfile_intercept(self, cmd: str) -> str:
        """Recognise an IND$FILE host transfer so the intercept attack has a
        transfer to sit on, and audit it."""
        parts = (cmd or "").split()
        direction = "GET"
        dsn = ""
        for i, p in enumerate(parts[1:], 1):
            up = p.upper()
            if up in {"GET", "PUT"}:
                direction = up
            elif "." in p and not dsn:
                dsn = p
        dsn = dsn or "USER.UPLOAD.DATA"
        self._audit_stage("IND$FILE TRANSFER", f"IND$FILE {direction} {dsn} initiated (file transfer over the 3270 session)",
                          transid="IND$", resource=dsn, cls="FACILITY", result="WARNING")
        return self._panel("IND$FILE HOST FILE TRANSFER", [
            f"TRANS={direction}  DATASET={dsn}",
            "DFHXS  IND$FILE transfer started over the TN3270 session.",
            "A MITM (hack3270 IND$FILE intercept) can read or rewrite the blocks",
            "in transit because the transfer rides the same unencrypted data stream.",
            "SECURE FIX: require TLS (--tls) and server-side integrity checks.",
        ], status="CICS-INDFILE-001")

    def security_smf_events(self) -> str:
        try:
            events = getattr(self.state, "backend_trace_events", [])[-18:]
            body = ["Recent simulated security / SMF evidence:", ""]
            for ev in events:
                body.append(f" {ev.get('timestamp','')[:19]} {ev.get('component',''):<8} {ev.get('smf_type',''):<6} {ev.get('action',''):<18} {ev.get('result','')} {ev.get('correlation_id','')}")
            if len(body) <= 2:
                body.append(" No simulated SMF/security events yet.")
        except Exception:
            body = ["No simulated SMF/security events available."]
        return self._panel("SECURITY / SMF EVENTS", body)

    def dvca_lab_control(self) -> str:
        return self._panel("DVCA LAB CONTROL", [
            "Commands available inside DVCA:",
            "  HACK ON / HACK OFF",
            "  SHOW FIELDS / SHOW HIDDEN / HIDE HIDDEN",
            "  DISABLE PROTECTION / ENABLE PROTECTION",
            "  REMOVE NUMERIC / RESTORE NUMERIC",
            "  PIN **** / PIN 1337 / BRUTE FORCE PIN",
            "  RESET DVCA",
            "",
            "Use DVCA to enter the vulnerable CICS application.",
        ])

    def cemt_menu(self) -> str:
        return self._panel("STATUS:  ENTER ONE OF THE FOLLOWING", ["  Discard", "  Inquire", "  Perform", "  Set"], "")
    def ceda_menu(self) -> str:
        return self._panel("ENTER ONE OF THE FOLLOWING", [" ADd", " ALter", " APpend", " CHeck", " COpy", " DEFine", " DELete", " DIsplay", " Expand", " Install", " Lock", " Move", " REMove", " REName", " UNlock", " USerdefine", " View"], "")
    def ceci_menu(self) -> str:
        return self._asset("CECI.txt", "STATUS: ENTER ONE OF THE FOLLOWING\n SEND RECEIVE READ WRITEQ LINK XCTL RETURN")
    def _resource_table(self, heading: str, rows: list[str]) -> str:
        body = [f" {heading}", " " + "-" * 76]
        body.extend(rows)
        return self._panel("CICS MASTER TERMINAL", body)

    def _cics_set_sit(self, cmd: str) -> str:
        m = re.search(r"(SEC|XTRAN|XCMD|XPCT|XFCT|XTST|XDCT|XPPT|DFLTUSER)\(([^)]+)\)", cmd, re.I)
        if not m:
            return "DFHXS0003 SYNTAX: CICS SET SIT SEC(YES) XTRAN(YES) XCMD(YES) XPCT(YES) XFCT(YES) XTST(YES) XDCT(YES) XPPT(YES) DFLTUSER(CICSUSER)"
        outs = []
        for m in re.finditer(r"(SEC|XTRAN|XCMD|XPCT|XFCT|XTST|XDCT|XPPT|DFLTUSER)\(([^)]+)\)", cmd, re.I):
            outs.append(self.region.set_sit_option(self.userid, m.group(1), m.group(2)))
        return "\n".join(outs)
    def _cemt(self, cmd: str) -> str:
        uc = cmd.upper()
        # INQUIRE aliases
        if any(x in uc for x in (" INQUIRE ", " I ")):
            return self._cemt_inquire(uc)
        if " SET " in f" {uc} ":
            return self._cemt_set(uc)
        if " PERFORM " in f" {uc} ":
            return self._cemt_perform(uc)
        if " DISCARD " in f" {uc} ":
            return self._cemt_discard(uc)
        return self._asset("CEMT.txt", self.cemt_menu())
    def _cemt_inquire(self, uc: str) -> str:
        if "SEC" in uc or "SECURITY" in uc:
            return self._resource_table("INQUIRE SECURITY", self.region.security_status_lines())
        if "FILE" in uc:
            rows = [f"  File({r.name:<8}) {r.attr('TYPE','VSAM'):<4} {getattr(r, 'open_state', 'OPEN')[:3].title():<3} {r.status[:3].title():<3} Rea({r.attr('READ','YES'):<3}) Upd({r.attr('UPDATE','NO'):<3}) Dsn({r.attr('DSN')})" for r in self.files.values()]
            return self._resource_table("INQUIRE FILE", rows)
        if "PROG" in uc or "PROGRAM" in uc:
            rows = [f"  Prog({r.name:<8}) Leng({r.attr('LENGTH','000000')}) Resc({r.attr('RESCOUNT','000000')}) Use({r.attr('USECOUNT','000000')}) {r.status.title()}" for r in self.programs.values()]
            return self._resource_table("INQUIRE PROGRAM", rows)
        if "TASK" in uc:
            rows = []
            for t in self.region.tasks.values():
                rows.append(f"  Tas({t['TASK']}) Tra({t['TRAN']:<4}) Fac({t['TERMID']:<6}) {t['STATUS']:<8} Use({t['USERID']:<8}) Prog({t['PROGRAM']:<8})")
            if not rows:
                now = datetime.now().strftime("%H:%M:%S")
                rows = [f"  Tas(000001) Tra(CEMT) Fac(LU320) Run TasPri(001) Use({self.userid:<8}) Tim({now})"]
            return self._resource_table("INQUIRE TASK", rows)
        if "TRAN" in uc or "TRANS" in uc:
            rows = [f"  Tra({r.name:<4}) Pri({r.attr('PRIORITY','001')}) Pro({r.attr('PROGRAM','DFH????'):<8}) {r.status.title()} Ins({'Yes' if getattr(r, 'installed', True) else 'No '}) Tda({r.attr('TASKDATALOC','ANY')})" for r in self.transactions.values()]
            return self._resource_table("INQUIRE TRANSACTION", rows)
        if "TERM" in uc or "TERMINAL" in uc:
            rows = [f"  Ter({r.name:<4}) Net({r.attr('NETNAME',''):<8}) {r.status.title()} Use({r.attr('USERID',''):<8})" for r in self.terminal_resources.values()]
            return self._resource_table("INQUIRE TERMINAL", rows)
        if "DB2CONN" in uc or "DB2" in uc:
            return self._resource_table("INQUIRE DB2CONN", ["  DB2Conn(DB2A) Status(Connected) Plan(CBSAPLAN) Threads(0003) Authid(CICSUSER)"])
        if "CONNECTION" in uc or "CONNECT" in uc:
            rows = [f"  Con({r.name:<4}) Net({r.attr('NETNAME',''):<8}) {r.status.title()} Acc({r.attr('ACCESSMETHOD','')})" for r in self.connections.values()]
            return self._resource_table("INQUIRE CONNECTION", rows)
        if "SYSTEM" in uc or "SYS" in uc:
            uptime = datetime.now() - self.start_time
            rows = [
                "  Sysid(CICS) Applid(CICS) Mvsimg(GIB1) Jobname(GICS    )",
                "  Cicsts(05.06.00) Aos(0001) MaxTask(00050) CurTask(00001)",
                f"  Start({self.start_time:%Y/%m/%d %H:%M:%S}) Uptime({str(uptime).split('.')[0]})",
            ]
            return self._resource_table("INQUIRE SYSTEM", rows)
        if "TSQUEUE" in uc or "TSQ" in uc:
            return self._resource_table("INQUIRE TSQUEUE", [f"  Tsq({r.name:<8}) Numitems({r.attr('ITEMS','00000000')}) Length({r.attr('LENGTH','00000080')}) {r.attr('LOCATION','MAIN').title()}" for r in self.region.tsqueues.values()])
        if "TDQUEUE" in uc or "TDQ" in uc:
            return self._resource_table("INQUIRE TDQUEUE", [f"  Tdq({r.name:<4}) Type({r.attr('TYPE','EXTRA').title():<8}) Ena Intrdr({r.attr('INTRDR','NO')})" for r in self.region.tdqueues.values()])
        return "DFHCE3552 INVALID INQUIRE OPTION."
    def _name_in_parens(self, text: str, keyword: str) -> Optional[str]:
        import re
        m = re.search(keyword + r"\(([^)]+)\)", text, re.I)
        return m.group(1).strip().upper() if m else None
    def _cemt_set(self, uc: str) -> str:
        if "SEC" in uc or "SECURITY" in uc:
            val = "YES" if any(x in uc for x in (" ON", " YES", "SEC(YES)")) else "NO" if any(x in uc for x in (" OFF", " NO", "SEC(NO)")) else "YES"
            return self.region.set_sit_option(self.userid, "SEC", val)
        if "PROGRAM" in uc or "PROG" in uc:
            name = self._name_in_parens(uc, "PROGRAM") or self._name_in_parens(uc, "PROG")
            if name and name in self.programs:
                if "DIS" in uc:
                    self.programs[name].status = "DISABLED"
                if "ENA" in uc:
                    self.programs[name].status = "ENABLED"
                if "NEWCOPY" in uc or "PHASEIN" in uc:
                    self.programs[name].attrs = {**(self.programs[name].attrs or {}), "USECOUNT": "000000"}
                self._audit_stage("CICS RESOURCE SET", f"CEMT SET PROGRAM({name}) {self.programs[name].status}", transid="CEMT", resource=name, cls="CICSPROG")
                return f"DFHCE3553 PROGRAM {name} SET {self.programs[name].status}."
            return "DFHCE3554 PROGRAM NOT FOUND."
        if "FILE" in uc:
            name = self._name_in_parens(uc, "FILE")
            if name and name in self.files:
                status = self.files[name].status
                if "CLOSED" in uc or "CLO" in uc:
                    status = status.replace("OPEN", "CLOSED") if "OPEN" in status else "CLOSED ENABLED"
                if "OPEN" in uc or "OPE" in uc:
                    status = status.replace("CLOSED", "OPEN") if "CLOSED" in status else "OPEN ENABLED"
                if "DIS" in uc:
                    status = status.replace("ENABLED", "DISABLED") if "ENABLED" in status else status + " DISABLED"
                if "ENA" in uc:
                    status = status.replace("DISABLED", "ENABLED") if "DISABLED" in status else status + " ENABLED"
                self.files[name].status = status
                if "CLOSED" in status:
                    self.files[name].open_state = "CLOSED"
                if "OPEN" in status:
                    self.files[name].open_state = "OPEN"
                self._audit_stage("CICS RESOURCE SET", f"CEMT SET FILE({name}) {status}", transid="CEMT", resource=name, cls="FCICSFCT")
                return f"DFHCE3553 FILE {name} SET {status}."
            return "DFHCE3554 FILE NOT FOUND."
        if "TRAN" in uc:
            name = self._name_in_parens(uc, "TRANSACTION") or self._name_in_parens(uc, "TRAN")
            if name and name in self.transactions:
                self.transactions[name].status = "DISABLED" if "DIS" in uc else "ENABLED"
                self._audit_stage("CICS RESOURCE SET", f"CEMT SET TRANSACTION({name}) {self.transactions[name].status}", transid="CEMT", resource=name, cls="TCICSTRN")
                return f"DFHCE3553 TRANSACTION {name} SET {self.transactions[name].status}."
            return "DFHCE3554 TRANSACTION NOT FOUND."
        if "TASK" in uc:
            name = self._name_in_parens(uc, "TASK")
            if name and name in self.region.tasks and "PURGE" in uc:
                self.region.tasks[name]["STATUS"] = "PURGED"
                self.region.add_log("INFO", "CEMT", self.userid, f"TASK {name} PURGED")
                return f"DFHCE3553 TASK {name} PURGED."
            return "DFHCE3554 TASK NOT FOUND."
        return "DFHCE3552 INVALID SET OPTION."
    def _cemt_perform(self, uc: str) -> str:
        if "SHUT" in uc:
            return "DFHCE3579 PERFORM SHUTDOWN ACCEPTED - SHUTDOWN NOT EXECUTED IN SIMULATOR."
        if "STAT" in uc:
            return self.generate_stats()
        if "DUMP" in uc:
            return "DFHDU0201 SYSTEM DUMP CODE GIBS WRITTEN TO SIMULATED DUMP DATA SET."
        return "DFHCE3578 PERFORM COMMAND COMPLETED."
    def _cemt_discard(self, uc: str) -> str:
        name = self._name_in_parens(uc, "PROGRAM") or self._name_in_parens(uc, "PROG")
        if name and name in self.programs:
            del self.programs[name]
            return f"DFHCE3581 PROGRAM {name} DISCARDED."
        return "DFHCE3582 RESOURCE NOT FOUND OR NOT DISCARDABLE."
    def _ceda(self, cmd: str) -> str:
        uc = cmd.upper()
        if uc.strip() == "CEDA":
            return self._asset("CEDA.txt", self.ceda_menu())
        if any(x in uc for x in (" DISPLAY", " VIEW", " EXPAND")):
            if "PROG" in uc or "PROGRAM" in uc:
                rows = [f"  PROGRAM   {r.name:<8} GROUP(GIBSON) STATUS({r.status}) LANGUAGE(COBOL)" for r in self.programs.values()]
                return self._resource_table("CEDA DISPLAY PROGRAM", rows)
            if "FILE" in uc:
                rows = [f"  FILE      {r.name:<8} GROUP(GIBSON) DSNAME({r.attr('DSN')}) STATUS({r.status})" for r in self.files.values()]
                return self._resource_table("CEDA DISPLAY FILE", rows)
            if "TRAN" in uc:
                rows = [f"  TRANSACTION {r.name:<8} GROUP(GIBSON) PROGRAM({r.attr('PROGRAM')}) STATUS({r.status})" for r in self.transactions.values()]
                return self._resource_table("CEDA DISPLAY TRANSACTION", rows)
        if any(x in uc for x in (" DEFINE", " ADD")):
            kind, name, attrs = parse_define(uc)
            group = attrs.get("GROUP", "GIBSON")
            corrid = self._cics_corrid("CED")
            if kind in {"PROGRAM", "PROG"} and name:
                self.region.define_program(name, group=group, language=attrs.get("LANGUAGE", "COBOL"), corrid=corrid, userid=self.userid)
                return f"DFHCE3561 PROGRAM {name} DEFINED SUCCESSFULLY IN GROUP {group}. INSTALL REQUIRED."
            if kind in {"TRANSACTION", "TRAN"} and name:
                try:
                    self.region.define_transaction(name, program=attrs.get("PROGRAM", "MYPROG"), group=group, corrid=corrid, userid=self.userid)
                except ValueError as exc:
                    return f"DFHCE3568 {exc}"
                return f"DFHCE3561 TRANSACTION {name} DEFINED SUCCESSFULLY IN GROUP {group}. INSTALL REQUIRED."
            return "DFHCE3560 CEDA DEFINE - ENTER TYPE AND NAME, E.G. CEDA DEFINE PROGRAM(MYPROG)."
        if " COPY" in uc:
            old = self._name_in_parens(uc, "TRANS") or self._name_in_parens(uc, "TRANSACTION") or self._name_in_parens(uc, "PROGRAM")
            new = self._name_in_parens(uc, "AS")
            grp = self._name_in_parens(uc, "TO") or self._name_in_parens(uc, "GROUP") or "GIBSON"
            corrid = self._cics_corrid("CED")
            if not old or not new:
                return "DFHCE3565 CEDA COPY - SPECIFY TRANS(old) AS(new) TO(group)."
            prog = self.region.copy_transaction(old, new, group=grp, userid=self.userid, corrid=corrid)
            self.region.add_log("WARNING", "CEDA", self.userid,
                                f"CEDA COPY created unprotected alias {new.upper()} -> {prog} (cicspwn --bypass signature)", corrid=corrid)
            return f"DFHCE3566 TRANSACTION {old.upper()} COPIED TO {new.upper()} IN GROUP {grp}. INSTALLED."
        if " INSTALL" in uc:
            group = self._name_in_parens(uc, "GROUP") or "GIBSON"
            installed = self.region.install_group(group, corrid=self._cics_corrid("INS"), userid=self.userid)
            return "DFHCE3562 INSTALL SUCCESSFUL. INSTALLED: " + (", ".join(installed) if installed else "NO ELIGIBLE RESOURCES")
        if " CHECK" in uc:
            return "DFHCE3563 CHECK SUCCESSFUL. NO ERRORS DETECTED."
        if " DELETE" in uc:
            return "DFHCE3564 DELETE SUCCESSFUL."
        return "DFHCE3569 CEDA COMMAND COMPLETE."
    def _extract_from_text(self, cmd: str) -> str:
        m = re.search(r"FROM\((.*)\)", cmd, re.I)
        if not m:
            return ""
        val = m.group(1).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            return val[1:-1]
        return val

    def _ceci(self, cmd: str) -> str:
        uc = cmd.upper()
        if uc.strip() in {"CECI", "CECI HELP"}:
            return self._asset("CECI.txt", self.ceci_menu())
        corrid = self._cics_corrid("CEC")
        display_cmd = cmd[5:].strip() if uc.startswith("CECI") else cmd
        response = "NORMAL"; detail = "DFHCE3570 SIMULATED EXECUTION COMPLETED SUCCESSFULLY."; extra = []
        if "WRITEQ" in uc and " TS" in uc:
            qname = self._name_in_parens(uc, "QUEUE") or self._name_in_parens(uc, "TSQUEUE") or "GIBSON"
            text = self._extract_from_text(cmd) or " "
            self.region.write_tsq(qname, text)
            detail = f"WRITEQ TS QUEUE({qname}) ITEM({len(self.region.read_tsq(qname)):08d})"
        elif "READQ" in uc and " TS" in uc:
            qname = self._name_in_parens(uc, "QUEUE") or self._name_in_parens(uc, "TSQUEUE") or "GIBSON"
            items = self.region.read_tsq(qname)
            if not items:
                response = "QIDERR"; detail = f"DFHRESP(QIDERR) QUEUE({qname}) NOT FOUND"
            else:
                extra = [f"  {i+1:06d} {item}" for i, item in enumerate(items[:12])]
                detail = f"READQ TS QUEUE({qname}) RETURNED {len(items)} ITEM(S)"
        elif "DELETEQ" in uc and " TS" in uc:
            qname = self._name_in_parens(uc, "QUEUE") or self._name_in_parens(uc, "TSQUEUE") or "GIBSON"
            if not self.region.delete_tsq(qname):
                response = "QIDERR"; detail = f"DFHRESP(QIDERR) QUEUE({qname}) NOT FOUND"
            else:
                detail = f"DELETEQ TS QUEUE({qname})"
        elif "WRITEQ" in uc and " TD" in uc:
            qname = self._name_in_parens(uc, "QUEUE") or self._name_in_parens(uc, "TDQUEUE") or "CSMT"
            self.region.write_tdq(qname, self._extract_from_text(cmd) or " ")
            detail = f"WRITEQ TD QUEUE({qname})"
        elif "READQ" in uc and " TD" in uc:
            qname = self._name_in_parens(uc, "QUEUE") or self._name_in_parens(uc, "TDQUEUE") or "CSMT"
            items = self.region.read_tdq(qname)
            if not items:
                response = "QIDERR"; detail = f"DFHRESP(QIDERR) TDQUEUE({qname}) NOT FOUND"
            else:
                extra = [f"  {i+1:06d} {item}" for i, item in enumerate(items[:12])]
                detail = f"READQ TD QUEUE({qname}) RETURNED {len(items)} ITEM(S)"
        elif ("STARTBR" in uc or "READNEXT" in uc or "ENDBR" in uc) and "FILE" in uc:
            fname = self._name_in_parens(uc, "FILE") or "FILEA"
            ok, msg = self._file_allowed(fname, access="READ", transid="CECI", corrid=corrid)
            if not ok:
                response = "NOTAUTH"; detail = msg
            elif fname not in self.files:
                response = "FILENOTFOUND"; detail = f"DFHFC0999 FILE {fname} IS NOT DEFINED"
            else:
                recs = self.region.file_records.get(fname, [])
                if "ENDBR" in uc:
                    detail = f"ENDBR FILE({fname}) NORMAL"
                else:
                    extra = [f"  {i+1:04d} {r}" for i, r in enumerate(recs[:12])]
                    detail = f"{'STARTBR' if 'STARTBR' in uc else 'READNEXT'} FILE({fname}) RETURNED {len(recs)} RECORD(S)"
        elif "READ" in uc and "FILE" in uc:
            fname = self._name_in_parens(uc, "FILE") or "FILEA"
            ok, msg = self._file_allowed(fname, access="READ", transid="CECI", corrid=corrid)
            if not ok:
                response = "NOTAUTH"; detail = msg
            elif fname not in self.files:
                response = "FILENOTFOUND"; detail = f"DFHFC0999 FILE {fname} IS NOT DEFINED"
            elif getattr(self.files[fname], "open_state", "OPEN") != "OPEN":
                response = "NOTOPEN"; detail = f"DFHRESP(NOTOPEN) FILE({fname}) CLOSED"
            else:
                key = self._name_in_parens(uc, "RIDFLD") or ""
                recs = self.region.file_records.get(fname, [])
                rec = ""
                if key:
                    rec = next((r for r in recs if r.upper().startswith(key.upper())), recs[0] if recs else "")
                else:
                    rec = recs[0] if recs else ""
                extra = [f"  RECORD = {rec}"] if rec else []
                detail = f"READ FILE({fname}) RIDFLD({key or '00000000'}) NORMAL"
        elif ("WRITE" in uc or "REWRITE" in uc) and "FILE" in uc:
            fname = self._name_in_parens(uc, "FILE") or "FILEA"
            ok, msg = self._file_allowed(fname, access="UPDATE", transid="CECI", corrid=corrid)
            if not ok:
                response = "NOTAUTH"; detail = msg
            else:
                rec = self._extract_from_text(cmd)
                if rec:
                    self.region.file_records.setdefault(fname, []).append(rec[:80])
                detail = f"{'REWRITE' if 'REWRITE' in uc else 'WRITE'} FILE({fname}) NORMAL" + (f" - {len(self.region.file_records.get(fname, []))} RECORD(S)" if rec else "")
        elif "LINK" in uc or "XCTL" in uc:
            pgm = self._name_in_parens(uc, "PROGRAM") or "UNKNOWN"
            if pgm not in self.programs:
                response = "PGMIDERR"; detail = f"DFHRESP(PGMIDERR) PROGRAM({pgm}) NOT FOUND"; self.region.abend(self.userid,"CECI","AEI0",detail,program=pgm)
            else:
                detail = f"{('XCTL' if 'XCTL' in uc else 'LINK')} PROGRAM({pgm}) NORMAL"
        elif "ABEND" in uc:
            code = self._name_in_parens(uc, "ABCODE") or "ASRA"
            self.region.abend(self.userid, "CECI", code, "CECI requested simulated abend", program="CECI")
            from gibson.core.abend import symptom_dump
            response = "ABEND"
            detail = (f"DFHAC2236 Transaction CECI abended with code {code}\n"
                      + symptom_dump(code, jobname="CICSGIB1", stepname="CICS", progname="CECI"))
        elif "SEND" in uc:
            sent = self._extract_from_text(cmd)
            detail = f"DFHCE3570 SIMULATED EXECUTION OF SEND COMPLETED SUCCESSFULLY" + ((f": {sent}") if sent else ".")
        elif "ASSIGN" in uc:
            opts = self._ceci_options(uc)
            vals = [(o, self.region.assign_value(o, userid=self.userid, terminal="LU320")) for o in opts] or \
                   [(o, self.region.assign_value(o, userid=self.userid, terminal="LU320"))
                    for o in ("APPLID", "SYSID", "USERID", "NETNAME", "NATLANGINUSE", "CICSTSLEVEL", "OPSYS")]
            extra = [f"  {o:<14}= {v}" for o, v in vals if v != ""]
            detail = "ASSIGN NORMAL - REGION IDENTITY RETURNED"
        elif "INQUIRE" in uc and "SYSTEM" in uc:
            opts = self._ceci_options(uc)
            keys = opts or ("CICSTSLEVEL", "RELEASE", "CICSSYS", "APPLID", "JOBNAME", "DFLTUSER", "SECURITYMGR", "OPSYS")
            vals = [(o, self.region.inquire_system_value(o)) for o in keys]
            extra = [f"  {o:<14}= {v}" for o, v in vals if v != ""]
            detail = "INQUIRE SYSTEM NORMAL"
        elif ("SPOOLOPEN" in uc) or ("SPOOLWRITE" in uc) or ("SPOOLCLOSE" in uc):
            return self._ceci_spool(cmd, uc, corrid)
        else:
            response = "INVREQ"; detail = "DFHRESP(INVREQ) COMMAND NOT SUPPORTED BY GIBSON CECI"
        self._audit_stage("CICS COMMAND EXECUTION", f"CECI EXEC CICS {display_cmd}", transid="CECI", resource=response, cls="TCICSTRN", corrid=corrid)
        self.region.add_log("INFO" if response == "NORMAL" else "ERROR", "CECI", self.userid, f"{response} {detail}", corrid=corrid)
        return self._panel("CECI - COMMAND LEVEL INTERPRETER", [f" COMMAND ===> EXEC CICS {display_cmd}", "", f" RESPONSE: {response}", f" EIBRESP={'0' if response=='NORMAL' else '16'} EIBRESP2=0", f" {detail}", *extra, f" CORRID={corrid}"])

    def _ceci_options(self, uc: str) -> list:
        import re
        verbs = {"ASSIGN", "INQUIRE", "SYSTEM", "EXEC", "CICS", "SPOOLOPEN",
                 "SPOOLWRITE", "SPOOLCLOSE", "FROM", "TOKEN", "OUTPUT", "INPUT", "RESP"}
        out = []
        for f in re.findall(r"([A-Z][A-Z0-9]+)\s*\(", uc):
            if f not in verbs and f not in out:
                out.append(f)
        return out

    def _ceci_spool(self, cmd: str, uc: str, corrid: str) -> str:
        """EXEC CICS SPOOLOPEN/SPOOLWRITE/SPOOLCLOSE - the JCL-submission path
        cicspwn uses for code execution (SPOOL=YES / INTRDR)."""
        if not getattr(self, "_spool_buffer", None):
            self._spool_buffer = []
        if "SPOOLOPEN" in uc:
            if not self.region.spool_enabled():
                self._audit_stage("CICS SPOOL ACCESS", "SPOOLOPEN denied - SPOOL=NO", transid="CECI", resource="SPOOL", cls="TCICSTRN", corrid=corrid, result="FAILURE")
                return self._panel("CECI - COMMAND LEVEL INTERPRETER", [" COMMAND ===> EXEC CICS SPOOLOPEN OUTPUT", "", " RESPONSE: NOTAUTH", " EIBRESP=70 EIBRESP2=2", " DFHRESP(NOTAUTH) SPOOL INTERFACE DISABLED (SPOOL=NO IN SIT)", f" CORRID={corrid}"])
            self._spool_token = corrid[-8:]
            self._spool_buffer = []
            self.region.add_log("INFO", "CECI", self.userid, f"SPOOLOPEN OUTPUT token {self._spool_token}", corrid=corrid)
            self._audit_stage("CICS SPOOL OPEN", "SPOOLOPEN OUTPUT to internal reader", transid="CECI", resource="INTRDR", cls="TCICSTRN", corrid=corrid)
            return self._panel("CECI - COMMAND LEVEL INTERPRETER", [" COMMAND ===> EXEC CICS SPOOLOPEN OUTPUT NODE(LOCAL) USERID(INTRDR)", "", " RESPONSE: NORMAL", " EIBRESP=0 EIBRESP2=0", f"  TOKEN         = {self._spool_token}", " SPOOL REPORT OPENED TO INTERNAL READER", f" CORRID={corrid}"])
        if "SPOOLWRITE" in uc:
            line = self._extract_from_text(cmd) or ""
            self._spool_buffer.append(line[:80])
            return self._panel("CECI - COMMAND LEVEL INTERPRETER", [" COMMAND ===> EXEC CICS SPOOLWRITE", "", " RESPONSE: NORMAL", " EIBRESP=0 EIBRESP2=0", f"  FLENGTH       = {len(line):08d}", f" RECORD {len(self._spool_buffer):04d} QUEUED TO INTERNAL READER", f" CORRID={corrid}"])
        # SPOOLCLOSE -> submit accumulated JCL to JES (simulated execution)
        jcl = "\n".join(self._spool_buffer) or "//GIBPWN   JOB (ACCT),CLASS=A\n//S1 EXEC PGM=IEFBR14"
        info = self._submit_spooled_jcl(jcl, corrid)
        self._spool_buffer = []
        return self._panel("CECI - COMMAND LEVEL INTERPRETER", [" COMMAND ===> EXEC CICS SPOOLCLOSE", "", " RESPONSE: NORMAL", " EIBRESP=0 EIBRESP2=0", *info, f" CORRID={corrid}"])

    def _submit_spooled_jcl(self, jcl: str, corrid: str) -> list:
        from datetime import datetime
        owner = (self.userid or self.region.security_options.get("DFLTUSER", "CICSUSER")).upper()
        up = jcl.upper()
        is_pwn = any(k in up for k in ("FTP", "REXX", "BPXBATCH", "CALL '", "ALTER ", "LISTUSER", "IRXJCL", "ADDUSER", "PERMIT"))
        try:
            job = self.state.jes.submit(jcl, owner, submitter=owner)
            jobid, jobname = job.jobid, job.jobname
        except Exception:
            jobid, jobname = "JOB00PWN", "GIBPWN"
        self._register_pwn_shell(jobname, jobid, owner, corrid, is_pwn)
        self._audit_stage("CICS JCL SUBMISSION", f"SPOOLCLOSE submitted {jobname} ({jobid}) via INTRDR from terminal task",
                          transid="CECI", resource=jobname, cls="JESJOBS", corrid=corrid,
                          result="WARNING" if is_pwn else "SUCCESS")
        self.region.add_log("WARNING" if is_pwn else "INFO", "CECI", owner,
                            f"INTRDR job {jobname}/{jobid} submitted from a CICS terminal task (cicspwn signature)" if is_pwn
                            else f"INTRDR job {jobname}/{jobid} submitted", corrid=corrid)
        lines = [f"  JOBNAME       = {jobname}", f"  JOBID         = {jobid}",
                 " JOB SUBMITTED TO INTERNAL READER - SIMULATED EXECUTION COMPLETE"]
        if is_pwn:
            lines.append(" GIBSON-LAB: payload recognised - simulated shell registered (OMVS: cicsshell)")
        return lines

    def _register_pwn_shell(self, jobname: str, jobid: str, owner: str, corrid: str, is_pwn: bool) -> None:
        from datetime import datetime
        store = getattr(self.state, "cics_pwn_shells", None)
        if store is None:
            store = []
            setattr(self.state, "cics_pwn_shells", store)
        store.append({
            "jobname": jobname, "jobid": jobid, "userid": owner.upper(), "corrid": corrid,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payload": "reverse_rexx" if is_pwn else "jcl", "active": bool(is_pwn),
            "applid": self.region.applid, "region": self.region.region,
        })

    def cebr(self, cmd: str = "CEBR") -> str:
        parts = cmd.split()
        qname = parts[1].upper() if len(parts) > 1 else "GIBSON"
        items = self.region.read_tsq(qname)
        source = "TSQ"
        if not items:
            items = self.region.read_tdq(qname)
            source = "TDQ"
        if not items:
            self.region.add_log("ERROR", "CEBR", self.userid, f"QIDERR queue {qname} not found")
            return self._panel("CEBR - TEMPORARY STORAGE BROWSE", [f" Queue name  ===> {qname}", "", " DFHRESP(QIDERR) QUEUE NOT FOUND"], "QIDERR")
        lines = [f" Queue name  ===> {qname}", f" Queue type  ===> {source}", " Item number ===> 00000001", ""]
        lines.extend([f" {i+1:06d}  {item}" for i, item in enumerate(items[:18])])
        return self._panel("CEBR - TEMPORARY STORAGE BROWSE", lines)

    def csmt(self, cmd: str = "CSMT") -> str:
        uc = cmd.upper()
        rows = list(self.region.log_entries)[-18:]
        if "TYPE(" in uc:
            typ = self._name_in_parens(uc, "TYPE") or ""
            rows = [r for r in self.region.log_entries if r.get("type") == typ][-18:]
        if "TRAN(" in uc:
            trn = self._name_in_parens(uc, "TRAN") or ""
            rows = [r for r in self.region.log_entries if r.get("transid") == trn][-18:]
        body = [f" {r['time']} {r['type']:<8} {r['transid']:<4} {r['userid']:<8} {r['message'][:45]}" for r in rows] or [" *** NO CICS LOG RECORDS ***"]
        return self._panel("CSMT - CICS LOG", body)

    def _cedf(self, cmd: str) -> str:
        uc = cmd.upper().strip()
        if uc in {"CEDF OFF", "CEDF,OFF"}:
            self.region.trace_enabled_for = ""
            return "DFHEDP DEBUG FACILITY DISABLED FOR THIS TERMINAL."
        parts = cmd.split()
        if len(parts) > 1:
            self.region.trace_enabled_for = parts[1].upper()
            return f"DFHEDP DEBUG FACILITY ENABLED FOR {self.region.trace_enabled_for}."
        trace = self.region.traces.get("OMEN") or []
        return self._panel("CEDF - EXEC CICS TRACE", trace or ["No trace records. Use CEDF OMEN then run OMEN."])

    def cesl(self) -> str:
        try:
            lines = deque(self.log_path.read_text(encoding="utf-8", errors="ignore").splitlines(), maxlen=18)
        except FileNotFoundError:
            lines = deque(["*** NO LOGS FOUND ***"], maxlen=18)
        return self._panel("CESL - SYSTEM LOGS", list(lines))
    def generate_stats(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime = datetime.now() - self.start_time
        return self._panel(
            "DFHCE3600 CICS STATISTICS",
            [
                f" STATISTICS AT {now}",
                f" UPTIME: {str(uptime).split('.')[0]}",
                " CPU%             5.3",
                " Transactions/Sec 0.45",
                " Current Tasks    1",
                " Max Tasks        50",
                " TS Queue Length  0",
            ],
        )
    def cicspwn_detection(self) -> str:
        sigs = {
            "CICS RESOURCE COPY": "RACF BYPASS - CEDA COPY of a protected transaction",
            "CICS RACF BYPASS": "RACF BYPASS - unprotected alias created",
            "CICS RACF BYPASS USE": "RACF BYPASS IN USE - alias ran a protected transaction",
            "CICS SPOOL OPEN": "SPOOL ABUSE - SPOOLOPEN to internal reader from a terminal task",
            "CICS SPOOL ACCESS": "SPOOL ACCESS attempt",
            "CICS JCL SUBMISSION": "CODE EXECUTION - JCL submitted via INTRDR from a CICS task",
            "CICS SIGNON POLICY": "SIGN-ON POLICY change",
        }
        rows = []
        recon = 0
        for inc in self.region.incidents:
            ev = (inc.stage or "").upper()
            if ev in sigs:
                rows.append((inc.ts.strftime("%H:%M:%S"), (inc.userid or "")[:8], sigs[ev]))
            elif ev == "CICS COMMAND EXECUTION" and ("ASSIGN" in (inc.action or "").upper() or "INQUIRE SYSTEM" in (inc.action or "").upper()):
                recon += 1
        lines = [f"Region {self.region.region}  Applid {self.region.applid}  Sysid {self.region.sysid}", ""]
        if recon:
            lines.append(f"[RECON ] {recon:>3} EXEC CICS ASSIGN / INQUIRE SYSTEM calls  (cicspwn -i fingerprint)")
        for ts, u, desc in rows[-16:]:
            lines.append(f"[{ts}] {u:<8} {desc}")
        if not rows and not recon:
            lines.append("No cicspwn signatures observed in this region yet.")
        lines += ["", f"Signature events: {len(rows)}   recon calls: {recon}",
                  "Evidence sources: SMF80 (RACF ICH408I), CICS OPERLOG/CSMT, master-console alerts.",
                  "Hunt tips: terminal task issuing SPOOLOPEN; CEDA COPY of CEMT/CECI; new unprotected transids."]
        return self._panel("CICSPWN DETECTION TIMELINE (BLUE TEAM)", lines, "SIMULATED - FOR SECURITY TRAINING")

    def cicspwn_report(self) -> str:
        probe = self.region.cicspwn_probe(self.userid)
        tx_lines = [f"  {x['name']:<4} {x['state']:<12} program={x.get('program','')} status={x.get('status','')}" for x in probe['transactions']]
        file_lines = [f"  {x['name']:<8} {x['state']:<10} {x['open']:<6} dsn={x['dsn']}" for x in probe['files']]
        queue_lines = [f"  {x['type']:<8} {x['name']:<8} state={x['state']}" for x in probe['queues']]
        lines = [
            f"APPLID={probe['applid']} REGION={probe['region']} SYSID={probe['sysid']} CORRID={probe['corrid']}",
            f"SECURITY={probe['security']} OUTCOME={probe['outcome']}",
            "",
            "TRANSACTION DISCOVERY",
            *tx_lines,
            "",
            "FILE DISCOVERY",
            *file_lines,
            "",
            "QUEUE DISCOVERY",
            *queue_lines,
            "",
            "NOTE: CICSPWN IS SIMULATED. NO HOST CODE IS EXECUTED.",
        ]
        return self._panel("CICSPWN STAGED DISCOVERY SUMMARY", lines, "FORENSIC EVIDENCE WRITTEN TO SMF80/OPERLOG")

    # ------------------------------------------------------------------
    # Safe training CICS banking lab (GMVB)
    # ------------------------------------------------------------------
    def _bank_screen(self, title: str, lines: list[str], status: str = "") -> str:
        header = ["SIGHBERBANK CICS BANKING LAB", "TRANSACTION PROCESSING REGION CICSGIB1 / TRANSID GMVB", ""]
        return self._panel(title, header + lines, status or self.bank_status)
    def _bank_login(self, userid: str, password: str) -> str:
        userid_u = (userid or "").upper()
        password_t = (password or "").strip()
        self.state.racf.load(merge=True)
        if self.state.racf.verify_password(userid_u, password_t):
            self.bank_authenticated = True
            self.bank_userid = userid_u
            self.bank_current = "MENU"
            self.bank_prev = "LOGN"
            self.bank_status = f"SIGN-ON SUCCESSFUL FOR {userid_u}"
            self.lab.login(self.lab_sid, userid_u, password_t)
            return self._render_bank()
        self.bank_authenticated = False
        self.bank_status = "INVALID USERID OR PASSWORD"
        return self._render_bank("LOGN")
    def _bank_login_passticket(self, userid: str, ticket: str, applid: str = "CICS") -> str:
        userid_u = (userid or "").upper()
        ticket_u = (ticket or "").upper().strip()
        appl_u = (applid or "CICS").upper().strip() or "CICS"
        result = get_passticket_service(self.state).validate(userid_u, appl_u, ticket_u, consumer="CICS-GMVB")
        if result.get("ok"):
            self.bank_authenticated = True
            self.bank_userid = userid_u
            self.bank_current = "MENU"
            self.bank_prev = "LOGN"
            self.bank_status = f"PASSTICKET ACCEPTED FOR {userid_u} / {appl_u}"
            self.lab.login(self.lab_sid, userid_u, "", passticket=ticket_u, applid=appl_u)
            return self._render_bank()
        self.bank_authenticated = False
        self.bank_status = str(result.get("message", "PASSTICKET REJECTED"))
        self.lab.login(self.lab_sid, userid_u, "", passticket=ticket_u, applid=appl_u)
        return self._render_bank("LOGN")
    def _render_bank(self, screen: str | None = None, message: str | None = None) -> str:
        if screen:
            self.bank_current = screen
        if message is not None:
            self.bank_status = message
        current = self.bank_current
        if current == "LOGN":
            return self._bank_screen("LOGN - CUSTOMER SIGNON", [
                "USERID . . . . . . .  ________",
                "PASSWORD . . . . . .  ________",
                "PASSTICKET . . . . .  ________",
                "APPLID . . . . . . .  ________",
                "ENTER FORMAT: userid password OR userid PTKT ticket [applid]",
                "GACF.DB CREDENTIALS APPLY. USE ~ TO MOVE BETWEEN FIELDS.",
                "PF12=LOGOUT  ~=NEXT FIELD  ENTER=SUBMIT",
            ])
        if current == "MENU":
            return self._bank_screen("MENU - MAIN MENU", [
                f"SIGNED ON USER . . .  {self.bank_userid or self.userid}",
                "",
                "1  CARG - CARGO / ITEM LOOKUP",
                "2  ORDE - PLACE ORDER",
                "3  ORDR - ORDER HISTORY",
                "4  ACCT - ACCOUNT INQUIRY",
                "5  STMT - STATEMENT SEARCH",
                "6  XFER - FUNDS TRANSFER",
                "7  APRV - APPROVAL QUEUE",
                "8  HACK - HACK3270 FIELD LAB",
                "9  LOGN - RETURN TO SIGNON",
                "",
                "SELECTION . . . . .  ____",
                "TYPE TRANSACTION ID OR MENU NUMBER.",
                "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD",
            ])
        if current == "CARG":
            item = self.bank_items.get(self.bank_last_item) if self.bank_last_item else None
            details = []
            if item:
                details = [
                    f"ITEM NUMBER . . . .  {item['item_number']}",
                    f"ITEM NAME . . . . .  {item['item_name']}",
                    f"PRICE . . . . . . .  {item['price']}",
                    f"SHIPPING COST . . .  {item['shipping_cost']}",
                    f"PURCHASABLE . . . .  {item['purchasable']}",
                    f"ORDER SUPPLY . . . . {item['order_supply']}",
                    f"COMMENTS . . . . . . {item['comments']}",
                ]
            else:
                details = ["ITEM NUMBER . . . .  _____", "", "ENTER A 5-DIGIT ITEM NUMBER."]
            return self._bank_screen("CARG - ITEM LOOKUP", details + ["", "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD"])
        if current == "ORDE":
            item = self.bank_items.get(self.bank_last_item) if self.bank_last_item else None
            lines = ["ENTER ITEM NUMBER TO PLACE AN ORDER."]
            if item:
                lines.extend([
                    f"DEFAULT ITEM . . . . {item['item_number']} {item['item_name']}",
                    f"PRICE/SHIP . . . . . {item['price']} / {item['shipping_cost']}",
                ])
            lines.extend(["", "ITEM NUMBER . . . .  _____", "ENTER ITEM NUMBER OR PRESS ENTER TO USE DEFAULT ITEM.", "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD"])
            return self._bank_screen("ORDE - PLACE ORDER", lines)
        if current == "ORDR":
            rows = [f"{o['index']}  {o['date']}  {o['item_number']}  {o['name'][:28]:<28}  {o['price']:>7}" for o in self.bank_orders[-8:]]
            return self._bank_screen("ORDR - ORDER HISTORY", ["INDEX  DATE      ITEM   NAME                          PRICE", "-----  --------  -----  ----------------------------  -------"] + rows + ["", "COMMAND . . . . . . ____", "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD"])
        if current == "ACCT":
            snap = self.lab.snapshot(self.lab_sid)
            lines = ["ACCOUNT . . . . . .  _________________", ""]
            if snap.get("rows"):
                row = snap["rows"][0]
                lines.extend([
                    f"ACCTNO . . . . . .  {row.get('ACCTNO','')}",
                    f"OWNER  . . . . . .  {row.get('OWNER','')}",
                    f"TYPE   . . . . . .  {row.get('TYPE','')}",
                    f"BALANCE. . . . . .  {row.get('BALANCE','')}",
                    f"STATUS . . . . . .  {row.get('STATUS','')}",
                    f"ROUTING. . . . . .  {row.get('ROUTING','')}",
                ])
            else:
                lines.append("ENTER AN ACCOUNT NUMBER OR TRY 10001' OR '1'='1")
            lines.extend(["", "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD"])
            return self._bank_screen("ACCT - ACCOUNT INQUIRY", lines, self.bank_status)
        if current == "STMT":
            snap = self.lab.snapshot(self.lab_sid)
            lines = ["ACCOUNT . . . . . .  _________________", "PERIOD . . . . . . .  ________", ""]
            rows = snap.get("rows") or []
            if rows:
                lines.append("STMTID     ACCTNO  PERIOD   AMOUNT      DESCRIPTION")
                lines.append("--------   ------  -------  ----------  ------------------------")
                for row in rows[:6]:
                    lines.append(f"{row.get('STMTID',''):<10} {row.get('ACCTNO',''):<6}  {row.get('PERIOD',''):<7}  {row.get('AMOUNT',''):<10}  {row.get('DESCRIPTION','')[:24]}")
            else:
                lines.append("SEARCH STATEMENTS OR TRY SQL-LIKE INPUT")
            lines.extend(["", "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD"])
            return self._bank_screen("STMT - STATEMENT SEARCH", lines, self.bank_status)
        if current == "XFER":
            snap = self.lab.snapshot(self.lab_sid)
            lines = [
                "SOURCE ACCOUNT . . .  _________________",
                "DEST ACCOUNT . . . .  _________________",
                "AMOUNT . . . . . . .  _________________",
                "PIN . . . . . . . .   ____",
                "MEMO . . . . . . . .  ________________________",
                "",
            ]
            rows = snap.get("rows") or []
            if rows:
                row = rows[0]
                lines.extend([
                    f"TXID . . . . . . .  {row.get('TXID','')}",
                    f"STATUS . . . . . .  {row.get('STATUS','')}",
                    f"REQUESTOR . . . . .  {row.get('REQUESTOR','')}",
                ])
            else:
                lines.append("SUBMIT A TRANSFER. HIDDEN FLAGS CAN BE TOGGLED IN HACK MODE.")
            lines.extend(["", "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD"])
            return self._bank_screen("XFER - FUNDS TRANSFER", lines, self.bank_status)
        if current == "APRV":
            snap = self.lab.snapshot(self.lab_sid)
            lines = ["TRANSFER ID . . . .   __________", ""]
            rows = snap.get("rows") or []
            if rows:
                row = rows[0]
                lines.extend([
                    f"TXID . . . . . . .  {row.get('TXID','')}",
                    f"SOURCE . . . . . .  {row.get('SOURCE','')}",
                    f"DEST . . . . . . .  {row.get('DESTINATION','')}",
                    f"AMOUNT . . . . . .  {row.get('AMOUNT','')}",
                    f"STATUS . . . . . .  {row.get('STATUS','')}",
                ])
            else:
                lines.append("APPROVE A PENDING TRANSFER OR TEST DIRECT WORKFLOW ACCESS")
            lines.extend(["", "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD"])
            return self._bank_screen("APRV - APPROVAL QUEUE", lines, self.bank_status)
        if current == "HACK":
            snap = self.lab.snapshot(self.lab_sid)
            hack = snap.get("hack", {})
            return self._bank_screen("HACK - FIELD MANIPULATION", [
                f"HACK FIELDS . . . .  {'ON' if hack.get('hack_enabled') else 'OFF'}",
                f"REVEAL HIDDEN . . .  {'Y' if hack.get('reveal_hidden') else 'N'}",
                f"REMOVE PROTECTION .  {'Y' if hack.get('remove_protection') else 'N'}",
                f"REMOVE NUMERIC  . .  {'Y' if hack.get('remove_numeric') else 'N'}",
                f"SHOW METADATA . . .  {'Y' if hack.get('show_metadata') else 'N'}",
                "",
                "HACK3270 WEB BANKING PANEL REMOVED FROM GOLDEN BASELINE.",
                "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD",
            ], self.bank_status)
        if current == "ADMN":
            return self._bank_screen("ADMN - HIDDEN ADMIN FUNCTIONS", [
                "DIRECT ORDER FILE ACCESS ACTIVE",
                "PRICE OVERRIDE PANEL AVAILABLE",
                "ORDER FILE AUTHORIZATION CHECKS: BYPASSED IN TRAINING DEMO",
                "",
                "COMMAND . . . . . . ____",
                "THIS SCREEN IS ONLY REACHED IN INSTRUCTOR-CONTROLLED DEMO MODE.",
                "PF3=BACK  PF4=MENU  PF12=LOGOUT  ~=NEXT FIELD",
            ], self.bank_status)
        return self._bank_screen("GMVB", ["UNKNOWN SCREEN STATE"], self.bank_status)
    def _bank_field_defs(self, screen: str | None = None) -> list[dict[str, object]]:
        current = (screen or self.bank_current).upper()
        if current == "LOGN":
            return [
                {"name": "USERID", "row": 7, "col": 24, "width": 8, "hidden": False},
                {"name": "PASSWORD", "row": 8, "col": 24, "width": 8, "hidden": True},
            ]
        if current == "MENU":
            return [{"name": "SELECTION", "row": 14, "col": 24, "width": 4, "hidden": False}]
        if current == "CARG":
            return [{"name": "ITEM", "row": 10, "col": 24, "width": 5, "hidden": False}]
        if current == "ORDE":
            return [{"name": "ITEM", "row": 11, "col": 24, "width": 5, "hidden": False}]
        if current == "ORDR":
            return [{"name": "COMMAND", "row": 18, "col": 24, "width": 4, "hidden": False}]
        if current == "ACCT":
            return [{"name": "ACCTNO", "row": 8, "col": 24, "width": 18, "hidden": False}, {"name": "AUTHFLAG", "row": 18, "col": 24, "width": 1, "hidden": True}]
        if current == "STMT":
            return [{"name": "ACCTNO", "row": 8, "col": 24, "width": 18, "hidden": False}, {"name": "PERIOD", "row": 9, "col": 24, "width": 8, "hidden": False}]
        if current == "XFER":
            return [{"name": "SRCACCT", "row": 8, "col": 24, "width": 18, "hidden": False}, {"name": "DSTACCT", "row": 9, "col": 24, "width": 18, "hidden": False}, {"name": "AMOUNT", "row": 10, "col": 24, "width": 18, "hidden": False}, {"name": "PIN", "row": 11, "col": 24, "width": 4, "hidden": True}, {"name": "MEMO", "row": 12, "col": 24, "width": 24, "hidden": False}, {"name": "AUTHFLAG", "row": 17, "col": 24, "width": 1, "hidden": True}, {"name": "ADMINFLAG", "row": 18, "col": 24, "width": 1, "hidden": True}, {"name": "DEBUGFLAG", "row": 19, "col": 24, "width": 1, "hidden": True}]
        if current == "APRV":
            return [{"name": "TXID", "row": 8, "col": 24, "width": 10, "hidden": False}, {"name": "ADMINFLAG", "row": 18, "col": 24, "width": 1, "hidden": True}]
        if current == "ADMN":
            return [{"name": "COMMAND", "row": 11, "col": 24, "width": 4, "hidden": False}]
        return []
    def _bank_default_for_field(self, screen: str, name: str) -> str:
        current = screen.upper()
        if current in {"CARG", "ORDE"} and name == "ITEM":
            return self.bank_last_item or ""
        if current == "ACCT" and name == "ACCTNO":
            return "10001"
        if current == "STMT":
            if name == "ACCTNO":
                return "10001"
            if name == "PERIOD":
                return "2026-04"
        if current == "XFER":
            defaults = {"SRCACCT": "10001", "DSTACCT": "10002", "AMOUNT": "50.00", "MEMO": "LAB TRANSFER", "PIN": "", "AUTHFLAG": "N", "ADMINFLAG": "N", "DEBUGFLAG": "N"}
            return defaults.get(name, "")
        return ""
    def _bank_prepare_form(self, screen: str | None = None) -> None:
        current = (screen or self.bank_current).upper()
        defs = self._bank_field_defs(current)
        previous = dict(self.bank_form_values)
        self.bank_form_values = {}
        for field in defs:
            name = str(field["name"])
            self.bank_form_values[name] = previous.get(name, self._bank_default_for_field(current, name))
        self.bank_focus = 0
    @staticmethod
    def _overlay(line: str, col: int, value: str) -> str:
        base = line.ljust(79)
        pos = max(0, col - 1)
        return (base[:pos] + value + base[pos + len(value):])[:79]
    def _render_bank_form(self) -> tuple[str, tuple[int, int]]:
        self._bank_prepare_form(self.bank_current) if not self.bank_form_values and self._bank_field_defs(self.bank_current) else None
        lines = self._render_bank().splitlines()
        screen = ScreenBuffer()
        for row, line in enumerate(lines[:24], start=1):
            screen.put(row, 1, line[:79])
        defs = self._bank_field_defs(self.bank_current)
        cursor = (22, 1)
        for idx, field in enumerate(defs):
            name = str(field["name"])
            row = int(field["row"])
            col = int(field["col"])
            width = int(field["width"])
            raw_value = self.bank_form_values.get(name, "")[:width]
            screen.add_field(row, col, width, raw_value, name=name, hidden=bool(field.get("hidden", False)), protected=False)
            if idx == self.bank_focus:
                cursor = (row, col + min(len(raw_value), width - 1 if width else 0))
        screen.set_cursor(*cursor)
        return screen.render_plain(), cursor
    def _bank_submit_form(self) -> str:
        current = self.bank_current
        if current == "LOGN":
            return self._bank_login(self.bank_form_values.get("USERID", ""), self.bank_form_values.get("PASSWORD", ""))
        if current == "MENU":
            return self._bank_handle_value(self.bank_form_values.get("SELECTION", ""))
        if current in {"CARG", "ORDE", "ORDR", "ADMN"}:
            value = self.bank_form_values.get("ITEM", self.bank_form_values.get("COMMAND", ""))
            return self._bank_handle_value(value)
        if current == "ACCT":
            snap = self.lab.account_lookup(self.lab_sid, self.bank_form_values.get("ACCTNO", ""))
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("ACCT", self.bank_status)
        if current == "STMT":
            snap = self.lab.statement_lookup(self.lab_sid, self.bank_form_values.get("ACCTNO", ""), self.bank_form_values.get("PERIOD", ""))
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("STMT", self.bank_status)
        if current == "XFER":
            snap = self.lab.transfer(self.lab_sid, self.bank_form_values)
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("XFER", self.bank_status)
        if current == "APRV":
            snap = self.lab.approve(self.lab_sid, self.bank_form_values.get("TXID", ""))
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("APRV", self.bank_status)
        if current == "HACK":
            return self._render_bank("HACK", "USE WEB HACK3270 PANEL")
        return self._render_bank(current, self.bank_status)
    def _bank_overflow(self, value: str) -> tuple[str, bool]:
        data = (value or "").strip().upper()
        if len(data) <= 5:
            return data, False
        self.bank_status = "SIMULATED OVERFLOW CONDITION DETECTED"
        if "ADMN" in data and self.bank_demo_admin:
            self.bank_current = "ADMN"
            self.bank_prev = "CARG"
            self.bank_status = "TRAINING DEMO CONTROL-FLOW REDIRECT ACTIVE"
            return data[:5], True
        return data[:5], False
    def _bank_handle_value(self, value: str) -> str:
        entered = (value or "").strip()
        current = self.bank_current
        if current == "LOGN":
            if not entered:
                return self._render_bank("LOGN", "ENTER USERID AND PASSWORD OR PASSTICKET")
            parts = entered.split()
            if len(parts) >= 3 and parts[1].upper() in {"PTKT", "PASSTICKET"}:
                appl = parts[3] if len(parts) >= 4 else "CICS"
                return self._bank_login_passticket(parts[0], parts[2], appl)
            if "~" in entered and " " not in entered and "/" not in entered:
                user, _, pw = entered.partition("~")
            elif "/PTKT/" in entered.upper() and " " not in entered:
                parts2 = entered.split("/")
                user = parts2[0]
                ticket = parts2[2] if len(parts2) > 2 else ""
                appl = parts2[3] if len(parts2) > 3 else "CICS"
                return self._bank_login_passticket(user, ticket, appl)
            elif "/" in entered and " " not in entered:
                user, _, pw = entered.partition("/")
            else:
                if len(parts) < 2:
                    return self._render_bank("LOGN", "ENTER FORMAT userid password OR userid PTKT ticket [applid]")
                user, pw = parts[0], parts[1]
            return self._bank_login(user, pw)
        if current == "MENU":
            target = entered.upper()
            mapping = {"1": "CARG", "2": "ORDE", "3": "ORDR", "4": "ACCT", "5": "STMT", "6": "XFER", "7": "APRV", "8": "HACK", "9": "LOGN", "LOGN": "LOGN", "MENU": "MENU", "CARG": "CARG", "ORDE": "ORDE", "ORDR": "ORDR", "ACCT": "ACCT", "STMT": "STMT", "XFER": "XFER", "APRV": "APRV", "HACK": "HACK", "ADMN": "ADMN"}
            dest = mapping.get(target, "")
            if dest == "ADMN" and not (self.bank_demo_admin or self._is_special()):
                return self._render_bank("MENU", "TRANSACTION ADMN NOT AUTHORIZED")
            if dest:
                self.bank_prev = self.bank_current
                return self._render_bank(dest, f"{dest} READY")
            return self._render_bank("MENU", "ENTER VALID MENU OPTION")
        if current == "CARG":
            item_no, redirected = self._bank_overflow(entered)
            if redirected:
                return self._render_bank("ADMN", self.bank_status)
            if item_no in self.bank_items:
                self.bank_last_item = item_no
                return self._render_bank("CARG", f"ITEM {item_no} FOUND")
            return self._render_bank("CARG", f"ITEM {item_no or 'BLANK'} NOT FOUND")
        if current == "ORDE":
            item_no = (entered or self.bank_last_item or "").strip().upper()
            if not item_no:
                return self._render_bank("ORDE", "ENTER ITEM NUMBER")
            item = self.bank_items.get(item_no)
            if not item:
                return self._render_bank("ORDE", f"ITEM {item_no} NOT FOUND")
            idx = f"{len(self.bank_orders)+1:05d}"
            self.bank_orders.append({"index": idx, "date": datetime.now().strftime("%m/%d/%y"), "name": item['item_name'], "price": item['price'], "shipping": item['shipping_cost'], "item_number": item_no})
            self.bank_last_item = item_no
            self.bank_prev = "ORDE"
            return self._render_bank("ORDR", f"ORDER {idx} CREATED FOR ITEM {item_no}")
        if current == "ORDR":
            return self._render_bank("ORDR", "ORDER HISTORY REFRESHED")
        if current == "ACCT":
            snap = self.lab.account_lookup(self.lab_sid, entered)
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("ACCT", self.bank_status)
        if current == "STMT":
            parts = entered.split()
            acct = parts[0] if parts else self.bank_form_values.get("ACCTNO", "")
            period = parts[1] if len(parts) > 1 else self.bank_form_values.get("PERIOD", "2026-04")
            snap = self.lab.statement_lookup(self.lab_sid, acct, period)
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("STMT", self.bank_status)
        if current == "XFER":
            parts = entered.split()
            payload = dict(self.bank_form_values)
            if len(parts) >= 3:
                payload.update({"SRCACCT": parts[0], "DSTACCT": parts[1], "AMOUNT": parts[2], "MEMO": " ".join(parts[3:]) if len(parts) > 3 else payload.get("MEMO", "LAB TRANSFER")})
            snap = self.lab.transfer(self.lab_sid, payload)
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("XFER", self.bank_status)
        if current == "APRV":
            txid = entered or self.bank_form_values.get("TXID", "")
            snap = self.lab.approve(self.lab_sid, txid)
            self.bank_status = snap.get("status", self.bank_status)
            return self._render_bank("APRV", self.bank_status)
        if current == "HACK":
            return self._render_bank("HACK", "USE WEB HACK3270 PANEL")
        if current == "ADMN":
            return self._render_bank("ADMN", "ADMIN PANEL READY")
        return self._render_bank("MENU", self.bank_status)
    def _bank_handle_key(self, key: str) -> str | None:
        key_u = (key or "").upper()
        if key_u in {"PF12", "F12"}:
            self.bank_authenticated = False
            self.bank_userid = ""
            self.bank_prev = "LOGN"
            return self._render_bank("LOGN", "SIGNED OFF FROM SIGHBERBANK")
        if key_u in {"PF4", "F4"}:
            if self.bank_authenticated:
                self.bank_prev = self.bank_current
                return self._render_bank("MENU", "MENU REQUESTED")
        if key_u in {"PF3", "F3"}:
            if self.bank_current == "MENU":
                return self._render_bank("LOGN", "BACK TO SIGNON")
            target = self.bank_prev or "MENU"
            self.bank_prev = "MENU"
            return self._render_bank(target, f"RETURNED TO {target}")
        return None
    def _gmvb_execute(self, cmd: str) -> str:
        parts = cmd.strip().split()
        if len(parts) == 1:
            return self._render_bank("LOGN", "ENTER USERID AND PASSWORD")
        action = parts[1].upper()
        if action == "LOGN":
            if len(parts) >= 5 and parts[3].upper() in {"PTKT", "PASSTICKET"}:
                return self._bank_login_passticket(parts[2], parts[4], parts[5] if len(parts) >= 6 else "CICS")
            if len(parts) >= 4:
                return self._bank_login(parts[2], parts[3])
            if len(parts) == 3 and "~" in parts[2]:
                user, _, pw = parts[2].partition("~")
                return self._bank_login(user, pw)
            return self._render_bank("LOGN", "ENTER FORMAT userid password OR userid PTKT ticket")
        if action in {"MENU", "CARG", "ORDE", "ORDR", "ACCT", "STMT", "XFER", "APRV", "HACK", "ADMN"}:
            self.bank_current = action
            if action == "ADMN" and not (self.bank_demo_admin or self._is_special()):
                return self._render_bank("MENU", "TRANSACTION ADMN NOT AUTHORIZED")
            if len(parts) >= 3:
                return self._bank_handle_value(" ".join(parts[2:]))
            return self._render_bank(action, f"{action} READY")
        return self._render_bank(self.bank_current, "UNKNOWN GMVB SUBCOMMAND")
    def run_mcgm_terminal(self, input_driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        self.bank_current = "LOGN"
        self.bank_prev = "LOGN"
        self.bank_status = "ENTER USERID AND PASSWORD"
        self.bank_authenticated = False
        self.bank_userid = ""
        self._bank_prepare_form("LOGN")
        while True:
            screen, cursor = self._render_bank_form()
            send(colors.CLEAR + colors.GREEN + screen + colors.RESET + f"\x1b[{cursor[0]};{cursor[1]}H")
            res = input_driver.read_key()
            if res.key == "EOF":
                return
            key = (res.key or "").upper()
            if key in {"PF12", "F12", "PF4", "F4", "PF3", "F3"}:
                before = self.bank_current
                key_out = self._bank_handle_key(key)
                if key_out is not None:
                    if key in {"PF12", "F12"} and before == "LOGN" and not self.bank_authenticated:
                        send(colors.CLEAR + colors.GREEN + key_out + colors.RESET + "\n")
                        return
                    self._bank_prepare_form(self.bank_current)
                continue
            defs = self._bank_field_defs(self.bank_current)
            if not defs:
                if key in {"ENTER", "TAB", "UP", "DOWN"} or res.text == "~":
                    self._bank_prepare_form(self.bank_current)
                continue
            current_field = defs[self.bank_focus]
            name = str(current_field["name"])
            width = int(current_field["width"])
            value = self.bank_form_values.get(name, "")
            if key in {"TAB", "DOWN", "RIGHT"} or (res.text or "").startswith("~"):
                self.bank_focus = (self.bank_focus + 1) % len(defs)
                continue
            if key == "UP":
                self.bank_focus = (self.bank_focus - 1) % len(defs)
                continue
            if key == "BACKSPACE":
                self.bank_form_values[name] = value[:-1]
                continue
            if key == "ENTER":
                self._bank_submit_form()
                self._bank_prepare_form(self.bank_current)
                continue
            if res.text and not (res.text or "").startswith("~") and len(value) < width:
                self.bank_form_values[name] = value + res.text.upper()


# End of golden-baseline CICS runtime. Removed FIBS/DVCA/CICSLAB patches are archived.
