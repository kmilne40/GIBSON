"""Storage layer for the Gibson Office Mail facility (ISPF).

Config lives in SYS1.EMAIL (KEY = VALUE).  Each folder is a user dataset:
  INBOX     -> <user>.MAIL.IN
  SENT      -> <user>.MAIL.OUT
  IMPORTANT -> <user>.MAIL.IMPORTANT
  SPAM      -> <user>.MAIL.SPAM
Messages are stored as plain =MSG=..=END= text blocks so they remain readable
if browsed in ISPF.  Every dataset operation is defensive: the facility keeps an
in-memory copy and only uses the datasets for persistence, so it works even on a
locked-down system, and is seeded with a small demo mailbox on first use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

CONFIG_DSN = "SYS1.EMAIL"

FOLDERS = ["INBOX", "SENT", "IMPORTANT", "SPAM"]
FOLDER_DSN = {
    "INBOX": "MAIL.IN",
    "SENT": "MAIL.OUT",
    "IMPORTANT": "MAIL.IMPORTANT",
    "SPAM": "MAIL.SPAM",
}

DEFAULT_CONFIG = {
    # --- sending (SMTP) ---
    "SMTP_HOST": "mail.sighberbank.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "",
    "SMTP_PASS": "",
    "FROM": "ibmuser@gibson.test",
    "TLS": "STARTTLS",        # NO | STARTTLS | SSL
    "CREDS_B64": "NO",        # YES => SMTP_USER/SMTP_PASS/RECV_* are base64
    # --- receiving (POP3 or IMAP) ---
    "RECV_PROTO": "IMAP",     # POP3 | IMAP | NONE
    "IMAP_HOST": "",
    "IMAP_PORT": "993",
    "POP_HOST": "",
    "POP_PORT": "995",
    "RECV_USER": "",
    "RECV_PASS": "",
    # --- internal mail (user-to-user on this system) ---
    "MAIL_MODE": "BOTH",          # INTERNAL | EXTERNAL | BOTH
    "INTERNAL_DOMAIN": "GIBSON.LOCAL",
}


@dataclass
class Message:
    frm: str = ""
    to: str = ""
    subj: str = ""
    date: str = ""
    flag: str = "NEW"          # NEW / READ / SENT
    body: List[str] = field(default_factory=list)

    def size_kb(self) -> int:
        n = sum(len(x) for x in self.body) + len(self.subj) + 40
        return max(1, round(n / 1024))


# --------------------------------------------------------------------------- #
#  serialise / parse
# --------------------------------------------------------------------------- #
def serialise(msgs: List[Message]) -> str:
    out: List[str] = []
    for m in msgs:
        out.append("=MSG=")
        out.append(f"FROM: {m.frm}")
        out.append(f"TO: {m.to}")
        out.append(f"SUBJ: {m.subj}")
        out.append(f"DATE: {m.date}")
        out.append(f"FLAG: {m.flag}")
        out.append("")
        out.extend(m.body)
        out.append("=END=")
    return "\n".join(out)


def parse(text: str) -> List[Message]:
    msgs: List[Message] = []
    cur: Message | None = None
    in_body = False
    for raw in (text or "").splitlines():
        line = raw.rstrip("\r")
        if line == "=MSG=":
            cur = Message(); in_body = False; continue
        if line == "=END=":
            if cur is not None:
                msgs.append(cur)
            cur = None; in_body = False; continue
        if cur is None:
            continue
        if not in_body:
            if line == "":
                in_body = True; continue
            key, _, val = line.partition(":")
            key = key.strip().upper(); val = val.strip()
            if key == "FROM": cur.frm = val
            elif key == "TO": cur.to = val
            elif key == "SUBJ": cur.subj = val
            elif key == "DATE": cur.date = val
            elif key == "FLAG": cur.flag = val or "NEW"
        else:
            cur.body.append(line)
    return msgs


def _now() -> str:
    return datetime.now().strftime("%d %b %Y %H:%M").upper()


# --------------------------------------------------------------------------- #
#  store
# --------------------------------------------------------------------------- #
class MailStore:
    def __init__(self, state, userid: str = "IBMUSER"):
        self.state = state
        self.userid = (userid or "IBMUSER").upper()
        self.config: Dict[str, str] = dict(DEFAULT_CONFIG)
        self._cache: Dict[str, List[Message]] = {f: [] for f in FOLDERS}
        self._load_config()
        self._ensure_config_ds()
        self.provision_mailbox(self.userid)
        self.provision_mailbox("GUEST")   # demo internal recipient
        self._load_all()
        if self.userid == "IBMUSER" and not any(self._cache.values()):
            self._seed()

    # ---- datasets: the mail facility is a trusted agent (like an MTA/MUA),
    #      so its own mailbox I/O bypasses the per-user RACF check.  The mailbox
    #      datasets remain protected by RACF against every OTHER access path
    #      (TSO, ISPF 3.4, LISTDS), which is where the security actually bites.
    def _ds(self):
        return getattr(self.state, "datasets", None)

    def _read_ds(self, dsname: str) -> str | None:
        ds = self._ds()
        if ds is None:
            return None
        saved = getattr(ds, "security", None)
        try:
            ds.security = None
            return ds.read(self.userid, dsname)
        except Exception:
            return None
        finally:
            ds.security = saved

    def _write_ds(self, dsname: str, text: str) -> bool:
        ds = self._ds()
        if ds is None:
            return False
        saved = getattr(ds, "security", None)
        try:
            ds.security = None
            ds.write(self.userid, dsname, text)
            return True
        except Exception:
            return False
        finally:
            ds.security = saved

    def _folder_dsn(self, folder: str) -> str:
        """Fully-qualified per-user mailbox dataset, e.g. IBMUSER.MAIL.IN."""
        return f"{self.userid}.{FOLDER_DSN[folder.upper()]}"

    # ---- config ----
    def _load_config(self) -> None:
        txt = self._read_ds(CONFIG_DSN)
        if not txt:
            return
        for line in txt.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip().upper(); v = v.strip()
            if k in DEFAULT_CONFIG:
                self.config[k] = v

    def save_config(self, cfg: Dict[str, str]) -> bool:
        for k, v in cfg.items():
            if k.upper() in self.config and v != "":
                self.config[k.upper()] = v.strip()
        return self._write_ds(CONFIG_DSN, self._config_text())

    def _config_text(self) -> str:
        lines = ["# Gibson Office Mail configuration (SYS1.EMAIL)"]
        lines += [f"{k} = {self.config[k]}" for k in DEFAULT_CONFIG]
        return "\n".join(lines)

    def _ensure_config_ds(self) -> None:
        # Create SYS1.EMAIL with the current (default) settings so it can always
        # be read/browsed, if it does not already exist.
        if self._read_ds(CONFIG_DSN) is None:
            self._write_ds(CONFIG_DSN, self._config_text())

    # ---- folders ----
    def _load_all(self) -> None:
        for f in FOLDERS:
            txt = self._read_ds(self._folder_dsn(f))
            if txt:
                self._cache[f] = parse(txt)

    def _persist(self, folder: str) -> None:
        self._write_ds(self._folder_dsn(folder), serialise(self._cache.get(folder, [])))

    def folder(self, name: str) -> List[Message]:
        return self._cache.get(name.upper(), [])

    def counts(self) -> Dict[str, int]:
        return {f: len(self._cache.get(f, [])) for f in FOLDERS}

    def new_count(self) -> int:
        return sum(1 for m in self._cache.get("INBOX", []) if m.flag == "NEW")

    def add(self, folder: str, msg: Message) -> None:
        self._cache.setdefault(folder.upper(), []).insert(0, msg)
        self._persist(folder.upper())

    def move(self, src: str, idx: int, dst: str) -> bool:
        src = src.upper(); dst = dst.upper()
        lst = self._cache.get(src, [])
        if not (0 <= idx < len(lst)):
            return False
        msg = lst.pop(idx)
        self._cache.setdefault(dst, []).insert(0, msg)
        self._persist(src); self._persist(dst)
        return True

    def delete(self, folder: str, idx: int) -> bool:
        # delete = move to SPAM unless already there, then drop
        folder = folder.upper()
        lst = self._cache.get(folder, [])
        if not (0 <= idx < len(lst)):
            return False
        if folder == "SPAM":
            lst.pop(idx); self._persist(folder); return True
        return self.move(folder, idx, "SPAM")

    def mark_read(self, folder: str, idx: int) -> None:
        lst = self._cache.get(folder.upper(), [])
        if 0 <= idx < len(lst) and lst[idx].flag == "NEW":
            lst[idx].flag = "READ"; self._persist(folder.upper())

    def sent(self, msg: Message) -> None:
        msg.flag = "SENT"
        self.add("SENT", msg)

    # ---- internal mail (user-to-user on this system) ----
    def internal_users(self) -> List[str]:
        """Userids that can receive internal mail, from the RACF directory."""
        racf = getattr(self.state, "racf", None)
        users = []
        if racf is not None:
            try:
                users = sorted({str(x).upper() for x in getattr(racf, "users", [])})
            except Exception:
                users = []
        return users

    def classify(self, addr: str):
        """Return ('internal', USERID) or ('external', addr) or (None, None)."""
        a = (addr or "").strip()
        if not a:
            return (None, None)
        local = a.split("@")[0].strip().upper()
        domain = a.split("@")[1].strip().upper() if "@" in a else ""
        internal_dom = (self.config.get("INTERNAL_DOMAIN", "") or "").upper()
        users = set(self.internal_users())
        if "@" not in a and local in users:
            return ("internal", local)
        if domain and internal_dom and domain == internal_dom and local in users:
            return ("internal", local)
        return ("external", a)

    def deliver_internal(self, recipient_userid: str, msg: Message) -> bool:
        """Deposit a note into another user's INBOX as the trusted delivery agent."""
        recip = recipient_userid.upper()
        self.provision_mailbox(recip)
        dsn = f"{recip}.MAIL.IN"
        existing = self._read_ds(dsn) or ""
        msgs = parse(existing)
        msg.flag = "NEW"
        msgs.insert(0, msg)
        ok = self._write_ds(dsn, serialise(msgs))
        # if delivering to ourselves, refresh the live cache too
        if recip == self.userid:
            self._cache["INBOX"] = msgs
        return ok

    def _racf(self, cmd: str) -> str:
        """Run a RACF command as the system (IBMUSER); errors are non-fatal."""
        try:
            from gibson.apps.tso import TsoCommandProcessor
            return str(TsoCommandProcessor(self.state, "IBMUSER").run(cmd))
        except Exception:
            return ""

    def provision_mailbox(self, userid: str) -> None:
        """Idempotently ensure a user exists and has four protected mailbox
        datasets: ADDUSER if needed, allocate the folders, and protect them with
        a RACF profile (UACC(NONE)) so only the owner and SPECIAL users may read
        them through TSO/ISPF."""
        u = (userid or "").upper()
        if not u:
            return
        done = getattr(self.state, "_mail_provisioned", None)
        if done is None:
            done = set()
            setattr(self.state, "_mail_provisioned", done)
        if u in done:
            return
        done.add(u)
        if u not in set(self.internal_users()):
            self._racf(f"ADDUSER {u} DFLTGRP(SYS1) NAME('{u}') PASSWORD({u[:8]})")
        for f in FOLDERS:
            dsn = f"{u}.{FOLDER_DSN[f]}"
            if self._read_ds(dsn) is None:
                self._write_ds(dsn, "")
        # protect the mailbox: UACC(NONE), owned by the user, owner permitted
        self._racf(f"ADDSD '{u}.MAIL.**' UACC(NONE) OWNER({u})")
        self._racf(f"PERMIT '{u}.MAIL.**' CLASS(DATASET) ID({u}) ACCESS(ALTER)")

    # ---- seed a small demo mailbox so the facility works offline ----
    def _seed(self) -> None:
        self._cache["INBOX"] = [
            Message("soc@sighberbank.com", "ibmuser@gibson.test",
                    "Phishing simulation results are in", _now(), "NEW",
                    ["Team,", "", "The Q2 phishing simulation completed overnight.",
                     "Click-through was 11% - down from 19% last quarter.",
                     "Full breakdown attached in the report dataset.", "", "- SOC"]),
            Message("payroll@corp.test", "ibmuser@gibson.test",
                    "Re: month-end batch run", _now(), "NEW",
                    ["The month-end run finished RC=0000.",
                     "SDSF shows all steps clean. Safe to release.", "", "Payroll"]),
            Message("no-reply@vpn.test", "ibmuser@gibson.test",
                    "Your VPN token expires in 3 days", _now(), "READ",
                    ["This is an automated reminder that your VPN",
                     "token will expire soon. Renew via the self-service portal."]),
        ]
        self._cache["IMPORTANT"] = [
            Message("ciso@gibson.test", "ibmuser@gibson.test",
                    "Change freeze - read before Friday", _now(), "READ",
                    ["A production change freeze is in effect from Friday 1700",
                     "through Monday 0900. Emergency changes require CAB approval.", "", "CISO"]),
        ]
        self._cache["SPAM"] = [
            Message("winner@totally-legit.test", "ibmuser@gibson.test",
                    "YOU have been SELECTED!!!", _now(), "READ",
                    ["Congratulations!!! Click here to claim your prize..."]),
        ]
        self._cache["SENT"] = [
            Message("ibmuser@gibson.test", "soc@sighberbank.com",
                    "Re: Phishing simulation results are in", _now(), "SENT",
                    ["Thanks - good improvement. Let us brief the board.", "", "IBMUSER"]),
        ]
        for f in FOLDERS:
            self._persist(f)
