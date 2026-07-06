"""Host-side IND$FILE CUT-mode state machine (Gibson is the host / IND$FILE).

The protocol logic is expressed against a small :class:`Channel` abstraction so
the identical state machine runs against:
  * :class:`ReferenceChannel` - the in-process reference emulator (tests);
  * :class:`SocketChannel`    - a real c3270/x3270 over the TN3270 socket.
"""
from __future__ import annotations

from typing import Callable, Optional, Protocol

from gibson.net.indfile.ft_cut_codec import decode_upload, encode_download
from gibson.net.indfile import ft_cut_frames as F
from gibson.net.indfile.ft_cut_layout import DEFAULT_LAYOUT, FtCutLayout


class TransferError(RuntimeError):
    pass


class Reply:
    """Channel reply: the AID the emulator returned and (for uploads) the
    reconstructed screen image."""
    def __init__(self, aid: Optional[int], buffer: Optional[bytes] = None):
        self.aid = aid
        self.buffer = buffer


class Channel(Protocol):
    def exchange(self, frame: "F.HostFrame") -> Reply:
        """Send one host frame, return the emulator's reply."""
        ...


# --- reference channel (tests) ------------------------------------------
class ReferenceChannel:
    def __init__(self, emulator):
        self.emu = emulator

    def exchange(self, frame: F.HostFrame) -> Reply:
        r = self.emu.feed(frame)
        return Reply(aid=r.aid, buffer=r.buffer)


# --- socket channel (live TN3270) ---------------------------------------
class SocketChannel:
    """Drives a real emulator over the TN3270 connection.

    ``send_bytes(data)`` writes a raw 3270 datastream (already IAC-escaped /
    EOR-terminated by the caller's send wrapper is NOT assumed; we append
    IAC EOR here).  ``recv_packet()`` returns one inbound AID packet (without
    the trailing IAC EOR), as Gibson's Tn3270Session already provides.
    """
    IAC = 0xFF
    EOR = 0xEF

    def __init__(self, L: FtCutLayout, send_bytes: Callable[[bytes], None],
                 recv_packet: Callable[[], bytes]):
        self.L = L
        self._send = send_bytes
        self._recv = recv_packet

    def exchange(self, frame: F.HostFrame) -> Reply:
        ds = frame_to_datastream(self.L, frame)
        # IAC-escape the body (double 0xFF), then terminate the record with
        # IAC EOR.  Gibson's send() is a raw sendall with no escaping.
        body = ds.replace(b"\xff", b"\xff\xff")
        self._send(body + bytes([self.IAC, self.EOR]))
        packet = self._recv()
        if not packet:
            raise TransferError("client disconnected during transfer")
        aid = packet[0]
        buffer = packet_to_buffer(self.L, packet)
        return Reply(aid=aid, buffer=buffer)


# --- 3270 datastream (de)serialisation ----------------------------------
def _encode_baddr(addr: int) -> bytes:
    """12-bit buffer address (two 6-bit bytes via the standard code table)."""
    code = b"\x40\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\x4a\x4b\x4c\x4d\x4e\x4f" \
           b"\x50\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\x5a\x5b\x5c\x5d\x5e\x5f" \
           b"\x60\x61\x62\x63\x64\x65\x66\x67\x68\x69\x6a\x6b\x6c\x6d\x6e\x6f" \
           b"\x70\x71\x72\x73\x74\x75\x76\x77\x78\x79\x7a\x7b\x7c\x7d\x7e\x7f"
    return bytes([code[(addr >> 6) & 0x3F], code[addr & 0x3F]])


