"""A small PROFS-style calendar for the Gibson Office Mail facility.

Appointments are stored per user in <userid>.MAIL.CALENDAR, which is covered by
the same RACF profile (<userid>.MAIL.**, UACC(NONE)) that protects the
mailboxes - so a user's calendar is private to them and to SPECIAL users, just
like their mail.  Records are one appointment per line:

    YYYY-MM-DD|HH:MM|description
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date as _date
from typing import Dict, List, Set


@dataclass
class Appt:
    date: str   # YYYY-MM-DD
    time: str   # HH:MM (may be empty)
    desc: str

    def line(self) -> str:
        return f"{self.date}|{self.time}|{self.desc}"


def parse(text: str) -> List[Appt]:
    out: List[Appt] = []
    for ln in (text or "").splitlines():
        ln = ln.rstrip("\n")
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        parts = ln.split("|", 2)
        if len(parts) == 3:
            out.append(Appt(parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return out


def serialise(appts: List[Appt]) -> str:
    head = "# Gibson Office Calendar (YYYY-MM-DD|HH:MM|description)"
    return "\n".join([head] + [a.line() for a in appts])


class CalendarStore:
    DSN_SUFFIX = "MAIL.CALENDAR"

    def __init__(self, state, userid: str = "IBMUSER"):
        self.state = state
        self.userid = (userid or "IBMUSER").upper()
        self.appts: List[Appt] = []
        self._load()

    def _dsn(self) -> str:
        return f"{self.userid}.{self.DSN_SUFFIX}"

    def _ds(self):
        return getattr(self.state, "datasets", None)

    def _read(self):
        ds = self._ds()
        if ds is None:
            return None
        saved = getattr(ds, "security", None)
        try:
            ds.security = None
            return ds.read(self.userid, self._dsn())
        except Exception:
            return None
        finally:
            ds.security = saved

    def _write(self, text: str) -> bool:
        ds = self._ds()
        if ds is None:
            return False
        saved = getattr(ds, "security", None)
        try:
            ds.security = None
            ds.write(self.userid, self._dsn(), text)
            return True
        except Exception:
            return False
        finally:
            ds.security = saved

    def _load(self) -> None:
        txt = self._read()
        if txt:
            self.appts = parse(txt)

    def save(self) -> bool:
        self.appts.sort(key=lambda a: (a.date, a.time))
        return self._write(serialise(self.appts))

    def add(self, date_str: str, time_str: str, desc: str) -> bool:
        self.appts.append(Appt(date_str, time_str.strip(), desc.strip()))
        return self.save()

    def delete(self, date_str: str, idx: int) -> bool:
        day = self.for_day(date_str)
        if 0 <= idx < len(day):
            target = day[idx]
            self.appts = [a for a in self.appts if a is not target]
            return self.save()
        return False

    def for_day(self, date_str: str) -> List[Appt]:
        return sorted([a for a in self.appts if a.date == date_str],
                      key=lambda a: a.time)

    def days_with_appts(self, year: int, month: int) -> Set[int]:
        out: Set[int] = set()
        pre = f"{year:04d}-{month:02d}-"
        for a in self.appts:
            if a.date.startswith(pre):
                try:
                    out.add(int(a.date[8:10]))
                except ValueError:
                    pass
        return out

    def month_count(self, year: int, month: int) -> int:
        pre = f"{year:04d}-{month:02d}-"
        return sum(1 for a in self.appts if a.date.startswith(pre))


def month_weeks(year: int, month: int) -> List[List[int]]:
    """Weeks for the month, Sunday-first, with 0 for padding days."""
    cal = calendar.Calendar(firstweekday=6)  # 6 = Sunday
    weeks: List[List[int]] = []
    week: List[int] = []
    for d in cal.itermonthdays(year, month):
        week.append(d)
        if len(week) == 7:
            weeks.append(week); week = []
    if week:
        weeks.append(week)
    return weeks


def today_iso() -> str:
    return _date.today().isoformat()
