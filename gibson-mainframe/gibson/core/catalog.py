from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json
import re

@dataclass
class CatalogAlias:
    name: str
    relate: str


@dataclass
class VsamCluster:
    """An ICF-catalogued VSAM cluster, with its DATA/INDEX/PATH/AIX
    associations, history, allocation and SMS class information - enough to
    render an authentic ``LISTCAT ENTRIES(...) ALL`` listing."""
    name: str
    cluster_type: str = "INDEXED"        # INDEXED | NONINDEXED | LINEAR | NUMBERED
    keys_len: int = 0
    keys_off: int = 0
    avg_reclen: int = 0
    max_reclen: int = 0
    tracks_pri: int = 0
    tracks_sec: int = 0
    cisize: int = 4096
    shareoptions: str = "(2 3)"
    volser: str = "SBVSM1"
    storclas: str = "SCSTD"
    mgmtclas: str = "MCSTD"
    dataclas: str = "DCVSAM"
    owner: str = ""
    created: str = ""
    aix: List[str] = field(default_factory=list)     # AIX names
    paths: List[str] = field(default_factory=list)   # PATH names

    @property
    def data_component(self) -> str:
        return f"{self.name}.DATA"

    @property
    def index_component(self) -> str:
        return f"{self.name}.INDEX"

    def to_dict(self) -> dict:
        return self.__dict__.copy()

