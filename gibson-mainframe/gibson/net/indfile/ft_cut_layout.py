"""IND$FILE CUT-mode screen layout and protocol constants.

THIS IS THE ONE PLACE THAT NEEDS A LIVE c3270 CONFIRMATION PASS.

Everything else in this package (the binary<->displayable codec, the
sequence/length/checksum maths, the GET/PUT state machine and EOF handling)
is ported verbatim from x3270 ``Common/ft_cut.c`` and is exercised end-to-end
by a reference-emulator round trip in the tests, so the *logic* is known-good.

What ft_cut.c reads/writes by symbolic name (``O_FRAME_TYPE`` etc.) is defined
numerically in its companion header ``ft_cut_ds.h``.  That header is not
publicly indexed and we cannot drive a live c3270 here to capture a
``ReadBuffer``, so the byte offsets and the FT_*/SC_*/EOF_* constant *values*
below are a best reconstruction from the published ``ft_cut.c`` logic and the
``s3270/Test/ft_cut.trc`` capture.  They are internally consistent (host and
reference emulator agree), which is what the tests prove.

To lock these against real c3270:
  1. Point c3270 at Gibson, start a GET, and run ``ReadBuffer(Ascii)`` /
     enable ``dsTrace`` to capture the first host frame.
  2. Adjust the offsets / FT_* / SC_* / EOF_* values in this dataclass only.
No other module hard-codes a layout number.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FtCutLayout:
    # --- screen geometry -------------------------------------------------
    rows: int = 24
    cols: int = 80

    # --- common frame header (host->emulator) ----------------------------
    # ft_cut.c gates on ea_buf[O_SF].fa && FA_IS_SKIP(...), then switches on
    # ea_buf[O_FRAME_TYPE].
    o_sf: int = 0            # Start Field attribute (protected/skip/nondisplay)
    o_frame_type: int = 1    # frame type byte

    # --- control-code frame (host->emulator) -----------------------------
    o_cc_frame_seq: int = 2
    o_cc_status_code: int = 3   # 2 bytes (big-endian)
    o_cc_message: int = 5       # 80-byte EBCDIC message area (abort text)

    # --- data frame: download = host->workstation (GET) ------------------
    o_dt_frame_seq: int = 2
    o_dt_len: int = 3           # 2 bytes, table6-encoded (raw length)
    o_dt_data: int = 5          # encoded data start

    # --- data-request frame: host asks workstation for data (PUT) --------
    o_dr_frame_seq: int = 2
    o_dr_sf: int = 3            # Start Field that precedes the upload area

    # --- upload response area: workstation->host (PUT) -------------------
    # Written by the emulator and read back by the host after Enter.
    o_up_frame_seq: int = 4
    o_up_csum: int = 5
    o_up_len: int = 6           # 2 bytes, table6-encoded
    o_up_data: int = 8          # encoded data start

    # --- AID / orders ----------------------------------------------------
    aid_enter: int = 0x7D
    aid_pf3: int = 0xF3
    order_sba: int = 0x11       # Set Buffer Address
    order_sf: int = 0x1D        # Start Field
    cmd_erase_write: int = 0xF5
    cmd_write: int = 0xF1
    wcc_reset_kbd: int = 0xC2   # WCC: reset + restore keyboard (unlock)

    # --- frame type values (ea_buf[O_FRAME_TYPE]) ------------------------
    ft_control_code: int = 0x01
    ft_data_request: int = 0x02
    ft_retransmit: int = 0x03
    ft_data: int = 0x04

    # --- control status codes (O_CC_STATUS_CODE, 2 bytes) ----------------
    sc_host_ack: int = 0x0001
    sc_xfer_complete: int = 0x0002
    sc_abort_file: int = 0x0003
    sc_abort_xmit: int = 0x0004

    # --- EOF sentinel (2 raw bytes in the data area) ---------------------
    # NOTE: kept off 0xFF so the bytes never collide with telnet IAC on the
    # raw (un-escaped) send path.  The true ft_cut_ds.h values are part of the
    # one-time live-c3270 confirmation (see module docstring).
    eof_data1: int = 0x9E
    eof_data2: int = 0x9F

    # --- derived ---------------------------------------------------------
    @property
    def screen_size(self) -> int:
        return self.rows * self.cols

    @property
    def o_response(self) -> int:
        """End of the usable buffer (ft_cut.c O_RESPONSE)."""
        return self.screen_size - 1

    @property
    def o_up_max(self) -> int:
        """Max upload data bytes per frame (ft_cut.c O_UP_MAX)."""
        return self.o_response - self.o_up_data

    @property
    def dt_data_max(self) -> int:
        """Max download data bytes per frame (O_RESPONSE - O_DT_DATA)."""
        return self.o_response - self.o_dt_data

    def addr_rc(self, offset: int) -> tuple[int, int]:
        """0-based linear offset -> (row, col), both 1-based, for tracing."""
        return (offset // self.cols + 1, offset % self.cols + 1)


DEFAULT_LAYOUT = FtCutLayout()
