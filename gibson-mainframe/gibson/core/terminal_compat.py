from __future__ import annotations

import os
import re
from dataclasses import dataclass

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class TerminalProfile:
    name: str = "RAW"
    cols: int = 132
    rows: int = 24
    echo_input: bool = True
    crlf: bool = False

    @property
    def is_guacamole(self) -> bool:
        return self.name.upper() == "GUACAMOLE"


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def normalize_crlf(text: str) -> str:
    """Convert all logical line endings to CRLF without creating CRCRLF."""
    if not text:
        return text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "\r\n")


def detect_terminal_profile(addr: tuple | None = None, terminal_type: str = "", cols: int | None = None, rows: int | None = None) -> TerminalProfile:
    """Choose a conservative compatibility profile for browser/Guacamole sessions.

    Guacamole's guacd container connects to Gibson from a Docker bridge address.
    In that path the browser terminal is typically 80x24 and echoes input locally.
    Raw ncat/telnet sessions on 2023 keep the legacy behaviour.
    """
    ip = ""
    if addr:
        try:
            ip = str(addr[0])
        except Exception:
            ip = ""
    tt = (terminal_type or "").upper()
    forced = os.environ.get("GIBSON_TERMINAL_PROFILE", "").upper()
    guac_nets = tuple(x.strip() for x in os.environ.get("GIBSON_GUACAMOLE_SOURCE_PREFIXES", "172.,10.88.,10.89.,192.168.255.").split(",") if x.strip())
    is_guac = forced == "GUACAMOLE" or "GUAC" in tt or any(ip.startswith(prefix) for prefix in guac_nets)
    if is_guac:
        return TerminalProfile("GUACAMOLE", cols or 80, rows or 24, echo_input=False, crlf=True)
    return TerminalProfile("RAW", cols or 132, rows or 24, echo_input=True, crlf=False)


def compact_vtam_screen(*, lu_name: str = "LU320", ip_address: str = "0.0.0.0", port: int | str = "", service_port: int | str = 2023, version: str = "30.227", system_name: str | None = None) -> str:
    """80-column-safe VTAM/logon screen from the canonical VTAM model."""
    from gibson.screens.vtam_model import VtamScreenModel
    model = VtamScreenModel(lu_name=lu_name, client_ip=ip_address, client_port=port, service_port=service_port, system_name=(system_name or "GIBSON").upper(), environment=f"{(system_name or 'GIBSON').upper()} PRODUCTION LPAR")
    return "\n".join(line[:78] for line in model.compact_lines()) + "\n"


def screen_lines_fit(text: str, cols: int) -> bool:
    return all(visible_len(line) <= cols for line in text.splitlines())
