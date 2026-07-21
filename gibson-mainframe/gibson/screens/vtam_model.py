from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from gibson.render.block_letters import block_lines

DEFAULT_VERSION = "30.227"
DEFAULT_SERVICE_PORT = 2023

BLOCK_LOGO = """
          ▇▇▇▇▇▇   ▇▇▇▇  ▇▇▇▇▇▇▇    ▇▇▇▇▇▇    ▇▇▇▇▇▇   ▇▇▇    ▇▇▇
         ▇▇▇▇▇▇▇▇  ▇▇▇▇  ▇▇▇▇▇▇▇▇  ▇▇▇▇▇▇▇▇  ▇▇▇▇▇▇▇▇  ▇▇▇▇   ▇▇▇
         ▇▇▇       ▇▇▇▇  ▇▇▇   ▇▇  ▇▇▇       ▇▇▇  ▇▇▇  ▇▇▇▇▇  ▇▇▇
         ▇▇▇       ▇▇▇▇  ▇▇▇▇▇▇▇   ▇▇▇▇▇▇▇▇  ▇▇▇  ▇▇▇  ▇▇▇▇▇▇ ▇▇▇
         ▇▇▇ ▇▇▇▇  ▇▇▇▇  ▇▇▇▇▇▇▇        ▇▇▇  ▇▇▇  ▇▇▇  ▇▇▇ ▇▇▇▇▇▇
         ▇▇▇   ▇▇  ▇▇▇▇  ▇▇▇   ▇▇       ▇▇▇  ▇▇▇  ▇▇▇  ▇▇▇  ▇▇▇▇▇
         ▇▇▇▇▇▇▇▇  ▇▇▇▇  ▇▇▇▇▇▇▇▇  ▇▇▇▇▇▇▇▇  ▇▇▇▇▇▇▇▇  ▇▇▇   ▇▇▇▇
          ▇▇▇▇▇▇   ▇▇▇▇  ▇▇▇▇▇▇▇    ▇▇▇▇▇▇    ▇▇▇▇▇▇   ▇▇▇    ▇▇▇
""".strip("\n")

SECURITY_BANNER = [
    "THIS SYSTEM CONTAINS RESTRICTED INFORMATION FOR AUTHORISED USERS ONLY",
    "THE SYSTEM MAY BE MONITORED, RECORDED, AND IS SUBJECT TO AUDIT",
    "UNAUTHORIZED USE OF THE SYSTEM IS PROHIBITED UNDER SCOTTISH LAW.",
    "USE OF THE SYSTEM INDICATES CONSENT TO MONITORING AND RECORDING.",
]


def _centered_frame(title: str, panel_width: int = 78) -> list[str]:
    """Return a stable ASCII frame with equal visible indent/width.

    The old VTAM banner indented the title/bottom rows but not the first
    asterisk row.  Build all three lines together so terminal colour or
    string changes cannot desynchronise the frame.
    """
    inner = f" {str(title or '').strip()} "
    frame_width = max(33, len(inner) + 2)
    indent = max(0, (panel_width - frame_width) // 2)
    pad = " " * indent
    return [
        pad + "*" * frame_width,
        pad + "*" + inner.center(frame_width - 2) + "*",
        pad + "*" * frame_width,
    ]

@dataclass(frozen=True)
class VtamScreenModel:
    environment: str = "GIBSON PRODUCTION LPAR"
    version: str = DEFAULT_VERSION
    lu_name: str = "LU320"
    client_ip: str = "0.0.0.0"
    client_port: int | str = ""
    service_port: int | str = DEFAULT_SERVICE_PORT
    sense_code: str = "AC/00"
    gtso_version: str = "GTSOv30.227"
    gdb_version: str = "GDb30.227"
    gics_version: str = "GICS v0.30"
    prompt: str = "Logon Type:"
    system_name: str = "GIBSON"

    @classmethod
    def from_addr(cls, addr: tuple | None = None, service_port: int | str = DEFAULT_SERVICE_PORT, system_name: str | None = None) -> "VtamScreenModel":
        ip = "0.0.0.0"
        cport: int | str = ""
        if addr:
            try:
                ip = str(addr[0])
                if len(addr) > 1:
                    cport = addr[1]
            except Exception:
                pass
        sysname = (system_name or os.getenv("GIBSON_SYSTEM_HOSTNAME") or "GIBSON").strip().upper() or "GIBSON"
        return cls(client_ip=ip, client_port=cport, service_port=service_port, system_name=sysname, environment=f"{sysname} PRODUCTION LPAR")

    def full_lines(self) -> list[str]:
        lines: list[str] = []
        lines.extend(_centered_frame(self.environment, panel_width=78))
        lines.append(" " + "-" * 76)
        for line in SECURITY_BANNER:
            lines.append(line.center(78))
        lines.append(" " + "-" * 76)
        lines.append("")
        # Raw VTAM/telnet clients vary in UTF-8 support. Use an ASCII-safe
        # dynamic logo for every hostname so the logon panel does not render
        # Unicode block bytes as mojibake.
        lines.extend(block_lines(self.system_name, max_width=78, fill="#"))
        lines.append("")
        lines.append(f"             LU NAME:  {self.lu_name:<8}  CLIENT IP: {self.client_ip:<15}  CLIENT PORT: {self.client_port}")
        lines.append("")
        lines.append(f"             SENSE CODE: {self.sense_code:<8}              SERVICE PORT: {self.service_port}")
        lines.append("             " + "-" * 65)
        lines.append("")
        lines.append(f"             {self.gtso_version:<24}     {self.gdb_version:<22}     {self.gics_version}")
        lines.append("LOGON using L TSO, L CICS, L DB2, L IMS, L ZVM or L TPF.")
        lines.append(self.prompt)
        return [line[:132] for line in lines]

    def compact_lines(self) -> list[str]:
        return [
            "-" * 78,
            f"                         {self.environment}",
            "-" * 78,
            "",
            f" THIS SYSTEM IS A {self.system_name} TRAINING SIMULATOR. USE IS MONITORED.",
            "",
            f" LU NAME      : {self.lu_name}",
            f" CLIENT IP    : {self.client_ip}",
            f" SERVICE PORT : {self.service_port}",
            f" CLIENT PORT  : {self.client_port}",
            f" SENSE CODE   : {self.sense_code}",
            "",
            f" {self.gtso_version:<18} {self.gdb_version:<18} {self.gics_version}",
            "",
            " LOGON using L TSO, L CICS, L DB2, L IMS, L ZVM or L TPF.",
            "",
            " Logon Type:",
        ]


def write_canonical_assets(root: Path | None = None) -> None:
    base = root or Path(__file__).resolve().parents[1]
    text = "\n".join(VtamScreenModel(client_ip="xxx.xxx.xxx.xxx", client_port="yyyyy", system_name="GIBSON").full_lines()) + "\n"
    for rel in ("screens/vtam.txt", "assets/vtam.txt"):
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
