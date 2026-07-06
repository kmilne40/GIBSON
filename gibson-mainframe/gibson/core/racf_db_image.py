"""Binary RACF database image - Scope A (racf2john brute-force layout).

Builds a flat binary ``SYS1.RACFDS.BACKUP`` whose USER profiles match the exact
on-disk layout that John the Ripper's ``racf2john`` extracts. ``racf2john`` does
NOT walk the RACF ICB / index / template structure; it is a brute-force byte
scanner that looks for the EBCDIC segment name ``"BASE    "`` and then reads a
small TLV field list out of the USER BASE segment that follows it. The USER
password field (BASE field number 12, length 8) carries the *real* RACF DES
hash, so ``racf2john SYS1.RACFDS.BACKUP`` -> ``john --format=racf`` cracks it.

Format derivation (cross-checked against two authoritative sources):

* JtR ``racf2john.c`` (Dhiru Kholia, 2012) - the brute-force scanner that the
  user actually runs.
* ``bigendiansmalls/racfdbparse`` (``parse_racf_db_new.py``) - a full RACF DB
  parser that decodes the *same* on-disk USER BASE segment. It confirms the byte
  offsets used below: record length is a big-endian uint32 at ``rec+5``, the
  EBCDIC ``"BASE    "`` segment name sits at ``rec+9``, the profile-name length
  is a uint16 at ``rec+17``, the profile name (EBCDIC userid) starts at
  ``rec+20``, and the BASE segment body that follows is a sequence of
  ``field-number(1) | length(1) | data`` triplets (with a high length bit
  signalling a 3-byte extended length).

A user record laid out this way satisfies racf2john's scan checks exactly:
with the signature's last byte at index ``i`` (the 4th EBCDIC space of
``"BASE    "``), ``i = rec+16`` so ``user_rec_addr = i-16 = rec``,
``user_rec_len = (buf[i-9]<<8)|buf[i-8]`` reads the low 16 bits of the uint32
length, ``buf[i+1]==0`` / ``buf[i+2]<9`` / ``buf[i+3]==0`` are the name-length
uint16 high byte, low byte and the trailing 0x00, the profile name is
``buf[i+4:i+4+namelen]``, and the BASE body starts at ``rec+20+namelen``.

Because the build environment has no JtR binary, the in-repo gate proves the
writer round-trips through :func:`parse` (which re-implements the same
brute-force scan racf2john uses) and that the embedded hashes match JtR's
published DES vectors; final acceptance (running the real ``racf2john``) is on
the target box. Every format constant racf2john is picky about lives in the
FORMAT section so a single adjustment retunes the whole image.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

# --------------------------------------------------------------------------- #
#  FORMAT - everything racf2john's scanner cares about, in one place           #
# --------------------------------------------------------------------------- #
BLOCK_SIZE = 4096
ICB_MARKER = b"RACFDS\x00\x00"          # 8-byte identifier kept at ICB+24
MIN_BLOCKS = 4                          # image is padded to at least this many

EBCDIC = "cp037"                        # A-Z/0-9 are identical across EBCDIC CPs

# EBCDIC "BASE    " (segment name) = the signature racf2john brute-forces for.
BASE_SEG = b"\xC2\xC1\xE2\xC5\x40\x40\x40\x40"   # 'B''A''S''E'' '' '' '' '

# Hash-algorithm tags (carried on the entry; the on-disk format is implied by
# which BASE fields are present, not by a flag byte).
ALG_DES = 0x00
ALG_KDFAES = 0x01

# Retained for backward compatibility with earlier callers/tests.
ENTRY_TYPE_USER = 0x04
ENTRY_TYPE_GROUP = 0x01

# RACF BASE-segment field numbers (template field ids) that matter here.
FN_ACTIVE = 0x02        # leading "active profile" field; racf2john gates on it
FN_PASSWORD = 0x0C      # 12: 8-byte legacy DES password hash
FN_KDFAES = 0x64        # 100: 40-byte KDFAES password extension (optional)

# Fixed-layout offsets inside a USER record (relative to record start).
OFF_RECLEN = 5          # uint32 BE total record length
OFF_BASESEG = 9         # 8-byte EBCDIC "BASE    "
OFF_NAMELEN = 17        # uint16 BE profile-name length
OFF_NAME = 20           # profile name (EBCDIC userid) starts here
HEADER_LEN_BASE = 20    # bytes before the profile name (= OFF_NAME)


def _ebcdic(text: str, width: int = 0) -> bytes:
    raw = (text or "").upper().encode(EBCDIC, errors="replace")
    return raw.ljust(width, b"\x40") if width else raw


def _from_ebcdic(raw: bytes) -> str:
    return raw.decode(EBCDIC, errors="replace").rstrip()


@dataclass
class RacfUserEntry:
    userid: str
    password_hex: str           # 16 hex chars (8-byte DES hash)
    algorithm: int = ALG_DES
    default_group: str = "SYS1"
    name: str = ""
    special: bool = False
    operations: bool = False
    pwdx_hex: str = ""          # optional KDFAES extension (80 hex / 40 bytes)


@dataclass
class RacfDbImage:
    users: List[RacfUserEntry] = field(default_factory=list)

    def add_user(self, userid: str, password_hex: str, **kw) -> None:
        self.users.append(
            RacfUserEntry(userid.upper()[:8], (password_hex or "").upper(), **kw)
        )

    # ---- one USER record in racf2john on-disk layout ------------------------
    def _user_record(self, u: RacfUserEntry) -> bytes:
        name = _ebcdic(u.userid)[:8]
        pnl = len(name)
        if not (1 <= pnl <= 8):
            raise ValueError(f"userid {u.userid!r} must be 1-8 EBCDIC bytes")

        # BASE-segment body: a sequence of field-number/length/data triplets.
        # racf2john gates on the first byte being the 0x02 "active" field, walks
        # the triplets, and picks up FN_PASSWORD (DES) / FN_KDFAES.
        body = bytearray()
        body += bytes((FN_ACTIVE, 0x00))                 # active marker, len 0
        hash8 = bytes.fromhex((u.password_hex or "").ljust(16, "0")[:16])
        body += bytes((FN_PASSWORD, 0x08)) + hash8       # DES password field
        if u.pwdx_hex:
            ext = bytes.fromhex(u.pwdx_hex)
            if len(ext) == 40:
                body += bytes((FN_KDFAES, 0x28)) + ext   # KDFAES ext (40 bytes)

        rec = bytearray()
        rec += b"\x00" * OFF_RECLEN                       # rec+0..rec+5 header
        rec += b"\x00\x00\x00\x00"                        # rec+5  length (fixup)
        rec += BASE_SEG                                   # rec+9  "BASE    "
        rec += struct.pack(">H", pnl)                    # rec+17 name length
        rec += b"\x00"                                    # rec+19 (scan checks 0)
        rec += name                                      # rec+20 EBCDIC userid
        rec += body                                      # BASE body (TLV)

        struct.pack_into(">I", rec, OFF_RECLEN, len(rec))  # total record length
        return bytes(rec)

    # ---- whole-image serialisation ------------------------------------------
    def to_bytes(self) -> bytes:
        # Block 0 is a minimal ICB carrying the marker the rest of Gibson keys
        # off (binary-dataset detection, the parity/exfil gate). racf2john never
        # reads it - it brute-force scans the whole file for "BASE    ", so the
        # USER records simply follow the ICB contiguously.
        icb = bytearray(BLOCK_SIZE)
        struct.pack_into(">I", icb, 0, 0x00000001)        # format id (not RDBU)
        struct.pack_into(">I", icb, 16, len(self.users))  # user count (info)
        icb[24:32] = ICB_MARKER
        icb[1010:1018] = "RACFDS  ".encode(EBCDIC)        # racfdbparse eyecatcher

        out = bytearray(icb)
        for u in self.users:
            out += self._user_record(u)

        # Pad to a whole number of 4 KB blocks, at least MIN_BLOCKS.
        blocks = (len(out) + BLOCK_SIZE - 1) // BLOCK_SIZE
        blocks = max(blocks, MIN_BLOCKS)
        out += b"\x00" * (blocks * BLOCK_SIZE - len(out))
        return bytes(out)


# --------------------------------------------------------------------------- #
#  Reference reader - re-implements racf2john's brute-force scan               #
# --------------------------------------------------------------------------- #
def parse(data: bytes) -> List[RacfUserEntry]:
    """Walk ``data`` exactly the way ``racf2john`` does: scan every byte for the
    EBCDIC ``"BASE    "`` signature, frame the USER record around it, and read
    the BASE-segment TLV fields. Returns the USER entries with their DES (and,
    if present, KDFAES) hashes. Round-tripping this against :meth:`to_bytes`
    proves the image is what the real racf2john will extract."""
    out: List[RacfUserEntry] = []
    n = len(data)
    i = 7
    while i < n:
        # signature occupies data[i-7 .. i] inclusive (8 bytes)
        if (
            data[i - 7:i + 1] == BASE_SEG
            and i + 4 < n
            and data[i + 1] == 0x00            # name-length high byte
            and 0 < data[i + 2] < 9            # name-length low byte (1..8)
            and data[i + 3] == 0x00            # trailing zero
            and i - 16 >= 0
        ):
            pnl = data[i + 2]
            userid = _from_ebcdic(data[i + 4:i + 4 + pnl])
            rec_addr = i - 16
            rec_len = (data[i - 9] << 8) | data[i - 8]
            header_len = (i + 4 + pnl) - rec_addr
            prof = data[rec_addr + header_len: rec_addr + rec_len]
            out.append(_walk_base_segment(userid, prof))
        i += 1
    return out


def _walk_base_segment(userid: str, prof: bytes) -> RacfUserEntry:
    """Walk a BASE-segment body (``field-number | length | data`` triplets,
    high length-bit => 3-byte extended length) and pull the password fields.
    Mirrors racf2john / racfdbparse field handling."""
    entry = RacfUserEntry(userid=userid, password_hex="")
    x = 0
    end = len(prof)
    while x + 2 <= end:
        fn = prof[x]
        fl = prof[x + 1]
        if fl >> 7 == 1:                       # extended: 3-byte length follows
            if x + 5 > end:
                break
            fl = int.from_bytes(prof[x + 2:x + 5], "big")
            fdata = prof[x + 5:x + 5 + fl]
            x += 5 + fl
        else:
            fdata = prof[x + 2:x + 2 + fl]
            x += 2 + fl
        if fn == FN_PASSWORD and len(fdata) == 8:
            entry.password_hex = fdata.hex().upper()
            if entry.algorithm == ALG_DES:
                entry.algorithm = ALG_DES
        elif fn == FN_KDFAES and len(fdata) == 40:
            entry.pwdx_hex = fdata.hex().upper()
            entry.algorithm = ALG_KDFAES
    return entry


def john_lines(entries: List[RacfUserEntry]) -> List[str]:
    """Render the ``racf2john`` output a defender would compare against.

    DES:    ``USERID:$racf$*USERID*<16 hex>``
    KDFAES: ``USERID:$racf$*USERID*<40-byte ext hex><8-byte hex>`` (the order
            John expects, matching racfdbparse's KDFAES emit).
    """
    out: List[str] = []
    for e in entries:
        if e.pwdx_hex and len(e.pwdx_hex) == 80:
            out.append(f"{e.userid}:$racf$*{e.userid}*{e.pwdx_hex}{e.password_hex}")
        else:
            out.append(f"{e.userid}:$racf$*{e.userid}*{e.password_hex}")
    return out
