from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import select
import socket
import time

from gibson.render.aid_keys import (
    AID_BYTE_TO_KEY, ANSI_FUNCTION_KEY_MAP, command_from_key,
    extract_3270_aid_key, extract_ansi_function_key, normalise_aid_alias,
)
from gibson.net.datastream3270 import normalise_terminal_input, looks_like_3270_frame
from gibson.render.terminal_event import TerminalEvent

# Backwards-compatible name used by older targeted tests and extension code.
PF_KEY_MAP = ANSI_FUNCTION_KEY_MAP

@dataclass
class InputResult:
    text: str
    key: Optional[str] = None
    event: object | None = None

class SocketInputDriver:
    """One-byte socket reader that normalises Enter, backspace and PF keys.

    The original Gibson logon used ``makefile().readline()``, which consumes a
    complete CRLF line.  Telnet clients such as Python ``telnetlib`` send
    ``\r\n``.  If a refactored byte-reader returns on ``\r`` and leaves the
    following ``\n`` pending, the next logon prompt immediately receives a
    blank line.  That is what broke ``nmap-sim.py`` and caused ambiguous user
    enumeration.  This reader drains CRLF/LFCR pairs to preserve the original
    Gibson logon transcript.
    """
    def __init__(self, conn, echo: bool = True, write_lock=None):
        self.conn = conn
        self.echo = echo
        self.write_lock = write_lock
        self._pending = bytearray()
        # Persistent-ish control-sequence state for c3270/x3270/telnet NVT paths.
        # Real clients can fragment visible caret notation (for example ^[[19~)
        # or ANSI ESC sequences across multiple socket reads. Keep key detection
        # ahead of echo so these bytes are consumed as function keys, not inserted
        # into ISPF/DVCA fields.
        self._pending_control = ""
        self._pending_control_started_at: float | None = None

    def send(self, text: str) -> None:
        data = text.encode("utf-8", errors="ignore")
        if self.write_lock is not None:
            with self.write_lock:
                self.conn.sendall(data)
        else:
            self.conn.sendall(data)

    def _recv1(self) -> bytes:
        if self._pending:
            b = bytes([self._pending[0]])
            del self._pending[0]
            return b
        return self.conn.recv(1)

    def _push_front(self, data: bytes) -> None:
        if data:
            self._pending = bytearray(data) + self._pending

    def _drain_newline_pair(self, first: int) -> None:
        expected = 10 if first == 13 else 13
        try:
            r, _, _ = select.select([self.conn], [], [], 0.02)
            if not r:
                return
            try:
                nxt = self.conn.recv(1, socket.MSG_PEEK)
            except (TypeError, ValueError, OSError):
                # SSLSocket.recv(..., MSG_PEEK) raises ValueError because
                # non-zero flags are not supported on TLS sockets.  Treat this
                # as "nothing to drain" so secure-mode input remains live.
                nxt = b""
            if nxt and nxt[0] == expected:
                self.conn.recv(1)
        except Exception:
            return

    def _consume_telnet_iac(self) -> None:
        """Best-effort discard of simple TELNET IAC negotiation triplets."""
        try:
            self.conn.recv(2)
        except Exception:
            pass

    _CARET_KEY_MAP = {
        "^I": "TAB",
        "^[OP": "F1", "^[OQ": "F2", "^[OR": "F3", "^[OS": "F4",
        "^[[15~": "F5", "^[[17~": "F6", "^[[18~": "F7", "^[[19~": "F8",
        "^[[20~": "F9", "^[[21~": "F10", "^[[23~": "F11", "^[[24~": "F12",
        "^[[A": "UP", "^[[B": "DOWN", "^[[C": "RIGHT", "^[[D": "LEFT",
    }
    _ANSI_KEY_MAP_LOCAL = {
        "\x1bOP": "F1", "\x1bOQ": "F2", "\x1bOR": "F3", "\x1bOS": "F4",
        "\x1b[15~": "F5", "\x1b[17~": "F6", "\x1b[18~": "F7", "\x1b[19~": "F8",
        "\x1b[20~": "F9", "\x1b[21~": "F10", "\x1b[23~": "F11", "\x1b[24~": "F12",
        "\x1b[A": "UP", "\x1b[B": "DOWN", "\x1b[C": "RIGHT", "\x1b[D": "LEFT",
        # Shift+Up / Shift+Down (xterm modifyOtherKeys) -> treated as UP/DOWN so
        # SHIFT+UP recalls the previous command from history.
        "\x1b[1;2A": "UP", "\x1b[1;2B": "DOWN",
        "\x1bOA": "UP", "\x1bOB": "DOWN",
    }
    _CONTROL_SEQUENCE_TIMEOUT_SECONDS = 0.30
    _CONTROL_SEQUENCE_MAX_LEN = 16

    @classmethod
    def _control_map(cls) -> dict[str, str]:
        m = dict(cls._CARET_KEY_MAP)
        m.update(cls._ANSI_KEY_MAP_LOCAL)
        return m

    @classmethod
    def _control_prefixes(cls) -> set[str]:
        prefixes: set[str] = set()
        for seq in cls._control_map():
            for i in range(1, len(seq)):
                prefixes.add(seq[:i])
        return prefixes

    @classmethod
    def is_known_control_sequence(cls, seq: str) -> bool:
        return seq in cls._control_map()

    @classmethod
    def control_sequence_to_key(cls, seq: str) -> str | None:
        return cls._control_map().get(seq)

    @classmethod
    def is_known_control_prefix(cls, seq: str) -> bool:
        return seq in cls._control_prefixes()

    def _recv1_timeout(self, timeout: float) -> bytes:
        if self._pending:
            return self._recv1()
        try:
            r, _, _ = select.select([self.conn], [], [], max(0.0, timeout))
            if not r:
                return b""
            return self.conn.recv(1)
        except Exception:
            return b""

    def _text_result(self, text: str) -> InputResult:
        return InputResult(text or "")

    def _control_mode_for_seq(self, seq: str) -> str:
        if seq.startswith("^"):
            return "caret"
        if seq.startswith("\x1b"):
            return "ansi"
        return "ansi"

    def _read_control_sequence(self, first: bytes) -> InputResult:
        """Read a fragmented c3270/x3270/telnet control sequence statefully.

        c3270/x3270 in Gibson's port-2023 ANSI/NVT compatibility mode may
        deliver function keys as actual ESC sequences (``\x1b[19~``) or as
        visible caret notation (``^[[19~``).  The bytes can be fragmented across
        socket reads.  This routine keeps a pending control buffer, performs
        prefix matching, and suppresses echo until the sequence is classified.
        """
        if not first:
            return self._text_result("")
        seq = first.decode("latin1", errors="ignore")
        self._pending_control = seq
        self._pending_control_started_at = time.monotonic()
        while True:
            key = self.control_sequence_to_key(seq)
            if key:
                self._pending_control = ""
                self._pending_control_started_at = None
                return self._key_result(key, raw_text=seq, client_mode=self._control_mode_for_seq(seq))
            if not self.is_known_control_prefix(seq):
                self._pending_control = ""
                self._pending_control_started_at = None
                return self._text_result(seq)
            if len(seq) >= self._CONTROL_SEQUENCE_MAX_LEN:
                self._pending_control = ""
                self._pending_control_started_at = None
                return self._text_result(seq)
            nb = self._recv1_timeout(self._CONTROL_SEQUENCE_TIMEOUT_SECONDS)
            if not nb:
                self._pending_control = ""
                self._pending_control_started_at = None
                return self._text_result(seq)
            # Telnet negotiation can appear between bytes. Consume it and keep
            # waiting rather than flushing a key prefix as text.
            if nb and nb[0] == 255:
                self._consume_telnet_iac()
                continue
            seq += nb.decode("latin1", errors="ignore")
            self._pending_control = seq

    def _key_result(self, key: str, *, raw_text: str = "", client_mode: str = "ansi") -> InputResult:
        key_u = (key or "").upper()
        event = TerminalEvent(
            aid=key_u,
            raw_aid=None,
            is_aid=True,
            command_text=command_from_key(key_u),
            raw_text=raw_text,
            source=client_mode,
            raw_frame=(raw_text or "").encode("utf-8", errors="ignore")[:4096],
            client_mode=client_mode,
            fallback_used=True,
        )
        return InputResult("", key_u, event)

    def _read_caret_sequence(self) -> Optional[InputResult]:
        """Compatibility wrapper for older tests/extensions.

        The previous implementation used a 20ms immediate lookahead and failed
        when c3270/x3270/telnet fragmented visible caret notation.  Delegate to
        the shared stateful control-sequence reader.
        """
        result = self._read_control_sequence(b"^")
        return result if result.key else None

    def _try_read_3270_aid(self, first: int) -> Optional[InputResult]:
        """Recognise a small TN3270 AID frame without full 3270 parsing.

        Some AID byte values overlap printable ASCII (for example PF24 is
        0x4c, 'L'), so low-value AID bytes are accepted only when the following
        bytes look frame-like or include IAC EOR.  Otherwise bytes are pushed
        back and ordinary ANSI command typing continues unchanged.
        """
        frame = bytearray([first])
        saw_eor = False
        old_timeout = None
        try:
            old_timeout = self.conn.gettimeout()
        except Exception:
            pass
        try:
            try:
                self.conn.settimeout(0.02)
            except Exception:
                pass
            for _ in range(64):
                try:
                    b = self.conn.recv(1)
                except (socket.timeout, TimeoutError, BlockingIOError):
                    break
                except Exception:
                    break
                if not b:
                    break
                frame.extend(b)
                if len(frame) >= 2 and frame[-2] == 0xFF and frame[-1] == 0xEF:
                    saw_eor = True
                    break
                if b in (b"\n", b"\r"):
                    break
        finally:
            try:
                self.conn.settimeout(old_timeout)
            except Exception:
                pass
        frame_bytes = bytes(frame)
        if looks_like_3270_frame(frame_bytes):
            event = normalise_terminal_input(frame_bytes)
            if event.is_aid:
                return InputResult(event.to_legacy_command(), event.aid, event)
        aid = extract_3270_aid_key(frame_bytes, saw_eor=saw_eor)
        if aid:
            return InputResult(command_from_key(aid), aid)
        self._push_front(bytes(frame[1:]))
        return None

    def read_line(self, prompt: str = "", hidden: bool = False, mask: bool = False, timeout: float | None = None, mask_char: str = "*", history: list | None = None) -> InputResult:
        if prompt:
            self.send(prompt)
        buf = bytearray()
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        # command-history recall state (SHIFT+UP / UP recalls previous commands)
        hist = list(history) if history else None
        hist_pos = len(hist) if hist else 0

        def _replace_line(new_text: str) -> None:
            # erase the currently-typed text on screen, then write the recalled
            # command and make it the new buffer.
            nonlocal buf
            if self.echo and not hidden:
                self.send("\b" * len(buf) + " " * len(buf) + "\b" * len(buf))
            buf = bytearray(new_text.encode("utf-8", errors="ignore"))
            if self.echo and not hidden:
                self.send(new_text)

        while True:
            if deadline is None:
                b = self._recv1()
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return InputResult(buf.decode("utf-8", errors="ignore").strip(), "TIMEOUT")
                b = self._recv1_timeout(remaining)
            if not b:
                if deadline is None:
                    return InputResult("", "EOF")
                return InputResult(buf.decode("utf-8", errors="ignore").strip(), "TIMEOUT")
            ch = b[0]
            if ch == 255:  # TELNET IAC
                self._consume_telnet_iac()
                continue
            if ch in (10, 13):
                self._drain_newline_pair(ch)
                if self.echo and not hidden:
                    self.send("\n")
                elif hidden:
                    self.send("\n")
                text = buf.decode("utf-8", errors="ignore").strip()
                mapped = normalise_aid_alias(text)
                if mapped:
                    return InputResult(mapped.command, mapped.aid)
                return InputResult(text)
            if ch == 9:
                return self._key_result("TAB", raw_text="\t", client_mode="ansi")
            if ch == 27:
                ctrl = self._read_control_sequence(b)
                # In-line command history: SHIFT+UP / UP / F12 / F24 recalls
                # the previous command (F12/F24 = bash-style retrieve), DOWN
                # walks forward.  Only active when a history list was supplied
                # (so password/panel prompts are unaffected).
                if hist and ctrl.key in ("UP", "DOWN", "F12", "PF12", "F24", "PF24"):
                    if ctrl.key in ("UP", "F12", "PF12", "F24", "PF24") and hist_pos > 0:
                        hist_pos -= 1
                        _replace_line(hist[hist_pos])
                    elif ctrl.key == "DOWN":
                        if hist_pos < len(hist) - 1:
                            hist_pos += 1
                            _replace_line(hist[hist_pos])
                        else:
                            hist_pos = len(hist)
                            _replace_line("")
                    continue
                if ctrl.key:
                    return ctrl
                # Unknown ESC text should not corrupt the command buffer; keep
                # legacy behaviour by treating it as ESC/cancel-like input.
                continue
            if ch in (8, 127):
                if buf:
                    buf.pop()
                    if self.echo and not hidden:
                        self.send("\b \b")
                    elif self.echo and hidden and mask:
                        self.send("\b \b")
                continue
            if not buf and ch in AID_BYTE_TO_KEY:
                aid = self._try_read_3270_aid(ch)
                if aid is not None:
                    return aid
            if ch == ord("^"):
                ctrl = self._read_control_sequence(b)
                if ctrl.key:
                    return ctrl
                text = ctrl.text or "^"
                buf.extend(text.encode("utf-8", errors="ignore"))
                if self.echo and not hidden:
                    self.send(text)
                elif self.echo and hidden and mask:
                    self.send(mask_char * len(text))
                continue
            buf.append(ch)
            if self.echo and not hidden:
                self.send(chr(ch))
            elif self.echo and hidden and mask:
                self.send(mask_char)

    def read_line_at(self, row: int, col: int, hidden: bool = False) -> InputResult:
        """Position the cursor using ANSI, then read a line."""
        self.send(f"\x1b[{row};{col}H")
        return self.read_line("", hidden=hidden)

    def read_key(self) -> InputResult:
        """Read one interactive key/character without waiting for Enter.

        Used by full-screen telnet panels such as the ISPF editor.  Printable
        characters are returned in ``text``; PF/arrow/TAB/ENTER/BACKSPACE are
        normalised into ``key``.  TELNET IAC negotiation bytes are discarded.
        """
        while True:
            b = self._recv1()
            if not b:
                return InputResult("", "EOF")
            ch = b[0]
            if ch == 255:  # TELNET IAC
                self._consume_telnet_iac()
                continue
            if ch in (10, 13):
                self._drain_newline_pair(ch)
                return InputResult(command_from_key("ENTER"), "ENTER")
            if ch == 9:
                return self._key_result("TAB", raw_text="\t", client_mode="ansi")
            if ch == 27:
                ctrl = self._read_control_sequence(b)
                if ctrl.key:
                    return ctrl
                return InputResult("", "ESC")
            if ch in AID_BYTE_TO_KEY:
                aid = self._try_read_3270_aid(ch)
                if aid is not None:
                    return aid
            if ch in (8, 127):
                return InputResult("", "BACKSPACE")
            if ch == ord("^"):
                ctrl = self._read_control_sequence(b)
                if ctrl.key:
                    return ctrl
                text = ctrl.text or "^"
                if len(text) > 1:
                    self._push_front(text[1:].encode("utf-8", errors="ignore"))
                return InputResult(text[0], None)
            if 32 <= ch <= 126:
                return InputResult(chr(ch), None)
            return InputResult("", f"CTRL-{ch}")


