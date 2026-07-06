from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

# Deterministic DNS fixtures for tcp-fix utility commands. These are used by
# PING/TRACERTE by default so training output is stable and no real DNS lookup
# is required. Offensive tools use a separate restricted resolver.
DNS_FIXTURES = {
    "example.com": "93.184.216.34",
    "google-dns.example": "8.8.8.8",
    "us-fixture.example": "198.51.100.25",
    "eu-fixture.example": "203.0.113.10",
    "ru-fixture.example": "5.188.10.10",
    "ir-fixture.example": "2.176.1.1",
    "cn-fixture.example": "1.2.3.4",
    "c2-fixture.example": "198.51.100.66",
}

@dataclass
class Listener:
    name: str
    port: int
    proto: str = "TCP"
    state: str = "LISTEN"
    jobname: str = ""
    user: str = ""
    description: str = ""

@dataclass
class HomeAddress:
    address: str
    link: str
    flags: str = "P"
    mtu: int = 1500

@dataclass
class Route:
    destination: str
    gateway: str
    flags: str
    refcnt: int = 0
    interface: str = "EZASAMEM"

@dataclass
class NetworkState:
    stack: str = "TCPIP"
    hostname: str = "GIBSON"
    aliases: dict[str, str] = field(default_factory=dict)
    home: List[HomeAddress] = field(default_factory=list)
    listeners: List[Listener] = field(default_factory=list)
    routes: List[Route] = field(default_factory=list)

    @classmethod
    def seeded(cls, config=None) -> "NetworkState":
        port = getattr(config, "port", 2023)
        ftp = getattr(config, "ftp_port", 2111)
        uss = getattr(config, "uss_port", 2022)
        dash = getattr(config, "dashboard_port", 8443)
        db2 = getattr(config, "db2_tcp_port", 50000)
        db2ws = getattr(config, "db2_ws_port", 50001)
        tn3270 = getattr(config, "tn3270_port", 3270)
        n = cls()
        n.hostname = "GIBSON"
        n.aliases = {"mainframe": "127.0.0.1", "localhost": "127.0.0.1", "gibson": "127.0.0.1"}
        n.home = [
            HomeAddress("127.0.0.1", "LOOPBACK", "P"),
        ]
        n.listeners = [
            Listener("GIBWEB", 80, jobname="GIBWEB", user="GIBSON", description="Welcome to Gibson web site"),
            Listener("GIBTSO", port, jobname="TCPIP", user="TCPIP", description="Gibson TSO/VTAM telnet listener"),
            Listener("APP8080", 8080, jobname="APP8080", user="GIBSON", description="CBSA/DVCA/hack3270/Tomcat shared router"),
            Listener("FIBS9080", 9080, jobname="FIBS", user="FIBS", description="FIBS Bank and Security Academy"),
            Listener("OMVSUSS", uss, jobname="OMVS", user="OMVS", description="Gibson USS shell listener"),
            Listener("FTPD1", ftp, jobname="FTPD1", user="FTPD", description="IBM FTP CS simulated listener"),
            Listener("GIBDASH", dash, jobname="GIBDASH", user="GIBSON", description="Gibson dashboard"),
            Listener("DB2DAS", db2, jobname="DB2DAS", user="DB2A", description="Db2 DAS/DRDA style listener"),
            Listener("DB2WS", db2ws, jobname="DB2WS", user="DB2A", description="Db2 WebSocket command shell"),
            Listener("JES2S001", 175, jobname="JES2", user="JES2", description="NJE clear listener"),
            Listener("JES2TLS", 2252, jobname="JES2", user="JES2", description="NJE TLS-style listener"),
        ]
        n.routes = [
            Route("127.0.0.0/8", "0.0.0.0", "U", interface="LOOPBACK"),
            Route("0.0.0.0/0", "127.0.0.1", "UG", interface="EZATCP00"),
        ]
        return n

    def set_hostname(self, hostname: str) -> None:
        name = (hostname or "GIBSON").strip().upper() or "GIBSON"
        self.hostname = name
        if not isinstance(getattr(self, "aliases", None), dict):
            self.aliases = {}
        self.aliases.setdefault("mainframe", "127.0.0.1")
        self.aliases.setdefault("localhost", "127.0.0.1")
        self.aliases[name.lower()] = "127.0.0.1"

    def _is_local_name(self, host: str) -> bool:
        h = (host or "").strip().lower().rstrip('.')
        aliases = getattr(self, "aliases", {}) or {}
        return h in {"", "mainframe", "localhost", "127.0.0.1", "::1"} or h == (self.hostname or "").lower() or h in aliases

    def resolve_utility_target(self, host: str) -> tuple[bool, str, str]:
        """Resolve a target for general TSO/OMVS TCP/IP utilities.

        This is intentionally separate from the offensive-tool resolver used by
        nmap/CICSPWN/msfconsole.  Local Gibson names resolve to loopback;
        external-looking hostnames use deterministic classroom fixtures by
        default.  Names ending in .invalid are treated as lookup failures.
        """
        raw = (host or "mainframe").strip().rstrip('.')
        display = self.display_host_for(raw)
        if self._is_local_name(raw):
            return True, "127.0.0.1", display
        import re
        if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", raw):
            return True, raw, raw
        lower = raw.lower()
        if not lower or lower.endswith(".invalid") or " " in lower:
            return False, "", raw or "UNKNOWN"
        if lower in DNS_FIXTURES:
            return True, DNS_FIXTURES[lower], raw
        return False, "", raw

    def display_ip_for(self, host: str) -> str:
        ok, ip, _ = self.resolve_utility_target(host)
        return ip if ok else ""

    def display_host_for(self, host: str) -> str:
        h = (host or "").strip().lower().rstrip('.')
        if h == "mainframe" or h == "":
            return "mainframe"
        if h == "localhost":
            return "localhost"
        if h in {"127.0.0.1", "::1"}:
            return "127.0.0.1"
        if h == (self.hostname or "").lower():
            return (self.hostname or "GIBSON")
        return (host or "unknown")

    def _header(self, option: str) -> List[str]:
        now = datetime.now().strftime("%H:%M:%S")
        return [
            f"EZZ2350I MVS TCP/IP NETSTAT CS V2R5       {now}",
            f"EZZ2585I Stack Name: {self.stack}",
            f"EZZ2586I Display option: {option}",
        ]

    def format(self, option: str = "ALL", sessions=None) -> str:
        opt = (option or "ALL").strip().upper()
        if opt in ("", "NETSTAT"):
            opt = "ALL"
        lines = self._header(opt)
        lines.append(f"EZZ2587I Host Name: {self.hostname}")
        if opt in ("HOME", "CONFIG", "ALL"):
            lines.extend(["", "Home address list:", "Address          LinkName   Flg  MTU", "---------------  ---------  ---  ----"])
            for h in self.home:
                lines.append(f"{h.address:<15}  {h.link:<9}  {h.flags:<3}  {h.mtu}  {self.hostname}")
        if opt in ("DEVLINKS", "CONFIG", "ALL"):
            lines.extend(["", "Device/link information:", "LinkName   Type      Status   MAC/Description", "---------  --------  -------  ----------------"])
            lines.append("LOOPBACK   LOOPBACK  READY    Internal loopback / mainframe 127.0.0.1")
        if opt in ("ROUTE", "CONFIG", "ALL"):
            lines.extend(["", "IPv4 routing table:", "Destination      Gateway          Flags  Interface", "---------------  ---------------  -----  ---------"])
            for r in self.routes:
                lines.append(f"{r.destination:<15}  {r.gateway:<15}  {r.flags:<5}  {r.interface}")
        if opt in ("PORTLIST", "CONN", "TELNET", "FTP", "ALL", "IDS", "VIPADCFG"):
            lines.extend(["", "Active sockets/listeners:", "User Id   Conn     Local Socket           Foreign Socket         State    Service", "--------  -------  ---------------------  ---------------------  -------  --------"])
            for l in self.listeners:
                if opt == "TELNET" and not any(tag in l.name.upper() for tag in ("3270", "OMVS", "USS")):
                    continue
                if opt == "FTP" and "FTP" not in l.name.upper():
                    continue
                lines.append(f"{l.user:<8}  0000001  127.0.0.1..{l.port:<8}   0.0.0.0..0            {l.state:<7}  {l.name}")
            if sessions:
                for idx, sess in enumerate(sessions.values(), start=2):
                    if getattr(sess, "connected", False):
                        lines.append(f"{sess.userid:<8}  {idx:07d}  127.0.0.1..2023     {sess.addr}..3270       ESTABL  TN3270")
        if opt == "ARP":
            lines.extend(["", "ARP cache:", "IP Address       MAC Address         Interface", "---------------  ------------------  ---------"])
            lines.append("127.0.0.1        00-00-00-00-00-00   LOOPBACK")
        if opt not in {"HOME", "CONFIG", "CONN", "ALL", "DEVLINKS", "ROUTE", "ARP", "PORTLIST", "TELNET", "FTP", "VIPADCFG", "IDS"}:
            lines.append(f"EZZ2376I NETSTAT OPTION {opt} IS NOT RECOGNIZED BY GIBSON")
        lines.append("EZZ2500I NETSTAT command complete")
        return "\n".join(lines)

    def ping(self, host: str) -> str:
        target = (host or "mainframe").strip()
        ok, ip, display = self.resolve_utility_target(target)
        if not ok:
            return "\n".join([f"CS V2R5: Pinging host {target}", f"EZZ3210I Unknown host {target}", "EZZ3218I Ping complete: 0 packets transmitted, 0 packets received"])
        return "\n".join([
            f"CS V2R5: Pinging host {display}",
            f"PING {display} ({ip}): 56 bytes of data",
            f"64 bytes from {ip}: icmp_seq=0 ttl=64 time=1 ms",
            f"64 bytes from {ip}: icmp_seq=1 ttl=64 time=1 ms",
            f"64 bytes from {ip}: icmp_seq=2 ttl=64 time=1 ms",
            "EZZ3218I Ping complete: 3 packets transmitted, 3 packets received",
        ])

    def traceroute(self, host: str) -> str:
        target = (host or "mainframe").strip()
        ok, ip, display = self.resolve_utility_target(target)
        if not ok:
            return "\n".join([f"EZZ3111I Traceroute to {target}", f"EZZ3210I Unknown host {target}", "EZZ3115I Trace failed"])
        if ip == "127.0.0.1":
            hops = [f" 1  {display} (127.0.0.1)  1 ms  1 ms  1 ms"]
        else:
            hops = [
                " 1  mainframe (127.0.0.1)  1 ms  1 ms  1 ms",
                " 2  192.0.2.1       2 ms  2 ms  2 ms",
                f" 3  {display} ({ip})  3 ms  3 ms  3 ms",
            ]
        return "\n".join([f"EZZ3111I Traceroute to {display} ({ip})", *hops, "EZZ3115I Trace complete"])