@dataclass
class CatalogManager:
    path: Path
    aliases: Dict[str, CatalogAlias] = field(default_factory=dict)
    clusters: Dict[str, VsamCluster] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "CatalogManager":
        mgr = cls(path=path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for name, relate in data.get("aliases", {}).items():
                    mgr.aliases[name.upper()] = CatalogAlias(name.upper(), str(relate).upper())
                for name, c in data.get("clusters", {}).items():
                    try:
                        mgr.clusters[name.upper()] = VsamCluster(**c)
                    except Exception:
                        continue
            except Exception:
                pass
        if not mgr.aliases:
            mgr.aliases = {
                "SYS1": CatalogAlias("SYS1", "USERCAT.SYS1"),
                "IBMUSER": CatalogAlias("IBMUSER", "USERCAT.USER"),
                "TCPIP": CatalogAlias("TCPIP", "USERCAT.TCPIP"),
            }
        return mgr

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "aliases": {k: v.relate for k, v in self.aliases.items()},
            "clusters": {k: v.to_dict() for k, v in self.clusters.items()},
        }, indent=2), encoding="utf-8")

    def define_alias(self, name: str, relate: str) -> str:
        self.aliases[name.upper()] = CatalogAlias(name.upper(), relate.upper())
        self.save()
        return f"IDC3009I ALIAS {name.upper()} DEFINED TO {relate.upper()}"

    def list_aliases(self) -> str:
        lines = ["ALIAS NAME                 RELATE", "----------                 ------------------------------"]
        for name in sorted(self.aliases):
            lines.append(f"{name:<26} {self.aliases[name].relate}")
        return "\n".join(lines)

    # --------------------------------------------------------------- VSAM
    @staticmethod
    def _kw(cmd: str, key: str) -> Optional[str]:
        m = re.search(key + r"\(([^)]*)\)", cmd, re.I)
        return m.group(1).strip() if m else None

    def define_cluster(self, cmd: str, owner: str = "IBMUSER") -> str:
        name = self._kw(cmd, "NAME")
        if not name:
            return ("IDC3014I CATALOG ERROR\n"
                    "IDC3009I ** VSAM CATALOG RETURN CODE IS 8 - REASON CODE IS IGG0CLEG-40\n"
                    "IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 8")
        name = name.upper()
        if name in self.clusters:
            return (f"IDC3014I CATALOG ERROR\n"
                    f"IDC3009I ** VSAM CATALOG RETURN CODE IS 8 - REASON CODE IS IGG0CLEG-6\n"
                    f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 8")
        u = cmd.upper()
        ctype = ("NONINDEXED" if "NONINDEXED" in u else
                 "LINEAR" if "LINEAR" in u or "LINEAR " in u else
                 "NUMBERED" if "NUMBERED" in u else "INDEXED")
        keys = self._kw(cmd, "KEYS")
        klen, koff = (0, 0)
        if keys:
            nums = re.findall(r"\d+", keys)
            if len(nums) >= 2:
                klen, koff = int(nums[0]), int(nums[1])
        rs = self._kw(cmd, "RECORDSIZE") or self._kw(cmd, "RECSZ")
        avg, mx = (0, 0)
        if rs:
            nums = re.findall(r"\d+", rs)
            if len(nums) >= 2:
                avg, mx = int(nums[0]), int(nums[1])
        tracks = self._kw(cmd, "TRACKS") or self._kw(cmd, "TRK")
        cyl = self._kw(cmd, "CYLINDERS") or self._kw(cmd, "CYL")
        pri, sec = (1, 1)
        src = tracks or cyl
        if src:
            nums = re.findall(r"\d+", src)
            if nums:
                pri = int(nums[0])
                sec = int(nums[1]) if len(nums) > 1 else 0
            if cyl:                      # 15 tracks/cylinder (3390)
                pri *= 15; sec *= 15
        c = VsamCluster(
            name=name, cluster_type=ctype, keys_len=klen, keys_off=koff,
            avg_reclen=avg, max_reclen=mx, tracks_pri=pri, tracks_sec=sec,
            shareoptions="(" + (self._kw(cmd, "SHAREOPTIONS") or self._kw(cmd, "SHR") or "2 3") + ")",
            volser=(self._kw(cmd, "VOLUMES") or self._kw(cmd, "VOL") or "SBVSM1").split()[0].upper(),
            storclas=(self._kw(cmd, "STORAGECLASS") or self._kw(cmd, "STORCLAS") or "SCSTD").upper(),
            mgmtclas=(self._kw(cmd, "MANAGEMENTCLASS") or self._kw(cmd, "MGMTCLAS") or "MCSTD").upper(),
            dataclas=(self._kw(cmd, "DATACLASS") or self._kw(cmd, "DATACLAS") or "DCVSAM").upper(),
            owner=owner.upper(),
            created=datetime.now().strftime("%Y.%j"),
        )
        self.clusters[name] = c
        self.save()
        out = ["IDCAMS  SYSTEM SERVICES",
               f"IDC0508I DATA ALLOCATION STATUS FOR VOLUME {c.volser} IS 0",
               f"IDC0512I NAME GENERATED-(D) {c.data_component}"]
        if ctype == "INDEXED":
            out.append(f"IDC0509I INDEX ALLOCATION STATUS FOR VOLUME {c.volser} IS 0")
            out.append(f"IDC0512I NAME GENERATED-(I) {c.index_component}")
        out.append("IDC0181I STORAGECLASS USED IS " + c.storclas)
        out.append("IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 0")
        return "\n".join(out)

    def define_aix(self, cmd: str) -> str:
        name = self._kw(cmd, "NAME")
        rel = self._kw(cmd, "RELATE")
        if not name or not rel:
            return "IDC3009I DEFINE AIX SYNTAX: DEFINE AIX(NAME(aixname) RELATE(clustername) KEYS(...))"
        name, rel = name.upper(), rel.upper()
        base = self.clusters.get(rel)
        if not base:
            return (f"IDC3012I ENTRY {rel} NOT FOUND\n"
                    f"IDC3009I ** VSAM CATALOG RETURN CODE IS 8 - REASON CODE IS IGG0CLEG-42\n"
                    f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 8")
        if name not in base.aix:
            base.aix.append(name)
        self.save()
        return "\n".join([
            "IDCAMS  SYSTEM SERVICES",
            f"IDC0512I NAME GENERATED-(D) {name}.DATA",
            f"IDC0512I NAME GENERATED-(I) {name}.INDEX",
            f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 0",
        ])

    def define_path(self, cmd: str) -> str:
        name = self._kw(cmd, "NAME")
        rel = self._kw(cmd, "PATHENTRY")
        if not name or not rel:
            return "IDC3009I DEFINE PATH SYNTAX: DEFINE PATH(NAME(pathname) PATHENTRY(aixname))"
        name = name.upper()
        for c in self.clusters.values():
            if rel.upper() in c.aix or rel.upper() == c.name:
                if name not in c.paths:
                    c.paths.append(name)
                self.save()
                return ("IDCAMS  SYSTEM SERVICES\n"
                        f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 0")
        return (f"IDC3012I ENTRY {rel.upper()} NOT FOUND\n"
                f"IDC3009I ** VSAM CATALOG RETURN CODE IS 8 - REASON CODE IS IGG0CLEG-42\n"
                f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 8")

    def delete_cluster(self, name: str) -> str:
        name = name.upper().strip("'")
        if name not in self.clusters:
            return (f"IDC3012I ENTRY {name} NOT FOUND\n"
                    f"IDC3009I ** VSAM CATALOG RETURN CODE IS 8 - REASON CODE IS IGG0CLEG-42\n"
                    f"IDC0551I ** ENTRY {name} NOT DELETED\n"
                    f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 8")
        self.clusters.pop(name)
        self.save()
        return "\n".join([
            f"IDC0550I ENTRY (C) {name} DELETED",
            f"IDC0550I ENTRY (D) {name}.DATA DELETED",
            f"IDC0550I ENTRY (I) {name}.INDEX DELETED",
            "IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 0",
        ])

    def listcat_entry(self, name: str) -> Optional[str]:
        """Full LISTCAT ENTRIES(name) ALL for a VSAM cluster, or None if the
        name is not a known cluster (caller falls back to dataset listing)."""
        c = self.clusters.get(name.upper().strip("'"))
        if not c:
            return None
        L: List[str] = ["IDCAMS  SYSTEM SERVICES"]
        L.append(f"CLUSTER ------- {c.name}")
        L.append(f"      IN-CAT --- USERCAT.VSAM")
        L.append("      HISTORY")
        L.append(f"        OWNER-IDENT-----{c.owner:<8}   CREATION--------{c.created}")
        L.append(f"        RELEASE----------------2   EXPIRATION------0000.000")
        L.append("      ASSOCIATIONS")
        L.append(f"        DATA-----{c.data_component}")
        if c.cluster_type == "INDEXED":
            L.append(f"        INDEX----{c.index_component}")
        for a in c.aix:
            L.append(f"        AIX------{a}")
        for p in c.paths:
            L.append(f"        PATH-----{p}")
        L.append("      SMSDATA")
        L.append(f"        STORAGECLASS ---{c.storclas:<8}  MANAGEMENTCLASS-{c.mgmtclas}")
        L.append(f"        DATACLASS ------{c.dataclas:<8}  LBACKUP ---0000.000.0000")
        L.append(f"    DATA ------- {c.data_component}")
        L.append("      ATTRIBUTES")
        L.append(f"        KEYLEN--------------{c.keys_len:>5}     RKP----------------{c.keys_off:>5}"
                 f"     AVGLRECL-----------{c.avg_reclen:>5}     MAXLRECL-----------{c.max_reclen:>5}")
        L.append(f"        CISIZE-------------{c.cisize:>6}     SHROPTNS{c.shareoptions:<6}"
                 f"     {'INDEXED' if c.cluster_type=='INDEXED' else c.cluster_type}")
        L.append("      ALLOCATION")
        L.append(f"        SPACE-TYPE------TRACK      HI-A-RBA-------{c.tracks_pri*56664:>10}")
        L.append(f"        SPACE-PRI----------{c.tracks_pri:>5}     HI-U-RBA-------{0:>10}")
        L.append(f"        SPACE-SEC----------{c.tracks_sec:>5}     VOLUME---------{c.volser}")
        if c.cluster_type == "INDEXED":
            L.append(f"    INDEX ------ {c.index_component}")
            L.append("      ATTRIBUTES")
            L.append(f"        KEYLEN--------------{c.keys_len:>5}     LEVELS--------------    1")
        L.append("IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 0")
        return "\n".join(L)

