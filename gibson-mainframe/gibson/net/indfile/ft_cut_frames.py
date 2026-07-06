"""IND$FILE CUT-mode frame construction.

A frame is, abstractly, a set of byte writes into the 24x80 screen buffer plus
a Start-Field (skip) attribute at ``o_sf``.  Two consumers use the same frame:

  * the reference emulator (tests) applies it to an in-memory buffer;
  * the live TN3270 path serialises it to a real 3270 EraseWrite datastream.

Building both from one ``HostFrame`` keeps them consistent by construction, so
the round-trip tests validate the very bytes the socket path emits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from gibson.net.indfile.ft_cut_codec import to6, from6
from gibson.net.indfile.ft_cut_layout import FtCutLayout


def fa_is_skip(fa: int) -> bool:
    """ft_cut.c FA_IS_SKIP: a protected+numeric (autoskip) field."""
    return (fa & 0x30) == 0x30


SKIP_FA = 0x3C  # protected (0x20) + numeric (0x10) + display bits


@dataclass
class HostFrame:
    """Abstract host->emulator frame: writes + a skip field attribute."""
    writes: Dict[int, int] = field(default_factory=dict)   # offset -> EBCDIC byte
    fa: Dict[int, int] = field(default_factory=dict)        # offset -> field attr
    cursor: int = 0
    label: str = ""

    def put(self, offset: int, value: int) -> None:
        self.writes[offset] = value & 0xFF

    def put_bytes(self, offset: int, data: bytes) -> None:
        for i, b in enumerate(data):
            self.writes[offset + i] = b

    def put_fa(self, offset: int, attr: int) -> None:
        self.fa[offset] = attr & 0xFF


# --- builders ------------------------------------------------------------
def _base_frame(L: FtCutLayout, frame_type: int, label: str) -> HostFrame:
    f = HostFrame(label=label)
    f.put_fa(L.o_sf, SKIP_FA)            # the gating skip field
    f.put(L.o_frame_type, frame_type)
    return f


def build_control(L: FtCutLayout, status: int, message: bytes = b"") -> HostFrame:
    f = _base_frame(L, L.ft_control_code, f"CONTROL 0x{status:04x}")
    f.put(L.o_cc_status_code, (status >> 8) & 0xFF)
    f.put(L.o_cc_status_code + 1, status & 0xFF)
    if message:
        # EBCDIC message area, blank-padded to 80
        msg = message[:80]
        f.put_bytes(L.o_cc_message, msg)
        for i in range(len(msg), 80):
            f.put(L.o_cc_message + i, 0x40)  # EBCDIC space
    return f


def build_host_ack(L: FtCutLayout) -> HostFrame:
    return build_control(L, L.sc_host_ack)


def build_xfer_complete(L: FtCutLayout) -> HostFrame:
    return build_control(L, L.sc_xfer_complete)


def build_abort(L: FtCutLayout, status: int, message: bytes = b"") -> HostFrame:
    return build_control(L, status, message)


def build_data(L: FtCutLayout, seq: int, encoded: bytes) -> HostFrame:
    """Download data frame (host->workstation, a GET).  ``encoded`` is the
    output of :func:`encode_download`.  ``raw_length`` is its length."""
    raw_length = len(encoded)
    if raw_length > L.dt_data_max:
        raise ValueError("download frame data exceeds buffer")
    f = _base_frame(L, L.ft_data, f"DATA seq={seq} len={raw_length}")
    f.put(L.o_dt_frame_seq, to6(seq))
    f.put(L.o_dt_len, to6((raw_length >> 6) & 0x3F))
    f.put(L.o_dt_len + 1, to6(raw_length & 0x3F))
    f.put_bytes(L.o_dt_data, encoded)
    return f


def build_data_eof(L: FtCutLayout, seq: int) -> HostFrame:
    """Download EOF frame: a DATA frame carrying the 2-byte EOF sentinel."""
    f = _base_frame(L, L.ft_data, f"DATA-EOF seq={seq}")
    f.put(L.o_dt_frame_seq, to6(seq))
    f.put(L.o_dt_len, to6((2 >> 6) & 0x3F))
    f.put(L.o_dt_len + 1, to6(2 & 0x3F))
    f.put(L.o_dt_data, L.eof_data1)
    f.put(L.o_dt_data + 1, L.eof_data2)
    return f


def build_data_request(L: FtCutLayout, seq: int) -> HostFrame:
    """Upload data-request frame (host asks workstation for data, a PUT).

    Includes the Start Field at ``o_dr_sf`` that fronts the response area the
    emulator writes into."""
    f = _base_frame(L, L.ft_data_request, f"DATA_REQUEST seq={seq}")
    f.put(L.o_dr_frame_seq, to6(seq))
    f.put_fa(L.o_dr_sf, SKIP_FA)
    f.cursor = L.o_up_frame_seq
    return f


# --- emulator upload reply (parsed on the host side) ---------------------
@dataclass
class UploadReply:
    seq: int
    csum: int                 # raw EBCDIC csum byte as received
    count: int                # decoded raw length
    encoded: bytes            # the raw encoded upload bytes (pre-decode)
    is_eof: bool = False


def parse_upload_reply(L: FtCutLayout, buf: bytes) -> UploadReply:
    """Read the upload response area out of a (post-Enter) screen image.

    ``buf`` is the full screen buffer (>= screen_size).  Mirrors the host side
    of ft_cut.c's upload handshake (seq/csum/len at fixed offsets, then data)."""
    seq = from6(buf[L.o_up_frame_seq])
    csum = buf[L.o_up_csum]
    count = (from6(buf[L.o_up_len]) << 6) | from6(buf[L.o_up_len + 1])
    encoded = bytes(buf[L.o_up_data:L.o_up_data + count])
    is_eof = (count == 2 and len(encoded) == 2 and
              encoded[0] == L.eof_data1 and encoded[1] == L.eof_data2)
    return UploadReply(seq=seq, csum=csum, count=count, encoded=encoded, is_eof=is_eof)
