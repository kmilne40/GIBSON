"""z/VM CP directory and privilege-class model (Phase 4 slices z1 + z2).

This is the security-relevant core of the z/VM simulation.  Real z/VM gates
every CP command behind *privilege classes* A-G held by a virtual machine in
the CP directory.  A general user (class G) cannot FORCE another guest off,
ATTACH a real device, or STORE into host storage - attempting it yields an
``HCPxxxnnnE ... not authorized`` message.  Modelling this lets the lab teach
z/VM privilege escalation the same way RACF teaches dataset escalation.

The model is deliberately small and self-contained: a :class:`CpDirectory`
holding :class:`VmGuest` records, plus a table mapping privileged CP commands
to the class that authorizes them.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple


# CP privilege classes and what they govern (IBM z/VM CP Planning & Admin).
CP_CLASS_DESC = {
    "A": "Primary system operator - system-wide control (FORCE, SHUTDOWN)",
    "B": "Real resource control - ATTACH/DETACH/VARY real devices",
    "C": "System programmer - alter host storage (STORE)",
    "D": "Spooling control - manage other users' spool files",
    "E": "System analyst - examine host storage (DISPLAY/DUMP, INDICATE)",
    "F": "Service representative - real device diagnosis (RDEVICE)",
    "G": "General user - control one's own virtual machine",
}

# Privileged CP commands -> the single class that authorizes them.  Commands not
# listed here are "universal" (any logged-on guest may issue them for its own
# virtual machine: QUERY, IPL, LOGOFF, DISCONNECT, DEFINE, LINK, SPOOL, SET,
# TERMINAL, MESSAGE, HELP, CLOSE).
#
# Every entry here has a real execution handler in zvm_session.py - the table
# only lists commands the class check actually gates something for.  Real
# z/VM also gates VARY (B), INDICATE/MONITOR (E) and RDEVICE (F), but those
# have no teaching value for this lab and no handler, so they're deliberately
# left out rather than kept as class checks that lead nowhere.
CP_PRIVILEGE = {
    "FORCE": "A",        # log another user off
    "SHUTDOWN": "A",     # shut the system down
    "SET SECUSER": "A",  # secondary-user / surveillance
    "SET PRIVCLASS": "A",
    "DEFINE VSWITCH": "B",   # create a virtual switch
    "SET VSWITCH": "B",      # grant/revoke vswitch access
    "ATTACH": "B",       # attach a real device to a guest
    "STORE": "C",        # alter host real storage
    "DISPLAY": "E",      # examine host real storage
    "DUMP": "E",
}
# PURGE / TRANSFER / ORDER are class G for one's own spool but class D for
# another guest's - enforced by ownership in the spool handler, not here.

# Universal commands that never require a privilege class.
CP_UNIVERSAL = {
    "QUERY", "Q", "IPL", "CMS", "LOGOFF", "LOG", "DISCONNECT", "DISC",
    "DEFINE", "LINK", "DETACH", "SPOOL", "SET", "TERMINAL", "TERM",
    "MESSAGE", "MSG", "MSGNOH", "TELL", "HELP", "CLOSE", "BEGIN", "READY",
}


@dataclass
class Minidisk:
    """A minidisk owned by a guest, with link passwords (the access surface).

    ``read_pw``/``write_pw`` follow z/VM directory conventions: the literal
    ``ALL`` means anyone may link in that mode without a password (a deliberate
    exposure used to teach), an empty string means no link is permitted in that
    mode, and any other value is the password that must be supplied on LINK.
    """
    addr: str
    label: str = ""
    read_pw: str = ""
    write_pw: str = ""
    cyls: int = 100


@dataclass
class RealDevice:
    """A real I/O device in the CP device pool (the ATTACH/DETACH surface,
    class B).  Unlike a minidisk (a slice of a guest's own DASD), a real device
    is system hardware that CP hands out whole - whichever guest holds it can
    read it, so handing one to the wrong guest is a real exposure."""
    addr: str
    devclass: str        # DASD | TAPE | OSA | CTC
    label: str
    attached_to: Optional[str] = None


@dataclass
class SpoolFile:
    spoolid: str
    queue: str          # RDR / PRT / PUN
    owner: str          # whose queue the file currently sits in
    origin: str         # the guest that created it
    name: str = ""
    ftype: str = ""
    records: int = 0
    date: str = "04/27/24"


@dataclass
class VmGuest:
    """One virtual machine entry in the CP directory."""
    userid: str
    classes: str = "G"          # privilege classes held, e.g. "ABCDEFG"
    storage: str = "32M"
    max_storage: str = "64M"
    dasd: List[str] = field(default_factory=lambda: ["191"])
    description: str = ""
    logged_on: bool = False
    disconnected: bool = False
    minidisks: Dict[str, "Minidisk"] = field(default_factory=dict)
    links: List[tuple] = field(default_factory=list)  # (owner, owner_addr, my_addr, mode)
    password: str = "ACCESS"     # CP directory logon password (weak by design for the lab)
    secuser: Optional[str] = None   # SET SECUSER: who receives a copy of this guest's I/O

    def has_class(self, cls: str) -> bool:
        return cls.upper() in self.classes.upper()


# Realistic seed directory for a z/VM security lab.  MAINT and SYSADMIN are
# fully privileged; the service machines hold only what they need; GUEST is a
# plain class-G user used to demonstrate denial.
_SEED: List[VmGuest] = [
    VmGuest("MAINT", "ABCDEFG", "128M", "1G", ["190", "191", "19D", "19E", "CF1"],
            "System maintenance (all privilege classes)", password="MAINT"),
    VmGuest("SYSADMIN", "ABCDEFG", "64M", "256M", ["191"], "Security administrator",
            password="SYSADM"),
    VmGuest("OPERATOR", "ABCDE", "64M", "128M", ["191"], "System operator console",
            password="OPER"),
    VmGuest("OPERATNS", "ABCDE", "32M", "64M", ["191"], "Operations / automation",
            password="OPERATNS"),
    VmGuest("DIRMAINT", "BG", "32M", "64M", ["155", "1DF", "2AC"],
            "Directory Maintenance service machine", password="DIRMAINT"),
    VmGuest("RACFVM", "BG", "32M", "64M", ["200", "490", "590"],
            "RACF/VM security server", password="RACFVM"),
    VmGuest("TCPIP", "BG", "64M", "128M", ["591", "592"], "TCP/IP stack", password="TCPIP"),
    VmGuest("GUEST", "G", "32M", "64M", ["191"], "General user", password="GUEST"),
    VmGuest("DEMO", "G", "32M", "64M", ["191"], "Demonstration user", password="DEMO"),
]


# Guests authorized to drive the DirMaint service machine (directory edits).
DIRMAINT_AUTH = {"MAINT", "SYSADMIN", "DIRMAINT"}

# Minidisk link passwords seeded per guest.  MAINT 191 is deliberately readable
# by ALL (a classic exposure to teach); RACFVM/DIRMAINT disks are protected.
_MDISK_SEED = {
    "MAINT": [Minidisk("191", "MNT191", read_pw="ALL", write_pw="MAINTWR", cyls=100),
              Minidisk("19E", "MNT19E", read_pw="ALL", write_pw="", cyls=50)],
    "RACFVM": [Minidisk("200", "RACF00", read_pw="", write_pw="", cyls=30),
               Minidisk("490", "RACF90", read_pw="RACFRD", write_pw="RACFWR", cyls=30)],
    "DIRMAINT": [Minidisk("1DF", "DRM1DF", read_pw="", write_pw="", cyls=20)],
    "SYSADMIN": [Minidisk("191", "ADM191", read_pw="ADMRD", write_pw="ADMWR", cyls=50)],
    "GUEST": [Minidisk("191", "GST191", read_pw="ALL", write_pw="", cyls=20)],
    "DEMO": [Minidisk("191", "DEMO91", read_pw="ALL", write_pw="", cyls=20)],
}

_SPOOL_SEED = [
    SpoolFile("0001", "RDR", "MAINT", "OPERATOR", "SYSLOG", "OUTPUT", 1024),
    SpoolFile("0002", "RDR", "MAINT", "MAINT", "SERVICE", "EXEC", 88),
    SpoolFile("0101", "RDR", "DEMO", "DEMO", "MYJOB", "DATA", 250),
    SpoolFile("0102", "PRT", "OPERATOR", "DEMO", "REPORT", "LISTING", 512),
]

# Real device pool (ATTACH/DETACH, class B).  Unowned until a class-B guest
# attaches one - deliberately includes a sensitive tape to show the blast
# radius of handing a real device to the wrong guest.
_RDEV_SEED = [
    RealDevice("0500", "TAPE", "Offsite backup tape - RACF database export"),
    RealDevice("0600", "OSA", "Production OSA-Express adapter (external network)"),
    RealDevice("0700", "DASD", "Spare 3390 volume - unformatted"),
]


class CpDirectory:
    """In-memory CP directory with logged-on state, minidisks and spool."""

    def __init__(self) -> None:
        self.guests: Dict[str, VmGuest] = {g.userid: replace(g) for g in _SEED}
        for uid, disks in _MDISK_SEED.items():
            if uid in self.guests:
                self.guests[uid].minidisks = {d.addr: replace(d) for d in disks}
        self.spool: List[SpoolFile] = [replace(s) for s in _SPOOL_SEED]
        self.vswitches: Dict[str, dict] = {
            "VSW1": {"owner": "SYSTEM", "grants": {"TCPIP", "MAINT"}},
        }
        self.real_devices: Dict[str, RealDevice] = {d.addr: replace(d) for d in _RDEV_SEED}

    # -- lookup ---------------------------------------------------------------
    def exists(self, userid: str) -> bool:
        return (userid or "").upper() in self.guests

    def get(self, userid: str) -> Optional[VmGuest]:
        return self.guests.get((userid or "").upper())

    def classes(self, userid: str) -> str:
        g = self.get(userid)
        return g.classes if g else "G"

    def logged_on_users(self) -> List[str]:
        return sorted(u for u, g in self.guests.items() if g.logged_on)

    # -- minidisk (z4) --------------------------------------------------------
    def minidisk(self, userid: str, addr: str) -> Optional[Minidisk]:
        g = self.get(userid)
        return g.minidisks.get((addr or "").upper()) if g else None

    # -- real device pool (ATTACH/DETACH, class B) -----------------------------
    def real_device(self, addr: str) -> Optional[RealDevice]:
        return self.real_devices.get((addr or "").upper())

    def attach_device(self, addr: str, userid: str) -> Tuple[bool, str]:
        """Attach a real device to a guest's virtual configuration.  Returns
        (ok, status) where status is one of ``ok`` / ``notfound`` / ``inuse``
        (already attached to a *different* guest; re-attaching to the same
        guest is idempotent)."""
        dev = self.real_device(addr)
        if dev is None:
            return False, "notfound"
        if dev.attached_to and dev.attached_to != (userid or "").upper():
            return False, "inuse"
        dev.attached_to = (userid or "").upper()
        return True, "ok"

    def detach_device(self, addr: str) -> Optional[str]:
        """Release a real device back to the pool.  Returns the userid that
        held it, or None if the device doesn't exist or wasn't attached."""
        dev = self.real_device(addr)
        if dev is None or dev.attached_to is None:
            return None
        holder = dev.attached_to
        dev.attached_to = None
        return holder

    # -- spool (z5) -----------------------------------------------------------
    def reader_files(self, userid: str) -> List[SpoolFile]:
        uid = (userid or "").upper()
        return [s for s in self.spool if s.owner == uid and s.queue == "RDR"]

    def spool_for(self, userid: str, queue: str = "") -> List[SpoolFile]:
        uid = (userid or "").upper()
        return [s for s in self.spool
                if s.owner == uid and (not queue or s.queue == queue.upper())]

    def find_spool(self, spoolid: str) -> Optional[SpoolFile]:
        sid = (spoolid or "").zfill(4)
        for s in self.spool:
            if s.spoolid == sid:
                return s
        return None

    def purge_spool(self, spoolid: str) -> bool:
        s = self.find_spool(spoolid)
        if s:
            self.spool.remove(s)
            return True
        return False

    def transfer_spool(self, spoolid: str, to_user: str) -> bool:
        s = self.find_spool(spoolid)
        if s:
            s.owner = (to_user or "").upper()
            s.queue = "RDR"
            return True
        return False

    # -- lifecycle (z3) -------------------------------------------------------
    def verify_password(self, userid: str, password: str) -> bool:
        """True if the userid is in the directory and the password matches its
        CP directory entry (case-insensitive).  Unknown userids return False."""
        g = self.get(userid)
        if g is None:
            return False
        return (password or "").upper() == (g.password or "").upper()

    def define_guest(self, userid: str, *, classes: str = "G", storage: str = "32M",
                     max_storage: str = "64M", password: str = "LBYONLY",
                     like: Optional[str] = None,
                     desc: str = "DirMaint-created guest") -> Tuple[Optional[VmGuest], str]:
        """Create a brand-new guest (virtual machine) in the directory, the way
        DIRMAINT ADD does.  Returns (guest, status) where status is one of
        ``ok`` / ``exists`` / ``badid``.  A ``LIKE`` prototype clones the
        prototype's privilege classes and storage (a realistic exposure: cloning
        an admin profile over-grants the new guest)."""
        uid = (userid or "").upper()
        if not uid or len(uid) > 8 or not uid.isalnum():
            return None, "badid"
        if uid in self.guests:
            return None, "exists"
        if like:
            proto = self.guests.get(like.upper())
            if proto is not None:
                classes = proto.classes
                storage = proto.storage
                max_storage = proto.max_storage
                desc = f"Created LIKE {proto.userid}"
        g = VmGuest(uid, classes, storage, max_storage, ["191"], desc, password=password,
                    minidisks={"191": Minidisk("191", f"{uid[:6]:>6}", read_pw="", write_pw="", cyls=20)})
        self.guests[uid] = g
        return g, "ok"

    def delete_guest(self, userid: str) -> bool:
        """Remove a guest from the directory (DIRMAINT PURGE).  Seed guests are
        protected from deletion."""
        uid = (userid or "").upper()
        if uid in self.guests and uid not in {g.userid for g in _SEED}:
            del self.guests[uid]
            return True
        return False

    def add_minidisk(self, userid: str, addr: str, cyls: int = 50,
                     label: str = "", read_pw: str = "", write_pw: str = "") -> bool:
        """Add a minidisk to an existing guest (DIRMAINT AMDISK)."""
        g = self.get(userid)
        if g is None:
            return False
        a = (addr or "").upper()
        g.minidisks[a] = Minidisk(a, label or f"{userid[:4].upper()}{a}", read_pw=read_pw,
                                  write_pw=write_pw, cyls=cyls)
        if a not in g.dasd:
            g.dasd.append(a)
        return True

    def logon(self, userid: str, *, allow_create: bool = True) -> Optional[VmGuest]:
        """Mark a guest logged on.  With ``allow_create`` (the lab-vulnerable
        path) an unknown userid is auto-defined as a transient class-G guest;
        otherwise an unknown userid is rejected (returns ``None``)."""
        uid = (userid or "").upper()
        g = self.guests.get(uid)
        if g is None:
            if not allow_create:
                return None
            g = VmGuest(uid, "G", "32M", "64M", ["191"], "Transient general user",
                        minidisks={"191": Minidisk("191", f"{uid[:6]:>6}", read_pw="ALL")})
            self.guests[uid] = g
        g.logged_on = True
        g.disconnected = False
        return g

    def logoff(self, userid: str) -> bool:
        g = self.get(userid)
        if g and g.logged_on:
            g.logged_on = False
            g.disconnected = False
            return True
        return False

    def disconnect(self, userid: str) -> bool:
        g = self.get(userid)
        if g and g.logged_on:
            g.disconnected = True
            return True
        return False


def parse_cp_command(cmd: str) -> tuple[str, str]:
    """Return (verb, required_class) for a CP command line.

    The verb is upper-cased; required_class is '' for universal commands or the
    single authorizing class for privileged ones.  Two-word privileged forms
    (SET SECUSER, SET PRIVCLASS) are recognised before the bare verb.
    """
    parts = (cmd or "").strip().upper().split()
    if not parts:
        return "", ""
    verb = parts[0]
    if len(parts) >= 2:
        two = f"{verb} {parts[1]}"
        if two in CP_PRIVILEGE:
            return two, CP_PRIVILEGE[two]
    if verb in CP_PRIVILEGE:
        return verb, CP_PRIVILEGE[verb]
    return verb, ""


def is_authorized(user_classes: str, required_class: str) -> bool:
    """A universal command (required_class == '') is always allowed; a
    privileged command requires the user to hold the authorizing class."""
    if not required_class:
        return True
    return required_class.upper() in (user_classes or "").upper()
