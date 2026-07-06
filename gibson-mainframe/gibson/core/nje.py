from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

class LineStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DRAINED = "DRAINED"
    INACTIVE = "INACTIVE"

@dataclass
class NJENode:
    name: str
    status: str = "ACTIVE"
    local: bool = False
    number: int = 1
    password: str = ""
    auth: str = "JOB=YES,NET=NO,DEVICE=NO,SYSTEM=NO"
    subnet: str = "CORP"

@dataclass
class NJELine:
    name: str
    node: str
    status: LineStatus = LineStatus.ACTIVE
    port: int = 175
    secure: bool = False

@dataclass
class NJENetwork:
    nodes: Dict[str, NJENode] = field(default_factory=dict)
    lines: Dict[str, NJELine] = field(default_factory=dict)

    @classmethod
    def seeded(cls) -> "NJENetwork":
        n = cls()
        n.nodes = {
            "GIBSON": NJENode("GIBSON", "OWNNODE", True, 1, subnet="CORP"),
            "HAL": NJENode("HAL", "ACTIVE", False, 2, password="HAL123", auth="JOB=YES,NET=YES,DEVICE=NO,SYSTEM=NO"),
            "ORAC": NJENode("ORAC", "ACTIVE", False, 3, password="ORAC123", auth="JOB=YES,NET=NO,DEVICE=NO,SYSTEM=NO"),
            "H4CKR": NJENode("H4CKR", "DRAINED", False, 4, password="", auth="JOB=NO,NET=NO,DEVICE=NO,SYSTEM=NO"),
        }
        n.lines = {
            "LINE1": NJELine("LINE1", "HAL", LineStatus.ACTIVE, 175, False),
            "LINE2": NJELine("LINE2", "ORAC", LineStatus.DRAINED, 2252, True),
        }
        return n

    def command(self, cmd: str) -> str | None:
        u = cmd.strip().upper()
        if u in ("$D NJEDEF", "$D N") or u.startswith("$D NJEDEF"):
            return self.display_njedef()
        if u in ("$D NODE", "$DNODE"):
            return self.display_nodes()
        if u.startswith("$D NODE("):
            name = u.split("(", 1)[1].split(")", 1)[0]
            node = self.nodes.get(name)
            return f"$HASP826 NODE({name}) NOT FOUND" if not node else self.display_node(node)
        if u in ("$D LINE", "$D L"):
            return self.display_lines()
        if u.startswith("$S LINE") or u.startswith("$S L"):
            line = u.split()[-1].replace(",", "").upper()
            if line in self.lines:
                self.lines[line].status = LineStatus.ACTIVE
                return f"$HASP000 {line} STARTED"
        if u.startswith("$P LINE") or u.startswith("$P L"):
            line = u.split()[-1].replace(",", "").upper()
            if line in self.lines:
                self.lines[line].status = LineStatus.DRAINED
                return f"$HASP000 {line} DRAINED"
        # ---- NMR operator-command injection (iNJEctor.py, Listings 10-11/12) ----
        # $T NJEDEF,NODENUM=n  - change the number of declared nodes
        if u.startswith("$T NJEDEF"):
            m = __import__("re").search(r"NODENUM=(\d+)", u)
            if m:
                self.nodenum = int(m.group(1))
                return ("$HASP831 NJEDEF\n"
                        f"$HASP831 NJEDEF OWNNAME=GIBSON,OWNNODE=1,CONNECT=(YES,10),\n"
                        f"$HASP831         NODENUM={self.nodenum}")
            return "$HASP003 RC=(52) - INVALID NJEDEF OPERAND"
        # $T NODE(n),NAME=H4CKR  - (re)define a node (add the rogue node)
        if u.startswith("$T NODE("):
            import re as _re
            num = _re.search(r"NODE\((\w+)\)", u)
            nm = _re.search(r"NAME=(\w+)", u)
            au = _re.search(r"AUTH=\(([^)]*)\)", u)
            if num and nm:
                name = nm.group(1).upper()
                self.nodes[name] = NJENode(name, "UNCONNECTED", False,
                                           int(num.group(1)) if num.group(1).isdigit() else len(self.nodes) + 1,
                                           auth="JOB=NO,NET=NO,DEVICE=NO,SYSTEM=NO")
                return (f"$HASP826 NODE({num.group(1)})\n"
                        f"$HASP826 NODE({num.group(1)}) NAME={name},STATUS=(UNCONNECTED),TRANSMIT=BOTH,")
            if num and au:
                # resolve node by number or name and set its authorities
                target = None
                for node in self.nodes.values():
                    if str(node.number) == num.group(1) or node.name == num.group(1).upper():
                        target = node
                        break
                if target is not None:
                    target.auth = au.group(1).upper().replace(" ", "")
                    return (f"$HASP826 NODE({target.number}) NAME={target.name},STATUS=(UNCONNECTED),\n"
                            f"$HASP826 AUTH=({target.auth})")
            return "$HASP003 RC=(52) - INVALID NODE OPERAND"
        # $ADD SOCKET(h4ckr),NODE=h4ckr,IPADDR=...  - point a socket at attacker IP
        if u.startswith("$ADD SOCKET(") or u.startswith("$T SOCKET("):
            import re as _re
            sm = _re.search(r"SOCKET\((\w+)\)", u)
            ipm = _re.search(r"IPADDR=([\d.]+)", u)
            nm = _re.search(r"NODE=(\w+)", u)
            if sm:
                name = sm.group(1).upper()
                self.lines[f"SOCK_{name}"] = NJELine(f"SOCK_{name}", (nm.group(1).upper() if nm else name),
                                                     LineStatus.INACTIVE, 175, False)
                ip = ipm.group(1) if ipm else "0.0.0.0"
                return (f"$HASP897 SOCKET({name})\n"
                        f"$HASP897 SOCKET({name}) STATUS=INACTIVE,IPADDR={ip},")
        return None

    def display_njedef(self) -> str:
        return "\n".join([
            "RESPONSE=GIB1",
            "$HASP831 NJEDEF",
            "$HASP831 NJEDEF  OWNNAME=GIBSON,OWNNODE=1,CONNECT=(YES,10),",
            "$HASP831         DELAY=120,HDRBUF=(LIMIT=10,WARN=80,FREE=10),",
            "$HASP831         JRNUM=1,JTNUM=1,SRNUM=1,STNUM=1,LINENUM=2,",
            "$HASP831         MAILMSG=NO,MAXHOP=16,NODENUM=50,PATH=1,",
            "$HASP831         RESTMAX=8000000,RESTNODE=150,RESTTOL=300,",
            "$HASP831         TIMETOL=30",
        ])

    def display_node(self, node: NJENode) -> str:
        return "\n".join([
            f"$HASP826 NODE({node.name}) STATUS={node.status},NUMBER={node.number},SUBNET={node.subnet}",
            f"$HASP826          AUTH=({node.auth})",
            f"$HASP826          PASSWORD={'********' if node.password else 'NONE'}",
        ])

    def display_nodes(self) -> str:
        lines = ["$HASP826 NJE NODE DISPLAY", "NODE     STATUS    LOCAL  AUTH", "-------- --------  -----  ------------------------------"]
        for node in self.nodes.values():
            lines.append(f"{node.name:<8} {node.status:<8} {'YES' if node.local else 'NO ':<5}  {node.auth}")
        lines.append("")
        lines.extend(self.display_lines().splitlines())
        return "\n".join(lines)

    def display_lines(self) -> str:
        lines = ["$HASP827 NJE LINE DISPLAY", "LINE     NODE     STATUS   PORT  SECURE", "-------- -------- -------- ----- ------"]
        for line in self.lines.values():
            lines.append(f"{line.name:<8} {line.node:<8} {line.status.value:<8} {line.port:<5} {'YES' if line.secure else 'NO'}")
        return "\n".join(lines)


