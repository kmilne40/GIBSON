"""Host-side IND$FILE CUT-mode file transfer for Gibson's TN3270 server.

CUT (Control Unit Terminal) mode rides the standard 3270 data stream (no
structured fields / TN3270E), which is exactly what Gibson speaks, so this is
the route that works against real c3270 / x3270 File->Transfer.

Modules:
  ft_cut_codec   - the binary<->displayable conversion (ported verbatim from
                   x3270 Common/ft_cut.c: alphas/conv[]/table6, encode/decode).
  ft_cut_layout  - screen-buffer offsets + protocol constants in ONE place
                   (the single thing that needs a live-c3270 confirmation pass).
  ft_cut_frames  - build host 3270 frames / parse emulator replies.
  ft_cut_host    - the host-side GET/PUT state machine.
  ft_cut_emulator- a faithful reference port of the emulator side, used only by
                   tests to drive full in-process round trips.
"""
from gibson.net.indfile.ft_cut_codec import encode_download, decode_upload, to6, from6
from gibson.net.indfile.ft_cut_layout import FtCutLayout, DEFAULT_LAYOUT

__all__ = [
    "encode_download", "decode_upload", "to6", "from6",
    "FtCutLayout", "DEFAULT_LAYOUT",
]
