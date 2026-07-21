from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class IndFileOptions:
    direction: str = "GET"
    host: str = "TSO"
    host_file: str = ""
    local_file: str = "DESKTOP.FILE"
    mode: str = "ASCII"
    cr: str = "KEEP"
    exist: str = "REPLACE"
    recfm: str = "FB"
    lrecl: int = 80
    blksize: int = 6160


def parse_options(text: str) -> IndFileOptions:
    opts: dict[str, str] = {}
    for k, v in re.findall(r"\b([A-Z$]+)\(([^)]*)\)", text or "", re.I):
        opts[k.upper()] = v.strip().strip("'").strip('"')
    for k, v in re.findall(r"\b([A-Za-z]+)=([^,\s)]+)", text or ""):
        opts[k.upper()] = v.strip().strip("'").strip('"')
    u = (text or "").upper()
    direction = "PUT" if any(x in u for x in [" PUT", " SEND", "DIRECTION=SEND"]) else "GET"
    lrecl = int(opts.get("LRECL", "80") or 80)
    blksize = int(opts.get("BLKSIZE", "6160") or 6160)
    # Canonical IND$FILE client syntax uses bare keywords, e.g.
    #   IND$FILE GET FOO.TEXT A:FOO.TXT ASCII CRLF
    # Honour those in addition to the MODE(...)/CR(...) forms.
    tokens = re.findall(r"\b([A-Z]+)\b", u)
    mode = opts.get("MODE", "").upper()
    if not mode:
        mode = "BINARY" if "BINARY" in tokens else "ASCII"
    cr = opts.get("CR", "").upper()
    if not cr:
        if "NOCRLF" in tokens or "NOCR" in tokens:
            cr = "REMOVE"
        elif "CRLF" in tokens:
            cr = "CRLF"     # direction-aware line-ending translation (resolved below)
        else:
            cr = "KEEP"
    return IndFileOptions(
        direction=direction,
        host=opts.get("HOST", "TSO").upper(),
        host_file=opts.get("DSN") or opts.get("DATASET") or opts.get("HOSTFILE") or "",
        local_file=opts.get("LOCAL") or opts.get("LOCALFILE") or "DESKTOP.FILE",
        mode=mode,
        cr=cr,
        exist=opts.get("EXIST", "REPLACE").upper(),
        recfm=opts.get("RECFM", "FB").upper(),
        lrecl=lrecl,
        blksize=blksize,
    )
