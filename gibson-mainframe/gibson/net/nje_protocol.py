"""NJE (Network Job Entry) TCP handshake codec - the 33-byte OPEN/ACK/NAK record.

Matches the wire format used by Soldier of Fortran's NJElib and the nmap
``nje-node-brute`` / ``nje-pass-brute`` scripts, whose OPEN template is::

    openNJEfmt = "\\xd6\\xd7\\xc5\\xd5@@@@%s\\0\\0\\0\\0%s\\0\\0\\0\\0\\0"
                  O   P   E   N  (sp*4) RHOST  RIP=0  OHOST  OIP=0  R=0

i.e. a 33-byte record laid out as (this is the order in Table 10-2 of the
chapter; the Listing 10-6 column labels are transposed):

    TYPE(8 EBCDIC)  RHOST(8 EBCDIC)  RIP(4)  OHOST(8 EBCDIC)  OIP(4)  R(1)

OHOST is the target node being probed; RHOST is the node the caller claims to
be. The server answers with the same 33-byte shape, TYPE set to ACK or NAK and
the reason byte R set to:

    0x01  OHOST unknown / invalid          (node does not exist)
    0x04  OHOST valid but RHOST unauthorised (confirms OHOST exists)
    0x00  OHOST and RHOST both valid        (full ACK)

This R-byte side-channel is exactly what nje-node-brute reads to enumerate node
names without authentication.
"""
from __future__ import annotations

import struct
from typing import Dict, Optional, Tuple

EBCDIC = "cp037"
RECORD_LEN = 33

R_OK = 0x00
R_UNKNOWN_OHOST = 0x01
R_BAD_RHOST = 0x04


def ebcdic8(text: str) -> bytes:
    """Upper-case, 8 bytes, EBCDIC, space (0x40) padded."""
    return text.upper()[:8].ljust(8).encode(EBCDIC, errors="replace")


def from_ebcdic(raw: bytes) -> str:
    return raw.decode(EBCDIC, errors="replace").strip()


def parse_open(data: bytes) -> Optional[dict]:
    """Parse a 33-byte NJE record; return its fields or None if not a record."""
    if not data or len(data) < RECORD_LEN:
        return None
    return {
        "type": from_ebcdic(data[0:8]),
        "rhost": from_ebcdic(data[8:16]),
        "rip": data[16:20],
        "ohost": from_ebcdic(data[20:28]),
        "oip": data[28:32],
        "r": data[32],
    }


def build_record(rtype: str, *, rhost: str, rip: bytes, ohost: str,
                 oip: bytes, r: int) -> bytes:
    """Build a 33-byte NJE record."""
    return (ebcdic8(rtype) + ebcdic8(rhost) + rip[:4].ljust(4, b"\x00")
            + ebcdic8(ohost) + oip[:4].ljust(4, b"\x00") + struct.pack("B", r & 0xFF))


def respond_open(data: bytes, nodes: Dict[str, dict]) -> Optional[Tuple[bytes, dict]]:
    """Given an inbound buffer, return (response_bytes, info) or None if it is
    not an OPEN.  ``nodes`` is a mapping of known node names (e.g.
    nje.CHAPTER10_NODES).  ``info`` describes the decision for logging."""
    pkt = parse_open(data)
    if pkt is None or pkt["type"].upper() != "OPEN":
        return None
    oh = pkt["ohost"].upper()
    rh = pkt["rhost"].upper()
    known = {k.upper() for k in nodes}
    if oh not in known:
        rtype, r = "NAK", R_UNKNOWN_OHOST
    elif rh not in known:
        rtype, r = "NAK", R_BAD_RHOST
    else:
        rtype, r = "ACK", R_OK
    resp = build_record(rtype, rhost=pkt["rhost"], rip=pkt["rip"],
                        ohost=pkt["ohost"], oip=pkt["oip"], r=r)
    info = {"type": rtype, "r": r, "ohost": oh, "rhost": rh}
    return resp, info


# ---------------------------------------------------------------------------
# I-record sign-on (drives nmap nje-pass-brute).
#
# After an OPEN that returns ACK (R=0x00), the client sends SOH/ENQ; the server
# replies DLE/ACK; the client then sends an I-record carrying the node password
# (NCCILPAS/NCCINPAS).  If the password is correct the server replies with a
# 'J' sign-on reply, otherwise a 'B' close record.  nje-pass-brute reads byte 19
# (the SRCB) of the reply: 0xC2 ('B') means bad password, anything else is good.
# ---------------------------------------------------------------------------

# 18-byte SOH/ENQ the client sends and the 18-byte DLE/ACK the server returns.
SOH_ENQ = bytes.fromhex("000000120000000000000002012d00000000")
DLE_ACK = bytes.fromhex("000000120000000000000002107000000000")

SRCB_I = 0xC9   # 'I' initial sign-on
SRCB_J = 0xD1   # 'J' sign-on reply (success)
SRCB_B = 0xC2   # 'B' close / sign-on reject (bad password)

# Offset of the 8-byte EBCDIC password inside the 62-byte I-record.
_IREC_PW_OFFSET = 37


def is_soh_enq(data: bytes) -> bool:
    return bool(data) and data[:14] == SOH_ENQ[:14]


def parse_irecord_password(data: bytes) -> Optional[str]:
    """Extract the node password (NCCILPAS) from an inbound I-record."""
    if not data or len(data) < _IREC_PW_OFFSET + 8:
        return None
    # confirm this looks like an I-record (RCB 0xF0, SRCB 'I' at offset 17/18)
    if len(data) > 18 and data[18] not in (SRCB_I,):
        # tolerate slight framing differences; still try to read the password
        pass
    return from_ebcdic(data[_IREC_PW_OFFSET:_IREC_PW_OFFSET + 8])


def _signon_record(srcb: int) -> bytes:
    """Build a minimal NCCR reply (J success / B reject) with the given SRCB at
    byte 19 (offset 18), which is what nje-pass-brute inspects."""
    body = bytes([
        0x00, 0x00, 0x00, 0x16,  # TTB len 0x16
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x0E,  # TTR
        0x10, 0x02,              # DLE STX
        0x80, 0x8F, 0xCF,        # BCB FCS
        0xF0,                    # RCB
        srcb,                    # SRCB  <- byte 19 the script checks
        0x00, 0x00, 0x00, 0x00, 0x00,
    ])
    return body


def signon_reply(password_ok: bool) -> bytes:
    return _signon_record(SRCB_J if password_ok else SRCB_B)


def check_node_password(ohost: str, password: str, nodes: Dict[str, dict]) -> bool:
    node = nodes.get(ohost.upper())
    if not node:
        return False
    expected = (node.get("password") or "").upper()
    # An empty node password means no I-record password is required.
    return (not expected) or (password.upper() == expected)
