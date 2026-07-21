from __future__ import annotations
import shlex
from dataclasses import dataclass
from .services import CbsaService
from .bms_screens import panel, main_menu
from .vuln_cics import cics_sqli_screen
from gibson.apps.pin_bruteforce import run_pin_bruteforce, get_active_pin_bruteforce
from gibson.core import dvcapin


def _kv(parts):
    out={}
    for p in parts:
        if '=' in p:
            k,v=p.split('=',1); out[k.lower()]=v
    return out

@dataclass
class CbppSession:
    authenticated: bool = False
    pin_authenticated: bool = False
    error_pending: bool = False
    escape_pending: bool = False
    requested_transid: str = ""
    last_message: str = "CBPP SIGNON REQUIRED"
    secure_mode: bool = False


def _get_cbpp_session(state, userid: str) -> CbppSession:
    sessions = getattr(state, "cbpp_sessions", None)
    if sessions is None:
        sessions = {}; setattr(state, "cbpp_sessions", sessions)
    key=(userid or "DEFAULT").upper()
    if key not in sessions:
        sessions[key]=CbppSession()
    return sessions[key]


def _emit_cbsa_event(state, event: str, userid: str, message: str, *, severity: str="INFO", result: str="SUCCESS"):
    try:
        state.record_security_event(userid or "UNKNOWN", event, message, result=result, service="CICS/CBSA")
    except Exception:
        pass
    if severity.upper() in {"WARN","ALERT","HIGH"}:
        try: state.notify_console(f"GIBCBSA {event} {message}", severity="ALERT" if severity.upper() in {"ALERT","HIGH"} else "WARN")
        except Exception: pass
        try: state.raise_dashboard_alert(message, severity="ALERT" if severity.upper() in {"ALERT","HIGH"} else "WARN", event_type=event)
        except Exception: pass


def cbpp_panel(msg: str="CBPP SIGNON REQUIRED", include_menu_phrase: bool = False) -> str:
    lines = []
    if include_menu_phrase:
        lines += ["CBSA MAIN MENU LOCKED - SIGNON REQUIRED", ""]
    lines += [
        "GACF USERID  ===>",
        "PASSWORD     ===>",
        "COMMAND      ===>",
        "",
        "Enter GACF credentials to start CBSA/OMEN.",
        "Training mode: PA1/PA3 and transaction escape can be explored in vulnerable labs.",
        "PF10 Instructions   PF3 End",
    ]
    return panel("CBPP - CBSA PRE-AUTHENTICATION", lines, msg)


def instructions_panel() -> str:
    return panel("CICS / CBSA / DVCA INSTRUCTIONS", [
        "DVCA: HACK ON exposes 3270 field-attribute training. BUY/PRICE tamper redraws on ENTER.",
        "CBSA: banking sample with CICS/COBOL vulnerabilities for safe training.",
        "CBPP: pre-authentication panel. Vulnerable mode demonstrates PA-key and TRANSID escape.",
        "CEMT/CEDA/CECI/CEDF/CEBR/CSMT: CICS supplied transaction simulations.",
        "Vulnerability labs: protected field tamper, COMMAREA trust, length mismatch, RECEIVE MAP,",
        "business logic bypass, debug leakage, and sensitive logging.",
        "Evidence: review CICS logs, SDSF/SMF, zSecure, dashboard and master console alerts.",
        "PF3/PF12 Back.  This is a safe Gibson educational simulation.",
    ], "INSTRUCTIONS")


def _check_gacf(state, user: str, password: str) -> bool:
    u=(user or "").upper(); p=password or ""
    if not u:
        return False
    try:
        state.racf.load(merge=True)
        if state.racf.verify_password(u, p): return True
    except Exception:
        pass
    # GACF lab fallback credentials deliberately scoped to CBPP training.
    return (u, p.upper()) in {("GACF", "GACF"), ("CBSA", "CBSA"), ("IBMUSER", "SYS1")}


