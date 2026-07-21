from __future__ import annotations

from typing import Any, Dict, List
import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from gibson.core.state import GibsonState
from gibson.render import colors
from gibson.render.input import SocketInputDriver
from gibson.apps.banking_lab import get_banking_lab
from gibson.apps.gmvb_service import get_gmvb_service
from gibson.apps.cbsa.store import get_cbsa_store
from gibson.apps.cbsa.db2_bridge import call_vuln_account_search
from gibson.core.security.racf_authorization import check_access, permit
from gibson.core.smf import record_smf


SYSTEM_INFO = {
    "GROUP": "DB2G1",
    "MEMBER": "DB2A",
    "SUBSYSTEM": "DB2A",
    "VERSION": "12.1",
    "ID": "GOSDB2",
    "LOCATION": "GIBSONDB2",
}


@dataclass
class Db2Job:
    jobid: str
    name: str
    status: str = "ENDED OK"


class Db2Simulator:
    """Db2 for z/OS style simulator shared by TSO, REST, FTP and DB2 services."""

    def __init__(self, state: GibsonState):
        self.state = state
        if not hasattr(state, "db2_jobs"):
            setattr(state, "db2_jobs", {})

    @property
    def active_jobs(self) -> Dict[str, Db2Job]:
        return getattr(self.state, "db2_jobs")

    def catalog(self) -> dict[str, list[dict[str, str]]]:
        users = [
            {"USERID": u.userid, "AUTHORITY": "SYSADM" if u.special else "NONE", "OMVS": "Y" if u.has_omvs else "N"}
            for u in self.state.racf.users.values()
        ]
        tables = [
            {"NAME": "SYSTABLES", "CREATOR": "SYSIBM", "TYPE": "T", "DBNAME": "DSNDB06", "TSNAME": "SYSTSTAB"},
            {"NAME": "SYSCOLUMNS", "CREATOR": "SYSIBM", "TYPE": "T", "DBNAME": "DSNDB06", "TSNAME": "SYSCOL"},
            {"NAME": "SYSUSERAUTH", "CREATOR": "SYSIBM", "TYPE": "V", "DBNAME": "DSNDB06", "TSNAME": "SYSUSER"},
            {"NAME": "SYSDBAUTH", "CREATOR": "SYSIBM", "TYPE": "T", "DBNAME": "DSNDB06", "TSNAME": "SYSDBAUT"},
            {"NAME": "SYSPLAN", "CREATOR": "SYSIBM", "TYPE": "T", "DBNAME": "DSNDB06", "TSNAME": "SYSPLAN"},
            {"NAME": "EMPLOYEES", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "EMPLOYE"},
            {"NAME": "ACCOUNTS", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "ACCOUNTS"},
        ]
        columns = [
            {"TBNAME": "SYSTABLES", "TBCREATOR": "SYSIBM", "NAME": "NAME", "COLTYPE": "VARCHAR", "LENGTH": "128"},
            {"TBNAME": "SYSTABLES", "TBCREATOR": "SYSIBM", "NAME": "CREATOR", "COLTYPE": "VARCHAR", "LENGTH": "128"},
            {"TBNAME": "SYSUSERAUTH", "TBCREATOR": "SYSIBM", "NAME": "GRANTEE", "COLTYPE": "VARCHAR", "LENGTH": "128"},
            {"TBNAME": "SYSUSERAUTH", "TBCREATOR": "SYSIBM", "NAME": "SYSADMAUTH", "COLTYPE": "CHAR", "LENGTH": "1"},
            {"TBNAME": "EMPLOYEES", "TBCREATOR": "GIBSON", "NAME": "EMPNO", "COLTYPE": "CHAR", "LENGTH": "6"},
            {"TBNAME": "EMPLOYEES", "TBCREATOR": "GIBSON", "NAME": "FIRSTNME", "COLTYPE": "VARCHAR", "LENGTH": "12"},
        ]
        bank = get_banking_lab(self.state)
        bank_tables, bank_columns = bank.table_metadata()
        tables.extend(bank_tables)
        columns.extend(bank_columns)
        data = {
            "SYSIBM.SYSTABLES": tables,
            "SYSIBM.SYSCOLUMNS": columns,
            "SYSIBM.SYSUSERAUTH": users,
            "SYSIBM.SYSTABAUTH": [
                {"GRANTEE": "IBMUSER", "CREATOR": "SYSIBM", "NAME": "SYSTABLES", "SELECTAUTH": "Y"},
                {"GRANTEE": "PUBLIC", "CREATOR": "SYSIBM", "NAME": "SYSCOLUMNS", "SELECTAUTH": "Y"},
            ],
            "SYSIBM.SYSUSERS": users,
            "SYSIBM.SYSDBAUTH": [
                {"GRANTEE": "IBMUSER", "DBNAME": "GIBDB", "DBADMAUTH": "Y", "CREATETABAUTH": "Y"},
                {"GRANTEE": "PUBLIC", "DBNAME": "GIBDB", "DBADMAUTH": "N", "CREATETABAUTH": "N"},
            ],
            "SYSIBM.SYSPLAN": [
                {"NAME": "DSNTEP2", "CREATOR": "SYSIBM", "VALID": "Y"},
                {"NAME": "SPUFI", "CREATOR": "SYSIBM", "VALID": "Y"},
            ],
            "GIBSON.EMPLOYEES": [
                {"EMPNO": "000010", "FIRSTNME": "CHRISTINE", "LASTNAME": "HAAS", "WORKDEPT": "A00"},
                {"EMPNO": "000020", "FIRSTNME": "MICHAEL", "LASTNAME": "THOMPSON", "WORKDEPT": "B01"},
            ],
        }
        data.update(bank.catalog())
        # GMVB integrated banking service tables are added last so every
        # subsystem (TSO DB2, ISPF SPUFI, React/API and CICS) sees one
        # shared table registry.  This is additive and preserves the
        # historical banking_lab catalog keys.
        svc = get_gmvb_service(self.state)
        data.update(svc.catalog())
        cbsa = get_cbsa_store(self.state)
        data.update(cbsa.tables())
        g_tables, g_cols = svc.table_metadata()
        c_tables, c_cols = cbsa.metadata()
        g_tables = list(g_tables) + list(c_tables)
        g_cols = list(g_cols) + list(c_cols)
        existing = {(r.get("CREATOR"), r.get("NAME")) for r in data.get("SYSIBM.SYSTABLES", [])}
        for row in g_tables:
            key = (row.get("CREATOR"), row.get("NAME"))
            if key not in existing:
                data.setdefault("SYSIBM.SYSTABLES", []).append(row)
                existing.add(key)
        existing_cols = {(r.get("TBCREATOR"), r.get("TBNAME"), r.get("NAME")) for r in data.get("SYSIBM.SYSCOLUMNS", [])}
        for row in g_cols:
            key = (row.get("TBCREATOR"), row.get("TBNAME"), row.get("NAME"))
            if key not in existing_cols:
                data.setdefault("SYSIBM.SYSCOLUMNS", []).append(row)
                existing_cols.add(key)
        return data

    def run_sql(self, sql: str, userid: str = "IBMUSER") -> List[Dict[str, str]]:
        q = " ".join(sql.strip().rstrip(";").upper().replace("\n", " ").split())
        if not q:
            raise ValueError("SQLCODE=-104, SQLSTATE=42601, EMPTY SQL STATEMENT")
        if q.startswith("SELECT CURRENT SQLID"):
            return [{"CURRENT SQLID": userid.upper()}]
        if q.startswith("SELECT CURRENT SERVER"):
            return [{"CURRENT SERVER": SYSTEM_INFO["LOCATION"]}]
        if q.startswith("DISPLAY"):
            return [{"MESSAGE": self.display_group()}]
        if q.startswith("GRANT "):
            m = re.search(r"GRANT\s+([A-Z, ]+)\s+ON\s+([A-Z0-9_.]+)\s+TO\s+([A-Z0-9#$@]+)", q)
            if not m:
                raise ValueError("SQLCODE=-104, SQLSTATE=42601, GRANT SYNTAX")
            access, table, grantee = m.group(1), m.group(2), m.group(3)
            permit(self.state, f"DB2A.{table}", "DSNR", grantee, "READ" if "SELECT" in access else "UPDATE")
            record_smf(self.state, "101", userid, "DB2 GRANT", f"TABLE={table} GRANTEE={grantee} ACCESS={access}")
            return [{"SQLCODE": "0", "MESSAGE": f"DSNT500I GRANT {access.strip()} ON {table} TO {grantee} COMPLETE"}]
        if q.startswith("REVOKE "):
            m = re.search(r"REVOKE\s+([A-Z, ]+)\s+ON\s+([A-Z0-9_.]+)\s+FROM\s+([A-Z0-9#$@]+)", q)
            if not m:
                raise ValueError("SQLCODE=-104, SQLSTATE=42601, REVOKE SYNTAX")
            access, table, grantee = m.group(1), m.group(2), m.group(3)
            from gibson.apps.racf_admin import get_racf_store
            st = get_racf_store(self.state)
            st.profiles.setdefault("DSNR", {}).setdefault(f"DB2A.{table}", {"UACC": "NONE", "PERMITS": {}})["PERMITS"].pop(grantee, None)
            record_smf(self.state, "101", userid, "DB2 REVOKE", f"TABLE={table} GRANTEE={grantee} ACCESS={access}")
            return [{"SQLCODE": "0", "MESSAGE": f"DSNT500I REVOKE {access.strip()} ON {table} FROM {grantee} COMPLETE"}]
        if q.startswith("INSERT "):
            rows = self._execute_insert(sql, userid)
            return [{"SQLCODE": "0", "ROWS": str(rows), "MESSAGE": f"DSNE615I NUMBER OF ROWS AFFECTED IS {rows}"}]
        if q.startswith("UPDATE "):
            rows = self._execute_update(sql, userid)
            return [{"SQLCODE": "0", "ROWS": str(rows), "MESSAGE": f"DSNE615I NUMBER OF ROWS AFFECTED IS {rows}"}]
        if q.startswith("DELETE "):
            return [{"SQLCODE": "0", "ROWS": "1", "MESSAGE": "DSNE615I NUMBER OF ROWS AFFECTED IS 1"}]
        if q.startswith("CALL CBSA.VULN_ACCOUNT_SEARCH"):
            m = re.search(r"\((.*)\)", sql, re.S)
            arg = (m.group(1) if m else "").strip().strip(";").strip().strip("'")
            res = call_vuln_account_search(self.state, arg.replace("''", "'"))
            return [{"RESULT": res.get("result", ""), "ROWS_RETURNED": str(res.get("rows_returned", 0)), "SIMULATED_SQL": res.get("simulated_sql", ""), "CORRELATION_ID": res.get("correlation_id", "")}]
        cat = self.catalog()
        # Known catalogs and training tables.
        for name, rows in cat.items():
            if f"FROM {name}" in q:
                if name in {"CBSA.VULN_ACCOUNT_LOOKUP", "CBSA.VULN_CUSTOMER_SEARCH"} and "CUSTOMER_INPUT" in q:
                    m = re.search(r"CUSTOMER_INPUT\s*=\s*'(.+)'", sql, re.I|re.S)
                    inp = (m.group(1) if m else "").replace("''", "'")
                    res = call_vuln_account_search(self.state, inp)
                    return res.get("rows", [])
                return self._filter_rows(rows, q)
        # Convenience matches
        if "FROM SYSIBM.SYSTABLES" in q:
            return self._filter_rows(cat["SYSIBM.SYSTABLES"], q)
        if "FROM SYSIBM.SYSCOLUMNS" in q:
            return self._filter_rows(cat["SYSIBM.SYSCOLUMNS"], q)
        if "FROM SYSIBM.SYSUSERAUTH" in q or "FROM SYSIBM.SYSUSERS" in q:
            return self._filter_rows(cat["SYSIBM.SYSUSERAUTH"], q)
        raise ValueError("SQLCODE=-104, SQLSTATE=42601, UNSUPPORTED SQL SYNTAX")

    def _filter_rows(self, rows: list[dict[str, str]], q: str) -> list[dict[str, str]]:
        result = [dict(r) for r in rows]
        if " WHERE " in q:
            cond = q.split(" WHERE ", 1)[1]
            if " ORDER BY " in cond:
                cond = cond.split(" ORDER BY ", 1)[0]
            if "'1'='1'" not in cond and " OR " not in cond:
                m = re.search(r"([A-Z0-9_]+)\s*=\s*'([^']*)'", cond)
                if m:
                    key, val = m.group(1), m.group(2)
                    result = [r for r in result if str(r.get(key, "")).upper() == val.upper()]
        if " ORDER BY " in q:
            ob = q.split(" ORDER BY ", 1)[1].split()[0].strip(',')
            result.sort(key=lambda r: str(r.get(ob, "")))
        return self._project_rows(result, q)

    def _project_rows(self, rows: list[dict[str, str]], q: str) -> list[dict[str, str]]:
        m = re.match(r"SELECT\s+(.+?)\s+FROM\s+", q)
        if not m:
            return rows
        cols = [c.strip().split()[-1] for c in m.group(1).split(',')]
        if cols == ['*'] or not cols:
            return rows
        return [{c: r.get(c, '') for c in cols} for r in rows]

    def _split_sql_values(self, text: str) -> list[str]:
        vals: list[str] = []
        cur = ''
        inq = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "'":
                inq = not inq
                i += 1
                continue
            if ch == ',' and not inq:
                vals.append(cur.strip())
                cur = ''
            else:
                cur += ch
            i += 1
        vals.append(cur.strip())
        return vals

    def _execute_insert(self, sql: str, userid: str) -> int:
        svc = get_gmvb_service(self.state)
        m = re.search(r"INSERT\s+INTO\s+([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)", sql, re.I | re.S)
        if not m:
            return 1
        table = m.group(1).upper()
        cols = [c.strip().upper() for c in m.group(2).split(',')]
        vals = self._split_sql_values(m.group(3))
        row = {c: (vals[i].strip().strip("'") if i < len(vals) else '') for i, c in enumerate(cols)}
        if table in {'FIBS.PROCTRAN', 'GMVB.PROCTRAN', 'GMVB.TRANSACTION'}:
            svc.write_processed_transaction(row | {'OPERATOR_ID': userid, 'SOURCE': 'DB2'})
            return 1
        if table in {'FIBS.AUDITLOG', 'GMVB.AUDITLOG'}:
            svc.audit_event(row.get('EVENT_TYPE', 'DB2'), userid, row.get('ACTION', 'INSERT'), row.get('RESULT', 'OK'), row.get('DETAILS', 'Inserted by Db2'), resource=row.get('RESOURCE', 'FIBS'), source='db2')
            return 1
        if table in {'FIBS.API_AUDIT', 'GMVB.API_AUDIT'}:
            svc.audit_event('API', userid, row.get('ACTION', 'INSERT'), row.get('RESULT', 'OK'), row.get('DETAILS', 'API audit inserted by Db2'), resource=row.get('RESOURCE', 'FIBS.API'), source='api')
            return 1
        if table in {'FIBS.TN3270_CAPTURE', 'GMVB.TN3270_CAPTURE'}:
            svc.audit_event('TN3270_CAPTURE', userid, row.get('ACTION', 'INSERT'), row.get('RESULT', 'OK'), row.get('BUFFER_EXCERPT', row.get('DETAILS', 'TN3270 capture inserted')), resource=row.get('CAPTURE_ID', 'CAPTURE'), source='db2')
            return 1
        if table in {'FIBS.HACK3270_EVENT', 'GMVB.HACK3270_EVENT'}:
            svc.audit_event('HACK3270', userid, row.get('ACTION', 'INSERT'), row.get('RESULT', 'OK'), row.get('DETAILS', 'HACK3270 event inserted'), resource=row.get('EVENT_ID', 'HACK3270'), source='db2')
            return 1
        return 1

    def _execute_update(self, sql: str, userid: str) -> int:
        svc = get_gmvb_service(self.state)
        m = re.search(r"UPDATE\s+([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s+SET\s+(.+?)(?:\s+WHERE\s+(.+))?$", sql.strip().rstrip(';'), re.I | re.S)
        if not m:
            return 1
        table = m.group(1).upper()
        assigns = {}
        for item in self._split_sql_values(m.group(2)):
            if '=' in item:
                k, v = item.split('=', 1)
                assigns[k.strip().upper()] = v.strip().strip("'")
        where = (m.group(3) or '').upper()
        key_match = re.search(r"([A-Z0-9_]+)\s*=\s*'([^']*)'", where)
        key = key_match.group(1) if key_match else ''
        val = key_match.group(2) if key_match else ''
        rows = 0
        if table in {'FIBS.ACCOUNT', 'GMVB.ACCOUNT'}:
            for acct, row in svc.accounts.items():
                if not key or str(row.get(key, '')).upper() == val.upper():
                    row.update(assigns); row['UPDATED_BY'] = userid.upper(); rows += 1
        elif table in {'FIBS.BATCH_TRANSFER', 'FIBS.PAYMENT_BATCH', 'GMVB.BATCH_TRANSFER', 'GMVB.PAYMENT_BATCH'}:
            for bid, row in svc.batches.items():
                if not key or str(row.get(key, '')).upper() == val.upper():
                    row.update(assigns); rows += 1
        return rows or 1

    def display_group(self) -> str:
        si = SYSTEM_INFO
        return (
            f"DSN7100I -{si['SUBSYSTEM']} DISPLAY GROUP REPORT\n"
            f"  GROUP ATTACH NAME: {si['GROUP']}\n"
            f"  MEMBER NAME      : {si['MEMBER']}\n"
            f"  SUBSYSTEM ID     : {si['ID']}\n"
            f"  LOCATION         : {si['LOCATION']}\n"
            f"  VERSION          : {si['VERSION']}"
        )

    def format_spufi(self, sql: str, userid: str = "IBMUSER") -> str:
        try:
            rows = self.run_sql(sql, userid)
        except Exception as e:
            return f"DSNT408I SQLCODE = -104, ERROR: {e}\nDSNT418I SQLSTATE   = 42601"
        if not rows:
            return "DSNE610I NUMBER OF ROWS DISPLAYED IS 0\nDSNE601I SQLSTAT = 00000"
        keys = list(rows[0].keys())
        widths = {k: max(len(k), *(len(str(r.get(k, ''))) for r in rows)) for k in keys}
        out = ["DSNE616I NUMBER OF ROWS DISPLAYED IS {0}".format(len(rows))]
        out.append("  ".join(k.ljust(widths[k]) for k in keys))
        out.append("  ".join("-" * widths[k] for k in keys))
        for r in rows:
            out.append("  ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys))
        out.append("DSNE601I SQLSTAT = 00000")
        out.append("DSNE618I END OF SQL STATEMENT PROCESSING")
        return "\n".join(out)

    def submit_job(self, name: str) -> str:
        jid = f"DB2{len(self.active_jobs)+1:05d}"
        self.active_jobs[jid] = Db2Job(jid, name[:8].upper() or "DB2JOB")
        return jid

    def shell_command(self, cmd: str, userid: str) -> str:
        uc = cmd.strip().upper()
        if uc == "HELP":
            return "Available commands: HELP, SHOW DBS, SHOW USERS, DISPLAY GROUP, OMVS STATUS, ID UID, RUN SQL <query>, SUBMIT JOB <name>, STATUS JOBS, CANCEL JOB <id>, LOGOUT"
        if uc == "SHOW DBS":
            return "Databases: DSNDB06, GIBDB, DSNDB01, DSNDB07"
        if uc == "SHOW USERS":
            return "Users:\n" + "\n".join(sorted(self.state.racf.users))
        if uc == "DISPLAY GROUP":
            return self.display_group()
        if uc == "OMVS STATUS":
            rec = self.state.racf.get(userid)
            return "OMVS segment: Present" if rec and rec.has_omvs else "OMVS segment: Missing"
        if uc == "ID UID":
            uid = 1000 + abs(hash(userid)) % 9000
            return f"UID={uid} GID={uid} HOME=/u/{userid.lower()} SHELL=/bin/sh"
        if uc.startswith("RUN SQL "):
            return self.format_spufi(cmd[len("RUN SQL "):], userid)
        if uc.startswith("SUBMIT JOB "):
            jid = self.submit_job(cmd[len("SUBMIT JOB "):])
            return f"JOB {jid} submitted."
        if uc == "STATUS JOBS":
            if not self.active_jobs:
                return "No active jobs."
            lines = ["JOB ID     NAME      STATUS"]
            for job in self.active_jobs.values():
                lines.append(f"{job.jobid:<10} {job.name:<8} {job.status}")
            return "\n".join(lines)
        if uc.startswith("CANCEL JOB "):
            jid = cmd[len("CANCEL JOB "):].strip().upper()
            if jid in self.active_jobs:
                del self.active_jobs[jid]
                return f"JOB {jid} cancelled."
            return "Job ID not found."
        if uc in ("LOGOUT", "QUIT", "EXIT"):
            return "Goodbye."
        return "Unknown command. Type HELP."


class Db2TerminalSession:
    """Interactive L DB2 terminal from the VTAM logon selector."""

    def __init__(self, state: GibsonState, userid: str = "IBMUSER"):
        self.state = state
        self.userid = userid.upper()
        self.db2 = Db2Simulator(state)
        self.ssid = "DSN1"

    def run(self, input_driver: SocketInputDriver, send) -> None:
        """ASCII/NVT (netcat/telnet) DB2I entry point.

        Presents the same full DB2I PRIMARY OPTION MENU as the 3270 client sees,
        but rendered as readable ASCII so line-mode clients don't get raw EBCDIC.
        The DSN line-mode command processor is reachable as option DSN.
        """
        message = ""
        while True:
            send(self.db2i_menu(message))
            message = ""
            res = input_driver.read_line("Option ===> ")
            key = (res.key or "").upper()
            choice = (res.text or "").strip().upper()
            if key in ("F3", "PF3") or choice in ("X", "EXIT", "END", "QUIT", "LOGOFF"):
                send("DSN9022I -DB2A DB2I SESSION ENDED\n")
                return
            if choice in ("DSN", "9", "COMMAND PROC"):
                self.dsn_command_processor(input_driver, send)
            elif choice in ("1", "SPUFI"):
                self.spufi_prompt(input_driver, send)
            elif choice in ("7", "DB2 COMMANDS"):
                send(colors.CLEAR + self.db2.display_group() + "\n")
                self._pause(input_driver)
            elif choice in ("2", "3", "4", "5", "6", "8", "DCLGEN", "PROGRAM PREP",
                            "PRECOMPILE", "BIND/REBIND/FREE", "RUN", "UTILITIES"):
                send(colors.CLEAR + colors.WHITE +
                     f"DSNE option {choice} is display-only in Gibson.\n" + colors.RESET +
                     "Use option 1 (SPUFI) or DSN for SQL and command activity.\n")
                self._pause(input_driver)
            elif choice in ("D", "DB2I DEFAULTS"):
                send(colors.CLEAR + colors.WHITE + "DB2I DEFAULTS\n" + colors.RESET +
                     f"  SSID ===> {self.ssid}\n  Defaults are display-only in Gibson.\n")
                self._pause(input_driver)
            elif choice == "":
                continue
            else:
                message = f"INVALID OPTION '{choice}'"

    def db2i_menu(self, message: str = "") -> str:
        """The full DB2I PRIMARY OPTION MENU as ASCII (single source of truth =
        the 3270 menu's option table)."""
        from gibson.apps.db2i3270.db2i_session import _MENU_OPTIONS
        lines = [
            colors.CLEAR + colors.WHITE + "DB2I PRIMARY OPTION MENU" + colors.RESET,
            "",
            colors.BLUE + "Option  ===>" + colors.RESET,
            "",
        ]
        for num, name, desc in _MENU_OPTIONS:
            lines.append(f"   {colors.WHITE}{num:>3}{colors.RESET}  {colors.TURQUOISE}{name:<18}{colors.RESET} {desc}")
        lines += ["", colors.GREEN + f"SSID ===> {self.ssid}" + colors.RESET]
        if message:
            lines += ["", colors.RED + message + colors.RESET]
        return "\n".join(lines) + "\n"

    def _pause(self, input_driver: SocketInputDriver) -> None:
        try:
            input_driver.read_line("Press ENTER to return to DB2I ===> ")
        except Exception:
            pass

    def spufi_prompt(self, input_driver: SocketInputDriver, send) -> None:
        send(colors.CLEAR + colors.WHITE + "DB2I SPUFI" + colors.RESET +
             "\nEnter an SQL statement (or END to return):\n")
        while True:
            res = input_driver.read_line("SQL ===> ")
            sql = (res.text or "").strip()
            if (res.key or "").upper() in ("F3", "PF3") or sql.upper() in ("END", "EXIT", "X", ""):
                return
            send(self.db2.format_spufi(sql, self.userid) + "\n")

    def dsn_command_processor(self, input_driver: SocketInputDriver, send) -> None:
        send(colors.CLEAR + self.banner())
        while True:
            res = input_driver.read_line("DSN SYSTEM(DB2A) ===> ")
            key = res.key or ""
            cmd = res.text.strip()
            uc = (key or cmd).upper()
            if uc in ("F3", "PF3", "EXIT", "QUIT", "LOGOFF", "END"):
                send("DSN9022I -DB2A DSN COMMAND PROCESSOR NORMAL COMPLETION\n")
                return
            if uc in ("HELP", "?"):
                send(self.help() + "\n")
            elif uc.startswith("RUN SQL "):
                send(self.db2.format_spufi(cmd[len("RUN SQL "):], self.userid) + "\n")
            elif uc.startswith("SELECT") or uc.startswith("INSERT") or uc.startswith("UPDATE") or uc.startswith("DELETE") or uc.startswith("GRANT"):
                send(self.db2.format_spufi(cmd, self.userid) + "\n")
            elif uc in ("DISPLAY GROUP", "-DISPLAY GROUP"):
                send(self.db2.display_group() + "\n")
            else:
                send(self.db2.shell_command(cmd, self.userid) + "\n")

    def banner(self) -> str:
        return (
            "DSN SYSTEM(DB2A)\n"
            "DSN7100I -DB2A DB2 COMMAND PROCESSOR - GIBSON\n"
            "COMMANDS: HELP, DISPLAY GROUP, RUN SQL <statement>, SHOW DBS, SHOW USERS, LOGOUT\n"
        )

    def help(self) -> str:
        return (
            "DB2 COMMAND PROCESSOR HELP\n"
            "  DISPLAY GROUP       Display simulated Db2 data sharing group\n"
            "  RUN SQL <sql>       Execute SQL through the simulator\n"
            "  SHOW DBS            List databases\n"
            "  SHOW USERS          List RACF/DB2 users\n"
            "  STATUS JOBS         Display DB2 submitted jobs\n"
            "  LOGOUT              Return to VTAM logon"
        )
