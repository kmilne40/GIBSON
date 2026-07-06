from __future__ import annotations

from typing import Dict, List
from dataclasses import dataclass, field
from gibson.core.state import GibsonState
from gibson.render import colors
from gibson.render.input import SocketInputDriver
from gibson.apps.gmvb_service import get_gmvb_service
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
            {"TBNAME": "EMPLOYEES", "TBCREATOR": "GIBSON", "NAME": "LASTNAME", "COLTYPE": "VARCHAR", "LENGTH": "15"},
            {"TBNAME": "EMPLOYEES", "TBCREATOR": "GIBSON", "NAME": "WORKDEPT", "COLTYPE": "CHAR", "LENGTH": "3"},
            {"TBNAME": "EMPLOYEES", "TBCREATOR": "GIBSON", "NAME": "HIREDATE", "COLTYPE": "DATE", "LENGTH": "4"},
            {"TBNAME": "EMPLOYEES", "TBCREATOR": "GIBSON", "NAME": "JOB", "COLTYPE": "CHAR", "LENGTH": "8"},
            {"TBNAME": "EMPLOYEES", "TBCREATOR": "GIBSON", "NAME": "SALARY", "COLTYPE": "DECIMAL", "LENGTH": "9"},
            {"TBNAME": "ACCOUNTS", "TBCREATOR": "GIBSON", "NAME": "ACCTNO", "COLTYPE": "CHAR", "LENGTH": "10"},
            {"TBNAME": "ACCOUNTS", "TBCREATOR": "GIBSON", "NAME": "OWNER", "COLTYPE": "VARCHAR", "LENGTH": "20"},
            {"TBNAME": "ACCOUNTS", "TBCREATOR": "GIBSON", "NAME": "BALANCE", "COLTYPE": "DECIMAL", "LENGTH": "11"},
            {"TBNAME": "ACCOUNTS", "TBCREATOR": "GIBSON", "NAME": "OPENED", "COLTYPE": "DATE", "LENGTH": "4"},
            {"TBNAME": "ACCOUNTS", "TBCREATOR": "GIBSON", "NAME": "STATUS", "COLTYPE": "CHAR", "LENGTH": "8"},
        ]
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
                {"NAME": "PAYPLAN", "CREATOR": "IBMUSER", "VALID": "Y"},
                {"NAME": "EMPPLAN", "CREATOR": "IBMUSER", "VALID": "Y"},
                {"NAME": "CBSAPLAN", "CREATOR": "GIBSON", "VALID": "Y"},
            ],
            "SYSIBM.SYSPACKAGE": [
                {"NAME": "PAYROLL", "COLLID": "GIBSON", "OWNER": "IBMUSER", "VALID": "Y"},
                {"NAME": "EMPMAINT", "COLLID": "GIBSON", "OWNER": "IBMUSER", "VALID": "Y"},
            ],
            "GIBSON.EMPLOYEES": [
                {"EMPNO": "000010", "FIRSTNME": "CHRISTINE", "LASTNAME": "HAAS", "WORKDEPT": "A00"},
                {"EMPNO": "000020", "FIRSTNME": "MICHAEL", "LASTNAME": "THOMPSON", "WORKDEPT": "B01"},
            ],
            "GIBSON.ACCOUNTS": [
                {"ACCTNO": "10001", "OWNER": "IBMUSER", "STATUS": "ACTIVE"},
                {"ACCTNO": "10002", "OWNER": "GUEST", "STATUS": "HOLD"},
            ],
        }
        svc = get_gmvb_service(self.state)
        data.update(svc.catalog())
        g_tables, g_cols = svc.table_metadata()
        existing = {(r.get("CREATOR"), r.get("NAME")) for r in data["SYSIBM.SYSTABLES"]}
        for row in g_tables:
            key = (row.get("CREATOR"), row.get("NAME"))
            if key not in existing:
                data["SYSIBM.SYSTABLES"].append(row)
                existing.add(key)
        existing_cols = {(r.get("TBCREATOR"), r.get("TBNAME"), r.get("NAME")) for r in data["SYSIBM.SYSCOLUMNS"]}
        for row in g_cols:
            key = (row.get("TBCREATOR"), row.get("TBNAME"), row.get("NAME"))
            if key not in existing_cols:
                data["SYSIBM.SYSCOLUMNS"].append(row)
                existing_cols.add(key)
        return data

    def plans(self) -> List[str]:
        try:
            return [r.get("NAME", "") for r in self.catalog().get("SYSIBM.SYSPLAN", []) if r.get("NAME")]
        except Exception:
            return []

    def packages(self) -> List[str]:
        try:
            return [r.get("NAME", "") for r in self.catalog().get("SYSIBM.SYSPACKAGE", []) if r.get("NAME")]
        except Exception:
            return []

    def tables(self) -> List[str]:
        try:
            seen, out = set(), []
            for r in self.catalog().get("SYSIBM.SYSTABLES", []):
                name = f"{r.get('CREATOR','')}.{r.get('NAME','')}"
                if r.get("NAME") and name not in seen:
                    seen.add(name)
                    out.append(name)
            return out
        except Exception:
            return []

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
            import re
            m = re.search(r"GRANT\s+([A-Z, ]+)\s+ON\s+([A-Z0-9_.]+)\s+TO\s+([A-Z0-9#$@]+)", q)
            if not m:
                raise ValueError("SQLCODE=-104, SQLSTATE=42601, GRANT SYNTAX")
            access, table, grantee = m.group(1), m.group(2), m.group(3)
            permit(self.state, f"DB2A.{table}", "DSNR", grantee, "READ" if "SELECT" in access else "UPDATE")
            record_smf(self.state, "101", userid, "DB2 GRANT", f"TABLE={table} GRANTEE={grantee} ACCESS={access}")
            return [{"SQLCODE": "0", "MESSAGE": f"DSNT500I GRANT {access.strip()} ON {table} TO {grantee} COMPLETE"}]
        if q.startswith("REVOKE "):
            import re
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
            return [{"SQLCODE": "0", "ROWS": "1", "MESSAGE": "DSNE615I NUMBER OF ROWS AFFECTED IS 1"}]
        if q.startswith("UPDATE ") or q.startswith("DELETE "):
            return [{"SQLCODE": "0", "ROWS": "1", "MESSAGE": "DSNE615I NUMBER OF ROWS AFFECTED IS 1"}]
        cat = self.catalog()
        # Known catalogs and training tables.
        for name, rows in cat.items():
            if f"FROM {name}" in q:
                if getattr(self.state, "strict_racf_mode", False):
                    dec = check_access(self.state, userid, "DSNR", f"DB2A.{name}", "READ")
                    if not dec.allowed:
                        record_smf(self.state, "101", userid, "DB2 SELECT DENIED", f"TABLE={name} USER={userid}", result="FAILURE")
                        raise ValueError(f"SQLCODE=-551, SQLSTATE=42501, {userid.upper()} DOES NOT HAVE SELECT ON {name}")
                record_smf(self.state, "101", userid, "DB2 SELECT", f"TABLE={name}")
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
        if " WHERE " not in q:
            return rows
        cond = q.split(" WHERE ", 1)[1]
        if "'1'='1'" in cond or " OR " in cond:
            return rows
        import re
        m = re.search(r"([A-Z0-9_]+)\s*=\s*'([^']*)'", cond)
        if m:
            key, val = m.group(1), m.group(2)
            return [r for r in rows if str(r.get(key, "")).upper() == val.upper()]
        return rows

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

    def run(self, input_driver: SocketInputDriver, send) -> None:
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
