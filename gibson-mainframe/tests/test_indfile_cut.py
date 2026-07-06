"""IND$FILE CUT-mode host transfer tests.

Validates the conversion codec, the 6-bit helpers, the GET/PUT host state
machine against the reference emulator, and the 3270 datastream
(de)serialisation used by the live socket path.  All internal-consistency
checks (host frames are decoded by a faithful ft_cut.c port and vice versa).
"""
import os
import random

from gibson.net.indfile.ft_cut_codec import (
    encode_download, decode_upload, to6, from6,
)
from gibson.net.indfile.ft_cut_layout import DEFAULT_LAYOUT as L
from gibson.net.indfile.ft_cut_emulator import ReferenceEmulator
from gibson.net.indfile.ft_cut_host import (
    CutHost, ReferenceChannel, frame_to_datastream, packet_to_buffer,
    _encode_baddr, _decode_baddr,
)
from gibson.net.indfile import ft_cut_frames as F


def _get(data: bytes) -> bytes:
    sink = bytearray()
    host = CutHost(ReferenceChannel(ReferenceEmulator(L, recv_sink=sink)))
    host.get(data)
    return bytes(sink)


def _put(data: bytes) -> bytes:
    return CutHost(ReferenceChannel(ReferenceEmulator(L, send_source=data))).put()


def test_codec_single_byte_round_trip():
    for b in range(256):
        assert decode_upload(encode_download(bytes([b]))) == bytes([b])


def test_codec_full_and_random():
    full = bytes(range(256))
    assert decode_upload(encode_download(full)) == full
    random.seed(1)
    for _ in range(1000):
        data = bytes(random.randint(0, 255) for _ in range(random.randint(0, 200)))
        assert decode_upload(encode_download(data)) == data


def test_six_bit_helpers():
    for v in range(64):
        assert from6(to6(v)) == v


def test_frame_split_is_lossless():
    # the host splits a continuous encoded stream across frames; decoding the
    # concatenation must recover the original regardless of split point
    data = os.urandom(4000)
    enc = encode_download(data)
    for chunk in (5, 13, 64, 255, 1914):
        joined = b"".join(enc[i:i + chunk] for i in range(0, len(enc), chunk))
        assert decode_upload(joined) == data


def test_get_round_trip():
    for data in [b"", b"A", b"HELLO WORLD", bytes(range(256)),
                 b"//JOB JOB 1\n//S EXEC PGM=IEFBR14\n" * 40, os.urandom(5000)]:
        assert _get(data) == data


def test_put_round_trip():
    for data in [b"", b"A", b"HELLO WORLD", bytes(range(256)),
                 b"//JOB JOB 1\n//S EXEC PGM=IEFBR14\n" * 40, os.urandom(5000)]:
        assert _put(data) == data


def test_get_completes_and_acks():
    sink = bytearray()
    emu = ReferenceEmulator(L, recv_sink=sink)
    CutHost(ReferenceChannel(emu)).get(b"DATA12345")
    assert emu.complete and not emu.aborted


def test_datastream_well_formed():
    ds = frame_to_datastream(L, F.build_data(L, 1, b"\xc1\xc2\xc3"))
    assert ds[0] == L.cmd_erase_write and ds[1] == L.wcc_reset_kbd
    assert bytes([L.order_sba]) in ds and bytes([L.order_sf]) in ds
    # no raw IAC in any frame body
    for fr in (F.build_host_ack(L), F.build_xfer_complete(L),
               F.build_data_eof(L, 1), F.build_data_request(L, 1),
               F.build_data(L, 2, encode_download(bytes(range(256))))):
        assert 0xFF not in frame_to_datastream(L, fr)


def test_upload_packet_parsing():
    count = 4
    upbytes = bytes([to6(1), to6(0x05), to6((count >> 6) & 0x3F), to6(count & 0x3F)])
    upbytes += b"\x7e\xc1\xc2\xc3"
    pkt = (bytes([L.aid_enter]) + _encode_baddr(L.o_up_frame_seq) +
           bytes([L.order_sba]) + _encode_baddr(L.o_up_frame_seq) + upbytes)
    r = F.parse_upload_reply(L, packet_to_buffer(L, pkt))
    assert r.seq == 1 and r.count == 4 and r.encoded == b"\x7e\xc1\xc2\xc3"


def test_fuzz_get_put():
    random.seed(7)
    for _ in range(120):
        data = os.urandom(random.randint(0, 3000))
        assert _get(data) == data
        assert _put(data) == data


class _WireEmulator:
    """Closes the SocketChannel loop through the real 3270 wire format.

    Consumes the host's EraseWrite datastream (IAC-escaped, EOR-terminated),
    parses it back to a HostFrame, feeds the ReferenceEmulator, and produces the
    inbound AID packet exactly as Gibson's recv_packet would deliver it."""

    def __init__(self, emu):
        self.emu = emu
        self._pending = None

    def _datastream_to_frame(self, ds: bytes) -> F.HostFrame:
        fr = F.HostFrame()
        i = 0
        assert ds[i] in (L.cmd_erase_write, L.cmd_write)
        i += 2  # command + WCC
        addr = 0
        n = len(ds)
        while i < n:
            b = ds[i]
            if b == L.order_sba:
                addr = _decode_baddr(ds[i + 1], ds[i + 2]); i += 3; continue
            if b == L.order_sf:
                fr.fa[addr] = ds[i + 1]; addr += 1; i += 2; continue
            fr.writes[addr] = b; addr += 1; i += 1
        return fr

    def send_bytes(self, data: bytes) -> None:
        assert data[-2:] == bytes([0xFF, 0xEF])          # IAC EOR
        body = data[:-2].replace(b"\xff\xff", b"\xff")    # un-escape IAC
        frame = self._datastream_to_frame(body)
        reply = self.emu.feed(frame)
        pkt = bytearray([reply.aid if reply.aid is not None else L.aid_enter])
        pkt += _encode_baddr(L.o_up_frame_seq)            # cursor
        if reply.buffer is not None:
            up = F.parse_upload_reply(L, reply.buffer)
            end = L.o_up_data + up.count
            pkt += bytes([L.order_sba]) + _encode_baddr(L.o_up_frame_seq)
            pkt += reply.buffer[L.o_up_frame_seq:end]
        self._pending = bytes(pkt)

    def recv_packet(self) -> bytes:
        p, self._pending = self._pending, None
        return p


def _socket_get(data: bytes) -> bytes:
    from gibson.net.indfile.ft_cut_host import SocketChannel
    sink = bytearray()
    wire = _WireEmulator(ReferenceEmulator(L, recv_sink=sink))
    host = CutHost(SocketChannel(L, wire.send_bytes, wire.recv_packet), L)
    host.get(data)
    return bytes(sink)


def _socket_put(data: bytes) -> bytes:
    from gibson.net.indfile.ft_cut_host import SocketChannel
    wire = _WireEmulator(ReferenceEmulator(L, send_source=data))
    host = CutHost(SocketChannel(L, wire.send_bytes, wire.recv_packet), L)
    return host.put()


def test_socket_get_round_trip():
    for data in [b"", b"A", bytes(range(256)),
                 b"//JOB JOB 1\n//S EXEC PGM=IEFBR14\n" * 30, os.urandom(4000)]:
        assert _socket_get(data) == data


def test_socket_put_round_trip():
    for data in [b"", b"A", bytes(range(256)),
                 b"//JOB JOB 1\n//S EXEC PGM=IEFBR14\n" * 30, os.urandom(4000)]:
        assert _socket_put(data) == data


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
