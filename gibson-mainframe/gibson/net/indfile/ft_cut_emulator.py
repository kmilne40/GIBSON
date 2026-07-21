"""Reference IND$FILE CUT-mode *emulator* (test aid).

A faithful port of the workstation side of x3270 ``Common/ft_cut.c`` so the
host state machine can be driven through a complete GET and PUT in-process,
proving the framing / sequencing / checksum / EOF logic is correct and
self-consistent.  This is NOT used in production (real c3270 is the emulator
there); it lives here so tests don't need a live terminal.

Faithful to ft_cut.c except for one deliberate simplification: incoming
download data is accumulated and decoded once at EOF rather than per-frame.
The result is identical because the host emits a single continuous
``encode_download`` stream split across frames, and the quadrant state ft_cut.c
persists across frames is equivalent to decoding the concatenation.  A separate
test asserts that frame-boundary splitting is lossless.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from gibson.net.indfile.ft_cut_codec import decode_upload, encode_download, to6
from gibson.net.indfile.ft_cut_frames import HostFrame, fa_is_skip
from gibson.net.indfile.ft_cut_layout import FtCutLayout


@dataclass
class EmuReply:
    """What the emulator sends back ('presses Enter'), abstractly."""
    aid: Optional[int]                 # None => frame ignored (no skip field)
    buffer: Optional[bytes] = None     # full screen image (upload reply) or None


class ReferenceEmulator:
    def __init__(self, L: FtCutLayout, *,
                 recv_sink: Optional[bytearray] = None,
                 send_source: Optional[bytes] = None):
        self.L = L
        self.buf = bytearray(L.screen_size)
        self.recv_sink = recv_sink            # GET: bytes delivered to workstation
        self._dl_accum = bytearray()          # GET: accumulated encoded download
        self.send_source = send_source or b"" # PUT: file to upload to host
        self._ul_encoded = b""                # PUT: whole source pre-encoded
        self._ul_pos = 0
        self.in_progress = False
        self.eof = False
        self.complete = False
        self.aborted = False
        self.abort_status = 0

    # -- main entry (ft_cut_data) -----------------------------------------
    def feed(self, frame: HostFrame) -> EmuReply:
        for off, b in frame.writes.items():
            self.buf[off] = b
        sf = frame.fa.get(self.L.o_sf, 0)
        if not (sf and fa_is_skip(sf)):
            return EmuReply(aid=None)
        ft = self.buf[self.L.o_frame_type]
        if ft == self.L.ft_control_code:
            return self._control_code()
        if ft == self.L.ft_data_request:
            return self._data_request(frame)
        if ft == self.L.ft_data:
            return self._data()
        # unknown frame -> abort
        self.aborted = True
        self.abort_status = self.L.sc_abort_xmit
        return self._ack()

    # -- cut_control_code -------------------------------------------------
    def _control_code(self) -> EmuReply:
        L = self.L
        code = (self.buf[L.o_cc_status_code] << 8) | self.buf[L.o_cc_status_code + 1]
        if code == L.sc_host_ack:
            self.in_progress = True
            self.eof = False
            # pre-encode the whole upload source once (continuous quadrant)
            self._ul_encoded = encode_download(self.send_source)
            self._ul_pos = 0
            return self._ack()
        if code == L.sc_xfer_complete:
            self.complete = True
            if self.recv_sink is not None:
                self.recv_sink[:] = decode_upload(bytes(self._dl_accum))
            return self._ack()
        if code in (L.sc_abort_file, L.sc_abort_xmit):
            self.aborted = True
            self.abort_status = code
            return self._ack()
        self.aborted = True
        self.abort_status = L.sc_abort_xmit
        return self._ack()

    # -- cut_data (download received by workstation) ----------------------
    def _data(self) -> EmuReply:
        L = self.L
        raw_length = (from6_(self.buf[L.o_dt_len]) << 6) | from6_(self.buf[L.o_dt_len + 1])
        data = bytes(self.buf[L.o_dt_data:L.o_dt_data + raw_length])
        if raw_length == 2 and data[0] == L.eof_data1 and data[1] == L.eof_data2:
            self.eof = True
            return self._ack()
        self._dl_accum.extend(data)
        return self._ack()

    # -- cut_data_request (upload sent by workstation) --------------------
    def _data_request(self, frame: HostFrame) -> EmuReply:
        L = self.L
        seq = self.buf[L.o_dr_frame_seq]   # echoed raw (EBCDIC table6)
        # take up to O_UP_MAX encoded bytes from the continuous stream
        chunk = self._ul_encoded[self._ul_pos:self._ul_pos + L.o_up_max]
        self._ul_pos += len(chunk)
        out = bytearray(self.buf)
        if not chunk and not self.eof:
            # EOF: emit the 2-byte sentinel
            self.eof = True
            out[L.o_up_data] = L.eof_data1
            out[L.o_up_data + 1] = L.eof_data2
            count = 2
            payload = bytes([L.eof_data1, L.eof_data2])
        else:
            for i, b in enumerate(chunk):
                out[L.o_up_data + i] = b
            count = len(chunk)
            payload = bytes(chunk)
        cs = 0
        for b in payload:
            cs ^= b
        out[L.o_up_frame_seq] = seq
        out[L.o_up_csum] = to6(cs & 0x3F)
        out[L.o_up_len] = to6((count >> 6) & 0x3F)
        out[L.o_up_len + 1] = to6(count & 0x3F)
        return EmuReply(aid=L.aid_enter, buffer=bytes(out))

    def _ack(self) -> EmuReply:
        return EmuReply(aid=self.L.aid_enter)


# local copy to avoid an extra import cycle in hot path
def from6_(ebc: int) -> int:
    from gibson.net.indfile.ft_cut_codec import from6
    return from6(ebc)
