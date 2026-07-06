"""CMS file system + command engine for the Gibson z/VM session.

Gives the z/VM CMS prompt a real per-user A-disk (filemode A1) and the core CMS
file commands, so a student can actually create, list, copy, rename, type, erase
and run files rather than seeing canned screens.

`cms_command(state, userid, line)` returns the full CMS response text (including
the trailing ``Ready;`` line) for the file commands it handles, or ``None`` for
commands the session itself owns (IPL / CP / LOGOFF / FILELIST panel / XEDIT).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CmsFile:
    fn: str
    ft: str
    fm: str = "A1"
    recfm: str = "V"
    lrecl: int = 80
    records: List[str] = field(default_factory=list)
    date: str = "2026-06-24 09:00:00"


@dataclass
class CmsDisk:
    files: Dict[Tuple[str, str], CmsFile] = field(default_factory=dict)
    accessed: Dict[str, str] = field(default_factory=dict)   # fm -> "vaddr R/W"


def _time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _ready(rc: int = 0) -> str:
    if rc:
        return f"Ready({rc:05d}); T=0.01/0.01 {_time()}"
    return f"Ready; T=0.01/0.01 {_time()}"


def _seed_disk() -> CmsDisk:
    d = CmsDisk()
    d.accessed = {"A": "191 R/W", "S": "190 R/O", "Y": "19E R/O"}
    files = [
        CmsFile("PROFILE", "EXEC", "A1", records=[
            "/* CMS PROFILE EXEC */", "'CP SET EMSG ON'",
            "say 'Welcome to z/VM CMS,' userid()", "exit 0"]),
        CmsFile("HELLO", "REXX", "A1", records=[
            "/* HELLO REXX */", "say 'Hello from z/VM CMS!'",
            "say 'Today is' date()", "exit 0"]),
        CmsFile("NOTEBOOK", "NOTEBOOK", "A1", records=["* personal notebook *"]),
        CmsFile("CMSLIB", "MACLIB", "S2", recfm="F", lrecl=80, records=["(macro library)"]),
    ]
    for f in files:
        d.files[(f.fn, f.ft)] = f
    return d


def get_cms_disk(state: Any, userid: str) -> CmsDisk:
    store = getattr(state, "zvm_cms", None)
    if store is None:
        store = {}
        try:
            state.zvm_cms = store
        except Exception:
            pass
    key = userid.upper()
    if key not in store:
        store[key] = _seed_disk()
    return store[key]


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _resolve(disk: CmsDisk, fn: str, ft: str) -> Optional[CmsFile]:
    return disk.files.get((fn.upper(), ft.upper()))


def _fmt_listing(files: List[CmsFile], with_header: bool, dateopt: bool) -> List[str]:
    out: List[str] = []
    if with_header:
        out.append("FILENAME FILETYPE FM   FORMAT LRECL  RECS BLOCKS DATE       TIME")
    for f in sorted(files, key=lambda x: (x.fn, x.ft)):
        recs = len(f.records)
        if with_header or dateopt:
            out.append(f"{f.fn:<8} {f.ft:<8} {f.fm:<4} {f.recfm:<6} {f.lrecl:>5} {recs:>5} "
                       f"{max(1, recs // 20):>6} {f.date[:10]} {f.date[11:]}")
        else:
            out.append(f"{f.fn:<8} {f.ft:<8} {f.fm}")
    return out


# --------------------------------------------------------------------------- #
#  Command engine
# --------------------------------------------------------------------------- #
def cms_command(state: Any, userid: str, line: str) -> Optional[str]:
    raw = (line or "").strip()
    if not raw:
        return None
    toks = raw.split()
    verb = toks[0].upper()
    args = toks[1:]
    disk = get_cms_disk(state, userid)

    # split off "( options" tail
    opts: List[str] = []
    if "(" in args:
        idx = args.index("(")
        opts = [a.upper() for a in args[idx + 1:]]
        args = args[:idx]
    elif args and args[-1].startswith("("):
        opts = [args[-1][1:].upper()] if len(args[-1]) > 1 else []
        args = args[:-1]

    if verb in ("LISTFILE", "LISTF", "LF"):
        pat_fn = args[0].upper() if len(args) > 0 else "*"
        pat_ft = args[1].upper() if len(args) > 1 else "*"
        hits = [f for f in disk.files.values()
                if (pat_fn in ("*", f.fn) or pat_fn == f.fn)
                and (pat_ft in ("*", f.ft) or pat_ft == f.ft)]
        if not hits:
            return "DMSLST002E FILE NOT FOUND.\n" + _ready(28)
        header = "FILELIST" in opts or "ALLOC" in opts or "DATE" in opts or "LABEL" in opts
        body = _fmt_listing(hits, header, "DATE" in opts)
        return "\n".join(body) + "\n" + _ready()

    if verb in ("TYPE", "T"):
        if len(args) < 2:
            return "DMSTYP002E SYNTAX: TYPE FN FT [FM]\n" + _ready(24)
        f = _resolve(disk, args[0], args[1])
        if f is None:
            return f"DMSTYP002E FILE '{args[0].upper()} {args[1].upper()}' NOT FOUND.\n" + _ready(28)
        return "\n".join(f.records) + ("\n" if f.records else "") + _ready()

    if verb == "COPYFILE" or verb == "COPY":
        if len(args) < 6:
            return "DMSCPY002E SYNTAX: COPYFILE FN1 FT1 FM1 FN2 FT2 FM2\n" + _ready(24)
        src = _resolve(disk, args[0], args[1])
        if src is None:
            return f"DMSCPY002E FILE '{args[0].upper()} {args[1].upper()}' NOT FOUND.\n" + _ready(28)
        nf = CmsFile(args[3].upper(), args[4].upper(), args[5].upper(),
                     recfm=src.recfm, lrecl=src.lrecl, records=list(src.records))
        disk.files[(nf.fn, nf.ft)] = nf
        return _ready()

    if verb in ("RENAME", "REN"):
        if len(args) < 6:
            return "DMSRNM002E SYNTAX: RENAME FN1 FT1 FM1 FN2 FT2 FM2\n" + _ready(24)
        src = _resolve(disk, args[0], args[1])
        if src is None:
            return f"DMSRNM002E FILE '{args[0].upper()} {args[1].upper()}' NOT FOUND.\n" + _ready(28)
        del disk.files[(src.fn, src.ft)]
        src.fn, src.ft, src.fm = args[3].upper(), args[4].upper(), args[5].upper()
        disk.files[(src.fn, src.ft)] = src
        return _ready()

    if verb in ("ERASE", "DISCARD", "DEL"):
        if len(args) < 2:
            return "DMSERS002E SYNTAX: ERASE FN FT [FM]\n" + _ready(24)
        key = (args[0].upper(), args[1].upper())
        if key not in disk.files:
            return f"DMSERS002E FILE '{args[0].upper()} {args[1].upper()}' NOT FOUND.\n" + _ready(28)
        del disk.files[key]
        return _ready()

    if verb == "STATE" or verb == "STATEW":
        if len(args) < 2:
            return "DMSSTT002E SYNTAX: STATE FN FT\n" + _ready(24)
        f = _resolve(disk, args[0], args[1])
        if f is None:
            return f"DMSSTT002E FILE '{args[0].upper()} {args[1].upper()}' NOT FOUND.\n" + _ready(28)
        return _ready()

    if verb in ("ACCESS", "ACC"):
        vaddr = args[0].upper() if args else "191"
        fm = (args[1].upper() if len(args) > 1 else "A").rstrip("1234567890") or "A"
        fm = fm[0]
        disk.accessed[fm] = f"{vaddr} R/W" if fm == "A" else f"{vaddr} R/O"
        return f"{vaddr} {fm} ({'R/W' if fm == 'A' else 'R/O'})\n" + _ready()

    if verb in ("RELEASE", "REL"):
        fm = (args[0].upper()[0] if args else "")
        if fm and fm in disk.accessed and fm != "A":
            del disk.accessed[fm]
            return _ready()
        return "DMSARE002E DISK NOT ACCESSED OR CANNOT RELEASE A-DISK\n" + _ready(36)

    if verb == "QUERY" or verb == "Q":
        sub = args[0].upper() if args else ""
        if sub in ("DISK", "DISKS"):
            lines = ["LABEL  VDEV M STAT CYL TYPE BLKSZ FILES BLKS USED-(%)"]
            for fm, info in sorted(disk.accessed.items()):
                vaddr, mode = info.split()
                nfiles = sum(1 for f in disk.files.values() if f.fm.startswith(fm))
                lines.append(f"CMS{fm}01 {vaddr:<4} {fm} {mode:<4} 010 3390 4096 {nfiles:>5}  200  17")
            return "\n".join(lines) + "\n" + _ready()
        if sub == "SEARCH":
            order = " ".join(f"CMS{fm}01 {info.split()[0]} {fm} {info.split()[1]}"
                             for fm, info in sorted(disk.accessed.items()))
            return order + "\n" + _ready()
        return None   # other QUERY subcommands handled by CP layer

    if verb in ("EXEC", "X") or (len(args) == 0 and
                                 (_resolve(disk, verb, "EXEC") or _resolve(disk, verb, "REXX"))):
        # EXEC fn   OR   bare fn that matches fn EXEC
        target = args[0].upper() if (verb in ("EXEC", "X") and args) else verb
        f = _resolve(disk, target, "EXEC") or _resolve(disk, target, "REXX")
        if f is None:
            return f"DMSEXC002E EXEC '{target}' NOT FOUND.\n" + _ready(28)
        out: List[str] = []
        for rec in f.records:
            s = rec.strip()
            up = s.upper()
            if up.startswith("SAY "):
                expr = s[4:].strip()
                txt = expr
                if expr.startswith("'") and "'" in expr[1:]:
                    txt = expr[1:expr.index("'", 1)]
                    tail = expr[expr.index("'", 1) + 1:].strip()
                    if "USERID()" in tail.upper():
                        txt += " " + userid.upper()
                elif expr.upper() == "DATE()":
                    txt = datetime.now().strftime("%d %b %Y").upper()
                else:
                    txt = expr.strip("'\"")
                    if "DATE()" in expr.upper():
                        txt = datetime.now().strftime("%d %b %Y").upper()
                    if "USERID()" in expr.upper():
                        txt = userid.upper()
                out.append(txt)
        return ("\n".join(out) + ("\n" if out else "")) + _ready()

    if verb == "HELP":
        return ("CMS file commands: LISTFILE, TYPE, COPYFILE, RENAME, ERASE, STATE,\n"
                "ACCESS, RELEASE, QUERY DISK|SEARCH, EXEC, XEDIT, FILELIST, RDRLIST.\n"
                + _ready())

    if verb == "FINIS":
        return _ready()

    return None    # not a CMS file command -> let the session handle it
