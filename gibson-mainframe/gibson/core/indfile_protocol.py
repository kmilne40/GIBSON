from __future__ import annotations

"""Bounded Gibson IND$FILE protocol helpers.

The command-mode path is fully supported. Native x3270/c3270 structured-field
Transfer() compatibility is intentionally staged: Gibson detects common
Transfer() option text and maps it to the same safe transfer engine. Full
byte-perfect 3270 structured-field emulation remains documented as a
compatibility boundary unless validated with client tooling.
"""

from typing import Any

from gibson.core.indfile_options import parse_options
from gibson.core.transfers import get_transfer_manager


def detect_transfer_command(text: str) -> bool:
    u = (text or "").upper()
    return "IND$FILE" in u or "TRANSFER(" in u or "DIRECTION=SEND" in u or "DIRECTION=RECEIVE" in u


def handle_typed_transfer(state: Any, userid: str, text: str) -> str:
    opts = parse_options(text)
    mgr = get_transfer_manager(state)
    dsn = opts.host_file or opts.local_file
    meta = {
        "MODE": opts.mode,
        "CR": opts.cr,
        "EXIST": opts.exist,
        "RECFM": opts.recfm,
        "LRECL": str(opts.lrecl),
        "BLKSIZE": str(opts.blksize),
    }
    if opts.direction == "GET":
        filename, data = mgr.indfile_get(userid, dsn, note="X3270-TYPED", options=meta)
        target = mgr.write_local(opts.local_file or filename, data)
        xmode = "BINARY" if opts.mode.upper() == "BINARY" else "ASCII"
        crn = "CRLF" if str(opts.cr).upper() in ("ADD", "CRLF") else ("NOCRLF" if str(opts.cr).upper() == "REMOVE" else "AS-IS")
        return ("\n".join([
            f"IND$FILE GET STARTED - DATASET({dsn.upper()}) MODE({xmode}) {crn}",
            f"TRANS03 {len(data)} BYTES TRANSFERRED FROM HOST",
            f"IND$FILE004I TRANSFER COMPLETE DIRECTION(GET) DATASET({dsn.upper()}) "
            f"LOCAL({target}) BYTES({len(data)})",
        ]))
    data = mgr.read_local(opts.local_file)
    info = mgr.indfile_put(userid, dsn, data, note="X3270-TYPED", options=meta)
    xmode = "BINARY" if opts.mode.upper() == "BINARY" else "ASCII"
    crn = "CRLF" if str(opts.cr).upper() in ("REMOVE", "CRLF") else "AS-IS"
    return ("\n".join([
        f"IND$FILE PUT STARTED - LOCAL({opts.local_file}) MODE({xmode}) {crn}",
        f"TRANS03 {info['bytes']} BYTES TRANSFERRED TO HOST",
        f"IND$FILE004I TRANSFER COMPLETE DIRECTION(PUT) DATASET({info['target']}) "
        f"BYTES({info['bytes']})",
    ]))
