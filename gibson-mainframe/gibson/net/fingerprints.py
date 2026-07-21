from __future__ import annotations

from typing import Iterable

from .service_profiles import ftp_banner

HTTP_SERVER_HEADER = ""
GIBSON_POWERED_BY = ""


def ftp_greeting(hostname: str = "GIBSON") -> str:
    # Matches nmap's service-detection signature:
    #   match ftp m/^220-([-.\w]+) IBM FTP.*(V\d+R\d+)/ p|IBM OS/390 ftpd| v/$2/ o|OS/390|
    # so `nmap -sV` reports the listener as "IBM OS/390 ftpd V2R5", as a real
    # z/OS Communications Server FTP daemon would. Training/simulator use only.
    from datetime import datetime
    host = hostname.upper()
    now = datetime.now()
    return (
        f"220-{host} IBM FTP CS V2R5 at {host}, {now:%H:%M:%S} on {now:%Y-%m-%d}.\r\n"
        f"220 Connection will not be allowed to remain inactive for more than 5 minutes.\r\n"
    )


def ftp_feat_response() -> str:
    return "\r\n".join([
        "211-Extensions supported:",
        " EPSV",
        " PASV",
        " SITE FILETYPE=FILE",
        " SITE FILETYPE=JES",
        " SITE FILETYPE=SQL",
        " SITE JES STATUS",
        " SITE JES PURGE",
        " SIZE",
        " HELP",
        "211 End",
    ]) + "\r\n"


def ftp_help_response(commands: Iterable[str] | None = None) -> str:
    cmds = commands or (
        "USER PASS QUIT SYST FEAT HELP PWD CWD TYPE PASV EPSV LIST NLST RETR STOR SITE",
        "SITE FILETYPE=FILE | SITE FILETYPE=JES | SITE FILETYPE=SQL",
    )
    lines = ["214-The following commands are recognized:"]
    lines.extend(f" {line}" for line in cmds)
    lines.append("214 Direct comments to GIBSON simulated FTPD1.")
    return "\r\n".join(lines) + "\r\n"


def zos_ftp_syst() -> str:
    return "215 UNIX Type: L8 Gibson simulated FTP service.\r\n"


def http_fingerprint_headers() -> dict[str, str]:
    return {}