# Chapter 10 NJE lab fixtures and helpers. Safe internal simulator only.
CHAPTER10_NODES = {
    'GIBSON': {'number':'001','password':'GIBSONPW','auth':'JOB,NET,DEVICE,SYSTEM','ports':[175,2252], 'secure':'OPTIONAL'},
    'HAL': {'number':'002','password':'HAL123','auth':'JOB,NET','ports':[175,2252], 'secure':'TLS-LABELLED'},
    'ORAC': {'number':'003','password':'ORACPW','auth':'JOB','ports':[175], 'secure':'CLEAR'},
}
def display_njedef() -> str:
    return 'NJEDEF  NODENUM=001  OWNNAME=GIBSON  NETSERV=GIBNJE  SOCKETS=(GIBSOCK,HALSO,ORACSOCK)'
def display_nodes() -> str:
    return '\n'.join([f"NODE({n}) NUMBER({v['number']}) AUTH=({v['auth']}) SECURE={v['secure']}" for n,v in CHAPTER10_NODES.items()])
def display_lines() -> str:
    return 'LINE1 UNIT=TCPIP STATUS=ACTIVE NODE=HAL\nLINE2 UNIT=TCPIP STATUS=ACTIVE NODE=ORAC'
def display_sockets() -> str:
    return 'SOCKET(GIBSOCK) PORT=175 STATUS=ACTIVE\nSOCKET(GIBTLS) PORT=2252 STATUS=ACTIVE TLS=YES'
def handshake(ohost: str, rhost: str, password: str='') -> str:
    oh=(ohost or '').upper(); rh=(rhost or '').upper()
    if oh not in CHAPTER10_NODES: return 'NAK REASON=0x01 UNKNOWN OHOST'
    if rh not in CHAPTER10_NODES: return 'NAK REASON=0x04 INVALID OR UNAUTHORISED RHOST'
    if password and password != CHAPTER10_NODES[oh]['password']: return 'NAK REASON=0x08 INVALID NODE PASSWORD'
    return f'OPEN OHOST={oh} RHOST={rh} ACK NODE={CHAPTER10_NODES[oh]["number"]}'
def xeq_job(target: str, jobname: str='GIBXEQ') -> str:
    t=(target or 'HAL').upper()
    if t not in CHAPTER10_NODES: return '$HASP122 NJE XEQ REJECTED - UNKNOWN NODE'
    return f"$HASP122 JOB {jobname} ROUTED VIA NJE TO {t}\nIEF403I {jobname} - STARTED - TIME=00.00.01\nIEF404I {jobname} - ENDED - COND CODE 0000"