@dataclass
class PanelInputResult:
    text: str = ""
    key: Optional[str] = None
    command: str = ""
    was_auto_submitted: bool = False
    raw_sequence: str = ""


def panel_input_value(result: InputResult, *, context: str = "ISPF") -> PanelInputResult:
    """Normalise panel input for ISPF/RACF/SDSF option fields.

    PF/TAB/CLEAR AID keys must be consumed as logical commands, not appended as
    printable field text.  If a terminal leaked caret-form ESC notation into a
    field, sanitize it as a fallback and return the corresponding logical key.
    """
    from gibson.render.aid_keys import extract_text_function_key, strip_known_control_text, command_from_key, normalise_aid_alias

    key = (result.key or "").strip().upper() if result else ""
    raw = (getattr(result, 'text', '') or '') if result else ''
    if key:
        return PanelInputResult(text="", key=key, command=command_from_key(key, context), was_auto_submitted=True, raw_sequence=raw)
    leaked = extract_text_function_key(raw)
    if leaked:
        return PanelInputResult(text="", key=leaked, command=command_from_key(leaked, context), was_auto_submitted=True, raw_sequence=raw)
    clean = strip_known_control_text(raw).strip()
    mapped = normalise_aid_alias(clean, context)
    if mapped:
        return PanelInputResult(text="", key=mapped.aid, command=mapped.command, was_auto_submitted=True, raw_sequence=raw)
    return PanelInputResult(text=clean, key=None, command=clean, was_auto_submitted=False, raw_sequence=raw)


def read_panel_command(driver: SocketInputDriver, row: int = 4, col: int = 13, *, context: str = "ISPF") -> PanelInputResult:
    try:
        res = driver.read_line_at(row, col)
    except Exception:
        res = driver.read_line('COMMAND ===> ')
    return panel_input_value(res, context=context)
