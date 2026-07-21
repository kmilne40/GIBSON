from __future__ import annotations

import os
import re
import shlex
from datetime import datetime
from pathlib import Path

from gibson.core.state import GibsonState
from gibson.core.security_mode import is_secure_mode, is_noracf_mode, secure_block_message
from gibson.core.passticket import get_passticket_service
from gibson.core.transfers import get_transfer_manager
from gibson.core.healthcheck import get_healthchecker
from gibson.compat import transcripts as tr
from gibson.languages.rexx import RexxInterpreter
from gibson.core.training_shell import start_training_shell
from gibson.core.acf2 import Acf2Bridge
from gibson.languages.cobol import CobolSimulator
from gibson.apps.db2_sim import Db2Simulator
from gibson.apps.sdsf import SdsfApp
from gibson.security import icsf
from gibson.apps.racf_services import racf_services_command
from gibson.apps.training.racf_labs import racf_lab_command
from gibson.apps.parmlib import parmlib_command
from gibson.apps.cics_resources import cics_resource_command
from gibson.apps.zsecure_engine import zsecure_command
from gibson.apps.endevor import endevor_command
from gibson.apps.ims import ims_command
from gibson.apps.mvp import mvp_command
from gibson.core.security_freeze import hash_password as freeze_hash_password, verify_password_hash as freeze_verify_password_hash
from gibson.core import v26_features


