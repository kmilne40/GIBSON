from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, Optional
import re
import uuid

from gibson.core.state import GibsonState

REMOVED_CICS_TRANSACTIONS = {"FIBS","CICSLAB","CICSLAB1","BLAB","GMVB"}


@dataclass
class CicsResourceState:
    """Simulator-safe CICS resource record.

    This is deliberately a bounded training model. It models CICS-like resource
    state and security evidence; it does not run host code or load real modules.
    """
    name: str
    rtype: str
    group: str = "GIBSON"
    status: str = "ENABLED"
    installed: bool = True
    open_state: str = "OPEN"
    attrs: Dict[str, str] = field(default_factory=dict)

    def attr(self, key: str, default: str = "") -> str:
        return self.attrs.get(key.upper(), default)

    def set_attr(self, key: str, value: str) -> None:
        self.attrs[key.upper()] = str(value)


@dataclass
class CicsIncident:
    corrid: str
    ts: datetime
    userid: str
    stage: str
    action: str
    result: str
    detail: str = ""
    transid: str = ""
    resource: str = ""
    resource_class: str = ""


class CicsRegionModel:
    """Stateful training model for a single Gibson CICS region.

    The model supplies resource inventories, simple lifecycle behaviour, and
    audit-friendly security decisions. It is intentionally small and safe, but
    it gives CEMT/CEDA/CECI/CICSPWN-style labs realistic state to interrogate.
    """
    def __init__(self, state: GibsonState, *, applid: str = "CICS", sysid: str = "GIB1", region: str = "CICSGIB1"):
        self.state = state
        self.applid = applid.upper()
        self.sysid = sysid.upper()
        self.region = region.upper()
        self.jobname = "GICS"
        self.release = "CICS TS 6.1 (Gibson simulated)"
        # Identity surfaced to EXEC CICS ASSIGN / INQUIRE SYSTEM (cicspwn -i).
        self.cicstslevel = "0720"          # CICS TS 6.1
        self.cicsrelease = "0720"
        self.cics_version = "6.1"
        self.lu_name = "LU320"
        self.natlang = "E"
        self.files_hlq = "GIBSON"          # HLQ of installed VSAM files
        self.library_path = "GIBSON.CICS.SDFHLOAD"
        self.opsys = "Z"
        self.security = "RACF"
        self.security_options = {"SEC": "YES", "XTRAN": "YES", "XCMD": "YES", "XPCT": "YES", "XFCT": "YES", "XTST": "YES", "XDCT": "YES", "XPPT": "YES", "DFLTUSER": "CICSUSER", "RESSEC": "ASIS", "SPOOL": "YES"}
        self.started = datetime.now()
        self.incidents: list[CicsIncident] = []
        self.transactions: Dict[str, CicsResourceState] = {}
        self.programs: Dict[str, CicsResourceState] = {}
        self.files: Dict[str, CicsResourceState] = {}
        self.tsqueues: Dict[str, CicsResourceState] = {}
        self.tdqueues: Dict[str, CicsResourceState] = {}
        self.terminals: Dict[str, CicsResourceState] = {}
        self.sessions: Dict[str, Dict[str, str]] = {}
        self.tasks: Dict[str, Dict[str, str]] = {}
        self.tsqueue_items: Dict[str, list[str]] = {}
        self.tdqueue_items: Dict[str, list[str]] = {}
        self.log_entries: list[Dict[str, str]] = []
        self.traces: Dict[str, list[str]] = {}
        self.trace_enabled_for: str = ""
        self._task_seq = 0
        self._seed()

    def _seed(self) -> None:
        for name, program, status in [
            ("CESN", "DFHSNP", "ENABLED"), ("CESF", "DFHSFP", "ENABLED"),
            ("CEMT", "DFHEMTP", "ENABLED"), ("CEDA", "DFHEDAP", "ENABLED"),
            ("CECI", "DFHECIP", "ENABLED"), ("CEBR", "DFHBRP", "ENABLED"),
            ("CEDF", "DFHEDF", "ENABLED"), ("CSMT", "DFHCSMT", "ENABLED"),
            ("OMEN", "BNKMENU", "ENABLED"), ("DVCA", "MCSTART", "ENABLED"), ("MCGM", "MCSTART", "ENABLED"),
            ("MCMM", "MCMMENU", "ENABLED"), ("MCOR", "MCORDERS", "ENABLED"), ("MCAD", "MCADDRSS", "ENABLED"),
            ("MCHI", "MCHISTRY", "ENABLED"), ("MCHS", "MCHISTRY", "ENABLED"), ("SCRT", "SECRET", "ENABLED"), ("CUST", "INQCUST", "ENABLED"),
            ("ACCT", "INQACC", "ENABLED"), ("TRAN", "TRANPST", "ENABLED"),
            ("BULK", "BLKPRC", "ENABLED"), ("REST", "RESTTST", "ENABLED"),
            ("TN32", "TN32CAP", "ENABLED"), ("COBL", "CBSAUTIL", "ENABLED"),
            ("ADMN", "CBSAADMN", "DISABLED"),
        ]:
            self.transactions[name] = CicsResourceState(name, "TRANSACTION", status=status, attrs={
                "PROGRAM": program, "TASKDATALOC": "ANY", "PRIORITY": "001", "PROTECTED": "YES" if name in {"CEMT", "CEDA", "CECI"} else "NO"
            })
        for name, length, status in [
            ("DFHWBADX", "000184", "ENABLED"), ("DFH0XCMN", "004096", "ENABLED"),
            ("DFHEMTP", "009728", "ENABLED"), ("DFHEDAP", "011264", "ENABLED"),
            ("DFHECIP", "007680", "ENABLED"), ("DFHCSMT", "005120", "ENABLED"),
            ("BNKMENU", "008192", "ENABLED"), ("MCSTART", "004096", "ENABLED"), ("MCMMENU", "006144", "ENABLED"), ("MCORDERS", "008192", "ENABLED"), ("MCADDRSS", "006144", "ENABLED"), ("MCHISTRY", "006144", "ENABLED"), ("SECRET", "002048", "ENABLED"), ("INQCUST", "006144", "ENABLED"),
            ("CRECUST", "006144", "ENABLED"), ("INQACC", "006144", "ENABLED"),
            ("CREACC", "006144", "ENABLED"), ("XFRFUN", "007168", "ENABLED"),
            ("DBCRFUN", "007168", "ENABLED"), ("TRANPST", "007168", "ENABLED"),
            ("BLKPRC", "005120", "ENABLED"), ("CARDAUTH", "005120", "ENABLED"),
            ("RESTTST", "004096", "ENABLED"), ("TN32CAP", "004096", "ENABLED"),
            ("CBSAADMN", "003584", "DISABLED"), ("DEMO001", "000456", "DISABLED"),
        ]:
            self.programs[name] = CicsResourceState(name, "PROGRAM", status=status, attrs={"LENGTH": length, "USECOUNT": "000000", "RESCOUNT": "000000", "LANGUAGE": "COBOL"})
        for name, dsn, ftype, status, read, update in [
            ("FILEA", "GIBSON.BANK.ACCOUNTS", "KSDS", "ENABLED", "YES", "YES"),
            ("FILEB", "GIBSON.BANK.TRANSFERS", "ESDS", "ENABLED", "YES", "NO"),
            ("BNKSTM", "GIBSON.BANK.STATEMENTS", "KSDS", "ENABLED", "YES", "YES"),
            ("CBSACUST", "CBSA.CUSTOMER", "KSDS", "ENABLED", "YES", "YES"),
            ("CBSAACC", "CBSA.ACCOUNT", "KSDS", "ENABLED", "YES", "YES"),
            ("CBSATRAN", "CBSA.PROCTRAN", "ESDS", "ENABLED", "YES", "NO"), ("DVCAPROD", "KICKS.DVCA.PRODUCTS.VSAM", "KSDS", "ENABLED", "YES", "YES"), ("DVCAHIST", "KICKS.DVCA.HISTORY.VSAM", "KSDS", "ENABLED", "YES", "YES"), ("DVCAADDR", "KICKS.DVCA.ADDRESS.VSAM", "KSDS", "ENABLED", "YES", "YES"),
            ("GACFDB", "SYS1.RACFDS", "KSDS", "ENABLED", "YES", "NO"),
        ]:
            self.files[name] = CicsResourceState(name, "FILE", status=status, open_state="OPEN" if name != "FILEB" else "CLOSED", attrs={"DSN": dsn, "TYPE": ftype, "READ": read, "UPDATE": update})
        for name, items, loc in [("GIBSON", "00000003", "MAIN"), ("BANKAUD", "00000008", "AUX"), ("PWNLOG", "00000000", "MAIN")]:
            self.tsqueues[name] = CicsResourceState(name, "TSQUEUE", attrs={"ITEMS": items, "LOCATION": loc, "LENGTH": "00000080"})
        for name, qtype, intrdr in [("CSSL", "INDIRECT", "NO"), ("CSMT", "EXTRA", "NO"), ("INTR", "EXTRA", "YES")]:
            self.tdqueues[name] = CicsResourceState(name, "TDQUEUE", attrs={"TYPE": qtype, "INTRDR": intrdr})
        self.terminals["LU320"] = CicsResourceState("LU320", "TERMINAL", status="INSERVICE ACQUIRED", attrs={"NETNAME": "LU320", "USERID": ""})
        self.terminals["T0001"] = CicsResourceState("T0001", "TERMINAL", status="INSERVICE RELEASED", attrs={"NETNAME": "TCP0001", "USERID": ""})
        self.tsqueue_items["GIBSON"] = ["GIBSON CICS TEMPORARY STORAGE QUEUE ITEM", "THIS IS A SIMULATED CEBR BROWSE DISPLAY"]
        self.tdqueue_items["CSMT"] = []
        # Record content for VSAM files, browsable/readable through CECI
        # (cicspwn --get-file / READ FILE / STARTBR-READNEXT). FILEA is the
        # classic CICS sample file shape.
        self.file_records: Dict[str, list[str]] = {
            "FILEA": [
                "000111 S. D. BORMAN     SURREY, ENGLAND         44-2316 261181 $0000.00",
                "000222 J. D. GOODMAN    BANGOR, WALES           44-3810 030680 $0100.11",
                "000333 H. O. ROSE       LONDON, ENGLAND         44-4068 160282 $0500.00",
                "000444 J. M. ARNOLD     MANCHESTER, ENGLAND     44-5142 040383 $0205.50",
                "000555 K. P. SINGH      LEICESTER, ENGLAND      44-6219 120783 $1000.00",
            ],
            "BNKSTM": [
                "0001 STATEMENT ACCT 0001 BAL 0000123456 CR",
                "0002 STATEMENT ACCT 0002 BAL 0000987654 CR",
            ],
            "CBSACUST": [
                "0000000001 JOHN SMITH         99 BANK ST  EDINBURGH  EH1 1AA",
                "0000000002 ALICE WONG         12 HIGH RD  GLASGOW    G1 2BB",
            ],
            "GACFDB": [
                "IBMUSER  SPECIAL OPERATIONS OMVS(UID=0) PASSWORD=********",
                "GUEST    NONE              OMVS(UID=99) PASSWORD=********",
            ],
        }
        try:
            for n in ["OMEN", "CSMT", "CEDF", "CEMT", "CEDA", "CECI", "CEBR", "CESN", "CESF"]:
                if self.state.dynamic_racf._find_profile("TCICSTRN", n) is None:
                    self.state.dynamic_racf.define("TCICSTRN", n, "IBMUSER", "READ")
            for n in ["CBSACUST", "CBSAACC", "CBSATRAN", "FILEA", "FILEB"]:
                if self.state.dynamic_racf._find_profile("FCICSFCT", n) is None:
                    self.state.dynamic_racf.define("FCICSFCT", n, "IBMUSER", "READ")
        except Exception:
            pass
        self.start_task("CICS", "DFHSIP", "SYSTEM")
        self.add_log("INFO", "CICS", "SYSTEM", "GIBCICS region initialized")

    def corrid(self, prefix: str = "CICS") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    def _log_oper(self, message: str) -> None:
        try:
            self.state.notify_console(message, severity="INFO")
        except Exception:
            pass

    def record_security(self, userid: str, event: str, detail: str, *, result: str = "SUCCESS", transid: str = "", resource: str = "", cls: str = "", profile: str = "", service: str = "CICS", corrid: str = "", terminal: str = "LU320") -> None:
        corrid = corrid or self.corrid("CIC")
        extra = {
            "USERID": (userid or "UNKNOWN").upper(), "GROUP": self.state._resolve_user_group(userid or "UNKNOWN"),
            "EVENT": event.upper(), "RESULT": result.upper(), "SYSTEM": getattr(self.state.network, "hostname", "MVSC").upper(),
            "JOBNAME": self.jobname, "CLASS": (cls or "CICS").upper(), "RESOURCE": (resource or transid or self.applid).upper(),
            "PROFILE": (profile or resource or transid or self.applid).upper(), "SERVICE": service.upper(), "MESSAGE_ID": "ICH408I",
            "TERMINAL": terminal, "APPLID": self.applid, "TRANSID": transid.upper(), "TERMID": terminal, "REGION": self.region,
            "CORRID": corrid, "DETAIL": detail,
        }
        if self.state.audit is not None:
            self.state.audit.record_smf80(userid or "UNKNOWN", event.upper(), detail, result=result.upper(), extra=extra)
        self.incidents.append(CicsIncident(corrid, datetime.now(), (userid or "UNKNOWN").upper(), event.upper(), detail, result.upper(), detail, transid.upper(), (resource or "").upper(), (cls or "").upper()))
        sev = "INFO" if result.upper() == "SUCCESS" else "ALERT"
        self.state.notify_console(f"DFHXS1101 {self.region} USER={userid.upper() if userid else 'UNKNOWN'} TRANSID={transid.upper() if transid else '----'} EVENT={event.upper()} RESULT={result.upper()} CORRID={corrid} {detail}".strip(), severity=sev)

    def security_status_lines(self) -> list[str]:
        opts = self.security_options
        return [
            "CICS SECURITY STATUS",
            f"  SEC      : {opts.get('SEC','YES')}",
            f"  XTRAN    : {opts.get('XTRAN','YES')}",
            f"  XCMD     : {opts.get('XCMD','YES')}",
            f"  XPCT     : {opts.get('XPCT','YES')}",
            f"  XFCT     : {opts.get('XFCT','YES')}",
            f"  XTST     : {opts.get('XTST','YES')}",
            f"  XDCT     : {opts.get('XDCT','YES')}",
            f"  XPPT     : {opts.get('XPPT','YES')}",
            f"  DFLTUSER : {opts.get('DFLTUSER','CICSUSER')}",
            f"  RACF     : {self.security}",
            f"  REGION   : {self.jobname}",
        ]

    # --- EXEC CICS ASSIGN / INQUIRE SYSTEM value providers (cicspwn -i) -------
    def assign_value(self, option: str, *, userid: str = "", terminal: str = "LU320") -> str:
        o = (option or "").upper()
        opts = self.security_options
        table = {
            "APPLID": self.applid, "SYSID": self.sysid, "QNAME": self.applid,
            "USERID": (userid or opts.get("DFLTUSER", "CICSUSER")).upper(),
            "OPID": "GIB", "OPCLASS": "1",
            "NETNAME": terminal or self.lu_name, "TERMINAL": terminal or self.lu_name,
            "PRINSYSID": self.sysid, "NATLANGINUSE": self.natlang, "LANGINUSE": self.natlang,
            "CICSREL": self.cicsrelease, "RELEASE": self.cicstslevel, "CICSTSLEVEL": self.cicstslevel,
            "OPSYS": self.opsys, "OPSYSREL": "270", "STARTCODE": "TO",
            "PROGRAM": "DFHECIP", "ABCODE": "    ", "FCI": "01",
        }
        return table.get(o, "")

    def inquire_system_value(self, option: str) -> str:
        o = (option or "").upper()
        table = {
            "CICSTSLEVEL": self.cicstslevel, "RELEASE": self.cicstslevel,
            "CICSSYS": self.sysid, "SYSID": self.sysid, "APPLID": self.applid,
            "JOBNAME": self.jobname, "OPSYS": self.opsys, "OPREL": "270",
            "DFLTUSER": self.security_options.get("DFLTUSER", "CICSUSER"),
            "SECURITYMGR": "EXTERNAL" if self.racf_active() else "NONE",
            "XAPPLID": self.applid, "DTRPGM": "DFHDYP", "DSALIMIT": "0008388608",
            "GMMTEXT": "GIBSON CICS / GICS", "PROGAUTOINST": "ACTIVE",
        }
        return table.get(o, "")

    def racf_active(self) -> bool:
        return self.security_options.get("SEC", "YES").upper() == "YES" and self.security.upper() in ("RACF", "ACF2", "TOPSECRET")

    def spool_enabled(self) -> bool:
        return self.security_options.get("SPOOL", "YES").upper() == "YES"

    def files_hlq_value(self) -> str:
        # Derive the HLQ from installed file DSNs (cicspwn reports "Files HLQ").
        for res in self.files.values():
            dsn = res.attrs.get("DSN", "") if res.attrs else ""
            if dsn:
                return dsn.split(".")[0]
        return self.files_hlq

    def copy_transaction(self, old: str, new: str, group: str = "GIBSON", userid: str = "", corrid: str = "") -> str:
        """CEDA COPY of a transaction. The copy is deliberately NOT security
        protected, which is exactly how cicspwn --bypass evades RACF."""
        o, n = old.upper(), new.upper()
        src = self.transactions.get(o)
        prog = (src.attrs.get("PROGRAM", "DFHEMTP") if src and src.attrs else "DFHEMTP")
        self.transactions[n] = CicsResourceState(n, "TRANSACTION", status="ENABLED", attrs={
            "PROGRAM": prog, "TASKDATALOC": "ANY", "PRIORITY": "001",
            "PROTECTED": "NO", "COPIEDFROM": o, "GROUP": group})
        self.record_security(userid or "CICSUSER", "CICS RESOURCE COPY",
                             f"CEDA COPY TRANS({o}) AS({n}) creates an unprotected alias of {o}",
                             result="WARNING", transid="CEDA", resource=n, cls="TCICSTRN",
                             profile=n, corrid=corrid)
        return prog

    def alias_target(self, transid: str) -> str:
        """Resolve a copied/alias transid to the supplied transaction it runs."""
        t = (transid or "").upper()
        res = self.transactions.get(t)
        if not res or not res.attrs:
            return ""
        prog = res.attrs.get("PROGRAM", "")
        return {"DFHEMTP": "CEMT", "DFHECIP": "CECI", "DFHEDAP": "CEDA",
                "DFHEDF": "CEDF", "DFHBRP": "CEBR"}.get(prog, "") if t not in {"CEMT", "CECI", "CEDA", "CEDF", "CEBR"} else ""

    def set_sit_option(self, userid: str, key: str, value: str) -> str:
        k = (key or '').upper(); v = (value or '').upper()
        if k not in {"SEC", "XTRAN", "XCMD", "XPCT", "XFCT", "XTST", "XDCT", "XPPT", "DFLTUSER"}:
            return f"DFHXS0001 SIT OPTION {k} NOT RECOGNIZED"
        if k != "DFLTUSER" and v not in {"YES", "NO", "ON", "OFF"}:
            return f"DFHXS0002 SIT OPTION {k} REQUIRES YES OR NO"
        if v == "ON": v = "YES"
        if v == "OFF": v = "NO"
        if k == "DFLTUSER":
            rec = self.state.racf.get(v)
            if rec is None:
                return f"DFHXS0004 DFLTUSER {v} NOT DEFINED"
        self.security_options[k] = v
        self.record_security(userid, "CICS SIT CHANGE", f"{k}={v}", result="SUCCESS", transid="CEMT", resource=k, cls="OPERCMDS", profile=f"CICS.SIT.{k}", corrid=self.corrid('SIT'))
        return f"DFHXS1200 {k} SET TO {v}"

    def check_transaction(self, userid: str, transid: str, *, access: str = "READ", corrid: str = "") -> tuple[bool, str]:
        t = (transid or "").upper()
        if self.security_options.get('SEC','YES') != 'YES' or self.security_options.get('XTRAN','YES') != 'YES':
            return True, ""
        if t not in self.transactions:
            return False, f"DFHAC2001 TRANSACTION {t} IS NOT DEFINED"
        if self.transactions[t].status.startswith("DIS"):
            self.record_security(userid, "CICS TRANSACTION ACCESS", f"TRANSACTION {t} DISABLED", result="FAILURE", transid=t, resource=t, cls="TCICSTRN", profile=t, corrid=corrid)
            return False, f"DFHAC2206 TRANSACTION {t} IS DISABLED"
        allowed = self.state.dynamic_racf.has_access("TCICSTRN", t, userid, access, self.state.racf)
        if not allowed:
            self.record_security(userid, "CICS TRANSACTION ACCESS", f"ACCESS {access} TO TRANSACTION {t} DENIED", result="FAILURE", transid=t, resource=t, cls="TCICSTRN", profile=t, corrid=corrid)
            return False, f"DFHXS1111 USER {userid.upper()} NOT AUTHORIZED FOR TRANSACTION {t}"
        self.record_security(userid, "CICS TRANSACTION ACCESS", f"ACCESS {access} TO TRANSACTION {t} ALLOWED", result="SUCCESS", transid=t, resource=t, cls="TCICSTRN", profile=t, corrid=corrid)
        return True, ""

    def check_file(self, userid: str, file_name: str, *, access: str = "READ", transid: str = "", corrid: str = "") -> tuple[bool, str]:
        f = (file_name or "").upper()
        if self.security_options.get('SEC','YES') != 'YES' or self.security_options.get('XFCT','YES') != 'YES':
            return True, ""
        if f not in self.files:
            return False, f"DFHFC0999 FILE {f} IS NOT DEFINED"
        allowed = self.state.dynamic_racf.has_access("FCICSFCT", f, userid, access, self.state.racf)
        if not allowed:
            self.record_security(userid, "CICS FILE ACCESS", f"ACCESS {access} TO FILE {f} DENIED", result="FAILURE", transid=transid, resource=f, cls="FCICSFCT", profile=f, corrid=corrid)
            return False, f"DFHXS1112 USER {userid.upper()} NOT AUTHORIZED FOR FILE {f}"
        self.record_security(userid, "CICS FILE ACCESS", f"ACCESS {access} TO FILE {f} ALLOWED", result="SUCCESS", transid=transid, resource=f, cls="FCICSFCT", profile=f, corrid=corrid)
        return True, ""

    def signon(self, userid: str, terminal: str = "LU320") -> None:
        u = (userid or "UNKNOWN").upper()
        self.sessions[u] = {"USERID": u, "TERMID": terminal, "SIGNON": datetime.now().strftime("%H:%M:%S"), "APPLID": self.applid}
        if terminal in self.terminals:
            self.terminals[terminal].attrs["USERID"] = u
        self.record_security(u, "CICS SIGNON", f"USER {u} SIGNED ON TO {self.applid}", result="SUCCESS", transid="CESN", resource=self.applid, cls="APPL", profile=self.applid, terminal=terminal)

    def signoff(self, userid: str, terminal: str = "LU320") -> None:
        u = (userid or "UNKNOWN").upper()
        self.sessions.pop(u, None)
        if terminal in self.terminals:
            self.terminals[terminal].attrs["USERID"] = ""
        self.record_security(u, "CICS SIGNOFF", f"USER {u} SIGNED OFF FROM {self.applid}", result="SUCCESS", transid="CESF", resource=self.applid, cls="APPL", profile=self.applid, terminal=terminal)

    def define_program(self, name: str, *, group: str = "GIBSON", language: str = "COBOL", corrid: str = "", userid: str = "IBMUSER") -> CicsResourceState:
        n = name.upper()
        res = CicsResourceState(n, "PROGRAM", group=group.upper(), status="DISABLED", installed=False, attrs={"LENGTH": "000256", "USECOUNT": "000000", "RESCOUNT": "000000", "LANGUAGE": language.upper()})
        self.programs[n] = res
        self.record_security(userid, "CICS RESOURCE DEFINE", f"CEDA DEFINE PROGRAM({n}) GROUP({group.upper()})", transid="CEDA", resource=n, cls="CICSPROG", profile=n, corrid=corrid)
        return res

    def define_transaction(self, name: str, *, program: str = "MYPROG", group: str = "GIBSON", corrid: str = "", userid: str = "IBMUSER") -> CicsResourceState:
        n = name.upper(); p = program.upper()
        if n in REMOVED_CICS_TRANSACTIONS:
            raise ValueError(f"TRANSACTION {n} WAS REMOVED FROM THE GOLDEN RUNTIME")
        res = CicsResourceState(n, "TRANSACTION", group=group.upper(), status="DISABLED", installed=False, attrs={"PROGRAM": p, "TASKDATALOC": "ANY", "PRIORITY": "001", "PROTECTED": "YES"})
        self.transactions[n] = res
        if self.state.dynamic_racf._find_profile("TCICSTRN", n) is None:
            self.state.dynamic_racf.define("TCICSTRN", n, "IBMUSER", "NONE")
            self.state.dynamic_racf.save()
        self.record_security(userid, "CICS RESOURCE DEFINE", f"CEDA DEFINE TRANSACTION({n}) PROGRAM({p}) GROUP({group.upper()})", transid="CEDA", resource=n, cls="TCICSTRN", profile=n, corrid=corrid)
        return res

    def install_group(self, group: str, *, corrid: str = "", userid: str = "IBMUSER") -> list[str]:
        g = group.upper()
        installed: list[str] = []
        for coll in (self.programs, self.transactions, self.files):
            for res in coll.values():
                if res.group == g:
                    res.installed = True
                    if res.status.startswith("DIS"):
                        res.status = "ENABLED"
                    installed.append(f"{res.rtype}({res.name})")
        self.record_security(userid, "CICS RESOURCE INSTALL", f"CEDA INSTALL GROUP({g}) INSTALLED={','.join(installed) or 'NONE'}", transid="CEDA", resource=g, cls="CICSCSD", profile=g, corrid=corrid)
        return installed

    def rows(self, kind: str) -> Iterable[CicsResourceState]:
        k = kind.upper()
        if k.startswith("FILE"):
            return self.files.values()
        if k.startswith("PROG"):
            return self.programs.values()
        if k.startswith("TRAN"):
            return self.transactions.values()
        if k.startswith("TSQ") or k.startswith("TSQUEUE"):
            return self.tsqueues.values()
        if k.startswith("TDQ") or k.startswith("TDQUEUE"):
            return self.tdqueues.values()
        if k.startswith("TERM"):
            return self.terminals.values()
        if k.startswith("TASK"):
            return [CicsResourceState(v["TASK"], "TASK", status=v.get("STATUS", ""), attrs=v) for v in self.tasks.values()]
        return []

    def add_log(self, kind: str, transid: str, userid: str, message: str, *, corrid: str = "") -> None:
        row = {"time": datetime.now().strftime("%H:%M:%S"), "type": kind.upper(), "transid": transid.upper(), "userid": (userid or "UNKNOWN").upper(), "message": message, "corrid": corrid or self.corrid("LOG")}
        self.log_entries.append(row)
        self.log_entries = self.log_entries[-200:]
        if row["type"] in {"SECURITY", "ABEND", "ERROR"}:
            self._log_oper(f"DFHLOG {row['type']} TRAN={row['transid']} USER={row['userid']} {message}")

    def start_task(self, transid: str, program: str, userid: str, terminal: str = "LU320") -> str:
        self._task_seq += 1
        tid = f"{self._task_seq:06d}"
        self.tasks[tid] = {"TASK": tid, "TRAN": transid.upper(), "PROGRAM": program.upper(), "USERID": (userid or "UNKNOWN").upper(), "TERMID": terminal, "STATUS": "RUNNING", "START": datetime.now().strftime("%H:%M:%S"), "ABEND": ""}
        self.add_log("ATTACH", transid, userid, f"Task {tid} attached program {program}")
        return tid

    def complete_task(self, tid: str, status: str = "COMPLETE", abend: str = "") -> None:
        if tid in self.tasks:
            self.tasks[tid]["STATUS"] = status.upper()
            self.tasks[tid]["ABEND"] = abend.upper()

    def abend(self, userid: str, transid: str, code: str, message: str, *, program: str = "") -> str:
        corrid = self.corrid("ABD")
        self.add_log("ABEND", transid, userid, f"ABEND {code}: {message}", corrid=corrid)
        self.incidents.append(CicsIncident(corrid, datetime.now(), userid.upper(), "CICS ABEND", message, "FAILURE", message, transid.upper(), program.upper(), code.upper()))
        return corrid

    def write_tsq(self, qname: str, text: str) -> None:
        q = qname.upper()
        self.tsqueue_items.setdefault(q, []).append(text)
        self.tsqueues[q] = CicsResourceState(q, "TSQUEUE", attrs={"ITEMS": f"{len(self.tsqueue_items[q]):08d}", "LOCATION": "MAIN", "LENGTH": f"{max([len(x) for x in self.tsqueue_items[q]]+[0]):08d}"})

    def read_tsq(self, qname: str) -> list[str]:
        return list(self.tsqueue_items.get(qname.upper(), []))

    def delete_tsq(self, qname: str) -> bool:
        q = qname.upper()
        existed = q in self.tsqueue_items or q in self.tsqueues
        self.tsqueue_items.pop(q, None); self.tsqueues.pop(q, None)
        return existed

    def write_tdq(self, qname: str, text: str) -> None:
        q = qname.upper()
        self.tdqueue_items.setdefault(q, []).append(text)
        self.tdqueues.setdefault(q, CicsResourceState(q, "TDQUEUE", attrs={"TYPE": "EXTRA", "INTRDR": "NO"}))

    def read_tdq(self, qname: str) -> list[str]:
        return list(self.tdqueue_items.get(qname.upper(), []))

    def cicspwn_probe(self, userid: str = "UNKNOWN") -> dict:
        """Return structured, simulator-safe CICSPWN-style discovery results."""
        corrid = self.corrid("PWN")
        self.record_security(userid, "CICSPWN DISCOVERY", "CICSPWN staged discovery started", result="SUCCESS", transid="PWN", resource=self.applid, cls="APPL", profile=self.applid, corrid=corrid)
        def trans_status(t: str) -> dict:
            res = self.transactions.get(t)
            if not res:
                return {"name": t, "state": "unavailable", "reason": "not defined"}
            ok = self.state.dynamic_racf.has_access("TCICSTRN", t, userid, "READ", self.state.racf)
            if not ok:
                state = "denied"
            elif res.status.startswith("DIS"):
                state = "disabled"
            else:
                state = "available"
            return {"name": t, "state": state, "program": res.attr("PROGRAM"), "status": res.status}
        tx = [trans_status(x) for x in ("CESN", "CEMT", "CEDA", "CECI", "CEBR", "OMEN")]
        files = [{"name": r.name, "state": "available" if self.state.dynamic_racf.has_access("FCICSFCT", r.name, userid, "READ", self.state.racf) else "denied", "dsn": r.attr("DSN"), "open": r.open_state, "status": r.status} for r in self.files.values()]
        programs = [{"name": r.name, "state": "available" if r.installed and not r.status.startswith("DIS") else "disabled", "status": r.status, "language": r.attr("LANGUAGE")} for r in self.programs.values()]
        queues = [{"name": r.name, "type": r.rtype, "state": "available", **r.attrs} for r in list(self.tsqueues.values()) + list(self.tdqueues.values())]
        sessions = list(self.sessions.values()) or [{"USERID": userid.upper(), "TERMID": "LU320", "APPLID": self.applid, "SIGNON": "SIMULATED"}]
        can_abuse = any(x["name"] in {"CECI", "CEDA", "CEMT"} and x["state"] == "available" for x in tx)
        if can_abuse:
            outcome = "bounded-simulation-possible"
            result = "SUCCESS"
        else:
            outcome = "blocked-by-transaction-security"
            result = "FAILURE"
        self.record_security(userid, "CICSPWN CAPABILITY", f"CICSPWN capability assessment {outcome}", result=result, transid="PWN", resource="CICSPWN", cls="TCICSTRN", profile="CICSPWN", corrid=corrid)
        return {"corrid": corrid, "applid": self.applid, "region": self.region, "sysid": self.sysid, "security": self.security, "transactions": tx, "files": files, "programs": programs, "queues": queues, "sessions": sessions, "outcome": outcome}


def get_cics_region(state: GibsonState) -> CicsRegionModel:
    model = getattr(state, "cics_region_model", None)
    if model is None:
        model = CicsRegionModel(state)
        setattr(state, "cics_region_model", model)
    return model


def parse_define(text: str) -> tuple[str, str, Dict[str, str]]:
    u = (text or "").upper()
    m = re.search(r"\b(PROGRAM|PROG|TRANSACTION|TRAN|FILE)\(([^)]+)\)", u)
    if not m:
        return "", "", {}
    attrs = {k.upper(): v.upper() for k, v in re.findall(r"([A-Z0-9]+)\(([^)]+)\)", u)}
    return m.group(1), m.group(2).strip().upper(), attrs
