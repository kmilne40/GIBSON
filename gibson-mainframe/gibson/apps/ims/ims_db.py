"""IMS DB learning module: a hierarchical database (DBD), a program view (PSB/PCB)
and a small DL/I call processor (GU / GN / GNP / ISRT / REPL / DLET).

This is the *learning* half of the IMS work - it teaches the hierarchical data
model and the DL/I call interface rather than a security control.  It is driven
from the same ``IMS`` command family:

    IMS DBD [name]                 show the database definition (segment hierarchy)
    IMS PSB [name]                 show the program spec block (PCBs / PROCOPT)
    IMS DLI GU  PART(PARTNO=P200)  get unique (direct, qualified by SSA)
    IMS DLI GN  [SEG] [SSA]        get next in hierarchical sequence
    IMS DLI GNP [SEG]              get next within parent
    IMS DLI ISRT PART(PARTNO=P400,DESC=WIDGET,TYPE=ROUND)
    IMS DLI REPL (QTY=0099)        replace the current segment
    IMS DLI DLET                   delete the current segment
    IMS DLI STATUS                 show current position + last status code

The database (PARTSDB) is the classic parts hierarchy:

    PART  (root, key PARTNO)
      |__ STOCK (key WHSE)
      |__ ORDER (key ORDNO)

PCB status codes returned in the panel mirror DL/I: blank = success, ``GE`` =
segment not found, ``GB`` = end of database, ``GP`` = no parent established,
``II`` = duplicate insert, ``AM``/``AD`` = call disallowed by PROCOPT.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------- #
#  DBD - segment hierarchy
# --------------------------------------------------------------------------- #
@dataclass
class SegType:
    name: str
    parent: Optional[str]
    key: str                       # key field name
    fields: list                   # ordered field names (incl. key)


_DBD_NAME = "PARTSDB"
_SEGS = {
    "PART":  SegType("PART", None, "PARTNO", ["PARTNO", "DESC", "TYPE"]),
    "STOCK": SegType("STOCK", "PART", "WHSE", ["WHSE", "QTY", "LOC"]),
    "ORDER": SegType("ORDER", "PART", "ORDNO", ["ORDNO", "QTY", "STATUS"]),
}
# child types in hierarchical (DBD) order under each parent
_CHILDREN = {"PART": ["STOCK", "ORDER"]}


@dataclass
class Occ:
    """A segment occurrence."""
    seg: str
    fields: dict
    children: dict = field(default_factory=dict)   # childtype -> list[Occ]

    @property
    def key(self):
        return self.fields.get(_SEGS[self.seg].key, "")


@dataclass
class ImsDb:
    roots: list = field(default_factory=list)      # list[Occ] (PART occurrences)
    # DL/I position state, per the PCB
    pos_path: list = field(default_factory=list)   # list[Occ] root..current
    last_status: str = "  "
    psb: str = "PARTPSB"
    procopt: str = "A"             # A=all, G=get-only (set by IMS PSB use)


def _seed_db() -> ImsDb:
    def part(no, desc, typ, stocks, orders):
        o = Occ("PART", {"PARTNO": no, "DESC": desc, "TYPE": typ})
        o.children["STOCK"] = [Occ("STOCK", {"WHSE": w, "QTY": q, "LOC": l}) for (w, q, l) in stocks]
        o.children["ORDER"] = [Occ("ORDER", {"ORDNO": n, "QTY": q, "STATUS": s}) for (n, q, s) in orders]
        return o
    db = ImsDb()
    db.roots = [
        part("P100", "BEARING", "ROUND",
             [("W01", "0083", "A12"), ("W02", "0012", "B07")],
             [("O5001", "0050", "OPEN")]),
        part("P200", "GASKET", "FLAT",
             [("W01", "0200", "C03")],
             []),
        part("P300", "VALVE", "ROUND",
             [],
             [("O5002", "0010", "SHIPPED")]),
    ]
    return db


def get_ims_db(state: Any) -> ImsDb:
    db = getattr(state, "ims_db", None)
    if db is not None:
        return db
    db = _seed_db()
    try:
        state.ims_db = db
    except Exception:
        pass
    return db


# --------------------------------------------------------------------------- #
#  Hierarchical sequence (preorder) for GN
# --------------------------------------------------------------------------- #
def _preorder(db: ImsDb):
    """Yield (occ, path) in IMS hierarchical sequence."""
    seq = []
    for root in db.roots:
        seq.append((root, [root]))
        for ct in _CHILDREN.get("PART", []):
            for child in root.children.get(ct, []):
                seq.append((child, [root, child]))
    return seq


# --------------------------------------------------------------------------- #
#  SSA parsing:  SEG(FIELD=VALUE,FIELD=VALUE)
# --------------------------------------------------------------------------- #
def _parse_ssas(text: str):
    """Return list of (segname, {field:value}).  Unqualified -> ({},)."""
    ssas = []
    i = 0
    text = text.strip()
    tokens = []
    # split on whitespace but keep SEG(...) together
    depth = 0
    cur = ""
    for ch in text:
        if ch == "(":
            depth += 1; cur += ch
        elif ch == ")":
            depth -= 1; cur += ch
        elif ch == " " and depth == 0:
            if cur:
                tokens.append(cur); cur = ""
        else:
            cur += ch
    if cur:
        tokens.append(cur)
    for tok in tokens:
        if "(" in tok and tok.endswith(")"):
            name = tok[:tok.index("(")].upper()
            inner = tok[tok.index("(") + 1:-1]
            quals = {}
            for part in inner.split(","):
                if "=" in part:
                    f, _, v = part.partition("=")
                    quals[f.strip().upper()] = v.strip().upper()
            ssas.append((name, quals))
        else:
            ssas.append((tok.upper(), {}))
    return ssas


def _match(occ: Occ, quals: dict) -> bool:
    for f, v in quals.items():
        if str(occ.fields.get(f, "")).upper() != v:
            return False
    return True


def _fmt_occ(occ: Occ) -> str:
    st = _SEGS[occ.seg]
    return f"{occ.seg:<6} " + "  ".join(f"{f}={occ.fields.get(f,'')}" for f in st.fields)


# --------------------------------------------------------------------------- #
#  DL/I calls
# --------------------------------------------------------------------------- #
def _gu(db: ImsDb, ssas) -> tuple:
    """Get Unique: navigate the path described by the SSAs to a single segment."""
    if not ssas:
        return None, "GE"
    # walk down the hierarchy following each SSA
    current_level = db.roots
    path = []
    occ = None
    for (segname, quals) in ssas:
        found = None
        for cand in current_level:
            if cand.seg == segname and _match(cand, quals):
                found = cand
                break
        if found is None:
            return None, "GE"
        path.append(found)
        occ = found
        # descend into this segment's children (flatten all child types in order)
        nxt = []
        for ct in _CHILDREN.get(found.seg, []):
            nxt.extend(found.children.get(ct, []))
        current_level = nxt
    db.pos_path = path
    return occ, "  "


def _gn(db: ImsDb, ssas) -> tuple:
    """Get Next in hierarchical sequence (optionally of a given segment type)."""
    seq = _preorder(db)
    want = ssas[0][0] if ssas else None
    want_quals = ssas[0][1] if ssas else {}
    # find current position index
    cur = db.pos_path[-1] if db.pos_path else None
    start = 0
    if cur is not None:
        for idx, (occ, _p) in enumerate(seq):
            if occ is cur:
                start = idx + 1
                break
    for occ, p in seq[start:]:
        if want and occ.seg != want:
            continue
        if want_quals and not _match(occ, want_quals):
            continue
        db.pos_path = p
        return occ, "  "
    return None, "GB"


def _gnp(db: ImsDb, ssas) -> tuple:
    """Get Next within Parent: children of the current established parent."""
    if not db.pos_path:
        return None, "GP"
    # parent = current position's parent if current is a child, else current
    if len(db.pos_path) >= 2:
        parent = db.pos_path[-2]
        cur = db.pos_path[-1]
    else:
        parent = db.pos_path[-1]
        cur = None
    kids = []
    for ct in _CHILDREN.get(parent.seg, []):
        kids.extend(parent.children.get(ct, []))
    want = ssas[0][0] if ssas else None
    started = cur is None
    for k in kids:
        if not started:
            if k is cur:
                started = True
            continue
        if want and k.seg != want:
            continue
        db.pos_path = [parent, k]
        return k, "  "
    return None, "GE"


def _isrt(db: ImsDb, ssas) -> tuple:
    if db.procopt == "G":
        return None, "AM"        # insert not allowed by PROCOPT=G
    if not ssas:
        return None, "AD"
    segname, quals = ssas[-1]
    st = _SEGS.get(segname)
    if st is None:
        return None, "AD"
    newocc = Occ(segname, {f: quals.get(f, "") for f in st.fields})
    if segname == "PART":
        if any(r.key == newocc.key for r in db.roots):
            return None, "II"
        newocc.children = {ct: [] for ct in _CHILDREN.get("PART", [])}
        db.roots.append(newocc)
        db.roots.sort(key=lambda o: o.key)
        db.pos_path = [newocc]
        return newocc, "  "
    # child insert: needs an established parent (PART)
    parent = db.pos_path[0] if db.pos_path else None
    if parent is None or parent.seg != "PART":
        return None, "GP"
    siblings = parent.children.setdefault(segname, [])
    if any(s.key == newocc.key for s in siblings):
        return None, "II"
    siblings.append(newocc)
    siblings.sort(key=lambda o: o.key)
    db.pos_path = [parent, newocc]
    return newocc, "  "


def _repl(db: ImsDb, ssas) -> tuple:
    if db.procopt == "G":
        return None, "AM"
    if not db.pos_path:
        return None, "GE"
    occ = db.pos_path[-1]
    # replace fields from a single (FIELD=VALUE,...) qualifier (any seg name)
    quals = ssas[0][1] if ssas else {}
    st = _SEGS[occ.seg]
    for f, v in quals.items():
        if f in st.fields and f != st.key:    # cannot change the key
            occ.fields[f] = v
    return occ, "  "


def _dlet(db: ImsDb, ssas) -> tuple:
    if db.procopt == "G":
        return None, "AM"
    if not db.pos_path:
        return None, "GE"
    occ = db.pos_path[-1]
    if occ.seg == "PART":
        db.roots = [r for r in db.roots if r is not occ]
    else:
        parent = db.pos_path[-2]
        lst = parent.children.get(occ.seg, [])
        parent.children[occ.seg] = [s for s in lst if s is not occ]
    db.pos_path = []
    return occ, "  "


_CALLS = {"GU": _gu, "GN": _gn, "GNP": _gnp, "ISRT": _isrt, "REPL": _repl, "DLET": _dlet}
_STATUS_TEXT = {
    "  ": "SUCCESSFUL", "GE": "SEGMENT NOT FOUND", "GB": "END OF DATABASE",
    "GP": "NO PARENT ESTABLISHED", "II": "DUPLICATE SEGMENT", "AM": "CALL DISALLOWED BY PROCOPT",
    "AD": "INVALID SSA / SEGMENT NAME",
}


# --------------------------------------------------------------------------- #
#  Rendering
# --------------------------------------------------------------------------- #
def _show_dbd() -> str:
    lines = [f" DBD {_DBD_NAME}  ACCESS=HDAM  (hierarchical parts database)",
             " -------------------------------------------------------------------------------",
             "   SEGMENT   PARENT    KEY FIELD   FIELDS"]
    for s in _SEGS.values():
        lines.append(f"   {s.name:<10}{(s.parent or '(root)'):<10}{s.key:<12}{', '.join(s.fields)}")
    lines += ["",
              "   Hierarchy:",
              "     PART  (root, key PARTNO)",
              "       |__ STOCK (key WHSE)",
              "       |__ ORDER (key ORDNO)"]
    return "\n".join(lines)


def _show_psb(db: ImsDb) -> str:
    return "\n".join([
        f" PSB {db.psb}   LANG=COBOL",
        " -------------------------------------------------------------------------------",
        f"   PCB TYPE=DB  DBDNAME={_DBD_NAME}  PROCOPT={db.procopt}  KEYLEN=14",
        "     SENSEG  NAME=PART,   PARENT=0",
        "     SENSEG  NAME=STOCK,  PARENT=PART",
        "     SENSEG  NAME=ORDER,  PARENT=PART",
        "",
        "   PROCOPT A = all (GU/GN/GNP/ISRT/REPL/DLET).  Use 'IMS PSB GET' for a",
        "   read-only (PROCOPT=G) view that rejects ISRT/REPL/DLET with status AM.",
    ])


def _show_status(db: ImsDb) -> str:
    pos = " -> ".join(f"{o.seg}({o.key})" for o in db.pos_path) if db.pos_path else "(none)"
    return (f" DL/I POSITION : {pos}\n"
            f" LAST STATUS   : '{db.last_status}'  {_STATUS_TEXT.get(db.last_status, '')}\n"
            f" PSB {db.psb}  PROCOPT={db.procopt}")


def _call_result(db: ImsDb, call: str, occ: Optional[Occ], status: str) -> str:
    db.last_status = status
    head = f" DL/I {call}   STATUS='{status}'  {_STATUS_TEXT.get(status, '')}"
    if occ is not None and status == "  ":
        io = _fmt_occ(occ)
        path = " -> ".join(f"{o.seg}({o.key})" for o in db.pos_path)
        return f"{head}\n   I/O AREA: {io}\n   POSITION: {path}"
    return head


# --------------------------------------------------------------------------- #
#  Command entry (called from ims_command for DB / DBD / PSB / DLI verbs)
# --------------------------------------------------------------------------- #
def dli_command(state: Any, userid: str, body: str) -> str:
    db = get_ims_db(state)
    raw = (body or "").strip()
    ub = raw.upper()

    if ub in ("DB", "DLI", "DL/I", "DB MENU", "DLI MENU"):
        return "\n".join([
            " IMS DB / DL/I  -  HIERARCHICAL DATABASE LAB",
            " -------------------------------------------------------------------------------",
            f"   Database {_DBD_NAME}: PART -> (STOCK, ORDER).  PSB {db.psb} PROCOPT={db.procopt}.",
            "",
            "     IMS DBD                         show the database definition",
            "     IMS PSB [GET|ALL]               show / set the program view (PROCOPT)",
            "     IMS DLI GU  PART(PARTNO=P200)   get unique (qualified)",
            "     IMS DLI GU  PART(PARTNO=P100) STOCK(WHSE=W02)   qualified path",
            "     IMS DLI GN  [SEG]               get next in hierarchical sequence",
            "     IMS DLI GNP [SEG]               get next within parent",
            "     IMS DLI ISRT PART(PARTNO=P400,DESC=WIDGET,TYPE=ROUND)",
            "     IMS DLI REPL (QTY=0099)         replace current segment",
            "     IMS DLI DLET                    delete current segment",
            "     IMS DLI STATUS                  current position + last status code",
        ])
    if ub == "DBD" or ub.startswith("DBD "):
        return _show_dbd()
    if ub == "PSB" or ub.startswith("PSB"):
        arg = ub[3:].strip()
        if arg in ("GET", "G"):
            db.procopt = "G"
            return f"PSB {db.psb} now PROCOPT=G (get-only); ISRT/REPL/DLET will return AM.\n\n" + _show_psb(db)
        if arg in ("ALL", "A"):
            db.procopt = "A"
            return f"PSB {db.psb} now PROCOPT=A (all calls allowed).\n\n" + _show_psb(db)
        return _show_psb(db)

    # DL/I calls:  DLI <CALL> <SSAs>   (the leading DLI is optional)
    if ub.startswith("DLI"):
        raw = raw[3:].strip()
        ub = raw.upper()
    parts = raw.split(None, 1)
    call = parts[0].upper() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    if call == "STATUS":
        return _show_status(db)
    if call in _CALLS:
        occ, status = _CALLS[call](db, _parse_ssas(rest))
        return _call_result(db, call, occ, status)
    return ("DFS1292E  UNRECOGNISED IMS DB REQUEST - try IMS DB, IMS DBD, IMS PSB, "
            "IMS DLI GU PART(PARTNO=P100)")