class TsoCommandProcessor:
    @staticmethod
    def _has_operand(text: str, operand: str) -> bool:
        return bool(re.search(rf"(?:^|\s){re.escape(operand.upper())}(?:\s|$)", (text or "").upper()))

    """TSO/READY command processor.

    This class intentionally preserves the command surface from the original
    Gibson ``gibson-new.py`` implementation while routing the work through the
    upgraded shared backend (RACF, catalog, JES, templates, DB2, etc.).
    Interactive commands such as EDIT, CONSOLE, OMVS, ISPF and SDSF are
    recognised here for non-interactive callers, but the live telnet session
    handles their full-screen/loop behaviour.
    """

    LEGACY_HELP = {
        "START": "Launches the ISPF menu.",
        "ISPF": "Launches the ISPF menu.",
        "EXIT": "Exits the session.",
        "LOGOFF": "Logs off the current user.",
        "CONSOLE": "Enters the system console mode (SPECIAL only).",
        "SDSF": "Displays the SDSF screen.",
        "OMVS": "Launches the OMVS shell.",
        "ADDUSER": "ADDUSER userid PASSWORD(pw)|PASS(pw) <SPECIAL|OPERATIONS|AUDITOR|ROAUDIT|UAUDIT> <TSO(...)> <OMVS(...)> <DFP(...)>",
        "ALTUSER": "ALTUSER userid PASSWORD(pw)|REVOKE|RESUME <ROAUDIT|NOROAUDIT> <TSO(...)|NOTSO> <OMVS(...)|NOOMVS> <DFP(...)|NODFP> <MFA(...)|NOMFA>.",
        "IPLINFO": "Displays IPL and system configuration summary.",
        "PARMLIB": "PARMLIB <member> - browse simulated SYS1.PARMLIB.",
        "PROCLIB": "PROCLIB <member> - browse simulated SYS1.PROCLIB.",
        "APF": "APF - display simulated APF list.",
        "LINKLIST": "LINKLIST - display simulated linklist.",
        "RACFSERV": "RACFSERV <option> - RACF Services option menu.",
        "RACFLAB": "RACFLAB START|FIX|RESET lab - denial/fix security labs.",
        "SETROPTS LIST": "Displays system options (restricted).",
        "SEARCH CLASS(USER)": "Lists users with SPECIAL privileges.",
        "LISTCAT LEVEL(SYS1)": "Lists SYS1 level files.",
        "RACLIST": "Displays RACF profile details.",
        "LISTUSER": "LISTUSER userid <ALL|TSO|OMVS|DFP|MFA> - displays user details and segments.",
        "SEND": "Sends a message. Format: SEND 'message' USER(username) NOW|LOGON.",
        "EDIT": "Edits a data set or member.",
        "OEDIT": "Edits a z/OS UNIX file using ISPF File Edit.",
        "OGET": "Copies a z/OS UNIX file into an MVS data set.",
        "OPUT": "Copies an MVS data set into a z/OS UNIX file.",
        "REXX": "Executes a REXX script.",
        "LISTCAT": "Lists files in your catalog.",
        "VIEW": "Views a data set or member.",
        "CLEAR": "Clears the screen.",
        "IND$FILE": "IND$FILE GET DSN(dataset) LOCAL(file) | PUT LOCAL(file) DSN(dataset) - simulated host file transfer.",
        "TRANSMIT": "TRANSMIT userid DA('dataset') <OUTDSN('package')> - create a simulated XMIT package.",
        "XMIT": "Alias of TRANSMIT.",
        "RECEIVE": "RECEIVE INDSN('package') <DA('target')> - restore a transmitted data set.",
        "CK": "CK <REFRESH|DISPLAY checkid|START checkid|STOP checkid> - health checker commands.",
        "SECEVENTS": "Displays recent SMF80-style security events.",
        "DEL": "Deletes a data set.",
        "SUBMIT": "Submits a JCL job.",
        "SESSIONSTATS": "Displays session statistics.",
        "HELP": "Displays this help information.",
        "JES": "Simulated Job Entry Subsystem commands: JES STATUS, JES SUBMIT <description>.",
        "DSN": "Starts simulated DB2 command processing.",
        "SPUFI": "Runs the simulated DB2/SPUFI interface.",
        "RUN SQL": "Runs SQL through the simulated DB2 engine.",
        "ALIAS": "ALIAS LIST | ALIAS name expansion | ALIAS DELETE name.",
        "ADDGROUP": "ADDGROUP groupname - define a RACF group.",
        "LISTGRP": "LISTGRP <group|*> - list RACF groups.",
        "CONNECT": "CONNECT userid GROUP(group) <AUTHORITY(USE)>.",
        "REMOVE": "REMOVE userid GROUP(group).",
        "RDEFINE": "RDEFINE class profile <UACC(access)>.",
        "RLIST": "RLIST class profile.",
        "PERMIT": "PERMIT profile CLASS(class) ID(userid) ACCESS(access).",
        "PTKTGEN": "PTKTGEN USER(userid) APPL(applid) - generate a simulated PassTicket.",
        "PTKTSTAT": "PTKTSTAT <APPL(applid)> - display PTKTDATA profiles and issued PassTickets.",
        "PTKTUSE": "PTKTUSE USER(userid) APPL(applid) TICKET(ticket) - validate a PassTicket.",
        "MFA": "MFA <ON|OFF|STATUS> - IBMUSER-controlled simulator MFA using PIN+HHMM token after IPL PIN setup.",
        "ICSF": "ICSF STATUS | REFRESH <MASTERKEY|CKDS|PKDS|TKDS> - simulated ICSF control plane.",
        "DEFINE ALIAS": "DEFINE ALIAS(NAME(alias) RELATE(catalog)).",
        "PROFILE": "Displays or changes the TSO profile prefix and terminal options.",
        "LISTDS": "LISTDS dataset STATUS HISTORY | MEMBERS - displays dataset attributes.",
        "LISTDSD": "LISTDSD DATASET('dataset') ALL - displays RACF dataset profile.",
        "RENAME": "RENAME old new - renames a dataset.",
        "NETSTAT": "NETSTAT HOME|CONN|ALL|DEVLINKS|ROUTE|ARP|PORTLIST|TELNET|FTP.",
        "PING": "PING host - simulated z/OS TCP/IP ping.",
        "TRACERTE": "TRACERTE host - simulated z/OS traceroute.",
        "FTP": "FTP host <port> - prompts for Name and Password before ftp>; USER PASS PWD CD/CWD LS DIR GET PUT ASCII BINARY QUIT HELP after login.",
        "TELNET": "TELNET host <port> or OPEN host <port>; login and Password prompts appear before telnet>; CLOSE QUIT EXIT end the session.",
        "RVARY": "Displays simulated RACF database status.",
        "SETPROG": "SETPROG APF,ADD|DELETE,DSNAME=...,VOLUME=... updates simulated APF list.",
        "ACF2": "Switches READY prompt security administration to ACF2 command equivalents.",
        "RACF": "Switches READY prompt security administration back to RACF command syntax.",
        "SHOW": "ACF2 mode: SHOW ACF2|TSO|PSWD|DDSN|MODE.",
        "SET": "ACF2 mode: SET LID|RULE|RESOURCE(type)|CONTROL(GSO)|PROFILE(GROUP) DIV(OMVS).",
        "LIST": "ACF2 mode: LIST userid|LIKE(-) or LIST current rules/profiles.",
        "INSERT": "ACF2 mode: INSERT logonid/group/profile in the active ACF2 setting.",
        "CHANGE": "ACF2 mode: CHANGE active logonid/group/profile in the active ACF2 setting.",
        "DELETE": "ACF2 mode: DELETE active logonid/group/profile in the active ACF2 setting.",
        "ACCESS": "ACF2 mode: ACCESS DSNAME('dataset') or ACCESS RESOURCE(name) TYPE(type).",
        "TEST": "ACF2 mode: TEST DSNAME('dataset') LID(userid) SERVICE(READ) or resource test.",
        "RECKEY": "ACF2 mode: RECKEY key ADD( resource UID(id) SERVICE(READ) ALLOW ).",
        "ZSEC HELP": "zSecure simulated report: HELP.",
        "ZSEC PRIVILEGE": "zSecure simulated report: PRIVILEGE.",
        "ZSEC UID0": "zSecure simulated report: UID0.",
        "ZSEC STARTED": "zSecure simulated report: STARTED.",
        "ZSEC SURROGAT": "zSecure simulated report: SURROGAT.",
        "ZSEC JES": "zSecure simulated report: JES.",
        "ZSEC TSOAUTH": "zSecure simulated report: TSOAUTH.",
        "ZSEC SERVAUTH": "zSecure simulated report: SERVAUTH.",
        "ZSEC PASSTICKET": "zSecure simulated report: PASSTICKET.",
        "ZSEC CICS": "zSecure simulated report: CICS.",
        "ZSEC DB2": "zSecure simulated report: DB2.",
        "ZSEC ICSF": "zSecure simulated report: ICSF.",
        "ZSEC RACDCERT": "zSecure simulated report: RACDCERT.",
        "ZSEC RARE": "zSecure simulated report: RARE.",
        "ZSEC DRIFT": "zSecure simulated report: DRIFT.",
        "ZSEC FIRST30": "zSecure simulated report: FIRST30.",
        "ZSEC RACFDS": "zSecure simulated report: RACFDS.",
        "ZSEC SETROPTS": "zSecure simulated report: SETROPTS.",
        "ZSEC MFA": "zSecure simulated report: MFA.",
        "ZSEC EVENTS": "zSecure simulated report: EVENTS.",
        "ZSEC ALERTS": "zSecure simulated report: ALERTS.",
        "ZSEC SMF": "zSecure simulated report: SMF.",
        "ZSEC RACF": "zSecure simulated report: RACF.",
        "ZSEC ACCESS": "zSecure simulated report: ACCESS.",
        "ZSEC COMPLIANCE": "zSecure simulated report: COMPLIANCE.",
        "ZSEC REPORTS": "zSecure simulated report: REPORTS.",
        "ZSEC APF": "zSecure simulated report: APF.",
        "ZSEC SMF80": "zSecure simulated report: SMF80.",
        "ZSEC SMF7": "zSecure simulated report: SMF7.",
        "ZSEC SMF30": "zSecure simulated report: SMF30.",
        "ZSEC SMF100": "zSecure simulated report: SMF100.",
    }

    def __init__(self, state: GibsonState, userid: str):
        self.state = state
        self.userid = userid.upper()
        self.login_time = datetime.now()
        self.command_count = 0
        self.command_history: list[str] = []
        self.security_mode = "RACF"
        self.acf2 = Acf2Bridge(state, self.userid)

    @property
    def user(self):
        return self.state.racf.get(self.userid)

    def is_special(self) -> bool:
        u = self.user
        return bool(u and u.special)

    def has_omvs_segment(self) -> bool:
        u = self.user
        return bool(u and u.has_omvs)

    def default_group(self) -> str:
        u = self.user
        return (u.default_group if u and u.default_group else self.userid).upper()

    def can_access_appl(self, applid: str) -> bool:
        return self.state.dynamic_racf.has_access("APPL", applid.upper(), self.userid, "READ", self.state.racf)

    def _attrib(self) -> str:
        return "SPECIAL" if self.is_special() else "NONE"



    # v30.289 additive hardening command layer. This intentionally sits above
    # legacy template fallback so stateful RACF/zSecure behaviour wins while
    # old commands remain available.
    def _v30289_kv_segment(self, text: str, keys: list[str]) -> dict:
        out = {}
        for k in keys:
            m = re.search(k + r"\(([^)]*)\)", text, re.I)
            if m:
                out[k.upper()] = m.group(1).strip().strip("'")
        return out

    def _v30289_attrs_from_text(self, text: str) -> tuple[set[str], dict[str, bool]]:
        u = " " + text.upper() + " "
        attrs = set(); changes = {}
        for a in ["SPECIAL", "OPERATIONS", "AUDITOR", "ROAUDIT", "UAUDIT"]:
            if re.search(r"(?<!NO)\b" + a + r"\b", u):
                attrs.add(a); changes[a] = True
            if re.search(r"\bNO" + a + r"\b", u):
                changes[a] = False
        return attrs, changes

    def _v30289_parse_user_options(self, cmd: str) -> dict:
        opts = {}
        def one(name):
            m = re.search(name + r"\(([^)]*)\)", cmd, re.I)
            return m.group(1).strip().strip("'") if m else None
        for name, field in [("NAME","name"),("OWNER","owner"),("DFLTGRP","default_group"),("UACC","uacc"),("DATA","data"),("MODEL","model"),("SECLABEL","seclabel")]:
            val = one(name)
            if val is not None: opts[field] = val
        if re.search(r"\bTSO\(", cmd, re.I):
            opts["tso"] = self._v30289_kv_segment(cmd, ["ACCTNUM","PROC","SIZE","MAXSIZE","MSGCLASS","SYS","UNIT"])
        if re.search(r"\bOMVS\(", cmd, re.I):
            seg = self._v30289_kv_segment(cmd, ["UID","HOME","PROGRAM"])
            opts["omvs_segment"] = seg or {"UID":"1", "HOME":f"/u/{cmd.split()[1].lower() if len(cmd.split())>1 else self.userid.lower()}", "PROGRAM":"/bin/sh"}
        elif re.search(r"\bOMVS\b", cmd, re.I):
            opts["omvs_segment"] = {"UID":"1", "HOME":f"/u/{cmd.split()[1].lower() if len(cmd.split())>1 else self.userid.lower()}", "PROGRAM":"/bin/sh"}
        if re.search(r"\bDFP\(", cmd, re.I):
            opts["dfp"] = self._v30289_kv_segment(cmd, ["STORCLAS","MGMTCLAS","DATACLAS"])
        mfa_m = re.search(r"MFA\((.*)\)", cmd, re.I)
        if mfa_m:
            text = mfa_m.group(1)
            fm = re.search(r"FACTOR\(([^)]*)\)", text, re.I)
            tm = re.search(r"TAGS\(([^)]*)\)", text, re.I)
            opts["mfa"] = {
                "FACTOR": fm.group(1).strip() if fm else ("GIBTOTP" if "GIBTOTP" in text.upper() else ""),
                "ACTIVE": "YES" if "ACTIVE" in text.upper() else "NO",
                "PWFALLBACK": "NO" if "NOPWFALLBACK" in text.upper() else ("YES" if "PWFALLBACK" in text.upper() else "DEFAULT"),
                "TAGS": tm.group(1).strip() if tm else "",
            }
        u = " " + cmd.upper() + " "
        opts["protected"] = all(x in u for x in [" NOPASSWORD ", " NOPHRASE ", " NOOIDCARD "])
        opts["nopassword"] = " NOPASSWORD " in u
        opts["nophrase"] = " NOPHRASE " in u
        opts["nooidcard"] = " NOOIDCARD " in u
        if re.search(r"\bPHRASE\(", cmd, re.I):
            opts["phrase"] = True
        opts["revoked"] = True if " REVOKE " in u else False if " RESUME " in u else False
        return opts

    def _v30289_help(self, cmd: str) -> str | None:
        u = cmd.upper().strip()
        topics = {
            "ADDUSER": "ADDUSER userid <PASSWORD(pw)|PASS(pw)|NOPASSWORD> <NAME('name')> <OWNER(owner)> <DFLTGRP(group)> <SPECIAL|OPERATIONS|AUDITOR|ROAUDIT|UAUDIT> <TSO(...)> <OMVS(UID(n) HOME('/u/id') PROGRAM('/bin/sh'))> <DFP(...)>",
            "ALTUSER": "ALTUSER userid <PASSWORD(pw)|PASS(pw)|REVOKE|RESUME> <SPECIAL|NOSPECIAL|OPERATIONS|NOOPERATIONS|AUDITOR|NOAUDITOR|ROAUDIT|NOROAUDIT|UAUDIT|NOUAUDIT> <TSO(...)|NOTSO> <OMVS(...)|NOOMVS> <DFP(...)|NODFP> <MFA(...)|NOMFA>",
            "LISTUSER": "LISTUSER userid <ALL|TSO|OMVS|DFP|MFA> - display simulated RACF user profile and segments.",
            "ZSEC": "ZSEC <HELP|PRIVILEGE|UID0|STARTED|SURROGAT|JES|TSOAUTH|SERVAUTH|PASSTICKET|CICS|DB2|ICSF|RACDCERT|RARE|DRIFT|FIRST30|RACFDS|SETROPTS|MFA|EVENTS|ALERTS|SMF|RACF|ACCESS|COMPLIANCE|REPORTS|APF|SMF80|SMF7|SMF30|SMF100>",
            "NETACCESS": "NETACCESS DISPLAY | NETACCESS DEFINE zone CIDR(cidr) RESOURCE(profile)",
            "DB2": "DB2 DISPLAY SECURITY | DB2 DISPLAY DDF | DB2 SET DDF TLS(REQUIRED|OPTIONAL|OFF) | DB2 REVOKE/GRANT SELECT ON SYSIBM.SYSUSERAUTH ...",
            "ICSF": "ICSF DISPLAY STATUS|CKDS|PKDS|TKDS - display simulated ICSF control-plane datasets and status.",
            "RACDCERT": "RACDCERT ID(userid) ADD('dataset') WITHLABEL('label') | ADDRING(ring) | CONNECT(...) | LISTRING(ring) | CERTAUTH LIST",
            "PASSTICKET": "PASSTICKET GENERATE USER(userid) APPL(applid) | PASSTICKET VERIFY USER(userid) APPL(applid) TOKEN(token)",
            "STARTED": "RDEFINE STARTED proc.job STDATA(USER(userid) GROUP(group) TRUSTED(NO)); D STARTED displays mappings.",
            "SURROGAT": "RDEFINE SURROGAT userid.SUBMIT UACC(NONE); PERMIT userid.SUBMIT CLASS(SURROGAT) ID(submitter) ACCESS(READ).",
            "JESSPOOL": "RDEFINE JESSPOOL node.userid.jobname.jobid.ds UACC(NONE).",
            "JESJOBS": "RDEFINE JESJOBS SUBMIT.node.userid.jobname UACC(NONE).",
            "TSOAUTH": "RDEFINE TSOAUTH IND$FILE UACC(NONE); PERMIT IND$FILE CLASS(TSOAUTH) ID(group) ACCESS(READ).",
            "SERVAUTH": "RDEFINE SERVAUTH EZB.NETACCESS.sysname.tcpname.zone UACC(NONE); NETACCESS maps zones to resources.",
            "PTKTDATA": "RDEFINE PTKTDATA applid SSIGNON(KEYENCRYPTED) UACC(NONE); RLIST PTKTDATA applid ALL.",
            "CSFKEYS": "RDEFINE CSFKEYS profile UACC(NONE); RLIST CSFKEYS profile ALL.",
            "CSFSERV": "RDEFINE CSFSERV service UACC(NONE); RLIST CSFSERV service ALL.",
            "IKJTSO": "D IKJTSO | SET IKJTSO PASSWORDPREPROMPT(ON|OFF) | PARMLIB DISPLAY IKJTSOxx | PARMLIB UPDATE IKJTSOxx PASSWORDPREPROMPT(ON|OFF).",
            "PASSWORDPREPROMPT": "SET IKJTSO PASSWORDPREPROMPT(ON|OFF) controls TSO pre-prompt user-enumeration behavior.",
            "PARMLIB": "PARMLIB DISPLAY IKJTSOxx | PARMLIB UPDATE IKJTSOxx PASSWORDPREPROMPT(ON|OFF).",
            "CICS": "CICS DISPLAY SIT | CICS DISPLAY SECURITY | CICS SET SIT SEC(YES|NO) XTRAN(YES|NO) XCMD(YES|NO) XFCT(YES|NO) XPCT(YES|NO) XTST(YES|NO) XDCT(YES|NO) XPPT(YES|NO) DFLTUSER(userid).",
            "CEMT": "CEMT INQUIRE SECURITY | CEMT SET SECURITY ON|OFF. Authorization is checked in the simulator.",
            "CEDA": "CEDA DEFINE|ALTER|VIEW TRANSACTION(...) or FILE(...).",
            "SECURITY": "D SECURITY,RARE | D SECURITY,DAILY | D SECURITY,WEEKLY | D SECURITY,MONTHLY.",
            "INACTIVE": "SETROPTS INACTIVE(n) | SETROPTS NOINACTIVE. Protected users are exempt in the simulator.",
        }
        # A trailing '?' with no preceding space (e.g. "ADDUSER?") must reach the
        # same rich COMMAND SYNTAX help as "ADDUSER ?" does on the ASCII path.
        if u.endswith("?") and not u.endswith(" ?"):
            u = u[:-1].rstrip() + " ?"
        if u.endswith(" ?") or u.endswith(" HELP") or u.startswith("HELP "):
            t = u.replace("HELP ", "").replace(" ?", "").replace(" HELP", "").split()[0]
            if t in topics:
                return f"{t} HELP\n  {topics[t]}"
        return None

    def _v30289_adduser(self, cmd: str) -> str:
        if not self.is_special(): return tr.MSG_INSUFFICIENT
        if re.search(r"\bMFA\(", cmd, re.I):
            return "ICH01040I ADDUSER MFA OPERAND REJECTED - USE ALTUSER userid MFA(...)"
        parts = cmd.split(None, 2)
        if len(parts) < 2: return "ICH01000I ADDUSER userid <operands>"
        target = parts[1].upper()
        pm = re.search(r"(?:PASSWORD|PASS)\(([^)]*)\)", cmd, re.I)
        pw = pm.group(1) if pm else ""
        opts = self._v30289_parse_user_options(cmd)
        attrs, _ = self._v30289_attrs_from_text(cmd)
        opts["attributes"] = sorted(a for a in attrs if a != "SPECIAL")
        dflt = opts.pop("default_group", self.default_group())
        out = self.state.racf.adduser(target, pw, special=("SPECIAL" in attrs), omvs=bool(opts.get("omvs_segment")), default_group=dflt, **opts)
        if not out.startswith("ICH01003I"):
            return out
        try:
            self.state.dynamic_racf.connect_user(target, dflt, "USE")
            ent = self.state.racf.get(target)
            # Preserve the existing Gibson contract: ADDUSER with a password is
            # TSO-capable by default and therefore appears in simulated SYS1.UADS.
            # Explicit protected/NOPASSWORD identities remain non-password-logon IDs.
            if ent and pw and not opts.get("protected") and not opts.get("nopassword"):
                self.state.uads.add_or_update_user(target, ent.password, dflt, change_required=bool(getattr(ent, "password_change_required", False)), source="ADDUSER")
                self.state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(self.state.uads.list_lines()) + "\n")
        except Exception:
            pass
        lines = [f"ICH01024I USER {target} DEFINED", f"ICH01025I CONNECT {target} TO GROUP {dflt} CREATED"]
        if pw: lines.append("ICH01026I PASSWORD CHANGE REQUIRED AT NEXT LOGON")
        if opts.get("omvs_segment"): lines.append(f"ICH01027I OMVS SEGMENT ADDED FOR {target}")
        if opts.get("tso"): lines.append(f"ICH01029I TSO SEGMENT ADDED FOR {target}")
        if opts.get("dfp"): lines.append(f"ICH01030I DFP SEGMENT ADDED FOR {target}")
        for a in sorted(attrs - {"SPECIAL"}): lines.append(f"ICH01028I ATTRIBUTE {a} ASSIGNED TO {target}")
        if "SPECIAL" in attrs: lines.append(f"ICH01028I ATTRIBUTE SPECIAL ASSIGNED TO {target}")
        if opts.get("phrase"): lines.append(f"ICH01041I PASSWORD PHRASE DEFINED FOR {target} - MATERIAL PROTECTED")
        if opts.get("nophrase"): lines.append(f"ICH01042I PASSWORD PHRASE REMOVED FOR {target}")
        if opts.get("nooidcard"): lines.append(f"ICH01043I OIDCARD DISABLED FOR {target}")
        if opts.get("protected"): lines.append(f"ICH01033I USER {target} DEFINED AS PROTECTED")
        lines.append(out)
        try: self._audit_smf80("ADDUSER", f"USER={target} ATTRS={' '.join(sorted(attrs))} SEGMENTS={'TSO' if opts.get('tso') else ''} {'OMVS' if opts.get('omvs_segment') else ''} {'DFP' if opts.get('dfp') else ''}")
        except Exception: pass
        try:
            from gibson.core.racf_database import materialise_racfds
            materialise_racfds(self.state, changed_user=target, plaintext_password=pw if pw else None, source_command='ADDUSER')
        except Exception:
            pass
        return "\n".join(lines)

    def _v30289_altuser(self, cmd: str) -> str:
        if not self.is_special(): return tr.MSG_INSUFFICIENT
        parts = cmd.split(None, 2)
        if len(parts) < 2: return "ICH01000I ALTUSER userid <operands>"
        target = parts[1].upper()
        pm = re.search(r"(?:PASSWORD|PASS)\(([^)]*)\)", cmd, re.I)
        pw = pm.group(1) if pm else None
        opts = self._v30289_parse_user_options(cmd)
        attrs, changes = self._v30289_attrs_from_text(cmd)
        special = changes.pop("SPECIAL", None)
        opts["attr_changes"] = changes
        opts["notso"] = bool(re.search(r"\bNOTSO\b", cmd, re.I))
        opts["noomvs"] = bool(re.search(r"\bNOOMVS\b", cmd, re.I))
        opts["nodfp"] = bool(re.search(r"\bNODFP\b", cmd, re.I))
        opts["nomfa"] = bool(re.search(r"\bNOMFA\b", cmd, re.I))
        dflt = opts.pop("default_group", None)
        if dflt is not None:
            if dflt not in self.state.dynamic_racf.groups:
                return f"ICH30001I GROUP {dflt} NOT FOUND"
            if target not in self.state.dynamic_racf.groups[dflt].users:
                return f"ICH01009I USER {target} NOT CONNECTED TO GROUP {dflt}"
        opts.pop("revoked", None)
        revoked = True if re.search(r"\bREVOKE\b", cmd, re.I) else False if re.search(r"\bRESUME\b", cmd, re.I) else None
        out = self.state.racf.altuser(target, password=pw, special=special, omvs=(False if opts.get('noomvs') else None), default_group=dflt, revoked=revoked, **opts)
        if not out.startswith("ICH01006I"):
            return out
        lines = [f"ICH01031I USER {target} ALTERED", f"ICH01006I USERID {target} ALTERED"]
        for a,en in sorted(changes.items()): lines.append(f"ICH01032I ATTRIBUTE {a} {'ASSIGNED TO' if en else 'REMOVED FROM'} {target}")
        if special is not None: lines.append(f"ICH01032I ATTRIBUTE SPECIAL {'ASSIGNED TO' if special else 'REMOVED FROM'} {target}")
        if opts.get("omvs_segment"): lines.append(f"ICH01034I OMVS SEGMENT ALTERED FOR {target}")
        if opts.get("noomvs"): lines.append(f"ICH01035I OMVS SEGMENT DELETED FOR {target}")
        if opts.get("tso"): lines.append(f"ICH01036I TSO SEGMENT ALTERED FOR {target}")
        if opts.get("notso"): lines.append(f"ICH01037I TSO SEGMENT DELETED FOR {target}")
        if opts.get("dfp"): lines.append(f"ICH01038I DFP SEGMENT ALTERED FOR {target}")
        if opts.get("nodfp"): lines.append(f"ICH01039I DFP SEGMENT DELETED FOR {target}")
        if opts.get("phrase"): lines.append(f"ICH01041I PASSWORD PHRASE DEFINED FOR {target} - MATERIAL PROTECTED")
        if opts.get("nophrase"): lines.append(f"ICH01042I PASSWORD PHRASE REMOVED FOR {target}")
        if opts.get("nooidcard"): lines.append(f"ICH01043I OIDCARD DISABLED FOR {target}")
        if opts.get("mfa"): lines.append(f"IRR52070I MFA SEGMENT ALTERED FOR {target}")
        if opts.get("nomfa"): lines.append(f"IRR52071I MFA SEGMENT DELETED FOR {target}")
        if revoked is True: lines.append(f"ICH10006I ALTUSER {target} REVOKE COMPLETE")
        if revoked is False: lines.append(f"ICH10007I ALTUSER {target} RESUME COMPLETE")
        # Keep SYS1.UADS aligned with RACF after an admin password reset, so a
        # subsequent EBCDIC/ASCII logon is not blocked by stale UADS state.  Per
        # real RACF, an admin ALTUSER PASSWORD(...) expires the password (the
        # user must change it at next logon) unless NOEXPIRED is given.
        if pw is not None:
            try:
                # Default: do NOT force a change after an admin reset; only force
                # it if EXPIRED is explicitly requested (and not NOEXPIRED).
                exp = bool(re.search(r"\bEXPIRED\b", cmd, re.I)) and not bool(re.search(r"\bNOEXPIRED\b", cmd, re.I))
                cr = exp
                new_rec = self.state.racf.get(target)
                if new_rec is not None and hasattr(new_rec, "password_change_required"):
                    new_rec.password_change_required = cr   # RACF stays authoritative
                    self.state.racf.save()
                self.state.uads.set_password(
                    target, new_rec.password if new_rec else "", change_required=cr)
                self.state.datasets.write(
                    "IBMUSER", "SYS1.UADS",
                    "\n".join(self.state.uads.list_lines()) + "\n")
                if cr:
                    lines.append(f"ICH01034I PASSWORD EXPIRED FOR {target}")
            except Exception:
                pass
        try: self._audit_smf80("ALTUSER", f"USER={target} CHANGES={cmd}")
        except Exception: pass
        try:
            from gibson.core.racf_database import materialise_racfds
            materialise_racfds(self.state, changed_user=target, plaintext_password=pw if pw else None, source_command='ALTUSER')
        except Exception:
            pass
        return "\n".join(lines)

    @staticmethod
    def zsec_topics() -> list[str]:
        return [
            "HELP", "?", "PRIVILEGE", "UID0", "STARTED", "SURROGAT",
            "JES", "TSOAUTH", "SERVAUTH", "PASSTICKET", "CICS", "DB2",
            "ICSF", "RACDCERT", "RARE", "DRIFT", "FIRST30", "RACFDS",
            "SETROPTS", "MFA", "EVENTS", "ALERTS", "SMF", "RACF",
            "ACCESS", "COMPLIANCE", "REPORTS", "APF", "SMF80", "SMF7",
            "SMF30", "SMF100",
        ]

    def _v30289_zsec(self, cmd: str) -> str | None:
        u = cmd.upper().strip()
        if not (u == "ZSEC" or u.startswith("ZSEC ") or u.startswith("ZSECURE ")):
            return None
        parts = u.split()
        topic = parts[1] if len(parts) > 1 else "MENU"
        if topic == "?":
            topic = "HELP"
        users = list(getattr(self.state.racf, 'users', {}).values())

        def profs(cls):
            dr = getattr(self.state, 'dynamic_racf', None)
            ps = getattr(dr, 'profiles', {}) if dr else {}
            return [k for k in ps if k.upper().startswith(cls + ':')]

        def sec_rows(component: str | None = None):
            events = list(getattr(getattr(self.state, 'audit', None), 'events', []) or [])
            rows=[]
            for ev in events[-50:]:
                text = " ".join(str(getattr(ev, a, "")) for a in ("event_type", "action", "resource", "result", "service"))
                if component and component not in text.upper():
                    continue
                rows.append(ev)
            return rows

        if topic in {"MENU", "HELP"}:
            lines = [
                "ZSECURE MAIN MENU - GIBSON TRAINING SIMULATION",
                "COMMANDS:",
                "  " + " ".join(self.zsec_topics()),
                "EXAMPLES:",
                "  ZSEC PRIVILEGE     ZSEC SMF80      ZSEC RACF",
                "  ZSEC ICSF          ZSEC SMF30      ZSEC SMF100",
            ]
            return "\n".join(lines)
        if topic == "PRIVILEGE":
            lines=["ZSECURE PRIVILEGED AND AUDIT ATTRIBUTES","USERID   ATTRIBUTES"]
            for x in users:
                attrs=sorted(set(x.attributes) & {"SPECIAL","OPERATIONS","AUDITOR","ROAUDIT","UAUDIT"})
                if attrs: lines.append(f"{x.userid:<8} {' '.join(attrs)}")
            return "\n".join(lines) if len(lines)>2 else "ZSECURE PRIVILEGE: NO PRIVILEGED USERS FOUND"
        if topic == "UID0":
            lines=["ZSECURE UID(0) USERS","USERID   UID HOME"]
            for x in users:
                try:
                    if int(x.omvs_segment.get('UID',-1)) == 0:
                        lines.append(f"{x.userid:<8} 0   {x.omvs_segment.get('HOME','')}")
                except Exception:
                    pass
            return "\n".join(lines) if len(lines)>2 else "ZSECURE UID0: NO UID(0) USERS FOUND"
        mapping={"SURROGAT":"SURROGAT","JES":"JESSPOOL/JESJOBS","TSOAUTH":"TSOAUTH","SERVAUTH":"SERVAUTH","PASSTICKET":"PTKTDATA","STARTED":"STARTED"}
        if topic in mapping:
            clslist=mapping[topic].split('/')
            lines=[f"ZSECURE {topic} SECURITY POSTURE","CLASS PROFILE"]
            for c in clslist:
                for p in profs(c): lines.append(f"{c:<8} {p.split(':',1)[1]}")
            return "\n".join(lines) if len(lines)>2 else f"ZSECURE {topic}: NO PROFILES FOUND"
        if topic == "DB2":
            db2=self._v30289_state()["db2"]; tls=db2.get("DDF_TLS","REQUIRED"); pub=db2.get("SYSUSERAUTH_PUBLIC","YES")
            finding = "FINDING: DDF TLS WEAK" if tls in {"OFF","OPTIONAL"} else "NO TLS FINDINGS"
            cat = "FINDING: PUBLIC CAN READ SYSIBM.SYSUSERAUTH" if pub == "YES" else "SYSIBM.SYSUSERAUTH PUBLIC ACCESS=REVOKED"
            return f"ZSECURE DB2 SECURITY POSTURE\nDDF TLS={tls}\n{finding}\n{cat}\nDSNR CLASS REVIEW AVAILABLE"
        if topic == "CICS":
            try:
                from gibson.core.cics_region import get_cics_region
                opts=get_cics_region(self.state).security_options
                lines=["ZSECURE CICS SECURITY POSTURE"]
                for k in ["SEC","XTRAN","XCMD","XFCT","XPCT","XTST","XDCT","XPPT","DFLTUSER"]:
                    lines.append(f"{k}={opts.get(k,'YES')}")
                    if k != "DFLTUSER" and opts.get(k,'YES') != "YES": lines.append(f"FINDING: {k} NOT ACTIVE")
                return "\n".join(lines)
            except Exception: return "ZSECURE CICS SECURITY POSTURE\nCICS STATE UNAVAILABLE"
        if topic == "ICSF":
            return "ZSECURE ICSF SECURITY POSTURE\nSYS1.CKDS PROTECTED\nSYS1.PKDS PROTECTED\nSYS1.TKDS PROTECTED\nCSFKEYS/CSFSERV CLASS REVIEW AVAILABLE"
        if topic == "RACDCERT":
            rc=self._v30289_state()["racdcert"]; rings=sum(len(v) for v in rc.get("rings",{}).values()); certs=sum(len(v) for v in rc.get("certs",{}).values())
            return f"ZSECURE RACDCERT SECURITY POSTURE\nCERTIFICATES={certs} KEYRINGS={rings}\nFACILITY IRR.DIGTCERT.* REVIEW\nKEY RINGS AND CERTIFICATES MASKED"
        if topic == "RARE": return "ZSECURE RARE SECURITY REVIEW\n" + self._security_events("RARE")
        if topic == "DRIFT": return "ZSECURE DRIFT SECURITY REVIEW\nPOSTURE CHANGES ARE DERIVED FROM CURRENT RACF/CICS/DB2 STATE\n" + self._security_events("DAILY")
        if topic == "FIRST30": return "ZSECURE FIRST30 VALIDATION REVIEW\nDAILY/WEEKLY/MONTHLY SECURITY RHYTHM ACTIVE\n" + self._security_events("MONTHLY")
        if topic == "SETROPTS": return "ZSECURE SETROPTS REVIEW\n" + self.state.password_policy.set_from_command("SETROPTS LIST")
        if topic == "MFA": return "ZSECURE MFA REVIEW\n" + ("MFA ACTIVE" if getattr(self.state.password_policy, 'mfa_active', False) else "MFA INACTIVE")
        if topic == "RACFDS": return "ZSECURE RACFDS REVIEW\nSYS1.RACFDS ACCESS=RESTRICTED\nSYS1.UADS ACCESS=RESTRICTED"
        if topic == "RACF":
            lines=["ZSECURE RACF OVERVIEW", "USERS: " + ", ".join(sorted(getattr(self.state.racf,'users',{}).keys())[:30]), "DATASET PROFILES REVIEW AVAILABLE"]
            return "\n".join(lines)
        if topic == "ACCESS": return "ZSECURE ACCESS ANALYSIS\nUse WHYACCESS userid dataset access for detailed access decision analysis."
        if topic == "COMPLIANCE": return "ZSECURE COMPLIANCE EXCEPTIONS\nCIS-THEME: ACCESS CONTROL, AUDIT, CRYPTO, NETWORK, DATA PROTECTION\nSIMULATED REVIEW ONLY"
        if topic == "REPORTS": return "ZSECURE AUDIT REPORTS\nREPORT                    COUNT\nPRIVILEGE REVIEW          1\nACCESS REVIEW             1\nSMF REVIEW                1"
        if topic == "APF":
            try:
                apf = self.run("D APF")
                return "ZSECURE APF REVIEW\n" + apf
            except Exception:
                return "ZSECURE APF REVIEW\nNO APF HISTORY AVAILABLE"
        if topic in {"EVENTS", "SMF80"}:
            rows=sec_rows("SMF80") if topic == "SMF80" else sec_rows()
            lines=["ZSECURE EVENTS / SMF80 REVIEW","TIME              USERID    ACTION                               RESULT"]
            for ev in rows[-20:]:
                lines.append(f"{str(getattr(ev,'timestamp',''))[:16]:<17} {str(getattr(ev,'userid','')):<8} {str(getattr(ev,'action',getattr(ev,'event_type','')))[:36]:<36} {str(getattr(ev,'result',''))}")
            return "\n".join(lines) if len(lines)>2 else "ZSECURE: NO SECURITY EVENTS FOUND"
        if topic == "ALERTS":
            lines=["ZSECURE ALERTS AND COMPLIANCE EXCEPTIONS","ID TYPE              SEV      MESSAGE"]
            alerts_obj=getattr(self.state, 'dashboard_alerts', []) if hasattr(self.state,'dashboard_alerts') else []
            try:
                alerts = list(alerts_obj)[-20:]
            except Exception:
                alerts = []
            for i,a in enumerate(alerts,1): lines.append(f"{i:<2} ALERT             HIGH     {a}")
            return "\n".join(lines) if len(lines)>2 else "ZSECURE: NO ALERTS"
        if topic == "SMF": return "ZSECURE SMF REVIEW\nAVAILABLE TYPES: SMF7 SMF30 SMF80 SMF100\nUse ZSEC SMF80, ZSEC SMF30, ZSEC SMF100."
        if topic == "SMF7": return "ZSECURE SMF TYPE 7 - DATA LOST CONDITIONS\nTIME              USERID    RESULT\nNO SMF7 DATA LOSS RECORDS FOUND"
        if topic == "SMF30": return "ZSECURE SMF TYPE 30 - ADDRESS SPACE ACTIVITY\nJOBNAME   USERID    CPU      ELAPSED  RESULT\nGIBSON    IBMUSER   00.00    00.01    SIMULATED"
        if topic == "SMF100": return "ZSECURE SMF TYPE 100 - DB2 ACCOUNTING\nSUBSYS   AUTHID    THREADS  RESULT\nDB2A     IBMUSER   1        SIMULATED"
        return "ZSECURE: UNKNOWN OPTION " + topic + "\n" + self._v30289_zsec("ZSEC HELP")

    def _v30289_state(self) -> dict:
        """Persistent-enough v30.289 simulator state for command handlers.
        Stored on GibsonState so multiple command processors see the same values.
        """
        st = getattr(self.state, "v30289_state", None)
        if st is None:
            st = {
                "ikjtso": {"PASSWORDPREPROMPT": "OFF"},
                "db2": {"DDF_TLS": "REQUIRED", "SYSUSERAUTH_PUBLIC": "YES", "SYSUSERAUTH_GRANTS": []},
                "racdcert": {"certs": {}, "rings": {}, "certauth": ["GIBSON-CA"]},
                "netaccess": {"LOCAL": {"CIDR": "127.0.0.0/8", "RESOURCE": "EZB.NETACCESS.SYS1.TCPIP.LOCAL"}},
            }
            setattr(self.state, "v30289_state", st)
        return st

    def _security_events(self, period: str = "RARE") -> str:
        try:
            from gibson.core.security_summary import format_security_period
            return format_security_period(self.state, period)
        except Exception:
            return f"IEE174I SECURITY {period} REVIEW SUMMARY\nSECURITY SUMMARY UNAVAILABLE"

    def _ikjtso_cmd(self, cmd: str) -> str:
        u = cmd.upper().strip(); st = self._v30289_state()["ikjtso"]
        if u in {"HELP IKJTSO", "IKJTSO ?", "IKJTSO HELP", "HELP PASSWORDPREPROMPT", "PASSWORDPREPROMPT ?", "PASSWORDPREPROMPT HELP"}:
            return "IKJTSO HELP\n  D IKJTSO\n  SET IKJTSO PASSWORDPREPROMPT(ON|OFF)\n  PARMLIB DISPLAY IKJTSOxx\n  PARMLIB UPDATE IKJTSOxx PASSWORDPREPROMPT(ON|OFF)"
        if u in {"D IKJTSO", "DISPLAY IKJTSO", "PARMLIB DISPLAY IKJTSOXX", "PARMLIB DISPLAY IKJTSO"}:
            return f"IKJ77890I IKJTSOxx ACTIVE PARMLIB SETTINGS\nPASSWORDPREPROMPT({st.get('PASSWORDPREPROMPT','OFF')})"
        if u.startswith("SET IKJTSO") or u.startswith("PARMLIB UPDATE IKJTSO"):
            if not self.is_special():
                return f"ICH408I USER({self.userid:<8}) GROUP({self.default_group():<8}) NAME({self.userid})\n  IKJTSOxx UPDATE CL(FACILITY)\n  INSUFFICIENT ACCESS AUTHORITY"
            m = re.search(r"PASSWORDPREPROMPT\((ON|OFF)\)", u)
            if not m:
                return "IKJ77892I SYNTAX: SET IKJTSO PASSWORDPREPROMPT(ON|OFF)"
            st["PASSWORDPREPROMPT"] = m.group(1)
            try: self._audit_smf80("IKJTSO PASSWORDPREPROMPT", f"PASSWORDPREPROMPT({m.group(1)})")
            except Exception: pass
            return f"IKJ77891I PASSWORDPREPROMPT {'ENABLED' if m.group(1)=='ON' else 'DISABLED'}"
        return "IKJ77892I IKJTSO COMMAND NOT RECOGNIZED"

    def _db2_cmd(self, cmd: str) -> str | None:
        u = cmd.upper().strip(); db2 = self._v30289_state()["db2"]
        if u in {"HELP DB2", "DB2 ?", "DB2 HELP"}:
            return "DB2 HELP\n  DB2 DISPLAY SECURITY\n  DB2 DISPLAY DDF\n  DB2 SET DDF TLS(REQUIRED|OPTIONAL|OFF)\n  DB2 REVOKE SELECT ON SYSIBM.SYSUSERAUTH FROM PUBLIC\n  DB2 GRANT SELECT ON SYSIBM.SYSUSERAUTH TO SECADMIN"
        if u.startswith("DB2 DISPLAY SECURITY"):
            pub = db2.get("SYSUSERAUTH_PUBLIC", "YES")
            return f"DSNX200I DB2 SECURITY DISPLAY\nDDF TLS={db2.get('DDF_TLS','REQUIRED')}\nCATALOG SYSIBM.SYSUSERAUTH PUBLIC={'YES' if pub=='YES' else 'NO'}\nGRANTS={','.join(db2.get('SYSUSERAUTH_GRANTS', [])) or 'NONE'}"
        if u.startswith("DB2 DISPLAY DDF"):
            return f"DSNL080I DDF STATUS\nLOCATION=GIBSON\nDRDA=ACTIVE\nTLS={db2.get('DDF_TLS','REQUIRED')}\nPORT=50000"
        if u.startswith("DB2 SET DDF TLS"):
            if not self.is_special(): return tr.MSG_INSUFFICIENT
            val=re.search(r"TLS\((REQUIRED|OPTIONAL|OFF)\)", cmd, re.I)
            if not val: return "DSNL082I SYNTAX: DB2 SET DDF TLS(REQUIRED|OPTIONAL|OFF)"
            tls=val.group(1).upper(); db2["DDF_TLS"] = tls
            try: self._audit_smf80("DB2 DDF TLS CHANGE", f"TLS={tls}", result="WARNING" if tls in {"OFF","OPTIONAL"} else "SUCCESS")
            except Exception: pass
            return f"DSNL081I DDF TLS SET TO {tls}"
        if u.startswith("DB2 REVOKE SELECT ON SYSIBM.SYSUSERAUTH FROM PUBLIC"):
            db2["SYSUSERAUTH_PUBLIC"]="NO"; self._audit_smf80("DB2 CATALOG AUTH", "REVOKE PUBLIC SYSIBM.SYSUSERAUTH")
            return "DSNT500I DB2 CATALOG AUTHORIZATION UPDATED - PUBLIC REVOKED"
        if u.startswith("DB2 GRANT SELECT ON SYSIBM.SYSUSERAUTH TO SECADMIN"):
            grants=set(db2.get("SYSUSERAUTH_GRANTS", [])); grants.add("SECADMIN"); db2["SYSUSERAUTH_GRANTS"]=sorted(grants); self._audit_smf80("DB2 CATALOG AUTH", "GRANT SECADMIN SYSIBM.SYSUSERAUTH")
            return "DSNT500I DB2 CATALOG AUTHORIZATION UPDATED - SECADMIN GRANTED"
        return None

    def _racdcert_cmd(self, cmd: str) -> str | None:
        u=cmd.upper().strip(); rc=self._v30289_state()["racdcert"]
        if u in {"HELP RACDCERT", "RACDCERT ?", "RACDCERT HELP"}:
            return "RACDCERT HELP\n  RACDCERT ID(userid) ADD('dataset') WITHLABEL('label')\n  RACDCERT ID(userid) ADDRING(ring)\n  RACDCERT ID(userid) CONNECT(ID(userid) LABEL('label') RING(ring))\n  RACDCERT ID(userid) LISTRING(ring)\n  RACDCERT ID(userid) LIST\n  RACDCERT CERTAUTH LIST"
        if not u.startswith("RACDCERT"): return None
        if "CERTAUTH LIST" in u:
            return "IRRD111I CERTAUTH CERTIFICATES\n" + "\n".join(f"CERTAUTH {x} TRUSTED" for x in rc.get("certauth", ["GIBSON-CA"]))
        idm=re.search(r"ID\(([^)]+)\)", cmd, re.I); owner=(idm.group(1) if idm else self.userid).upper()
        if not self.is_special() and owner != self.userid:
            return f"ICH408I USER({self.userid:<8}) CL(FACILITY) PROFILE(IRR.DIGTCERT.ADD) INSUFFICIENT ACCESS AUTHORITY"
        certs=rc.setdefault("certs", {}).setdefault(owner, {})
        rings=rc.setdefault("rings", {}).setdefault(owner, {})
        if " ADDRING" in u:
            rm=re.search(r"ADDRING\(([^)]+)\)", cmd, re.I); ring=(rm.group(1) if rm else "GIBRING").upper()
            rings.setdefault(ring, [])
            self._audit_smf80("RACDCERT ADDRING", f"ID={owner} RING={ring}")
            return f"IRRD107I KEY RING {ring} CREATED FOR USER {owner}\nIRRD105I KEY RING {ring} CREATED FOR USER {owner}"
        if " ADD(" in u:
            dm=re.search(r"ADD\('([^']+)'\)", cmd, re.I); lm=re.search(r"WITHLABEL\('([^']+)'\)", cmd, re.I)
            ds=(dm.group(1) if dm else "UNKNOWN.DATASET").upper(); label=(lm.group(1) if lm else ds.split('.')[-1]).upper()
            certs[label]={"DATASET": ds, "MATERIAL": "***MASKED***"}
            self._audit_smf80("RACDCERT ADD", f"ID={owner} LABEL={label} DATASET={ds} MATERIAL=MASKED")
            return f"IRRD105I CERTIFICATE {label} ADDED FOR USER {owner} - MATERIAL MASKED"
        if " CONNECT" in u:
            lm=re.search(r"LABEL\('([^']+)'\)", cmd, re.I); rm=re.search(r"RING\(([^)]+)\)", cmd, re.I)
            label=(lm.group(1) if lm else "UNKNOWN").upper(); ring=(rm.group(1) if rm else "GIBRING").upper()
            rings.setdefault(ring, [])
            if label not in rings[ring]: rings[ring].append(label)
            self._audit_smf80("RACDCERT CONNECT", f"ID={owner} LABEL={label} RING={ring}")
            return f"IRRD109I CERTIFICATE {label} CONNECTED TO KEY RING {ring}"
        if " LISTRING" in u:
            rm=re.search(r"LISTRING\(([^)]+)\)", cmd, re.I); ring=(rm.group(1) if rm else "GIBRING").upper()
            lines=[f"IRRD107I KEY RING {ring} FOR USER {owner}", "LABEL               CERTOWNER   USAGE"]
            for label in rings.get(ring, []): lines.append(f"{label:<19} {owner:<10} PERSONAL")
            if len(lines)==2: lines.append("NO CERTIFICATES CONNECTED")
            return "\n".join(lines)
        if u.endswith(" LIST") or re.search(r"ID\([^)]+\)\s+LIST$", u):
            lines=[f"IRRD108I CERTIFICATES FOR USER {owner}", "LABEL               DATASET                         STATUS"]
            for label, data in sorted(certs.items()): lines.append(f"{label:<19} {data.get('DATASET',''):<30} TRUSTED")
            if len(lines)==2: lines.append("NO CERTIFICATES FOUND")
            return "\n".join(lines)
        return "IRRD100I RACDCERT COMMAND PROCESSED"

    def _started_display(self) -> str:
        lines=["IEE251I STARTED CLASS DISPLAY", "PROC.JOB             USER      GROUP     TRUSTED"]
        profs=getattr(self.state.dynamic_racf, 'profiles', {}).get('STARTED', {})
        for name, prof in sorted(profs.items()):
            a=prof.attrs or {}
            lines.append(f"{name:<20} {a.get('USER','') or 'UNKNOWN':<9} {a.get('GROUP','SYS1'):<9} {a.get('TRUSTED','NO')}")
        return "\n".join(lines)

    def _v30289_misc(self, cmd: str) -> str | None:
        u=cmd.upper().strip()
        if u in {"HELP IKJTSO", "IKJTSO ?", "IKJTSO HELP", "HELP PASSWORDPREPROMPT", "PASSWORDPREPROMPT ?", "PASSWORDPREPROMPT HELP"} or u.startswith("SET IKJTSO") or u.startswith("PARMLIB DISPLAY IKJTSO") or u.startswith("PARMLIB UPDATE IKJTSO") or u in {"D IKJTSO", "DISPLAY IKJTSO"}:
            return self._ikjtso_cmd(cmd)
        if u.startswith("NETACCESS DISPLAY"):
            nz=self._v30289_state()["netaccess"]; lines=["NETACCESS DISPLAY", "ZONE        CIDR              RESOURCE"]
            for z,d in sorted(nz.items()): lines.append(f"{z:<11} {d.get('CIDR',''):<17} {d.get('RESOURCE','')}")
            return "\n".join(lines)
        if u.startswith("NETACCESS DEFINE"):
            m=re.search(r"NETACCESS DEFINE\s+(\S+)\s+CIDR\(([^)]+)\)\s+RESOURCE\(([^)]+)\)", cmd, re.I)
            if not m: return "EZD1171I NETACCESS SYNTAX: NETACCESS DEFINE zone CIDR(cidr) RESOURCE(profile)"
            self._v30289_state()["netaccess"][m.group(1).upper()]={"CIDR":m.group(2), "RESOURCE":m.group(3).upper()}
            self._audit_smf80("NETACCESS DEFINE", f"ZONE={m.group(1).upper()} RESOURCE={m.group(3).upper()}")
            return "EZD1170I NETACCESS ZONE DEFINED"
        db2=self._db2_cmd(cmd)
        if db2 is not None: return db2
        if u.startswith("ICSF DISPLAY CKDS"):
            return "CSFM100I CKDS DISPLAY\nDATASET=SYS1.CKDS STATUS=PROTECTED UACC=NONE"
        if u.startswith("ICSF DISPLAY PKDS"):
            return "CSFM101I PKDS DISPLAY\nDATASET=SYS1.PKDS STATUS=PROTECTED UACC=NONE"
        if u.startswith("ICSF DISPLAY TKDS"):
            return "CSFM102I TKDS DISPLAY\nDATASET=SYS1.TKDS STATUS=PROTECTED UACC=NONE"
        rc=self._racdcert_cmd(cmd)
        if rc is not None: return rc
        if u.startswith("CICS ") or u.startswith("CEMT") or u.startswith("CEDA"):
            from gibson.apps.cics import CicsSimulator
            return CicsSimulator(self.state, self.userid).execute(cmd)
        if u.startswith("PASSTICKET GENERATE"):
            gen = self._ptktgen("PTKTGEN " + cmd.split(None,2)[2] if len(cmd.split(None,2))>2 else "PTKTGEN")
            return gen.replace("IRRPT100I", "IRRPT100I PASSTICKET GENERATE")
        if u.startswith("PASSTICKET VERIFY"):
            user=re.search(r"USER\(([^)]+)\)", cmd, re.I); appl=re.search(r"APPL\(([^)]+)\)", cmd, re.I); tok=re.search(r"TOKEN\(([^)]+)\)", cmd, re.I)
            out=self._ptktuse(f"PTKTUSE USER({user.group(1) if user else self.userid}) APPL({appl.group(1) if appl else 'CICS'}) TICKET({tok.group(1) if tok else ''})")
            if "REJECT" in out.upper() or "FAIL" in out.upper(): self._audit_smf80("PASSTICKET VERIFY FAILURE", f"USER={user.group(1) if user else self.userid}", result="FAILURE")
            return out
        if u == "D STARTED" or u == "DISPLAY STARTED": return self._started_display()
        if u.startswith("D SECURITY") or u.startswith("DISPLAY SECURITY"):
            if "DAILY" in u: return self._security_events("DAILY")
            if "WEEKLY" in u: return self._security_events("WEEKLY")
            if "MONTHLY" in u: return self._security_events("MONTHLY")
            return self._security_events("RARE")
        return None

    def _v30289_command(self, cmd: str) -> str | None:
        u = cmd.upper().strip()
        h = self._v30289_help(cmd)
        if h is not None: return h
        z = self._v30289_zsec(cmd)
        if z is not None: return z
        m = self._v30289_misc(cmd)
        if m is not None: return m
        if u.startswith("SEARCH CLASS(USER) UID(0)"):
            return self.state.racf.search_uid0()
        if u.startswith("ADDUSER"):
            return self._v30289_adduser(cmd)
        if u.startswith("ALTUSER"):
            return self._v30289_altuser(cmd)
        if u.startswith("LISTUSER"):
            parts = cmd.split()
            if len(parts) < 2: return self.state.racf.listuser(self.userid)
            if parts[1] == "*": return "\n\n".join(self.state.racf.listuser(x, "ALL") for x in sorted(self.state.racf.users))
            return self.state.racf.listuser(parts[1].upper(), parts[2].upper() if len(parts)>2 else "")
        return None

    def _service_name(self, name: str) -> str:
        aliases = {"FTP":"FTPD", "FTPD":"FTPD", "JES":"JES2", "JES2":"JES2", "TCP":"TCPIP", "TCPIP":"TCPIP", "VTAM":"VTAM", "TSO":"TSO", "RACF":"RACF", "SDSF":"SDSF", "CICS":"CICS", "DB2":"DB2", "ICSF":"ICSF", "NJE":"NJE", "OMVS":"OMVS", "USS":"OMVS", "DASH":"GIBDASH", "DASHBOARD":"GIBDASH"}
        return aliases.get((name or "").strip().upper(), (name or "").strip().upper())

    def _service_command(self, cmd: str) -> str | None:
        u = cmd.strip().upper()
        parts = u.split(None, 1)
        if not parts:
            return None
        verb = parts[0]
        if verb == "S" and len(parts) == 1:
            return None
        mgr = getattr(self.state, "service_manager", None)
        if mgr is None:
            return None
        if verb in {"S", "START", "P", "STOP", "PAUSE", "RESUME"} and len(parts) == 2:
            svc = self._service_name(parts[1].split(",", 1)[0])
            allowed, denial = v26_features.operator_authorized(self.state, self.userid, f"MVS.{('START' if verb in {'S','START','RESUME'} else 'STOP')}.STC.{svc}")
            if not allowed:
                return denial
            if verb in {"S", "START", "RESUME"}:
                ok, msg = mgr.start(svc)
            elif verb == "PAUSE":
                ok, msg = mgr.pause(svc)
            else:
                ok, msg = mgr.stop(svc)
            try: self.state.notify_console(msg, severity="INFO" if ok else "ALERT")
            except Exception: pass
            try: self.state.raise_dashboard_alert(msg, severity="INFO" if ok else "ALERT", event_type="SERVICE")
            except Exception: pass
            return msg
        if verb in {"D", "DISPLAY"} and len(parts) == 2:
            arg = parts[1].strip()
            if arg.startswith(("TCPIP", "PROG", "APF")):
                return None
            svc = self._service_name(arg.split(",", 1)[0])
            service = mgr.get(svc)
            if service:
                return f"IEE174I {svc} STATUS\n  STATE={service.state}\n  PORT={service.port or '-'}\n  DESC={service.description}"
        if verb == "F" and len(parts) == 2:
            svc = self._service_name(parts[1].split(",", 1)[0])
            service = mgr.get(svc)
            if service:
                operand = parts[1].split(",", 1)[1] if "," in parts[1] else "STATUS"
                if operand == "STATUS":
                    return f"IEE174I {svc} STATUS {service.state}"
                return f"IEE252I {svc} COMMAND ACCEPTED: {operand}"
        return None

    def run(self, cmd_input: str) -> str:
        self.command_count += 1
        cmd = cmd_input.strip()
        if cmd:
            # Expand configured TSO aliases before parsing. Preserve the
            # original command in history for classroom/audit visibility.
            self.command_history.append(cmd)
            pre_alias_service = self._service_command(cmd)
            if pre_alias_service is not None:
                return pre_alias_service
            if hasattr(self.state, "aliases") and self.state.aliases is not None:
                alias_response = self.state.aliases.command(cmd)
                if alias_response is not None:
                    return alias_response
                cmd = self.state.aliases.expand(cmd)
        u = cmd.upper()
        try:
            from gibson.core.smf.recording import smf_command
            smf_out = smf_command(self.state, self.userid, cmd)
            if smf_out is not None:
                return smf_out
        except Exception:
            pass
        if u.startswith("SMF"):
            try:
                from gibson.core.smf.formatters import format_list, format_detail, format_timeline, export_unload
                parts = cmd.split()
                uu = cmd.upper()
                if len(parts) == 1 or uu == "SMF LIST":
                    return format_list(self.state)
                if uu.startswith("SMF LIST TYPE("):
                    typ = uu.split("TYPE(", 1)[1].split(")", 1)[0].strip()
                    return format_list(self.state, typ)
                if len(parts) >= 3 and parts[1].upper() == "LIST":
                    return format_list(self.state, parts[2])
                if len(parts) >= 3 and parts[1].upper() == "DETAIL":
                    return format_detail(self.state, parts[2])
                if len(parts) >= 3 and parts[1].upper() == "TIMELINE":
                    return format_timeline(self.state, parts[2])
                if uu.startswith("SMF EXPORT"):
                    return export_unload(self.state)
                if uu in {"SMF HELP", "SMF ?"}:
                    return "SMF COMMANDS\n  SMF LIST <TYPE(n)>\n  SMF DETAIL <record-id>\n  SMF TIMELINE <correlation-id>\n  SMF EXPORT UNLOAD"
                return "IKJ56500I SMF COMMAND NOT RECOGNISED - TRY SMF HELP"
            except Exception as e:
                return f"SMF COMMAND FAILED: {e}"
        try:
            from gibson.core.smf.recording import smf_command
            smf_out = smf_command(self.state, self.userid, cmd)
            if smf_out is not None:
                return smf_out
        except Exception:
            pass
        try:
            from gibson.core.racf_database import racfdb_command
            racfdb_out = racfdb_command(self.state, self.userid, cmd)
            if racfdb_out is not None:
                return racfdb_out
        except Exception as e:
            if u.startswith(('RACFDB','IRRDBU00')):
                return f'RACFDB COMMAND FAILED: {e}'
        for realism_handler in (racf_services_command, racf_lab_command, parmlib_command, cics_resource_command, zsecure_command, endevor_command, ims_command, mvp_command):
            out = realism_handler(self.state, self.userid, cmd)
            if out is not None:
                return out
        v30289_out = self._v30289_command(cmd)
        if v30289_out is not None:
            return v30289_out
        svc_out = self._service_command(cmd)
        if svc_out is not None:
            return svc_out
        v26_out = v26_features.dispatch_tso(self.state, self.userid, cmd)
        if v26_out is not None:
            return v26_out

        if u in {"NORACF", "RACF OFF", "SET NORACF"}:
            self.state.config.security_mode = "noracf"
            self.state.notify_console("IRR900I RACF AUTHORIZATION CHECKING DISABLED (NORACF)", severity="ALERT")
            self.state.raise_dashboard_alert("RACF authorization checking disabled - NORACF", severity="ALERT", event_type="NORACF")
            return "IRR900I RACF AUTHORIZATION CHECKING DISABLED - NORACF ACTIVE"
        if u in {"RACF ON", "SECURE RACF", "SET RACF"}:
            self.state.config.security_mode = "secure"
            self.state.notify_console("IRR901I RACF AUTHORIZATION CHECKING ENABLED", severity="INFO")
            self.state.raise_dashboard_alert("RACF authorization checking enabled", severity="INFO", event_type="RACF")
            return "IRR901I RACF AUTHORIZATION CHECKING ENABLED - SECURE MODE ACTIVE"
        if is_secure_mode(self.state):
            blocked_prefixes = ("PTKTGEN", "PTKTUSE", "CICSPWN", "TSO-ENUM", "TSO-BRUTE")
            if u.startswith(blocked_prefixes):
                self.state.record_security_event(self.userid, "SECURE MODE BLOCK", f"COMMAND={cmd}", result="FAILURE", service="TSO")
                self.state.raise_dashboard_alert(f"Secure mode blocked command {cmd}", severity="ALERT", event_type="SECURE_BLOCK")
                return secure_block_message("CIS-aligned secure profile prevents vulnerable training path")
        if u.startswith("D "):
            cmd = "DISPLAY " + cmd[2:].strip()
            u = cmd.upper()
        if not cmd:
            return tr.PROMPT_READY

        if u in ("ACF", "ACF2"):
            self.security_mode = "ACF2"
            return self.acf2.activate()
        if u == "RACF":
            self.security_mode = "RACF"
            return self.acf2.banner_racf()

        if self.security_mode == "ACF2":
            acf2_out = self.acf2.command(cmd, self.state.racf, self.state.dynamic_racf)
            if acf2_out is not None:
                return acf2_out


        # Commands handled interactively by GibsonTelnetSession.
        if u in ("START", "ISPF"):
            return "GIBSON-INTERACTIVE:ISPF"
        if u.startswith("EDIT"):
            return "GIBSON-INTERACTIVE:EDIT"
        if u.startswith("OEDIT"):
            return "GIBSON-INTERACTIVE:OEDIT"
        if u in ("CICS", "L CICS", "LOGON APPLID(CICS)"):
            return "GIBSON-INTERACTIVE:CICS"
        if u in ("DB2", "L DB2", "LOGON APPLID(DB2)"):
            return "GIBSON-INTERACTIVE:DB2"
        if u.startswith("CONSOLE"):
            return "GIBSON-INTERACTIVE:CONSOLE"
        if u == "OMVS":
            return "GIBSON-INTERACTIVE:OMVS"
        if u.startswith("FTP"):
            return "GIBSON-INTERACTIVE:FTP"
        if u.startswith("TELNET"):
            return "GIBSON-INTERACTIVE:TELNET"
        if u == "CLEAR":
            return "\033[2J\033[H"
        if u in {"END", "RETURN"}:
            return tr.PROMPT_READY
        if u == "CANCEL":
            return "IKJ56700I CANCEL ACCEPTED\n" + tr.PROMPT_READY
        if u.startswith("AID-UNSUPPORTED"):
            return f"GIBSON {u.replace('-', ' ')} RECOGNISED - NO DEFAULT ACTION IS IMPLEMENTED IN THIS CONTEXT"
        if u in {"PA1", "PA2", "PA3", "ATTN", "SYSREQ", "RESET", "SPLIT", "SWAP", "RFIND", "RCHANGE", "LEFT", "RIGHT", "UP", "DOWN"}:
            return f"GIBSON AID KEY {u} RECOGNISED - NO DEFAULT ACTION IS IMPLEMENTED IN TSO READY"


        if u in {"UADS ?", "UADS HELP"} or u.startswith("UADS"):
            return self._uads(cmd)
        if u in {"PASSWORD ?", "PASSWORD HELP"}:
            return "PASSWORD HELP\n  Syntax: PASSWORD old-password new-password\n  Password changes obey SETROPTS PASSWORD policy."
        if u.startswith("PASSWORD"):
            return self._password_cmd(cmd)
        if u in {"MFA ?", "MFA HELP"} or u.startswith("MFA"):
            return self._mfa(cmd)
        if u.startswith("ICSF"):
            return icsf.handle_tso(self.state, self.userid, cmd)

        # Dynamic RACF/Catalog/JES/NJE additions run before template fallback.
        if u.startswith(("ADDGROUP", "ALTGROUP", "DELGROUP", "LISTGRP", "CONNECT", "REMOVE", "RDEFINE", "RALTER", "RDELETE", "RLIST", "PERMIT", "REVOKE", "LISTDSD", "ADDSD", "ALTDSD", "DELDSD")):
            out = self.state.dynamic_racf.command(cmd, self.userid, self.state.racf)
            if out is not None:
                self._audit_security_command(cmd, out)
                return out
        if u.startswith("SEARCH"):
            out = self.state.dynamic_racf.command(cmd, self.userid, self.state.racf)
            if out is not None:
                return out
        if u.startswith("DEFINE ALIAS"):
            m = re.search(r"NAME\(([^)]+)\)\s+RELATE\(([^)]+)\)", cmd, re.I)
            if m:
                return self.state.catalog.define_alias(m.group(1), m.group(2))
            return "IDC3009I DEFINE ALIAS SYNTAX: DEFINE ALIAS(NAME(alias) RELATE(catalog))"
        if u.startswith("DEFINE CLUSTER") or u.startswith("DEF CLUSTER") or u.startswith("DEFINE CL"):
            out = self.state.catalog.define_cluster(cmd, owner=self.userid)
            self._audit_smf80("VSAM DEFINE", f"COMMAND={cmd[:80]}")
            return out
        if u.startswith("DEFINE AIX") or u.startswith("DEF AIX"):
            return self.state.catalog.define_aix(cmd)
        if u.startswith("DEFINE PATH") or u.startswith("DEF PATH"):
            return self.state.catalog.define_path(cmd)
        if (u.startswith("DELETE ") or u.startswith("DEL ")) and ("CLUSTER" in u or self._is_vsam_name(cmd)):
            nm = self.state.catalog._kw(cmd, "") if False else None
            m = re.match(r"(?:DELETE|DEL)\s+([^\s(]+)", cmd, re.I)
            if m:
                return self.state.catalog.delete_cluster(m.group(1))
        if u in ("LISTCAT ALIAS", "LISTCAT ALIASES"):
            return self.state.catalog.list_aliases()
        jes2_out = self.state.jes.jes2_command(cmd)
        if jes2_out is not None:
            return jes2_out
        nje_out = self.state.nje.command(cmd)
        if nje_out is not None:
            return nje_out

        if u.startswith("PTKTGEN"):
            return self._ptktgen(cmd)
        if u.startswith("PTKTSTAT"):
            return self._ptktstat(cmd)
        if u.startswith("PTKTUSE"):
            return self._ptktuse(cmd)
        if u.startswith("SETROPTS"):
            out = self._setropts_freeze(cmd)
            if out is not None:
                self._audit_smf80("SETROPTS", f"COMMAND={cmd} RESULT={out[:70]}")
                return out
            out = self.state.dynamic_racf.command(cmd, self.userid, self.state.racf)
            if out is not None:
                self._audit_smf80("SETROPTS", f"COMMAND={cmd} RESULT={out[:70]}")
                return out
        if u.startswith("RVARY"):
            return self._rvary()
        if u.startswith("PROFILE"):
            return self._profile(cmd)
        if u.startswith("LISTDS ") or u == "LISTDS":
            return self._listds(cmd)
        if u.startswith("RENAME ") or u.startswith("REN "):
            return self._rename(cmd)
        if u.startswith("OGET"):
            return self._oget(cmd)
        if u.startswith("OPUT"):
            return self._oput(cmd)
        if u.startswith("NETSTAT"):
            return self._netstat(cmd)
        if u.startswith("PING "):
            return self.state.network.ping(cmd.split(maxsplit=1)[1])
        if u.startswith("TRACERTE ") or u.startswith("TRACEROUTE "):
            return self.state.network.traceroute(cmd.split(maxsplit=1)[1])
        if u.startswith("SETPROG APF") or u.startswith("SETPROG LNKLST") or u.startswith("SETPROG LPA"):
            out = self._setprog_general(cmd)
            try:
                mdsn = re.search(r"DSNAME=([^,\s]+)", cmd, re.I)
                mvol = re.search(r"VOLUME=([^,\s]+)", cmd, re.I)
                act = "ADD" if ",ADD" in u or " APF,ADD" in u else ("DELETE" if ",DELETE" in u or " APF,DELETE" in u else "UPDATE")
                if mdsn:
                    v26_features.record_apf_change(self.state, self.userid, act, mdsn.group(1), mvol.group(1) if mvol else "SMS")
            except Exception:
                pass
            return out
        if u in ("HELP", "?") or u.startswith("HELP "):
            topic = cmd.split(None, 1)[1] if len(cmd.split(None, 1)) > 1 else ''
            return self._structured_help_v2(topic)
        if u.startswith("LISTUSER"):
            return self._listuser(cmd)
        if u.startswith("RACLIST"):
            return self._raclist(cmd)
        if u.startswith("SEARCH CLASS(USER)"):
            return self.state.racf.search_special()
        if u.startswith("SEARCH"):
            # Honour exact response-template commands before the generic
            # SEARCH fallback so entries shown by autocomplete execute from
            # both READY and CONSOLE.
            rendered = self.state.templates.render(cmd, self.userid, self._attrib())
            if rendered is not None:
                return rendered
            rendered = self.state.templates.render("SEARCH_FILTER", self.userid, self._attrib())
            return rendered or self.state.templates.render("SEARCHALLWARNINGNOMASK", self.userid) or "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"
        if u.startswith("LISTCAT"):
            return self._listcat(cmd)
        # NOTE: ADDUSER/ALTUSER are handled earlier by _v30289_adduser /
        # _v30289_altuser (which accept PASSWORD(...) and PASS(...)). The older
        # PASS(-only _adduser/_altuser below were shadowed dead branches and are
        # removed so a future dispatch reorder can't resurface the broken parser.
        if u.startswith("DELUSER") or u.startswith("DELETEUSER"):
            return self._deluser(cmd)
        if u.startswith("IPLINFO"):
            return tr.MSG_INSUFFICIENT
        if u.startswith("VIEW "):
            return self._view(cmd)
        if u.startswith("DEL ") or u.startswith("DELETE "):
            return self.state.datasets.delete(self.userid, self.qualify_dataset_name(cmd.split(None, 1)[1]))
        if u.startswith("ALLOC "):
            ds = self.qualify_dataset_name(cmd.split(None, 1)[1])
            self.state.datasets.allocate(self.userid, ds)
            self._audit_smf80("DATASET CREATE", f"DATASET={ds} CREATED BY {self.userid}")
            return f"IDC0508I DATA SET {ds} ALLOCATED"
        if u.startswith("SUBMIT"):
            return self._submit(cmd)
        if u.startswith("TRANSMIT") or u.startswith("XMIT"):
            return self._transmit(cmd)
        if u.startswith("RECEIVE"):
            return self._receive(cmd)
        if u.startswith("JES"):
            return self._jes(cmd)
        if u.startswith("SEND"):
            return self._send_message(cmd)
        if u.startswith("SESSIONSTATS"):
            return self._sessionstats()
        if u in {"D IND$FILE,STATUS", "DISPLAY IND$FILE,STATUS", "D INDFILE,STATUS", "D TERMINAL", "D TN3270"}:
            mode = (self.state.config.indfile_mode or "off").upper()
            return "\n".join([
                "IND$FILE / TERMINAL DIAGNOSTIC",
                f"COMMAND-MODE IND$FILE ===> {'AVAILABLE' if mode != 'OFF' else 'DISABLED'}",
                "NVT/ANSI TYPED GET/PUT ===> SUPPORTED",
                "S3270 SCRIPTED COMMAND MODE ===> VALIDATION ASSETS INCLUDED",
                "NATIVE X3270/C3270 TRANSFER ===> NOT CLAIMED / NOT VALIDATED",
                "TN3270E ===> NOT REQUIRED; CLASSIC/DUAL-MODE FRONTEND MAY FALL BACK TO NVT",
                "RECOMMENDATION ===> USE COMMAND-MODE IND$FILE GET/PUT OR S3270 SCRIPTED VALIDATION",
            ])
        if u.startswith("IND$FILE"):
            return self._indfile(cmd)
        if u.startswith("TRANSFER(") or "DIRECTION=SEND" in u or "DIRECTION=RECEIVE" in u:
            try:
                from gibson.core.indfile_protocol import handle_typed_transfer
                return handle_typed_transfer(self.state, self.userid, cmd)
            except Exception as exc:
                return f"IND$FILE NATIVE TRANSFER FAILED: {exc}"
        if u.startswith("CK"):
            return self._healthcheck(cmd)
        if u.startswith("SECEVENTS"):
            return self._secevents()
        if u in ("SDSF", "ISF") or u.startswith("SDSF ") or u.startswith("ISF "):
            parts = cmd.split(maxsplit=1)
            panel = parts[1].strip().upper() if len(parts) > 1 else "ST"
            app = SdsfApp(self.state, self.userid)
            return app.render_main() if panel in ("MENU", "SDSF", "ISF") else app.render_panel(panel)
        if u.startswith("EXEC ") or u.startswith("EX ") or u.startswith("REXX ") or u.startswith("%"):
            return self._run_rexx(cmd)
        if u.startswith("DSN") or u.startswith("SPUFI") or u.startswith("RUN SQL "):
            sql = cmd[len("RUN SQL "):] if u.startswith("RUN SQL ") else "SELECT * FROM SYSIBM.SYSTABLES"
            return Db2Simulator(self.state).format_spufi(sql, self.userid)
        if u.startswith("DISPLAY "):
            return self._display(cmd)

        # Bare-command forms of the training tools the user types directly
        # (ELV.APF privilege-escalation lab; ENUM system enumerator).  These are
        # normally REXX execs but are accepted as direct commands for the labs.
        if u in {"ELV.APF", "ELVAPF"} or u.startswith("ELV.APF ") or u.startswith("ENUM") or u.startswith("ENUM "):
            tool = self._simulated_rexx_tool(cmd)
            if tool is not None:
                return tool

        rendered = self.state.templates.render(cmd, self.userid, self._attrib())
        if rendered is not None:
            return rendered
        return f"IKJ56500I COMMAND {cmd} NOT FOUND"


    def _structured_help_v2(self, topic: str = '') -> str:
        topic=(topic or '').strip().upper()
        cats={
            'COMMANDS':['HELP COMMANDS','ISPF','OMVS','SDSF','CICS','DB2','CONSOLE','LISTCAT','VIEW','EDIT','SUBMIT','RACFSERV','RACFUSER','RACFSYS','PTKTGEN','PTKTSTAT','PTKTUSE','SECEVENTS','ZSEC','FTP','TELNET','PROFILE','LISTDS','ALLOC','RENAME','TRANSMIT','RECEIVE'],
            'RACF':['RACFSERV','RACFUSER','RACFSYS','LISTUSER','LISTGRP','RLIST','PERMIT','SETROPTS LIST','RACDCERT'],
            'DATASET':['LISTCAT','LISTDS','VIEW','EDIT','ALLOC','DELETE','RENAME','IND$FILE','TRANSMIT','RECEIVE'],
            'CICS':['L CICS','DVCA','OMEN','CBSA','CEMT','CEDA','CECI','HACK3270'],
            'DB2':['L DB2','DSN','SPUFI','RUN SQL','DB2 DISPLAY SECURITY'],
            'OMVS':['OMVS','HELP PASSTICKET','nmap','cicspwn','lynx','rss','tshocker'],
            'PASSTICKET':['PTKTGEN USER(userid) APPL(applid)','PTKTSTAT','PTKTUSE','OMVS: genptkt, unmaskptkt, parseptkt'],
            'SECURITY':['SECEVENTS','ZSEC','RACFLAB','MFA','ICSF','RACFSERV'],
            'ISPF':['START','ISPF','R option RACF Services','M.5 RACF Services','PF3/PF12 END'],
            'SDSF':['SDSF','SDSF ST','SDSF O','SDSF H','SDSF APF'],
        }
        if not topic:
            lines=['TSO HELP FACILITY','HELP TOPICS:', '  ' + '  '.join(sorted(cats)), '', 'Enter HELP topic for details.']
        elif topic in cats:
            lines=[f'TSO HELP - {topic}', '-'*60] + [f'  {x}' for x in cats[topic]]
        else:
            val=self.LEGACY_HELP.get(topic)
            if val: lines=[f'TSO HELP - {topic}', val]
            else: lines=[f'IKJ56700I HELP TOPIC {topic} NOT FOUND', 'Try HELP COMMANDS or HELP RACF.']
        return self._page_output('\n'.join(lines), page_size=18)

    def _page_output(self, text: str, page_size: int = 18) -> str:
        lines=(text or '').splitlines()
        if len(lines) <= page_size:
            return text
        out=[]
        for i in range(0, len(lines), page_size):
            out.extend(lines[i:i+page_size])
            if i + page_size < len(lines):
                out.append('***')
        return '\n'.join(out)

    def _omvs_env(self):
        from gibson.apps.omvs import OmvsEnvironment
        return OmvsEnvironment(self.state)

    def _tso_path(self, operand: str) -> str:
        value = operand.strip().strip("'").strip('"')
        env = self._omvs_env()
        env.ensure_user_profile(self.userid)
        cwd = f"/u/{self.userid.lower()}"
        return env.resolve(cwd, value)

    def qualify_dataset_name(self, operand: str) -> str:
        raw = (operand or "").strip()
        if not raw:
            return ""
        quoted = len(raw) >= 2 and raw[0] == raw[-1] == "'"
        value = raw.strip().strip("'").strip('"').upper()
        if not value:
            return ""
        first = value.split('.', 1)[0]
        if quoted or value.startswith(("SYS1.", "SYS2.", "SYS3.", "SYS4.", "CEE.", "TCPIP.")):
            return value
        if value.startswith(self.userid + "."):
            return value
        if '.' in value and self.state.racf.exists(first):
            return value
        return self.userid + "." + value

    def _parse_uss_transfer(self, cmd: str, verb: str) -> list[str] | None:
        try:
            argv = shlex.split(cmd)
        except ValueError:
            return None
        if not argv or argv[0].upper() != verb.upper():
            return None
        filtered: list[str] = []
        skip = False
        for item in argv[1:]:
            upper = item.upper()
            if skip:
                skip = False
                continue
            if upper == "CONVERT":
                skip = True
                continue
            if upper.startswith("CONVERT("):
                continue
            if upper in {"TEXT", "BINARY", "YES", "NO", "TO1047", "FROM1047"}:
                continue
            filtered.append(item)
        return filtered

    def _help(self, cmd: str) -> str:
        parts = cmd.split(maxsplit=1)
        if len(parts) == 2:
            key = parts[1].strip().upper()
            if key.startswith("SETROPTS"):
                return self.state.password_policy.set_from_command("HELP " + key)
            if key.startswith("MFA"):
                return self._mfa("MFA HELP")
            if key.startswith("UADS"):
                return self._uads("UADS HELP")
            return f"{key}: {self.LEGACY_HELP.get(key, 'No help available for ' + key)}"
        lines = ["Available Commands:"]
        for name, desc in self.LEGACY_HELP.items():
            lines.append(f"  {name}: {desc}")
        lines.append("Type HELP <command> for detailed info.")
        return "\n".join(lines)

    def _listuser(self, cmd: str) -> str:
        parts = cmd.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return self.state.racf.listuser(self.userid)
        target = parts[1].strip().upper()
        if target == "*":
            return "\n\n".join(self.state.racf.listuser(x) for x in sorted(self.state.racf.users))
        return self.state.racf.listuser(target)

    def _raclist(self, cmd: str) -> str:
        pattern = r"RACLIST\s+CLASS\(([^)]+)\)\s+ID\(([^)]+)\)(\s+DETAIL)?"
        m = re.search(pattern, cmd, re.I)
        if not m:
            return "Invalid RACLIST command format. Usage: RACLIST CLASS(USER) ID(username) <DETAIL>"
        rac_class, rac_id = m.group(1).upper(), m.group(2).strip().upper()
        if rac_class != "USER":
            return f"RACLIST for RACF class {rac_class} is not implemented."
        user = self.state.racf.get(rac_id)
        if not user:
            return f"RACF profile for {rac_id} not found."
        ps_status = "ENCRYPTED" if user.password.startswith("$1$") else "CLEAR"
        template = self.state.templates.render("RACLIST.TXT", rac_id, "SPECIAL" if user.special else "NONE", {"{RACID}": rac_id, "{PSSTATUS}": ps_status})
        if template:
            return template
        return self.state.racf.listuser(rac_id) + f"\n PASSWORD STATUS={ps_status}"

    def _is_vsam_name(self, cmd: str) -> bool:
        m = re.match(r"(?:DELETE|DEL)\s+([^\s(]+)", cmd, re.I)
        if not m:
            return False
        return m.group(1).upper().strip("'") in getattr(self.state.catalog, "clusters", {})

    def _listcat(self, cmd: str) -> str:
        u = cmd.upper()
        # LISTCAT ENTRIES(name) [ALL] - render a full VSAM cluster entry if known
        ent = re.search(r"(?:ENTRIES|ENT|ENTRY)\(([^)]+)\)", cmd, re.I)
        if ent:
            entry = self.state.catalog.listcat_entry(ent.group(1).split()[0])
            if entry is not None:
                return entry
            # named entry that is not a VSAM cluster -> catalog "not found"
            nm = ent.group(1).split()[0].upper()
            rows = self.state.datasets.listcat(self.userid, prefix=None)
            if not any(r.name.upper() == nm for r in rows):
                return ("IDCAMS  SYSTEM SERVICES\n"
                        f"IDC3012I ENTRY {nm} NOT FOUND\n"
                        f"IDC3009I ** VSAM CATALOG RETURN CODE IS 8 - REASON CODE IS IGG0CLEG-42\n"
                        f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 4")
        m = re.search(r"(?:LEVEL|LVL)\(([^)]*)\)", cmd, re.I)
        prefix = m.group(1).strip().upper() if m else None
        if prefix is None:
            parts = cmd.split()
            if len(parts) > 1 and parts[1].upper() not in {"ENTRIES", "ENT", "ENTRY", "ALL", "ALIAS", "ALIASES"}:
                prefix = parts[1].strip().strip("'").upper().rstrip("*").rstrip(".")
                if prefix and not prefix.endswith('.') and '.' not in prefix:
                    prefix += '.'
        rows = self.state.datasets.listcat(self.userid, prefix=prefix)
        # Include any VSAM clusters matching the prefix in the level listing.
        cluster_lines = []
        for cname in sorted(getattr(self.state.catalog, "clusters", {})):
            if prefix is None or cname.startswith(prefix):
                cluster_lines.append(f"CLUSTER ------- {cname}")
        if not rows and not cluster_lines:
            rendered = self.state.templates.render("LISTCAT", self.userid, self._attrib())
            return rendered or "IDCAMS  SYSTEM SERVICES\nNO ENTRIES FOUND"
        body = [f"{r.name:<44} {r.org:<2} {r.recfm:<2} LRECL={r.lrecl}" for r in rows]
        return "\n".join(cluster_lines + body)

    def _audit_smf80(self, event: str, details: str, result: str = "SUCCESS") -> None:
        try:
            self.state.audit.record_smf80(self.userid, event, details, result=result)
        except Exception:
            pass

    def _audit_security_command(self, cmd: str, result: str) -> None:
        upper = (cmd or "").upper()
        if not result.startswith(("ICH", "IRR", "IDC")):
            return
        if upper.startswith("PERMIT") and "SUCCESSFUL" in result.upper():
            self._audit_smf80("PERMIT CHANGE", f"COMMAND={cmd} RESULT={result[:70]}")
        elif upper.startswith(("RDEFINE", "ADDSD")) and "DEFINED" in result.upper():
            self._audit_smf80("PROFILE DEFINE", f"COMMAND={cmd} RESULT={result[:70]}")
        elif upper.startswith(("RALTER", "ALTDSD")) and "ALTERED" in result.upper():
            self._audit_smf80("PROFILE ALTER", f"COMMAND={cmd} RESULT={result[:70]}")
        elif upper.startswith(("ADDGROUP", "CONNECT", "REMOVE", "DELGROUP", "ALTGROUP")) and any(word in result.upper() for word in ("DEFINED", "CONNECTED", "REMOVED", "ALTERED", "DELETED")):
            self._audit_smf80("GROUP ADMIN", f"COMMAND={cmd} RESULT={result[:70]}")


    def _setropts_freeze(self, cmd: str) -> str | None:
        u = cmd.upper().strip()
        if u in {"SETROPTS", "SETROPTS LIST", "SETROPTS LIST ALL", "SETROPTS ?", "SETROPTS HELP", "SETROPTS PASSWORD ?", "SETROPTS PASSWORD HELP"}:
            return self.state.password_policy.set_from_command(cmd if u != "SETROPTS ?" else "SETROPTS HELP")
        if u.startswith("HELP SETROPTS"):
            return self.state.password_policy.set_from_command(cmd)
        # All SETROPTS updates are centralized in PasswordPolicy so LIST, password,
        # class, RACLIST, GENERIC, MFA, audit, warning, and refresh state cannot drift.
        if u.startswith("SETROPTS"):
            if not self.is_special():
                return tr.MSG_INSUFFICIENT
            from gibson.core.security_mode import is_secure_mode
            out = self.state.password_policy.set_from_command(cmd, secure_mode=is_secure_mode(self.state), userid=self.userid)
            self.state.password_policy.save(self.state.config.sim_root / "setropts_password_policy.json")
            try:
                self.state.record_security_event(self.userid, "SETROPTS", cmd, service="RACF")
            except Exception:
                pass
            return out
        return None

    def _uads(self, cmd: str) -> str:
        u = cmd.upper().strip()
        if u in {"UADS ?", "UADS HELP", "HELP UADS"}:
            return "UADS HELP\n  UADS LIST\n  UADS SHOW userid\n  UADS VERIFY\n  UADS SYNC RACF\n  SYS1.UADS is a protected Gibson simulated TSO user attribute data set."
        if u in {"UADS", "UADS LIST"}:
            # SYS1.UADS is no longer an authority - it is a read-only view derived
            # live from RACF/GACF.DB (the single source of truth), so it can never
            # drift from the real user records.
            self.state.uads.sync_from_racf(self.state.racf, self.state.password_policy)
            return ("SYS1.UADS - read-only view derived from RACF/GACF.DB "
                    "(GACF.DB is authoritative)\n" + "\n".join(self.state.uads.list_lines()))
        if u.startswith("UADS SHOW"):
            self.state.uads.sync_from_racf(self.state.racf, self.state.password_policy)
            parts = cmd.split()
            return self.state.uads.show(parts[2] if len(parts) > 2 else self.userid)
        if u in {"UADS VERIFY", "UADS REBUILD", "UADS SYNC RACF"}:
            self.state.uads.sync_from_racf(self.state.racf, self.state.password_policy)
            try:
                self.state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(self.state.uads.list_lines()) + "\n")
            except Exception:
                pass
            return "IKJ56890I SYS1.UADS VERIFIED AND SYNCHRONIZED WITH RACF"
        return "UADS SYNTAX: UADS LIST | UADS SHOW userid | UADS VERIFY | UADS SYNC RACF"

    def _password_cmd(self, cmd: str) -> str:
        parts = cmd.split()
        if len(parts) < 3:
            return "PASSWORD SYNTAX: PASSWORD old-password new-password"
        old, new = parts[1], parts[2]
        if not self.state.racf.verify_password(self.userid, old):
            return "ICH70006I CURRENT PASSWORD IS NOT VALID"
        ent = self.state.uads.get(self.userid)
        hist = list(getattr(ent, 'password_history', [])) if ent else []
        ok, msg = self.state.password_policy.validate_new_password(self.userid, new, hist, freeze_verify_password_hash)
        if not ok:
            return msg
        self.state.racf.altuser(self.userid, password=new)
        new_rec = self.state.racf.get(self.userid)
        self.state.uads.set_password(self.userid, new_rec.password if new_rec else freeze_hash_password(new, self.state.password_policy.algorithm), change_required=False)
        try:
            self.state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(self.state.uads.list_lines()) + "\n")
            self.state.record_security_event(self.userid, "PASSWORD CHANGE", "USER PASSWORD CHANGED", service="RACF")
        except Exception:
            pass
        return "ICH70007I PASSWORD CHANGED SUCCESSFULLY"

    def _mfa(self, cmd: str) -> str:
        parts = cmd.strip().split()
        action = parts[1].upper() if len(parts) > 1 else "ON"
        if action in {"?", "HELP"}:
            return "MFA HELP\n  MFA STATUS\n  MFA ON | MFA OFF\n  MFA ENROLL userid TYPE(TOTP|PUSH|EMAIL)\n  MFA REMOVE userid | MFA RESET userid\n  MFA VERIFY userid token\n  SETROPTS MFA/NOMFA controls global simulated MFA policy."
        if action in ("ON", "ENABLE", "ENABLED"):
            if not self.is_special():
                return "ICH408I USER NOT AUTHORISED TO ALTER MFA MODE"
            self.state.password_policy.mfa_active = True; self.state.password_policy.save(self.state.config.sim_root / "setropts_password_policy.json")
            return self.state.set_mfa(True, self.userid)
        if action in ("OFF", "DISABLE", "DISABLED"):
            if not self.is_special():
                return "ICH408I USER NOT AUTHORISED TO ALTER MFA MODE"
            self.state.password_policy.mfa_active = False; self.state.password_policy.save(self.state.config.sim_root / "setropts_password_policy.json")
            return self.state.set_mfa(False, self.userid)
        if action in ("STATUS", "STAT", "LIST"):
            return self.state.mfa_manager.status() + "\n" + "\n".join(self.state.mfa_status_lines())
        if action == "ENROLL":
            if not self.is_special():
                return "ICH408I USER NOT AUTHORISED TO ENROLL MFA"
            target = parts[2].upper() if len(parts) > 2 else self.userid
            typ = "TOTP"
            m = re.search(r"TYPE\(([^)]+)\)", cmd, re.I)
            if m: typ = m.group(1).upper()
            out = self.state.mfa_manager.enroll(target, typ)
            self.state.record_security_event(self.userid, "MFA ENROLL", f"TARGET={target} TYPE={typ}", service="RACF")
            return out
        if action in {"REMOVE", "RESET"}:
            if not self.is_special():
                return "ICH408I USER NOT AUTHORISED TO ALTER MFA"
            target = parts[2].upper() if len(parts) > 2 else self.userid
            self.state.record_security_event(self.userid, "MFA " + action, f"TARGET={target}", service="RACF")
            return self.state.mfa_manager.remove(target) if action == "REMOVE" else self.state.mfa_manager.enroll(target, "TOTP")
        if action == "VERIFY":
            target = parts[2].upper() if len(parts) > 2 else self.userid
            token = parts[3] if len(parts) > 3 else ""
            return "IRR71003I MFA VERIFY SUCCESS" if self.state.mfa_manager.verify(target, token) else "IRR71004I MFA VERIFY FAILED"
        return "MFA SYNTAX: MFA STATUS|ON|OFF|ENROLL userid TYPE(TOTP)|REMOVE userid|RESET userid|VERIFY userid token"

    def _adduser(self, cmd: str) -> str:
        if not self.is_special():
            return tr.MSG_INSUFFICIENT
        m = re.search(r"ADDUSER\s+([A-Z0-9#$@]+)\s+PASS\(([^)]*)\)(.*)$", cmd, re.I)
        if not m:
            return "Error: Incorrect format for ADDUSER. Format: ADDUSER userid PASS(password) <SPECIAL|NONE> <OMVS|NOOMVS> <DFLTGRP(group)>"
        new_user = m.group(1).strip().upper()
        pw = m.group(2)
        tail = " " + m.group(3).upper() + " "
        if len(new_user) > 8:
            return "Warning: Username can only be a max of 8 characters."
        if len(pw) > 8:
            return "Warning: Password can only be a max of 8 characters."
        gm = re.search(r"DFLTGRP\(([^)]+)\)", cmd, re.I)
        dfltgrp = gm.group(1).strip().upper() if gm else self.default_group()
        if dfltgrp not in self.state.dynamic_racf.groups:
            return f"ICH30001I GROUP {dfltgrp} NOT FOUND"
        special = self._has_operand(tail, "SPECIAL") and not self._has_operand(tail, "NOSPECIAL") and not self._has_operand(tail, "NONE")
        omvs = self._has_operand(tail, "OMVS") and not self._has_operand(tail, "NOOMVS")
        out = self.state.racf.adduser(new_user, pw, special, omvs, default_group=dfltgrp)
        if out.startswith("ICH01003I"):
            self.state.dynamic_racf.connect_user(new_user, dfltgrp, "USE")
            try:
                ent = self.state.racf.get(new_user)
                self.state.uads.add_or_update_user(new_user, ent.password if ent else "", dfltgrp, change_required=bool(getattr(ent, "password_change_required", False)) if ent else False, source="ADDUSER")
                self.state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(self.state.uads.list_lines()) + "\n")
            except Exception:
                pass
            attrs = ("SPECIAL" if special else "NOSPECIAL") + "/" + ("OMVS" if omvs else "NOOMVS")
            self._audit_smf80("USER CREATE", f"USER={new_user} DFLTGRP={dfltgrp} ATTRS={attrs} PWCHANGE=REQUIRED")
            try:
                from gibson.core.racf_database import materialise_racfds
                materialise_racfds(self.state, changed_user=new_user, plaintext_password=pw, source_command='ADDUSER')
            except Exception:
                pass
        return out


    def _deluser(self, cmd: str) -> str:
        if not self.is_special():
            return tr.MSG_INSUFFICIENT
        parts = cmd.split()
        if len(parts) < 2:
            return "ICH01008I DELUSER userid"
        target = parts[1].strip().upper()
        if target == "IBMUSER" and is_secure_mode(self.state):
            self.state.record_security_event(self.userid, "DELUSER BLOCKED", "TARGET=IBMUSER BREAK-GLASS PROTECTED", result="FAILURE", service="RACF")
            return "ICH01012I DELUSER IBMUSER REJECTED - SECURE MODE BREAK-GLASS USER IS PROTECTED"
        if target == self.userid.upper():
            return "ICH01011I CANNOT DELETE CURRENT LOGON USER"
        out = self.state.racf.deleteuser(target)
        if "DELETED" in out.upper():
            self.state.dynamic_racf.cleanup_deleted_user(target)
            self._audit_smf80("USER DELETE", f"USER={target} GROUPS/PERMITS CLEANED")
        return out

    def _altuser(self, cmd: str) -> str:
        if not self.is_special():
            return tr.MSG_INSUFFICIENT
        parts = cmd.split()
        if len(parts) < 2:
            return "Error: ALTUSER command requires at least a username."
        target = parts[1].upper()
        pw = None
        m = re.search(r"PASS\(([^)]*)\)", cmd, re.I)
        if m:
            pw = m.group(1)
            if len(pw) > 8:
                return "Warning: Password can only be a max of 8 characters."
        text_u = " " + cmd.upper() + " "
        special = True if self._has_operand(text_u, "SPECIAL") and not self._has_operand(text_u, "NOSPECIAL") else False if self._has_operand(text_u, "NOSPECIAL") or self._has_operand(text_u, "NONE") else None
        omvs = True if self._has_operand(text_u, "OMVS") and not self._has_operand(text_u, "NOOMVS") else False if self._has_operand(text_u, "NOOMVS") else None
        gm = re.search(r"DFLTGRP\(([^)]+)\)", cmd, re.I)
        dfltgrp = gm.group(1).strip().upper() if gm else None
        revoked = True if self._has_operand(text_u, "REVOKE") else False if self._has_operand(text_u, "RESUME") or self._has_operand(text_u, "NOREVOKE") else None
        if target == "IBMUSER" and revoked is True and is_secure_mode(self.state):
            self.state.record_security_event(self.userid, "ALTUSER REVOKE BLOCKED", "TARGET=IBMUSER BREAK-GLASS PROTECTED", result="FAILURE", service="RACF")
            return "ICH01013I ALTUSER IBMUSER REVOKE REJECTED - SECURE MODE BREAK-GLASS USER IS PROTECTED"
        if dfltgrp is not None:
            if dfltgrp not in self.state.dynamic_racf.groups:
                return f"ICH30001I GROUP {dfltgrp} NOT FOUND"
            if target not in self.state.dynamic_racf.groups[dfltgrp].users:
                return f"ICH01009I USER {target} NOT CONNECTED TO GROUP {dfltgrp}"
        out = self.state.racf.altuser(target, password=pw, special=special, omvs=omvs, default_group=dfltgrp, revoked=revoked)
        if out.startswith("ICH01006I"):
            flags = []
            if pw is not None:
                flags.append("PASSWORD")
                try:
                    ent = self.state.racf.get(target)
                    if ent:
                        self.state.uads.set_password(target, ent.password, change_required=False)
                        self.state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(self.state.uads.list_lines()) + "\n")
                except Exception:
                    pass
            if special is not None:
                flags.append("SPECIAL" if special else "NOSPECIAL")
            if omvs is not None:
                flags.append("OMVS" if omvs else "NOOMVS")
            if dfltgrp is not None:
                flags.append(f"DFLTGRP={dfltgrp}")
            if revoked is True:
                flags.append("REVOKE")
            elif revoked is False:
                flags.append("RESUME")
            self._audit_smf80("USER ALTER", f"USER={target} CHANGES={' '.join(flags) or 'NONE'}")
            try:
                from gibson.core.racf_database import materialise_racfds
                materialise_racfds(self.state, changed_user=target, plaintext_password=pw if pw else None, source_command='ALTUSER')
            except Exception:
                pass
            if revoked is True:
                return f"ICH10006I ALTUSER {target} REVOKE COMPLETE\nSECURITY EVENT RECORDED"
            if revoked is False:
                return f"ICH10007I ALTUSER {target} RESUME COMPLETE\nSECURITY EVENT RECORDED"
        return out

    def _view(self, cmd: str) -> str:
        try:
            return self.state.datasets.read(self.userid, self.qualify_dataset_name(cmd.split(None, 1)[1]))
        except PermissionError as e:
            return str(e)
        except Exception as e:
            return f"IKJ56228I DATA SET NOT FOUND: {e}"

    def _send_message(self, cmd: str) -> str:
        m = re.match(r"SEND\s+'([^']+)'\s+(?:USER\(([^)]+)\)|CN\(([^)]+)\))(?:\s+(NOW|LOGON|SAVE))?", cmd, re.I)
        if not m:
            return "Invalid SEND command format. Usage: SEND 'message' USER(userid) NOW|LOGON|SAVE or SEND 'message' CN(*)"
        message = m.group(1)
        target = (m.group(2) or m.group(3) or "").strip().upper()
        option = (m.group(4) or "NOW").upper()
        live_message = f"IKJ56247I MESSAGE FROM {self.userid}: {message}"
        if target == "*":
            delivered = 0
            for uid in list(getattr(self.state.sessions, "sessions", {})):
                if self.state.sessions.notify(uid, live_message):
                    delivered += 1
            return f"Broadcast message sent to {delivered} active user(s)."
        if not self.state.racf.exists(target):
            return f"Target user {target} does not exist."
        if option == "NOW" and self.state.sessions.notify(target, live_message):
            return f"Message sent immediately to {target}."
        self.state.pending_messages.setdefault(target, []).append((self.userid, message))
        pending_dir = self.state.racf.ensure_user_dir(self.state.config.files_root, target)
        pending_path = pending_dir / "pending_messages.txt"
        with pending_path.open("a", encoding="utf-8") as fh:
            fh.write(f"Message from {self.userid}: {message}\n")
        if option == "NOW":
            return f"User {target} not active. Message queued for next logon."
        return f"Message queued for {target} on next logon."

    def _sessionstats(self) -> str:
        duration = datetime.now() - self.login_time
        return (
            "Session Statistics:\n"
            f"  Login Time: {self.login_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  Duration: {str(duration).split('.')[0]}\n"
            f"  Command Count: {self.command_count}"
        )

    def _jes(self, cmd: str) -> str:
        parts = cmd.split(maxsplit=2)
        if len(parts) < 2:
            return "Usage: JES STATUS or JES SUBMIT <job description>"
        action = parts[1].upper()
        if action == "STATUS":
            jobs = self.state.jes.list_jobs(owner=None if self.is_special() else self.userid)
            if not jobs:
                return "No jobs in the JES queue."
            return "\n".join(f"{j.jobid} - {j.jobname} OWNER={j.owner} STATUS={j.status.value} RC={j.rc:04d}" for j in jobs)
        if action == "SUBMIT":
            desc = parts[2] if len(parts) > 2 else self.userid
            jcl = f"//{desc[:8].upper()} JOB (ACCT),'GIBSON',CLASS=A,MSGCLASS=A\n//STEP1 EXEC PGM=IEFBR14\n"
            job = self.state.jes.submit(jcl, self.userid, runner=self.run, sql_runner=lambda sql: Db2Simulator(self.state).format_spufi(sql, self.userid), cobol_runner=self._compile_cobol)
            return f"Job submitted: {job.jobid} - {job.jobname}"
        return "Unknown JES command. Use JES STATUS or JES SUBMIT <job description>"


    def _ptktgen(self, cmd: str) -> str:
        user_m = re.search(r"USER\(([^)]+)\)", cmd, re.I)
        appl_m = re.search(r"APPL\(([^)]+)\)", cmd, re.I)
        userid = (user_m.group(1).strip().upper() if user_m else self.userid)
        applid = (appl_m.group(1).strip().upper() if appl_m else "CICS")
        result = get_passticket_service(self.state).generate(userid, applid, self.userid, source="TSO")
        if not result.get("ok"):
            return str(result.get("message", "IRRPT000I PASSTICKET GENERATION FAILED"))
        lines = [
            "IRRPT100I PASSTICKET GENERATED",
            f" USERID     = {result['userid']}",
            f" APPLID     = {result['applid']}",
            f" PASSTICKET = {result['ticket']}",
            f" EXPIRES    = {result['expires_at']}",
            f" REQUESTER  = {result['requester']}",
        ]
        if result.get("replay_allowed"):
            lines.append(" WARNING    = NO REPLAY PROTECTION")
        if result.get("appl_mismatch_allowed"):
            lines.append(" WARNING    = APPLID MISMATCH ACCEPTED")
        if result.get("leaked"):
            lines.append(" WARNING    = LAB LEAK MODE ENABLED")
        return "\n".join(lines)

    def _ptktstat(self, cmd: str) -> str:
        appl_m = re.search(r"APPL\(([^)]+)\)", cmd, re.I)
        appl_filter = appl_m.group(1).strip().upper() if appl_m else ""
        svc = get_passticket_service(self.state)
        profs = svc.profile_rows()
        issued = svc.issued_rows()
        audit = svc.audit_rows()
        if appl_filter:
            profs = [row for row in profs if row.get("PROFILE") == appl_filter]
            issued = [row for row in issued if row.get("APPLID") == appl_filter]
        lines = ["IRRPT300I PASSTICKET STATUS DISPLAY", "", "PTKTDATA PROFILES", "-----------------"]
        if profs:
            for row in profs:
                lines.append(
                    f" {row['PROFILE']:<8} REPLAY={row['REPLAY']:<3} APPLCHK={row['APPLCHK']:<7} LABLEAK={row['LABLEAK']:<3} VALIDSECS={row['VALIDSECS']:<3} KEY={row['KEYMASKED']}"
                )
        else:
            lines.append(" NO PTKTDATA PROFILES FOUND")
        lines.extend(["", "ISSUED PASSTICKETS", "------------------"])
        if issued:
            for row in issued[:10]:
                lines.append(
                    f" {row['TICKET']} USER={row['USERID']} APPL={row['APPLID']} USED={row['USED']} USES={row['USES']} EXPIRES={row['EXPIRES']}"
                )
        else:
            lines.append(" NO PASSTICKETS ISSUED")
        lines.extend(["", "RECENT AUDIT", "------------"])
        if audit:
            for row in audit[:8]:
                lines.append(f" {row['TIME']} {row['SEVERITY']:<5} {row['DETAIL']}")
        else:
            lines.append(" NO AUDIT RECORDS")
        return "\n".join(lines)

    def _ptktuse(self, cmd: str) -> str:
        user_m = re.search(r"USER\(([^)]+)\)", cmd, re.I)
        appl_m = re.search(r"APPL\(([^)]+)\)", cmd, re.I)
        tick_m = re.search(r"TICKET\(([^)]+)\)", cmd, re.I)
        if not user_m or not tick_m:
            return "IKJ56700I SYNTAX: PTKTUSE USER(userid) APPL(applid) TICKET(ticket)"
        userid = user_m.group(1).strip().upper()
        applid = appl_m.group(1).strip().upper() if appl_m else "CICS"
        ticket = tick_m.group(1).strip().upper()
        result = get_passticket_service(self.state).validate(userid, applid, ticket, consumer="TSO")
        return str(result.get("message", "IRRPT299I PASSTICKET PROCESSED"))

    def _profile(self, cmd: str) -> str:
        u = cmd.upper()
        prefix = self.userid
        if "NOPREFIX" in u:
            return (
                "CHAR(0)  LINE(0)    PROMPT   INTERCOM   NOPAUSE NOMSGID NOMODE  NOWTP\n"
                "VER NOPREFIX\n"
                "DEFAULT LINE/CHARACTER DELETE CHARACTERS IN EFFECT FOR THIS TERMINAL"
            )
        m = re.search(r"PREFIX\(([^)]+)\)", cmd, re.I)
        if m:
            prefix = m.group(1).upper()
        return (
            "CHAR(0)  LINE(0)    PROMPT   INTERCOM   NOPAUSE NOMSGID NOMODE  NOWTP\n"
            f"VER PREFIX({prefix})\n"
            "DEFAULT LINE/CHARACTER DELETE CHARACTERS IN EFFECT FOR THIS TERMINAL"
        )

    def _listds(self, cmd: str) -> str:
        parts = cmd.split()
        if len(parts) < 2:
            return "IKJ56700I MISSING DATA SET NAME"
        full = self.qualify_dataset_name(parts[1])
        upper = cmd.upper()
        try:
            if self.state.datasets.security is not None:
                self.state.datasets.security.authorize(self.userid, full, "READ")
        except PermissionError as exc:
            return str(exc)
        rows = self.state.datasets.listcat(self.userid, prefix=full)
        match = next((r for r in rows if r.name == full), None)
        if "MEMBERS" in upper:
            try:
                members = self.state.datasets.members(self.userid, full)
                return "\n".join([f"{full} MEMBERS", "--MEMBER--"] + [m[:8].upper() for m in members])
            except Exception:
                return f"IKJ56228I DATA SET {full} NOT FOUND"
        if not match:
            return f"IKJ56228I DATA SET {full} NOT FOUND"
        meta = self.state.datasets.meta(self.userid, full)
        base = [
            f"{match.name}",
            " --RECFM-LRECL-BLKSIZE-DSORG-CREATED---EXPIRES---SECURITY--DDNAME---DISP",
            f"   {match.recfm:<5} {match.lrecl:<5} {match.blksize:<7} {match.org:<5} {meta.get('CREATED','11/17/27')[:10]:<10} * *     RACF      SYS00014 KEEP",
            " --VOLUMES--",
            f"   {match.volume}",
        ]
        if "STATUS" in upper or "HISTORY" in upper:
            try:
                member_count = len(self.state.datasets.members(self.userid, full)) if match.org == "PO" else 0
            except Exception:
                member_count = 0
            base += [
                "", "STATUS/HISTORY:",
                f"  CATALOGED . . . : {str(meta.get('CATALOGED', True)).upper()}",
                f"  OWNER . . . . . : {meta.get('OWNER', self.userid)}",
                f"  CREATED . . . . : {meta.get('CREATED','')}",
                f"  REFERENCED . . : {meta.get('REFERENCED','')}",
                f"  CHANGED . . . . : {meta.get('CHANGED','')}",
                f"  LAST USER . . . : {meta.get('LASTUSER','')}",
                f"  PRIMARY/SECOND  : {meta.get('PRIMARY','1')}/{meta.get('SECONDARY','1')} {meta.get('SPACE_UNITS','TRKS')}",
                f"  DIRECTORY BLKS  : {meta.get('DIRBLKS','0')}",
                f"  MEMBER COUNT . : {member_count}",
            ]
        return "\n".join(base)

    def _oget(self, cmd: str) -> str:
        if not self.has_omvs_segment():
            return "FSUM6003 user does not have an OMVS segment"
        ops = self._parse_uss_transfer(cmd, "OGET")
        if not ops or len(ops) != 2:
            return "OGET SYNTAX: OGET 'pathname' dataset.name"
        pathname, dsname = ops
        env = self._omvs_env()
        try:
            text = env.read_text(self._tso_path(pathname))
        except Exception:
            return f"OGET FAILED: {pathname} NOT FOUND"
        full_dsn = self.qualify_dataset_name(dsname)
        self.state.datasets.write(self.userid, full_dsn, text)
        return f"{pathname} COPIED TO {full_dsn}"

    def _oput(self, cmd: str) -> str:
        if not self.has_omvs_segment():
            return "FSUM6003 user does not have an OMVS segment"
        ops = self._parse_uss_transfer(cmd, "OPUT")
        if not ops or len(ops) != 2:
            return "OPUT SYNTAX: OPUT dataset.name 'pathname'"
        dsname, pathname = ops
        env = self._omvs_env()
        full_dsn = self.qualify_dataset_name(dsname)
        try:
            text = self.state.datasets.read(self.userid, full_dsn)
        except Exception:
            return f"OPUT FAILED: {full_dsn} NOT FOUND"
        env.write_text(self._tso_path(pathname), text)
        return f"{full_dsn} COPIED TO {pathname}"

    def _rename(self, cmd: str) -> str:
        parts = cmd.split()
        if len(parts) < 3:
            return "IKJ56700I RENAME SYNTAX: RENAME old new"
        old, new = self.qualify_dataset_name(parts[1]), self.qualify_dataset_name(parts[2])
        try:
            if self.state.datasets.security is not None:
                self.state.datasets.security.authorize(self.userid, old, "ALTER")
                self.state.datasets.security.authorize(self.userid, new, "ALLOCATE")
        except PermissionError as exc:
            return str(exc)
        oldp = self.state.datasets.ds_path(self.userid, old)
        newp = self.state.datasets.ds_path(self.userid, new)
        if not oldp.exists():
            return f"IDC3012I ENTRY {old.upper()} NOT FOUND"
        newp.parent.mkdir(parents=True, exist_ok=True)
        oldp.rename(newp)
        oldmeta = self.state.datasets.meta_path(oldp)
        if oldmeta.exists():
            oldmeta.rename(self.state.datasets.meta_path(newp))
        return f"ENTRY {old} RENAMED TO {new}"

    def _free(self, cmd: str) -> str:
        return "IKJ56893I DATA SET FREED"

    def _netstat(self, cmd: str) -> str:
        parts = cmd.split(maxsplit=1)
        opt = parts[1].strip().upper() if len(parts) > 1 else "ALL"
        return self.state.network.format(opt, self.state.sessions.sessions)

    def _rvary(self) -> str:
        return (
            "ICH15013I RACF DATABASE STATUS:\n"
            "ACTIVE USE  NUM VOLUME   DATASET\n"
            "------ ---  --- ------   -------\n"
            " YES   PRIM   1 SBSYS1   SYS1.RACFDS\n"
            " YES   BACK   1 SBRES1   SYS1.RACFDS.BACKUP\n"
            "ICH15020I RVARY COMMAND HAS FINISHED PROCESSING."
        )


    def _secevents(self) -> str:
        events = [e for e in self.state.audit.events if e.component == "SMF80"][-20:]
        if not events:
            return "NO SMF80 EVENTS RECORDED"
        lines = [
            "TIME     USERID   GROUP    EVENT    RESULT   SERVICE   RESOURCE                 DETAIL",
            "-------- -------- -------- -------- -------- -------- ------------------------ ------------------------------",
        ]
        for e in events:
            row = self.state.audit.smf80_row(e, system=getattr(self.state.network, "hostname", "MVSC").upper())
            lines.append(
                f"{row['TIME']:<8} {row['USERID']:<8} {row['GROUP']:<8} {row['EVENT']:<8} {row['RESULT']:<8} {row['SERVICE'][:8]:<8} {row['RESOURCE'][:24]:<24} {row['DETAIL'][:30]}"
            )
        return "\n".join(lines)

    def _healthcheck(self, cmd: str) -> str:
        text = cmd.split(None, 1)[1] if len(cmd.split(None, 1)) > 1 else "REFRESH"
        out = get_healthchecker(self.state).command(text)
        self.state.refresh_health_checks()
        return out

    def _indfile(self, cmd: str) -> str:
        mode = (self.state.config.indfile_mode or "off").lower()
        if mode == "off":
            return "IND$FILE TRANSFER IS DISABLED IN THIS GIBSON CONFIGURATION"
        action, meta = get_transfer_manager(self.state).parse_indfile(self.userid, cmd)
        dsn = meta.get("dataset", "")
        local = meta.get("local", "DESKTOP.FILE")
        if action == "GET":
            try:
                filename, data = get_transfer_manager(self.state).indfile_get(self.userid, dsn, note="TSO", options=meta)
            except Exception as exc:
                return f"IND$FILE GET FAILED: {exc}"
            try:
                target = get_transfer_manager(self.state).write_local(local or filename, data)
            except Exception as exc:
                return f"IND$FILE GET FAILED: {exc}"
            crn = "CRLF" if str(meta.get('CR','')).upper() in ("ADD","CRLF") else ("NOCRLF" if str(meta.get('CR','')).upper()=="REMOVE" else "AS-IS")
            return (f"IND$FILE001I TRANSFER STARTED DIRECTION(GET) MODE({meta.get('MODE','ASCII').upper()}) {crn}\n"
                    f"IND$FILE002I DATASET({dsn}) -> LOCAL({local})\n"
                    f"TRANS03 {len(data)} BYTES TRANSFERRED FROM HOST\n"
                    f"IND$FILE003I BYTES TRANSFERRED {len(data)}\n"
                    f"IND$FILE004I TRANSFER COMPLETE\n STAGED={target}")
        try:
            data = get_transfer_manager(self.state).read_local(local)
            note = f"TSO LOCAL={local}"
        except FileNotFoundError:
            data = f"SIMULATED IND$FILE PUT FROM {local} BY {self.userid}\n".encode("utf-8")
            note = f"TSO LOCAL={local} SAMPLE"
        except Exception as exc:
            return f"IND$FILE PUT FAILED: {exc}"
        try:
            info = get_transfer_manager(self.state).indfile_put(self.userid, dsn, data, note=note, options=meta)
        except Exception as exc:
            return f"IND$FILE PUT FAILED: {exc}"
        return (f"IND$FILE001I TRANSFER STARTED DIRECTION(PUT) MODE({meta.get('MODE','ASCII').upper()})\n"
                f"IND$FILE002I LOCAL({local}) -> DATASET({info['target']})\n"
                f"TRANS03 {info['bytes']} BYTES TRANSFERRED TO HOST\n"
                f"IND$FILE003I RECORDS WRITTEN {info.get('records','-')} BYTES {info['bytes']}\n"
                f"IND$FILE004I TRANSFER COMPLETE")

    def _transmit(self, cmd: str) -> str:
        if not self.state.config.transmit_receive:
            return "TRANSMIT/RECEIVE SUPPORT IS DISABLED"
        m_user = re.search(r"(?:TRANSMIT|XMIT)\s+([A-Z0-9#$@.]+)", cmd, re.I)
        m_da = re.search(r"(?:DA|DATASET)\(([^)]+)\)", cmd, re.I)
        m_out = re.search(r"OUTDSN\(([^)]+)\)", cmd, re.I)
        m_title = re.search(r"TITLE\(([^)]+)\)", cmd, re.I)
        if not (m_user and m_da):
            return "IKJ56700I SYNTAX: TRANSMIT userid DA(dataset) <OUTDSN(package)> <TITLE(text)>"
        info = get_transfer_manager(self.state).transmit(self.userid, m_user.group(1), m_da.group(1), outdsn=m_out.group(1) if m_out else "", title=m_title.group(1) if m_title else "")
        return f"INMR001I TRANSMIT CREATED\n SOURCE={info['source']}\n OUTDSN={info['package']}\n RECIPIENT={info['recipient']}"

    def _receive(self, cmd: str) -> str:
        if not self.state.config.transmit_receive:
            return "TRANSMIT/RECEIVE SUPPORT IS DISABLED"
        m_in = re.search(r"INDSN\(([^)]+)\)", cmd, re.I)
        m_da = re.search(r"(?:DA|DATASET)\(([^)]+)\)", cmd, re.I)
        if not m_in:
            return "IKJ56700I SYNTAX: RECEIVE INDSN(dataset) <DA(target)>"
        info = get_transfer_manager(self.state).receive(self.userid, m_in.group(1), target=m_da.group(1) if m_da else "")
        return f"INMR901I RECEIVE COMPLETE\n INDSN={info['indsn']}\n RESTORED={info['restored']}"

    def _setprog_general(self, cmd: str) -> str:
        u = cmd.upper()
        if u.startswith("SETPROG APF"):
            result = self._setprog_apf(cmd)
        elif u.startswith("SETPROG LNKLST"):
            m = re.search(r"DSNAME=\(?\s*'?([^,'\s\)]+)'?\s*\)?", cmd, re.I)
            # LNKLST data sets are fully qualified system data sets - never
            # userid-prefixed (same rule as APF).
            dsn = m.group(1).strip().strip("'\"").upper() if m else "UNKNOWN.LINKLIB"
            if dsn not in self.state.apf_libraries:
                self.state.apf_libraries.append(dsn)
                self._persist_apf()
            result = f"CSV470I LNKLST SET UPDATED FOR {dsn}"
        else:
            m = re.search(r"DSNAME=\(?\s*'?([^,'\s\)]+)'?\s*\)?", cmd, re.I)
            dsn = m.group(1).strip().strip("'\"").upper() if m else "UNKNOWN.LPA.LIB"
            result = f"CSV480I LPA STATE UPDATED FOR {dsn}"
        self.state.refresh_health_checks()
        return result

    def _setprog_apf(self, cmd: str) -> str:
        u = cmd.upper()
        m = re.search(r"DSNAME=\(?\s*'?([^,'\s\)]+)'?\s*\)?", cmd, re.I)
        # APF library names are ALWAYS fully qualified (system data sets); they
        # are never prefixed with the TSO userid.  Store exactly as typed.
        dsn = m.group(1).strip().strip("'\"").upper() if m else "UNKNOWN.APF.LIB"
        if ",DELETE" in u or "APF,DEL" in u:
            try:
                self.state.apf_libraries.remove(dsn)
            except ValueError:
                pass
            self._persist_apf()
            self.state.notify_console(f"CSV492I APF LIBRARY {dsn} REMOVED FROM DYNAMIC APF LIST", severity="INFO")
            return f"CSV410I DATA SET {dsn} REMOVED FROM APF LIST"
        if dsn not in self.state.apf_libraries:
            self.state.apf_libraries.append(dsn)
        self._persist_apf()
        self.state.datasets.allocate(self.userid, dsn, org="PO")
        volm = re.search(r"VOLUME=([^,\s]+)", cmd, re.I)
        vol = volm.group(1).upper() if volm else "SMS"
        message = f"CSV493I APF LIBRARY {dsn} CREATED AND ADDED TO DYNAMIC APF LIST ON {vol}"
        self.state.notify_console(message, severity="ALERT")
        self.state.raise_dashboard_alert(message, severity="ALERT", event_type="APF_LIBRARY")
        return f"CSV410I DATA SET {dsn} ON VOLUME {vol} ADDED TO APF LIST"

    def _persist_apf(self) -> None:
        """Persist the dynamic APF list so additions survive a restart and are
        shared with a separately-run console process (the apf vulnerability lab
        relies on the addition being visible everywhere)."""
        fn = getattr(self.state, "persist_apf_libraries", None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass

    def _display(self, cmd: str) -> str:
        key = cmd.upper().replace(" ", " ").strip()
        if key.startswith("DISPLAY TCPIP,,NETSTAT"):
            opt = "ALL"
            parts = key.split(",")
            if len(parts) >= 3 and parts[-1].strip():
                opt = parts[-1].strip()
            return self.state.network.format(opt, self.state.sessions.sessions)
        template_map = {
            "DISPLAY TIME": "DT.TXT",
            "DISPLAY IPLINFO": "DISPLAY IPLINFO",
            "DISPLAY LOGGER": "DISPLAY LOGGER",
            "DISPLAY SMS": "DISPLAY SMS",
            "DISPLAY TCPIP": "DISPLAY TCPIP",
            "DISPLAY A,L": "DAL.TXT",
            "DISPLAY PROG,APF": "DPROGAPF",
        }
        name = template_map.get(key)
        if name:
            return self.state.templates.render(name, self.userid, self._attrib()) or self._synthetic_display(key)
        return self._synthetic_display(key)

    def _synthetic_display(self, key: str) -> str:
        now = datetime.now().strftime("%Y.%j %H:%M:%S")
        if key == "DISPLAY TIME":
            return f"IEE136I LOCAL: TIME={now} GIBSON LPAR=GIB1"
        if key in ("DISPLAY PROG,APF", "DISPLAY APF"):
            lines = ["CSV450I APF LIST DISPLAY", "DSNAME                              VOLSER   STATUS"]
            for lib in self.state.apf_libraries:
                vol = "WORK01" if "VULN" in lib or lib.startswith("RUARIV") else "MVSRES"
                lines.append(f"{lib:<35} {vol:<8} APF")
            return "\n".join(lines)
        if key == "DISPLAY IPLINFO":
            return "IEE254I IPLINFO DISPLAY\n SYSTEM IPLED AT 2026.107 08:00:00\n RELEASE z/OS 02.05.00 GIBSON TRAINING LPAR"
        if key == "DISPLAY LOGGER":
            return "IXG601I SYSTEM LOGGER STATUS\n LOGGER ACTIVE, LOG STREAMS AVAILABLE"
        if key == "DISPLAY SMS":
            return "IGD002I SMS STATUS DISPLAY\n SMS IS ACTIVE. ACS ROUTINES ARE AVAILABLE."
        if key in ("DISPLAY SMF,O", "DISPLAY SMF"):
            return "IEE974I SMF PARAMETERS\n RECORDING DATA SETS ACTIVE\n TYPE 80 RACF RECORDING ACTIVE"
        if key == "DISPLAY A,L":
            return "IEE114I 00.00.00 2026.107 ACTIVITY\n JOBS     M/S    TS USERS    SYSAS\n FTPD1    STC    IBMUSER     OMVS\n CICS     STC    RUARIV      DB2A"
        return f"IEE600I REPLY TO {key} - SIMULATED DISPLAY COMPLETE"

    def _default_setropts(self) -> str:
        return (
            "ICH31005I SETROPTS LIST\n"
            " RACLIST CLASSES = USER DATASET FACILITY\n"
            " GENERIC COMMAND PROCESSING IS IN EFFECT\n"
            " PASSWORD PROCESSING OPTIONS: HISTORY=10 INTERVAL=30"
        )

    def _submit(self, cmd: str) -> str:
        parts = cmd.split(None, 1)
        if len(parts) < 2:
            return "IKJ56700I MISSING DATA SET NAME"
        rest = parts[1].strip()
        userm = re.search(r"USER\(([^)]+)\)", rest, re.I)
        cmd_exec_user = None
        if userm:
            cmd_exec_user = userm.group(1).strip().upper()
            rest = re.sub(r"USER\([^)]+\)", "", rest, flags=re.I).strip()
        spec = rest.strip().strip("'")
        try:
            jcl = self.state.datasets.read(self.userid, spec)
        except Exception:
            fallback_user = cmd_exec_user or self.userid
            jcl = (
                f"//{fallback_user[:7]}J JOB (ACCT),'SURROGAT TEST',CLASS=A,MSGCLASS=A,USER={fallback_user}\n"
                "//STEP1 EXEC PGM=IEFBR14\n"
                "//SYSPRINT DD SYSOUT=*\n"
                "//SYSUDUMP DD SYSOUT=*\n"
            )
        exec_user = cmd_exec_user or self.userid
        m = re.search(r"^//[^\s]+\s+JOB\s+.*?\bUSER\s*=\s*([A-Z0-9#$@]+)", jcl, re.I | re.M)
        if m:
            exec_user = m.group(1).upper()
        if exec_user != self.userid and not self.state.dynamic_racf.has_access("SURROGAT", f"{exec_user}.SUBMIT", self.userid, "READ", self.state.racf):
            self.state.record_security_event(self.userid, "SURROGAT SUBMIT", f"TARGET={exec_user}", result="FAILURE", service="JES")
            return f"ICH408I USER({self.userid}) NOT AUTHORIZED TO SUBMIT AS {exec_user}"
        job = self.state.jes.submit(
            jcl,
            exec_user,
            runner=self.run,
            sql_runner=lambda sql: Db2Simulator(self.state).format_spufi(sql, self.userid),
            cobol_runner=self._compile_cobol,
            submitter=self.userid,
        )
        self.state.record_security_event(self.userid, "JOB SUBMIT", f"JOBID={job.jobid} EXECUSER={exec_user}", service="JES")
        return f"IKJ56250I JOB {job.jobname}({job.jobid}) SUBMITTED"

    def _compile_cobol(self, source: str):
        result = CobolSimulator().compile(source)
        return result.rc, result.listing, result.display_lines

    def _simulated_rexx_tool(self, cmd: str) -> str | None:
        u = cmd.upper()
        if "SEARCHRX" in u:
            return "\n".join([
                " *** Datasets in WARNING mode",
                self.state.dynamic_racf.search("SEARCH ALL WARNING NOMASK", self.state.racf),
                "",
                " *** READ or greater datasets",
                " SYS1.PARMLIB",
                " SYS1.RACFDS",
                "",
                " *** Unix Privileged resources",
                " ICH31005I NO ENTRIES MEET SEARCH CRITERIA",
                "",
                " *** BPX Access",
                self.state.dynamic_racf.search("SEARCH CLASS(FACILITY) FILTER(BPX.**)", self.state.racf),
                "",
                " *** Surrogate Access",
                self.state.dynamic_racf.search("SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)", self.state.racf),
            ])
        if "SYS0WN" in u:
            return "\n".join([
                "Script to check SYSPROC/SYSEXEC permissions",
                "SYSPROC:",
                "+-----------------------------------------------------------------------+",
                "| Sysproc DSN         | Volume | Created Date | Reference Date | Access |",
                "|---------------------|--------|--------------|----------------|--------|",
                "| SYSTSO.BASE.CLIST   | TK5RES |   18/08/25   |    13/11/25    | NONE   |",
                "| SYS1.SISPCLIB       | TK5SYS |   18/08/25   |    13/11/25    | NONE   |",
                "| SYS1.SISPEXEC       | TK5RES |   18/08/25   |    13/11/25    | NONE   |",
                "+-----------------------------------------------------------------------+",
                "SYSEXEC:",
                "+-----------------------------------------------------------------------+",
                "| Sysexec DSN         | Volume | Created Date | Reference Date | Access |",
                "|---------------------|--------|--------------|----------------|--------|",
                "| SYS1.VULNAPF.LIB    | TK5RES |   16/11/25   |    16/11/25    | ALTER  |",
                "| SYS1.SISPEXEC       | TK5RES |   18/08/25   |    13/11/25    | NONE   |",
                "+-----------------------------------------------------------------------+",
            ])
        if "ENUM" in u:
            arg = "ALL"
            m = re.search(r"'\s*(ALL|SEC|APF|SVC|WHO|PATH|CAT|VERS|JOB|TSTA)\s*'", cmd, re.I)
            if m:
                arg = m.group(1).upper()
            sections = []
            if arg in ("ALL", "SEC"):
                sec_rows = []
                for ds in ("SYS1.RACFDS", "SYS1.RACFDS.BACKUP"):
                    prof = self.state.dynamic_racf._find_profile("DATASET", ds)
                    warn = "YES" if prof and prof.warning else "NO"
                    access = self.state.dynamic_racf.effective_access("DATASET", ds, self.userid, self.state.racf) if prof else "NONE"
                    uacc = prof.uacc if prof else "NONE"
                    sec_rows.append(f"{uacc:<4} | {warn:<4} | {access:<6} | {ds}")
                sections.extend(["$$$$$$$$$$$$$", "$$ Security Settings", "$$$$$$$$$$$$$", "External Security Manager:", "Product: RACF", "Version: FMID HRF7791", "Datasets:", "UACC | WARN | ACCESS | DATASET", "-----|------|--------|--------------------------------------------"] + sec_rows + ["SETROPTS Info:", "SPECIAL users are audited", "OPERATIONS users are NOT audited", "Dynamic access checks active", ""])
            if arg in ("ALL", "APF"):
                apf_rows = []
                for lib in self.state.apf_libraries:
                    access = self.state.dynamic_racf.effective_access("DATASET", lib, self.userid, self.state.racf)
                    apf_rows.append(f"{lib:<35} {access}")
                sections.extend(["$$$$$$$$$$$$$", "$$ APF Libraries", "$$$$$$$$$$$$$"] + apf_rows + [""])
            if arg in ("ALL", "SVC"):
                sections.extend(["$$$$$$$$$$$$$", "$$ SVC Table", "$$$$$$$$$$$$$", "SVC  000 IGC0001I IBM SUPERVISOR", "SVC  233 ELV.SVC TRAINING ENTRY (SIMULATED)", ""])
            if arg in ("ALL", "WHO"):
                sections.extend(["$$$$$$$$$$$$$", "$$ Logged-on Users", "$$$$$$$$$$$$$"] + [f"{s.userid:<8} {s.addr:<15} CONNECTED" for s in self.state.sessions.sessions.values()] + [""])
            if arg in ("ALL", "PATH"):
                sections.extend(["$$$$$$$$$$$$$", "$$ TSO Execution Path", "$$$$$$$$$$$$$", "SYSPROC: SYSTSO.BASE.CLIST SYS1.SISPCLIB", "SYSEXEC: SYS1.VULNAPF.LIB SYS1.SISPEXEC", ""])
            return "\n".join(sections).strip() or "ENUM option processed by Gibson."
        if "ELV.SVC" in u:
            if "LIST" in u:
                return "ELV.SVC SIMULATED SVC LIST\nSVC 233 AVAILABLE FOR LAB DEMONSTRATION\nNO REAL STORAGE IS MODIFIED."
            return "ELV.SVC SIMULATED PRIVILEGE PROOF COMPLETE\nSESSION STATE ONLY - NO REAL SYSTEM MODIFIED."
        if "ELV.SELF" in u:
            if "LIST" in u:
                return "ELV.SELF ADDRESS SPACE LIST\nIBMUSER  TSU00001 ACTIVE\nCICS     STC00042 ACTIVE\nDB2A     STC00051 ACTIVE"
            return "ELV.SELF SIMULATED ACEE TARGET CHANGE COMPLETE\nSESSION STATE ONLY - NO REAL SYSTEM MODIFIED."
        if "ELV.APF" in u:
            writable_apf = []
            for lib in sorted(self.state.apf_libraries):
                access = self.state.dynamic_racf.effective_access("DATASET", lib, self.userid, self.state.racf)
                if access not in {"UPDATE", "CONTROL", "ALTER"} and lib.startswith(self.userid + "."):
                    # Training APF lab compatibility: user-owned APF libraries are
                    # treated as updateable lab candidates unless a stronger
                    # explicit RACF rule denies them.
                    access = "UPDATE"
                if access in {"UPDATE", "CONTROL", "ALTER"}:
                    writable_apf.append((lib, access))
            writable_apf.sort(key=lambda item: (0 if item[0].startswith(self.userid + ".") else 1, item[0]))
            if "LIST" in u or "CHECK" in u:
                if not writable_apf:
                    return "ELV.APF TRAINING CHECK\nNO UPDATEABLE APF LIBRARIES FOUND FOR THIS USER."
                return "ELV.APF TRAINING CHECK\nCANDIDATE APF LIBRARIES:\n" + "\n".join(f"{lib} ({access})" for lib, access in writable_apf)
            if not writable_apf:
                return "ELV.APF TRAINING SIMULATION FAILED\nNO UPDATEABLE APF LIBRARY IS AVAILABLE TO THIS USER."
            if not self.state.racf.get(self.userid):
                return "ELV.APF TRAINING SIMULATION FAILED\nUSER PROFILE NOT FOUND."
            self.state.racf.altuser(self.userid, special=True, omvs=True)
            chosen, access = writable_apf[0]
            # Emit an SMF80 security event so the HMS auto-detect (elv_apf / T1068)
            # fires - this makes the lab a complete red-and-blue exercise.
            try:
                self.state.record_security_event(
                    self.userid, "ALTUSER SPECIAL",
                    f"ELV.APF APF-ESCALATION VIA {chosen} ACCESS={access} - SPECIAL GRANTED",
                    service="RACF", result="SUCCESS")
            except Exception:
                pass
            self.state.notify_console(f"ICH70001I TRAINING APF ESCALATION COMPLETE FOR {self.userid} VIA {chosen} ACCESS={access} - SPECIAL ENABLED", severity="ALERT")
            return "\n".join([
                "ELV.APF TRAINING SIMULATION",
                f"APF CANDIDATE FOUND: {chosen}",
                f"DATASET ACCESS AT TIME OF LOAD: {access}",
                "ACEE UPDATE ROUTINE: SIMULATED",
                f"ICH01006I USERID {self.userid} ALTERED",
                f"SPECIAL ATTRIBUTE NOW ACTIVE FOR {self.userid}",
                "BPX.SUPERUSER PATH ENABLED IN TRAINING PROFILE",
                "NO REAL SYSTEM STORAGE OR AUTHORIZED CODE WAS MODIFIED.",
            ])
        return None

    def _run_rexx(self, cmd: str) -> str:
        sim = self._simulated_rexx_tool(cmd)
        if sim is not None:
            return sim
        target = cmd.strip()
        args = ""
        token_re = r"'[^']*'|\"[^\"]*\"|\S+"
        if target.startswith("%"):
            rest = target[1:].strip()
            parts = re.findall(token_re, rest)
            if parts:
                target = parts[0]
                args = " ".join(parts[1:]).strip().strip("'")
            else:
                target = rest
        else:
            parts = re.findall(token_re, target)
            if len(parts) >= 2:
                target = parts[1]
                args = " ".join(parts[2:]).strip().strip("'")
            else:
                target = parts[0] if parts else ""
        target = target.strip().strip("'").strip('"')
        try:
            source = self.state.datasets.read(self.userid, target)
        except Exception:
            source = None
            # SYSEXEC-style fallback: search the MVP-installed REXX library so a
            # bare name or %NAME resolves after  RX MVP INSTALL  has run.
            if "(" not in target:
                try:
                    source = self.state.datasets.read(
                        self.userid, f"{self.userid.upper()}.MVP.EXEC({target.upper()})")
                except Exception:
                    source = None
            if source is None:
                source = f"SAY 'REXX EXEC {target} NOT FOUND - SIMULATED'"
        u_source = source.upper()
        if target.upper().endswith("USHELL.REXX") or "MATT_DAEMON" in u_source or "SOCKET('BIND'" in u_source:
            requested_port = 0
            for tok in args.replace('L', ' ').replace('R', ' ').split():
                if tok.isdigit():
                    requested_port = int(tok)
                    break
            _srv, port = start_training_shell(
                self.state,
                self.userid,
                lambda uid: TsoCommandProcessor(self.state, uid).run,
                port=requested_port,
                ttl=300,
                shell_id=f"REXX-{self.userid}-{target.upper()}",
            )
            self.state.notify_console(
                f"IRR9201I TRAINING REXX SHELL LISTENER ACTIVE FOR {self.userid} ON PORT {port}",
                severity="ALERT",
            )
            return (
                f"IRX0000I REXX LISTENER SIMULATION STARTED ON PORT {port}\n"
                f"CONNECT USING NC {self.state.config.host or '127.0.0.1'} {port}\n"
                "ASCII TRAINING SHELL ACTIVE - EBCDIC TRANSLATION NOT REQUIRED."
            )
        return RexxInterpreter(
            tso_runner=self.run,
            userid=self.userid,
            dataset_read=lambda dsn: self.state.datasets.read(self.userid, self.qualify_dataset_name(dsn)),
            dataset_write=lambda dsn, data: self.state.datasets.write(self.userid, self.qualify_dataset_name(dsn), data),
            ispexec=lambda payload: f"ISPEXEC {payload}",
        ).run(source, args=args)
