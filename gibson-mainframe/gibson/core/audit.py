from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class AuditEvent:
    ts: datetime
    userid: str
    command: str
    result: str
    component: str = "TSO"
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class AuditLog:
    path: Optional[Path] = None
    events: List[AuditEvent] = field(default_factory=list)

    def record(
        self,
        userid: str,
        command: str,
        result: str,
        component: str = "TSO",
        *,
        extra: Optional[Dict[str, str]] = None,
    ) -> None:
        safe_extra = {str(k).upper(): str(v) for k, v in (extra or {}).items() if v is not None and str(v) != ""}
        event = AuditEvent(datetime.now(), userid.upper(), command, result[:240].replace("\n", " "), component, safe_extra)
        self.events.append(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            extra_text = ""
            if safe_extra:
                extra_text = " [" + " ".join(f"{k}={v}" for k, v in sorted(safe_extra.items())) + "]"
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(f"{event.ts.isoformat()} {event.component} {event.userid}: {event.command} => {event.result}{extra_text}\n")

    def record_smf80(
        self,
        userid: str,
        event: str,
        details: str = "",
        *,
        result: str = "SUCCESS",
        extra: Optional[Dict[str, str]] = None,
    ) -> None:
        evt = (event or "SECURITY EVENT").upper()
        detail = (details or "").strip()
        command = f"SMF TYPE 80 {evt}"
        message = f"{result.upper()} {detail}".strip()
        safe_extra = {str(k).upper(): str(v) for k, v in (extra or {}).items() if v is not None and str(v) != ""}
        safe_extra.setdefault("EVENT", evt)
        safe_extra.setdefault("RESULT", result.upper())
        safe_extra.setdefault("DETAIL", detail)
        self.record(userid, command, message, "SMF80", extra=safe_extra)

    def record_smf30(
        self,
        userid: str,
        event: str = "SESSION START",
        details: str = "",
        *,
        result: str = "SUCCESS",
        extra: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a simulator SMF Type 30 job/session activity event."""
        evt = (event or "SESSION START").upper()
        detail = (details or "").strip()
        command = f"SMF TYPE 30 {evt}"
        message = f"{result.upper()} {detail}".strip()
        safe_extra = {str(k).upper(): str(v) for k, v in (extra or {}).items() if v is not None and str(v) != ""}
        safe_extra.setdefault("EVENT", evt)
        safe_extra.setdefault("RESULT", result.upper())
        safe_extra.setdefault("DETAIL", detail)
        safe_extra.setdefault("RECORD_TYPE", "30")
        self.record(userid, command, message, "SMF30", extra=safe_extra)


    def record_smf7(
        self,
        userid: str = "SYSTEM",
        reason: str = "SMF DATA LOST",
        *,
        count_lost: int = 1,
        affected_record_types: str = "UNKNOWN",
        service: str = "SMF",
        severity: str = "WARNING",
        extra: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a simulator SMF Type 7 data-lost event."""
        data = {str(k).upper(): str(v) for k, v in (extra or {}).items() if v is not None}
        data.update({
            "RECORD_TYPE": "7",
            "EVENT": "SMF DATA LOST",
            "REASON": reason,
            "COUNT_LOST": str(int(count_lost)),
            "AFFECTED_RECORD_TYPES": affected_record_types,
            "SERVICE": service.upper(),
            "SEVERITY": severity.upper(),
            "TIME": datetime.now().strftime("%H:%M:%S"),
            "DATE": datetime.now().strftime("%Y-%m-%d"),
        })
        self.record(userid, "SMF TYPE 7 SMF DATA LOST", f"{severity.upper()} {reason} COUNT={count_lost}", "SMF7", extra=data)

    def smf7_detail_lines(self, event: AuditEvent) -> List[str]:
        x = {str(k).upper(): str(v) for k, v in (event.extra or {}).items()}
        return [
            "SMF TYPE 7 DATA LOST RECORD DETAIL",
            "",
            f"USERID   : {event.userid}",
            f"TIME     : {x.get('TIME', event.ts.strftime('%H:%M:%S'))}",
            f"DATE     : {x.get('DATE', event.ts.strftime('%Y-%m-%d'))}",
            f"SYSTEM   : {x.get('SYSTEM', 'MVSC')}",
            f"SERVICE  : {x.get('SERVICE', 'SMF')}",
            f"REASON   : {x.get('REASON', event.result)}",
            f"COUNT    : {x.get('COUNT_LOST', '1')}",
            f"AFFECTED : {x.get('AFFECTED_RECORD_TYPES', 'UNKNOWN')}",
            f"SEVERITY : {x.get('SEVERITY', 'WARNING')}",
        ]

    def last_successful_logon(self, userid: str) -> Optional[AuditEvent]:
        user = (userid or "").upper()
        for event in reversed(self.events):
            if event.component != "SMF80":
                continue
            if event.userid != user:
                continue
            if event.extra.get("EVENT") != "LOGON":
                continue
            if event.extra.get("RESULT") != "SUCCESS":
                continue
            return event
        return None

    def smf80_row(self, event: AuditEvent, *, system: str = "MVSC") -> Dict[str, str]:
        extra = {str(k).upper(): str(v) for k, v in (event.extra or {}).items()}
        return {
            "USERID": extra.get("USERID", event.userid),
            "GROUP": extra.get("GROUP", ""),
            "EVENT": extra.get("EVENT", event.command.replace("SMF TYPE 80 ", "")),
            "RESULT": extra.get("RESULT", event.result.split()[0] if event.result else ""),
            "TIME": extra.get("TIME", event.ts.strftime("%H:%M:%S")),
            "DATE": extra.get("DATE", event.ts.strftime("%Y-%m-%d")),
            "SYSTEM": extra.get("SYSTEM", system),
            "JOBNAME": extra.get("JOBNAME", ""),
            "CLASS": extra.get("CLASS", ""),
            "RESOURCE": extra.get("RESOURCE", ""),
            "PROFILE": extra.get("PROFILE", ""),
            "SERVICE": extra.get("SERVICE", ""),
            "MESSAGE_ID": extra.get("MESSAGE_ID", ""),
            "TERMINAL": extra.get("TERMINAL", ""),
            "ADDR": extra.get("ADDR", ""),
            "APPLID": extra.get("APPLID", ""),
            "TRANSID": extra.get("TRANSID", ""),
            "TERMID": extra.get("TERMID", ""),
            "REGION": extra.get("REGION", ""),
            "CORRID": extra.get("CORRID", ""),
            "DETAIL": extra.get("DETAIL", event.result),
        }

    def smf80_detail_lines(self, event: AuditEvent, *, system: str = "MVSC") -> List[str]:
        row = self.smf80_row(event, system=system)
        lines = [
            "SMF TYPE 80 SECURITY RECORD DETAIL",
            "",
            f"USERID   : {row['USERID']}",
            f"GROUP    : {row['GROUP']}",
            f"EVENT    : {row['EVENT']}",
            f"RESULT   : {row['RESULT']}",
            f"TIME     : {row['TIME']}",
            f"DATE     : {row['DATE']}",
            f"SYSTEM   : {row['SYSTEM']}",
            f"JOBNAME  : {row['JOBNAME']}",
            f"CLASS    : {row['CLASS']}",
            f"RESOURCE : {row['RESOURCE']}",
            f"PROFILE  : {row['PROFILE']}",
            f"SERVICE  : {row['SERVICE']}",
            f"MESSAGE  : {row['MESSAGE_ID']}",
        ]
        if row.get("TERMINAL"):
            lines.append(f"TERMINAL : {row['TERMINAL']}")
        if row.get("ADDR"):
            lines.append(f"ADDRESS  : {row['ADDR']}")
        for label, key in (("APPLID", "APPLID"), ("TRANSID", "TRANSID"), ("TERMID", "TERMID"), ("REGION", "REGION"), ("CORRID", "CORRID")):
            if row.get(key):
                lines.append(f"{label:<8} : {row[key]}")
        if row.get("DETAIL"):
            lines.extend(["", f"DETAIL   : {row['DETAIL']}"])
        return lines
