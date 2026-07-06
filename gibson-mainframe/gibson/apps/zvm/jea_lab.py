"""z/VM "Just Enough Authority" privilege lab (roadmap Phase 2).

Teaches privilege-class *creep* and its blast radius on z/VM.  A hypervisor
compromise is never one-VM: CP privilege classes govern who may read or alter
**host real storage**, which is shared by every guest.  Over-grant a Linux guest
class C/E and it can reach straight into another guest's memory.

What the lab demonstrates
-------------------------
* **Class creep** - a Linux guest (LINUX01) that needs only class G is granted
  B, C and E (a pattern that happens when admins clone an operator/admin
  directory profile to "make networking work").
* **DISPLAY HOST  (class E)** - examine host real storage and read another
  guest's secret (RACF master key, MAINT logon material, TCPIP HiperSockets
  buffer) sitting in shared real memory.
* **STORE HOST   (class C)** - alter host real storage and corrupt another
  guest's memory cross-guest.
* **HiperSockets isolation bypass** - an IQD device that, when a guest holds the
  network class, reaches another LPAR, side-stepping the LPAR (PR/SM) EAL5+
  isolation boundary.
* **Audit + remediation** - a privilege-class-creep audit, then Just Enough
  Authority: reduce every guest to its role baseline and split admin roles.

Modes (config ``zvm_jea_lab_vulnerable_mode`` / env ``GIBSON_ZVM_JEA_VULNERABLE``)
* **vulnerable** (default): LINUX01 holds ``BCEG``; DISPLAY/STORE HOST and the
  HiperSockets bridge succeed and leak/corrupt cross-guest.
* **fixed**: LINUX01 reduced to ``G``; the existing privilege-class enforcement
  denies DISPLAY/STORE HOST and an audit event (ICH408I-style) is cut.

Reference: Altmark & Bitner, *z/VM Security and Integrity* - altering host real
storage via ``CP STORE HOST`` is a privilege **class C** command; examining it is
**class E**.  IBM CP Planning & Administration warns class G alone is usually all
a Linux guest needs and that HiperSockets can cross the LPAR isolation boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple


# The Linux guest at the centre of the lab and the excess it is granted.
LAB_GUEST = "LINUX01"
VULN_CLASSES = "BCEG"     # over-granted: B real-device, C alter-storage, E examine
JEA_CLASSES = "G"         # Just Enough Authority for a Linux workload

# The classes each role actually needs (the audit baseline).  Anything held
# beyond this is "creep".
ROLE_BASELINE: Dict[str, str] = {
    "MAINT": "ABCDEFG",     # system maintenance legitimately holds everything
    "SYSADMIN": "ABCDEFG",  # (split-admin remediation is discussed in the doc)
    "OPERATOR": "ABDG",     # operator: FORCE/SHUTDOWN(A), spool(D), own VM(G), real(B)
    "OPERATNS": "ABDG",
    "DIRMAINT": "BG",
    "RACFVM": "BG",
    "TCPIP": "BG",
    "GUEST": "G",
    "DEMO": "G",
    "LINUX01": "G",         # a Linux guest needs only class G
    "LINUX02": "G",
}


@dataclass
class HostCell:
    """A region of **host real storage** holding a secret owned by some guest.

    Host real storage is shared by all guests; the privilege class is the only
    thing standing between a guest and another guest's secrets here.
    """
    addr: str            # real storage address, e.g. "021000"
    owner: str           # the guest whose secret lives here
    label: str
    value: str
    hipersocket: bool = False   # part of the IQD/HiperSockets frame buffer


# Secrets seeded into shared host real storage.  Deliberately cross-owner so a
# single over-privileged guest reading host storage leaks everyone.
HOST_STORAGE_SEED: List[HostCell] = [
    HostCell("021000", "RACFVM", "RACF database master key (in RACFVM nucleus buffer)",
             "RACFKEY=7F3A9C12E0B45D8A"),
    HostCell("048000", "MAINT", "MAINT logon material (clear in CP logon work area)",
             "MAINT:MAINT  AUTOLOG=YES"),
    HostCell("055000", "LINUX01", "LINUX01 root SSH private-key page",
             "ssh-rsa-priv:MIIBOgIBAAJBA..."),
    HostCell("0A4000", "TCPIP", "HiperSockets IQD frame buffer (LPAR-to-LPAR)",
             "IQD0.LP2 PAYLOAD: GACF/GACF -> CBSA", hipersocket=True),
    HostCell("0C2000", "DIRMAINT", "DirMaint directory password cache",
             "DIRM PW CACHE: LINUX01=ACCESS GUEST=GUEST"),
]


def host_store(state) -> Dict[str, HostCell]:
    """Live, per-run host real storage map (so STORE HOST edits persist)."""
    store = getattr(state, "zvm_host_storage", None)
    if store is None:
        store = {c.addr: replace(c) for c in HOST_STORAGE_SEED}
        try:
            state.zvm_host_storage = store
        except Exception:
            pass
    return store


# --------------------------------------------------------------------------- #
#  Remediation: apply Just Enough Authority to the live CP directory.
# --------------------------------------------------------------------------- #
def apply_remediation(directory, *, vulnerable: bool) -> None:
    """Ensure the lab guest exists and holds the right classes for the mode.

    Vulnerable -> over-granted ``BCEG``; fixed -> Just Enough Authority ``G``.
    Idempotent; safe to call on every session start.
    """
    from gibson.apps.zvm.cp_directory import VmGuest, Minidisk
    g = directory.get(LAB_GUEST)
    if g is None:
        directory.guests[LAB_GUEST] = VmGuest(
            LAB_GUEST, VULN_CLASSES if vulnerable else JEA_CLASSES,
            "256M", "512M", ["191", "200"],
            "Linux on IBM Z production guest", password="LINUX01")
        directory.guests[LAB_GUEST].minidisks = {
            "191": Minidisk("191", "LNX191", read_pw="ALL", write_pw="", cyls=50)}
    else:
        g.classes = VULN_CLASSES if vulnerable else JEA_CLASSES


# --------------------------------------------------------------------------- #
#  DISPLAY HOST (class E) - examine host real storage.
# --------------------------------------------------------------------------- #
def parse_host_addr(cmd: str) -> Optional[str]:
    """Extract a real-storage address from a DISPLAY/STORE HOST command, or None
    to mean 'the whole known map'.  Accepts ``HOST 021000``, ``H021000``."""
    toks = (cmd or "").upper().split()
    for t in toks[1:]:
        if t in ("HOST",):
            continue
        t2 = t[1:] if t.startswith("H") and len(t) > 1 else t
        t2 = t2.split(".")[0].split(",")[0]
        if t2 and all(ch in "0123456789ABCDEF" for ch in t2):
            return t2.zfill(6)
    return None


def examine_host(state, userid: str, cmd: str) -> Tuple[str, bool]:
    """DISPLAY HOST - return host real-storage contents.  The caller has already
    passed the class-E privilege check.  Returns (text, cross_guest_leak)."""
    store = host_store(state)
    addr = parse_host_addr(cmd)
    cells = ([store[addr]] if addr in store
             else list(store.values()) if addr is None else [])
    if not cells:
        if addr is not None:
            return (f"DISPLAY HOST {addr}\n{addr}  00000000 00000000 00000000 00000000\n"
                    f"  (no tagged content at this real address)"), False
        return "DISPLAY HOST: no host storage tagged in the lab map", False
    leak = any(c.owner != userid for c in cells)
    out = ["DISPLAY HOST  (CP privilege class E - examine host real storage)"]
    for c in cells:
        flag = "  <== NOT YOUR GUEST" if c.owner != userid else ""
        out.append(f"R{c.addr}  OWNER={c.owner:<8}{flag}")
        out.append(f"          {c.label}")
        out.append(f"          {c.value}")
    return "\n".join(out), leak


def alter_host(state, userid: str, cmd: str) -> Tuple[str, bool]:
    """STORE HOST addr value - alter host real storage (class C).  Returns
    (text, cross_guest_write)."""
    store = host_store(state)
    addr = parse_host_addr(cmd)
    if addr is None or addr not in store:
        target = addr or "?"
        return (f"STORE HOST {target}\n"
                f"HCPxxx Host real storage at {target} altered (untagged region).", False)
    cell = store[addr]
    # everything after the address token becomes the new value
    up = cmd.upper()
    pos = up.find(addr) if addr in up else -1
    new_val = cmd[pos + len(addr):].strip() if pos >= 0 else "CORRUPTED"
    new_val = new_val or "CORRUPTED-BY-" + userid
    cross = cell.owner != userid
    old_owner = cell.owner
    cell.value = new_val
    msg = ["STORE HOST  (CP privilege class C - alter host real storage)",
           f"R{addr}  OWNER={old_owner}  <- overwritten by {userid}",
           f"          was: {cell.label}",
           f"          now: {new_val}"]
    if cross:
        msg.append(f"          *** cross-guest write: {userid} just corrupted "
                   f"{old_owner}'s memory ***")
    return "\n".join(msg), cross


# --------------------------------------------------------------------------- #
#  HiperSockets isolation.
# --------------------------------------------------------------------------- #
def hipersockets_status(directory, *, vulnerable: bool) -> str:
    g = directory.get(LAB_GUEST)
    has_net = bool(g and ("B" in g.classes.upper()))
    lines = ["QUERY HIPERSOCKETS  (IQD virtual LAN)",
             "IQD0  CHPID E0  TYPE IQD  FRAMESIZE 16K"]
    if vulnerable and has_net:
        lines += [
            "  LPAR REACH : LP1(this), LP2(CBSA/GACF), LP3(PAYROLL)",
            "  *** LINUX01 holds the network class and the IQD bridges LPARs:",
            "      traffic crosses the PR/SM (LPAR) EAL5+ isolation boundary.",
            "      A guest on LP1 can reach services isolated on LP2/LP3."]
    else:
        lines += [
            "  LPAR REACH : LP1(this) only",
            "  IQD confined to this LPAR; PR/SM isolation boundary intact."]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Privilege-class-creep audit.
# --------------------------------------------------------------------------- #
def over_granted(directory) -> List[Tuple[str, str, str, str]]:
    """Return (userid, held, baseline, excess) for every guest holding classes
    beyond its role baseline."""
    rows: List[Tuple[str, str, str, str]] = []
    for uid in sorted(directory.guests):
        g = directory.guests[uid]
        held = (g.classes or "G").upper()
        base = ROLE_BASELINE.get(uid, "G").upper()
        excess = "".join(c for c in held if c not in base)
        if excess:
            rows.append((uid, held, base, excess))
    return rows


def audit_report(directory) -> str:
    rows = over_granted(directory)
    out = ["CP PRIVILEGE-CLASS CREEP AUDIT",
           "------------------------------------------------------------",
           "GUEST     HELD      BASELINE  EXCESS  RISK"]
    risk = {"A": "system control", "B": "real device/network", "C": "alter host storage",
            "D": "other-user spool", "E": "examine host storage", "F": "device diag"}
    if not rows:
        out.append("(none) - every guest holds Just Enough Authority.")
    for uid, held, base, excess in rows:
        why = ", ".join(risk.get(c, c) for c in excess)
        out.append(f"{uid:<9} {held:<9} {base:<9} {excess:<7} {why}")
    out += ["------------------------------------------------------------",
            "Remediation: reduce each guest to its baseline (Just Enough",
            "Authority) and split the single all-class admin into separate",
            "hypervisor-admin and storage-admin roles."]
    return "\n".join(out)
