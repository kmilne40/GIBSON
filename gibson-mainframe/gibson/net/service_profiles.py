from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class ServiceProfile:
    """Scanner-visible identity for a Gibson listener.

    These profiles deliberately describe only service-level behaviour.  They do
    not attempt to spoof the host TCP/IP stack or change lab command semantics.
    """

    name: str
    default_port: int
    protocol: str
    banner: str = ""
    nmap_service: str = ""
    nmap_version: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""


def ftp_banner(hostname: str = "GIBSON", product: str = "Gibson FTPD") -> str:
    now = datetime.now()
    return (
        f"220-GIBSON FTP service at {hostname.upper()}, {now:%H:%M:%S} on {now:%Y-%m-%d}.\r\n"
        "220 Connection will close if idle for more than 5 minutes.\r\n"
    )


FTP_ZOS = ServiceProfile(
    name="FTPD1",
    default_port=21,
    protocol="ftp",
    nmap_service="ftp",
    nmap_version="Gibson FTPD",
    notes="Protocol-safe FTP greeting; no scanner spoofing is injected at runtime.",
)

TN3270E = ServiceProfile(
    name="VTAM23",
    default_port=23,
    protocol="telnet/tn3270",
    nmap_service="tn3270",
    nmap_version="Gibson VTAM TN3270",
    notes="Clean Telnet negotiation only; no fake service prologue or probe response.",
)

VTAM_TELNET = ServiceProfile(
    name="GIBTSO",
    default_port=23,
    protocol="telnet/vtam",
    nmap_service="tn3270",
    nmap_version="Gibson VTAM compatible listener",
    notes="Line-mode compatible listener; TN3270 mode is used only after negotiation.",
)

NJE = ServiceProfile(
    name="GIBNJE",
    default_port=175,
    protocol="nje",
    nmap_service="nje",
    nmap_version="IBM Network Job Entry (JES2)",
    notes="Silent until the 33-byte OPEN record; answers ACK/NAK with reason codes 0x01/0x04.",
)

NJE_TLS = ServiceProfile(
    name="GIBNJETLS",
    default_port=2252,
    protocol="ssl/nje",
    nmap_service="nje",
    nmap_version="IBM Network Job Entry (JES2 over TLS)",
    notes="NJE over TLS; deploy certificates and mutual authentication.",
)

HTTP_DASHBOARD = ServiceProfile(
    name="GIBDASH",
    default_port=8443,
    protocol="http",
    nmap_service="http",
    nmap_version="Gibson Dashboard",
    headers={"X-Powered-By": "Gibson z/OS Simulator"},
)