def _decode_baddr(b0: int, b1: int) -> int:
    code = b"\x40\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\x4a\x4b\x4c\x4d\x4e\x4f" \
           b"\x50\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\x5a\x5b\x5c\x5d\x5e\x5f" \
           b"\x60\x61\x62\x63\x64\x65\x66\x67\x68\x69\x6a\x6b\x6c\x6d\x6e\x6f" \
           b"\x70\x71\x72\x73\x74\x75\x76\x77\x78\x79\x7a\x7b\x7c\x7d\x7e\x7f"
    if (b0 & 0xC0) == 0x00:   # 14-bit form
        return ((b0 & 0x3F) << 8) | b1
    return (code.index(b0 & 0xFF) << 6) | code.index(b1 & 0xFF)


def frame_to_datastream(L: FtCutLayout, frame: F.HostFrame) -> bytes:
    """Serialise a HostFrame to a real 3270 EraseWrite datastream (sans EOR;
    the caller's send wrapper adds IAC EOR)."""
    out = bytearray()
    out.append(L.cmd_erase_write)
    out.append(L.wcc_reset_kbd)
    # field attributes first (Start Field orders)
    for off in sorted(frame.fa):
        out.append(L.order_sba)
        out += _encode_baddr(off)
        out.append(L.order_sf)
        out.append(frame.fa[off])
    # data writes, coalesced into runs
    writes = frame.writes
    for off in sorted(writes):
        out.append(L.order_sba)
        out += _encode_baddr(off)
        out.append(writes[off])
    return bytes(out)


def packet_to_buffer(L: FtCutLayout, packet: bytes) -> bytes:
    """Reconstruct a screen-buffer image from an inbound AID packet.

    Packet layout: AID, cursor-addr(2), then [SBA(0x11) addr(2) data...]* .
    Modified-field data runs are laid into a zeroed buffer at their addresses."""
    buf = bytearray(L.screen_size)
    i = 1
    # cursor address (2 bytes) if present
    if len(packet) >= 3:
        i = 3
    n = len(packet)
    addr = 0
    while i < n:
        b = packet[i]
        if b == L.order_sba and i + 2 < n:
            addr = _decode_baddr(packet[i + 1], packet[i + 2])
            i += 3
            continue
        if 0 <= addr < L.screen_size:
            buf[addr] = b
            addr += 1
        i += 1
    return buf


# --- the state machine ---------------------------------------------------
class CutHost:
    def __init__(self, channel: Channel, layout: FtCutLayout = DEFAULT_LAYOUT):
        self.ch = channel
        self.L = layout

    def _expect_ack(self, reply: Reply) -> None:
        if reply.aid not in (self.L.aid_enter,):
            raise TransferError(f"expected ENTER ack, got AID {reply.aid!r}")

    def get(self, data: bytes) -> int:
        """Download ``data`` (host->workstation).  Returns bytes sent."""
        L = self.L
        self._expect_ack(self.ch.exchange(F.build_host_ack(L)))
        encoded = encode_download(data)
        seq = 1
        pos = 0
        while pos < len(encoded):
            chunk = encoded[pos:pos + L.dt_data_max]
            pos += len(chunk)
            self._expect_ack(self.ch.exchange(F.build_data(L, seq, chunk)))
            seq = (seq + 1) & 0x3F
        self._expect_ack(self.ch.exchange(F.build_data_eof(L, seq)))
        self._expect_ack(self.ch.exchange(F.build_xfer_complete(L)))
        return len(data)

    def put(self) -> bytes:
        """Upload (workstation->host).  Returns the received file bytes."""
        L = self.L
        self._expect_ack(self.ch.exchange(F.build_host_ack(L)))
        accumulated = bytearray()
        seq = 1
        guard = 0
        while True:
            guard += 1
            if guard > L.screen_size * 8:
                raise TransferError("upload exceeded sane frame count")
            reply = self.ch.exchange(F.build_data_request(L, seq))
            if reply.buffer is None:
                raise TransferError("no upload payload from emulator")
            up = F.parse_upload_reply(L, reply.buffer)
            if up.is_eof:
                break
            accumulated += up.encoded
            seq = (seq + 1) & 0x3F
        result = decode_upload(bytes(accumulated))
        self._expect_ack(self.ch.exchange(F.build_xfer_complete(L)))
        return result