def _parse_login(cmd: str):
    parts=cmd.strip().split()
    kv=_kv(parts)
    user=kv.get('user') or kv.get('userid') or kv.get('id')
    pw=kv.get('pass') or kv.get('password') or kv.get('pw')
    if not user and parts:
        user=parts[0]
    if not pw and len(parts)>=2:
        pw=parts[1]
    return (user or "").upper(), pw or ""


def _cbsa_vuln_panel(state, userid, op: str, args: list[str], svc: CbsaService):
    s=svc.store
    opu=op.upper()
    if opu in {"FIELD", "TAMPER", "PROTECTED"}:
        _emit_cbsa_event(state,"CBSA_PROTECTED_FIELD_TAMPER",userid,"Protected approval flag trusted in vulnerable CBSA mode", severity="WARN")
        return panel("CBSA PROTECTED FIELD TAMPER", ["APPROVAL_FLAG=Y returned from terminal map", "SERVER DECISION: TRUSTED CLIENT FIELD", "RESULT: HIGH-VALUE TRANSFER APPROVED", "SECURE FIX: recompute approval server-side."], "CBSA-PROT-FLD-001")
    if opu in {"COMMAREA", "STATE"}:
        _emit_cbsa_event(state,"CBSA_COMMAREA_TRUST_BYPASS",userid,"Client-returned COMMAREA step trusted", severity="WARN")
        return panel("CBSA COMMAREA TRUST BYPASS", ["RETURNED_STEP=APPROVED", "SERVER DECISION: CONTINUE WITHOUT PRIOR AUTH STEP", "RESULT: transaction sequence bypassed", "SECURE FIX: store authoritative server-side state."], "CBSA-COMM-001")
    if opu in {"BUFFER", "BO", "OVERFLOW"}:
        _emit_cbsa_event(state,"CBSA_BUFFER_OVERFLOW_SIM",userid,"Oversized CICS field simulated adjacent flag corruption", severity="ALERT")
        from gibson.core.abend import symptom_dump
        dump = symptom_dump("ASRA", jobname="CICSGIB1", stepname="CICS", progname="BNKUPD").splitlines()
        return panel("CBSA BUFFER OVERFLOW SIMULATION", ["INPUT LENGTH: 96  TARGET FIELD: 32", "SIMULATED EFFECT: ADJACENT APPROVED-FLAG CORRUPTED", "CICS-LIKE ABEND: ASRA SIMULATED - PROGRAM BNKUPD", ""] + dump + ["", "SECURE FIX: validate length before MOVE/RECEIVE MAP."], "CBSA-ASRA-SIM")
    if opu in {"RECEIVE", "MAP"}:
        _emit_cbsa_event(state,"CBSA_ASRA_SIMULATED_ABEND",userid,"Unsafe RECEIVE MAP length handling simulated", severity="WARN")
        return panel("CBSA RECEIVE MAP VALIDATION", ["MAP FIELD returned longer than program copybook field", "VULNERABLE RESULT: truncation changes transaction type", "SECURE FIX: enforce length and allowed values after RECEIVE MAP."], "CBSA-RECV-001")
    if opu in {"BUSINESS", "LOGIC"}:
        _emit_cbsa_event(state,"CBSA_BUSINESS_LOGIC_BYPASS",userid,"Negative/duplicate transaction accepted in vulnerable mode", severity="WARN")
        return panel("CBSA BUSINESS LOGIC BYPASS", ["AMOUNT=-1000.00", "VULNERABLE RESULT: credit generated by negative debit", "SECURE FIX: enforce amount bounds and idempotency."], "CBSA-BIZ-001")
    if opu in {"DEBUG", "ERROR"}:
        _emit_cbsa_event(state,"CBSA_DEBUG_LEAKAGE",userid,"Program/map/table detail leaked in CBSA error", severity="WARN")
        return panel("CBSA DEBUG ERROR LEAKAGE", ["SQLCODE=-204 TABLE=CBSA.ACCOUNT PLAN=CBSAPLAN", "PROGRAM=BNKSRCH MAPSET=BNKMAP", "SECURE FIX: generic user error plus correlation ID only."], "CBSA-DBG-001")
    if opu in {"LOG", "SENSITIVE"}:
        _emit_cbsa_event(state,"CBSA_SENSITIVE_LOGGING",userid,"Sensitive field written to training evidence", severity="WARN")
        return panel("CBSA SENSITIVE LOGGING", ["TRACE: ACCOUNT=00000103 PIN=****", "VULNERABLE RESULT: sensitive value reached CICS trace", "SECURE FIX: redact before logging."], "CBSA-LOG-001")
    return panel("CBSA VULNERABILITY TRAINING", ["Supported: FIELD, COMMAREA, BUFFER, RECEIVE, BUSINESS, DEBUG, LOG"], "CBSA-VULN")


def execute_omen(state, userid, command=""):
    svc=CbsaService(state); s=svc.store
    cmd=(command or "").strip()
    uc=cmd.upper()
    cbpp=_get_cbpp_session(state, userid)
    cbpp_enabled=bool(getattr(state.config,"cbpp_enabled", True))
    # Auth/PIN is the default training path, including IBMUSER.
    # Instructor bypass must be explicitly enabled by config and is labelled.
    if (userid or '').upper() == 'IBMUSER' and bool(getattr(state.config, 'cbsa_ibmuser_bypass', False)):
        cbpp_enabled = False
    vuln_escape=bool(getattr(state.config,"cbpp_vulnerable_escape_enabled", True)) and not bool(getattr(state.config,"cbpp_secure_mode", False))
    # CBPP pre-authentication gate for OMEN/CBSA and active CBSA sessions.
    if cbpp_enabled and not cbpp.authenticated:
        if not cmd or uc in {"OMEN","CBSA","MENU"}:
            return cbpp_panel(cbpp.last_message, include_menu_phrase=not bool(getattr(state.config,"cbpp_secure_mode", False)))
        if uc in {"PF10","F10","INSTRUCTIONS","INSTR","HELP"}:
            return instructions_panel()
        if uc in {"PA1","PA3"}:
            cbpp.error_pending=True; cbpp.escape_pending=vuln_escape; cbpp.last_message="GIBCBP01I ATTENTION KEY NOT VALID FOR CBPP SIGNON - ENTER TO CONTINUE"
            _emit_cbsa_event(state,"CBSA_CBPP_PAKEY_ESCAPE",userid,cbpp.last_message,severity="ALERT" if vuln_escape else "WARN", result="WARNING")
            return cbpp_panel(cbpp.last_message)
        if cbpp.escape_pending and uc in {"", "ENTER"}:
            cbpp.authenticated=True; cbpp.escape_pending=False; cbpp.last_message="CBPP VULNERABLE ESCAPE ACCEPTED - CBSA MENU"
            _emit_cbsa_event(state,"CBSA_INVALID_TRANSID_ESCAPE",userid,"ENTER continued from CBPP error to CBSA menu",severity="ALERT")
            return main_menu("CBPP BYPASS - TRAINING MODE")
        # typed transaction escape during vulnerable pending state
        first=uc.split()[0] if uc else ""
        if cbpp.escape_pending and first in {"CEMT","CEDA","CECI","CEDF","CEBR","CSMT","CBSA","OMEN"}:
            cbpp.authenticated=True; cbpp.escape_pending=False; cbpp.requested_transid=first
            _emit_cbsa_event(state,"CBSA_INVALID_TRANSID_ESCAPE",userid,f"CBPP escape routed to {first}",severity="ALERT")
            return "GIBSON_CICS_ROUTE:"+cmd
        user,pw=_parse_login(cmd)
        if _check_gacf(state,user,pw):
            cbpp.authenticated=True; cbpp.pin_authenticated=False; cbpp.last_message=f"CBPP SIGNON COMPLETE USER {user} - PIN REQUIRED"
            _emit_cbsa_event(state,"CBSA_CBPP_LOGIN_SUCCESS",user,"CBPP GACF signon successful",severity="INFO")
            return panel("CBSA / OMEN PIN CHALLENGE", ["CBSA MAIN MENU LOCKED - PIN REQUIRED", "", "ENTER CBSA ACCESS PIN ===>", "", "Type configured DVCAPIN or BRUTE FORCE PIN DATASET=GUEST.4CHAR.PIN", "PF3 End"], cbpp.last_message)
        cbpp.last_message="GIBCBP02E GACF USERID OR PASSWORD NOT VALID"
        _emit_cbsa_event(state,"CBSA_CBPP_LOGIN_FAILURE",user or userid,cbpp.last_message,severity="WARN",result="FAILURE")
        return cbpp_panel(cbpp.last_message)
    if cbpp_enabled and cbpp.authenticated and not cbpp.pin_authenticated:
        active_brute = get_active_pin_bruteforce(state, userid or "GUEST", "CBSA OMEN")
        if active_brute is not None and (not uc or uc in {"ENTER", ""}):
            active_brute.maybe_tick(state, reveal_success=True)
            if active_brute.status == 'SUCCESS': cbpp.pin_authenticated=True
            return panel("CBSA / OMEN PIN BRUTE FORCE", (active_brute.frames[-1] if active_brute.frames else active_brute.render_frame()).splitlines(), "CBSA PIN TRAINING")
        if uc.startswith("V "):
            sub=cmd[2:].strip(); parts=sub.split(); op=parts[0].upper() if parts else ""; args=parts[1:]
            if bool(getattr(state.config, "cbsa_vuln", False)):
                return _cbsa_vuln_panel(state, userid, op, args, svc)
            return panel("CBSA SECURITY TRAINING MODE", ["Security Training Mode is disabled."], "DISABLED")
        if uc.startswith("BRUTE FORCE PIN") or uc.startswith("B ") or uc == "B":
            kv = _kv(cmd.split())
            ds = kv.get('dataset') or kv.get('dsn') or (cmd.split()[-1] if "." in cmd.split()[-1] else f"{(userid or 'GUEST').upper()}.4CHAR.PIN")
            sess = run_pin_bruteforce(state, userid or "GUEST", "CBSA OMEN", ds)
            if sess.status == 'SUCCESS': cbpp.pin_authenticated=True
            try:
                from gibson.core.smf.records.type110 import cics_monitor
                cics_monitor(state, userid=userid or 'GUEST', transaction_id='OMEN', program='CBSAOMEN', result='WARNING', applid='CBSA', terminal_id='TERM', correlation_id=getattr(sess, 'correlation_id', ''), detail=f'CBSA/OMEN PIN BRUTE FORCE DATASET={ds}')
            except Exception:
                pass
            return panel("CBSA / OMEN PIN BRUTE FORCE", (sess.frames[-1] if sess.frames else sess.render_frame()).splitlines(), "CBSA PIN TRAINING")
        if uc.startswith("PIN "):
            pin = cmd.split(None,1)[1].strip() if len(cmd.split(None,1))>1 else ""
        else:
            pin = cmd.strip()
        if pin and dvcapin.verify(state, pin):
            cbpp.pin_authenticated=True
            _emit_cbsa_event(state,"CBSA_PIN_SUCCESS",userid,"CBSA/OMEN PIN accepted",severity="INFO")
            return main_menu("CBSA PIN ACCEPTED - OMEN READY")
        if not cmd or uc in {"OMEN","CBSA","MENU"}:
            return panel("CBSA / OMEN PIN CHALLENGE", ["ENTER CBSA ACCESS PIN ===>", "", "B  BRUTE FORCE PIN", "Example: BRUTE FORCE PIN DATASET=GUEST.4CHAR.PIN"], "PIN REQUIRED")
        _emit_cbsa_event(state,"CBSA_PIN_FAILURE",userid,"CBSA/OMEN PIN failed",severity="WARN", result="FAILURE")
        return panel("CBSA / OMEN PIN CHALLENGE", ["ENTER CBSA ACCESS PIN ===>", "", "PIN INVALID", "B  BRUTE FORCE PIN"], "PIN REQUIRED")
    if not cmd or uc in {"OMEN","CBSA","MENU"}: return main_menu()
    if uc in {"PF10","F10","INSTRUCTIONS","INSTR","HELP"}: return instructions_panel()
    if uc in {"LOGOFF","SIGNOFF","CBPP RESET"}:
        cbpp.authenticated=False; cbpp.pin_authenticated=False; cbpp.error_pending=False; cbpp.escape_pending=False; cbpp.last_message="CBPP SIGNON REQUIRED"
        return cbpp_panel("CBPP SESSION RESET")
    active_brute = get_active_pin_bruteforce(state, userid or "GUEST", "CBSA OMEN")
    if active_brute is not None and (not uc or uc in {"ENTER", ""}):
        active_brute.maybe_tick(state, reveal_success=True)
        return panel("CBSA / OMEN PIN BRUTE FORCE", (active_brute.frames[-1] if active_brute.frames else active_brute.render_frame()).splitlines(), "CBSA PIN TRAINING")
    if uc.startswith("BRUTE FORCE PIN") or uc.startswith("B ") or uc == "B":
        kv = _kv(cmd.split())
        ds = kv.get('dataset') or kv.get('dsn') or (cmd.split()[-1] if cmd.split() and "." in cmd.split()[-1] else f"{(userid or 'GUEST').upper()}.4CHAR.PIN")
        sess = run_pin_bruteforce(state, userid or "GUEST", "CBSA OMEN", ds)
        try:
            from gibson.core.smf.records.type110 import cics_monitor
            cics_monitor(state, userid=userid or 'GUEST', transaction_id='OMEN', program='CBSAOMEN', result='WARNING', applid='CBSA', terminal_id='TERM', correlation_id=getattr(sess, 'correlation_id', ''), detail=f'CBSA/OMEN PIN BRUTE FORCE DATASET={ds}')
        except Exception:
            pass
        return panel("CBSA / OMEN PIN BRUTE FORCE", (sess.frames[-1] if sess.frames else sess.render_frame()).splitlines(), "CBSA PIN TRAINING")
    if uc in {"V","TRAIN","VULN"}:
        if not bool(getattr(state.config, "cbsa_vuln", False)):
            return panel("CBSA SECURITY TRAINING MODE", ["Security Training Mode is disabled.", "Start Gibson with --with-cbsa-api --vuln or --with-cbsa-api --cbsa-vuln."], "DISABLED")
        return panel("CBSA SECURITY TRAINING MODE", ["  SQLI <payload>       SQL injection account search", "  IDOR <account>       IDOR account enquiry", "  FIELD                Protected field tamper", "  COMMAREA             Client-state trust", "  BUFFER               Buffer/length mismatch simulation", "  RECEIVE              RECEIVE MAP validation", "  BUSINESS             Business logic bypass", "  DEBUG                Error/debug leakage", "  LOG                  Sensitive logging", "  EVENTS               Evidence/audit viewer", "", "Examples:", "  V SQLI 1001' OR '1'='1", "  V FIELD", "  V BUFFER"], "CBSA TRAINING MODE")
    if uc.startswith("V "):
        if not bool(getattr(state.config, "cbsa_vuln", False)):
            return panel("CBSA SECURITY TRAINING MODE", ["Security Training Mode is disabled.", "Start Gibson with --with-cbsa-api --vuln or --with-cbsa-api --cbsa-vuln."], "DISABLED")
        sub=cmd[2:].strip(); parts=sub.split(); op=parts[0].upper() if parts else ""; args=parts[1:]
        if op == "SQLI": return panel("CBSA SECURITY TRAINING", cics_sqli_screen(s, sub[5:].strip()).splitlines(), "SQLI COMPLETE")
        if op == "IDOR":
            acc=sub.split(None,1)[1].strip().zfill(8); a=svc.account(acc); s.audit("CICS","IDOR_ACCOUNT",acc,"RETURNED",1,scenario="CBSA_VULN_IDOR")
            return panel("CBSA IDOR TRAINING RESULT", [f"ACCOUNT: {a.account_number}", f"CUSTOMER: {a.customer_id}", f"BALANCE: {a.actual_balance}", "OWNERSHIP CHECK: BYPASSED IN TRAINING MODE"], "CBSA-IDOR-001")
        if op == "EVENTS":
            rows=(s.api_audit+s.cics_audit+s.sqli_events+s.vuln_events)[-12:]
            return panel("CBSA SECURITY EVIDENCE VIEW", [f"{r.get('EVENT_ID','')[:20]:<22} {r.get('CHANNEL',''):<5} {r.get('ACTION',''):<22} {r.get('RESULT','')}" for r in rows] or ["NO EVENTS"], "CBSA AUDIT")
        return _cbsa_vuln_panel(state, userid, op, args, svc)
    parts=cmd.split(); op=parts[0].upper(); args=parts[1:]
    try:
        if op=="1":
            c=svc.customer(args[0]); s.audit("CICS","INQCUST",args[0],"OK",1); return panel("CBSA DISPLAY CUSTOMER", [f"CUSTOMER: {c.customer_id}",f"NAME    : {c.name}",f"ADDR1   : {c.address1}",f"STATUS  : {c.status}"])
        if op=="2":
            a=svc.account(args[0]); s.audit("CICS","INQACC",args[0],"OK",1); return panel("CBSA DISPLAY ACCOUNT", [f"ACCOUNT : {a.account_number}",f"CUSTOMER: {a.customer_id}",f"TYPE    : {a.account_type}",f"BALANCE : {a.actual_balance}",f"AVAIL   : {a.available_balance}"])
        if op=="A":
            rows=svc.list_accounts(args[0]); s.audit("CICS","INQACCCU",args[0],"OK",len(rows)); return panel("CBSA CUSTOMER ACCOUNTS", [f"{a.account_number:<10} {a.account_type:<10} BAL {a.actual_balance}" for a in rows] or ["NO ACCOUNTS"])
        kv=_kv(args)
        if op=="3":
            name=kv.get('name',' '.join(args) or 'NEW CUSTOMER'); c=svc.create_customer({'name':name}, channel="CICS"); return panel("CBSA CREATE CUSTOMER", [f"CUSTOMER CREATED: {c.customer_id}",f"NAME: {c.name}"])
        if op=="4":
            a=svc.create_account({'customer_id':kv.get('customer',kv.get('customer_id','1001')),'balance':kv.get('balance','0.00')}, channel="CICS"); return panel("CBSA CREATE ACCOUNT", [f"ACCOUNT CREATED: {a.account_number}",f"CUSTOMER: {a.customer_id}",f"BALANCE: {a.actual_balance}"])
        if op=="5":
            c=svc.update_customer(kv.get('customer',args[0]), {'name':kv.get('name','UPDATED CUSTOMER')}, channel="CICS"); return panel("CBSA UPDATE CUSTOMER", [f"CUSTOMER UPDATED: {c.customer_id}", f"NAME: {c.name}"])
        if op=="6":
            a=svc.credit_debit(kv.get('account',args[0]), kv.get('amount',args[1] if len(args)>1 else '0'), channel="CICS"); return panel("CBSA CREDIT/DEBIT", [f"ACCOUNT: {a.account_number}", f"BALANCE: {a.actual_balance}", f"AVAILABLE: {a.available_balance}"])
        if op=="7":
            src,dst=svc.transfer(kv.get('from'), kv.get('to'), kv.get('amount','0'), channel="CICS"); return panel("CBSA TRANSFER FUNDS", [f"FROM: {src.account_number} BAL {src.actual_balance}", f"TO  : {dst.account_number} BAL {dst.actual_balance}"])
        if op=="8":
            a=svc.delete_account(kv.get('account',args[0]), channel="CICS"); return panel("CBSA DELETE ACCOUNT", [f"ACCOUNT DELETED: {a.account_number}"])
    except Exception as e:
        s.abend("BNKMENU","OMEN","CBSAERR",str(e),cmd)
        return panel("CBSA ERROR", [str(e), "Enter OMEN to return to the main menu."], "ERROR")
    return main_menu("INVALID CBSA OPTION")
