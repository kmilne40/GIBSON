from __future__ import annotations

from typing import Any

PARMLIB_MEMBERS = {
    "IEASYS00": "SYSNAME=MVSC\nIPLPARM=SYS1.IPLPARM\nPROG=00\nSMF=00\nOMVS=00\nCON=00\n",
    "COMMND00": "COM='S JES2'\nCOM='S TCPIP'\nCOM='S CICS'\nCOM='S DB2A'\nCOM='S FIBS'\n",
    "PROG00": "APF ADD DSNAME(SYS1.LINKLIB) VOLUME(SBSYS1)\nAPF ADD DSNAME(SYS1.SVCLIB) VOLUME(SBSYS1)\nLNKLST ADD NAME(LNKLST00) DSNAME(SYS1.LINKLIB)\n",
    "IKJTSO00": "AUTHCMD NAMES(CONSOLE,OPER,PARMLIB)\nAUTHPGM NAMES(IKJEFT01,IRXJCL)\n",
    "CONSOL00": "CONSOLE DEVNUM(0700) AUTH(MASTER) ROUTCODE(ALL)\nDEFAULT LEVEL(ALL)\n",
    "SMFPRM00": "ACTIVE\nDSNAME(SYS1.MAN1,SYS1.MAN2)\nJWT(003000)\nTYPE(30,80,101,110,119)\n",
    "BPXPRM00": "ROOT FILESYSTEM('OMVS.ZFS.ROOT') TYPE(ZFS) MODE(RDWR)\nFILESYSTYPE TYPE(ZFS) ENTRYPOINT(IOEFSCM)\n",
    "TCPIP": "PROFILE TCPIP\nPORT 2023 TCP GIBSONVTAM\nPORT 8080 TCP CBSA\nPORT 9080 TCP FIBS\n",
}
PROCLIB_MEMBERS = {
    "JES2": "//JES2 PROC\n//IEFPROC EXEC PGM=HASJES20\n",
    "CICS": "//CICS PROC APPLID=CICS\n//DFHSIP EXEC PGM=DFHSIP,PARM='START=AUTO'\n",
    "DB2A": "//DB2A PROC\n//DSN1MSTR EXEC PGM=DSN1MSTR\n",
    "TCPIP": "//TCPIP PROC\n//TCPIP EXEC PGM=EZBTCPIP\n",
    "FIBS": "//FIBS PROC PORT=9080\n//WEB EXEC PGM=FIBS9080\n",
}


def _live_members(state: Any, dsn: str, fallback: dict[str, str]) -> dict[str, str]:
    """Read the real members of a SYS1 PDS from the live dataset store so the
    explorer reflects the actual seeded PARMLIB/PROCLIB content (system GIBSON),
    not a hardcoded stub. Falls back to the static dict if the dataset or store
    is unavailable (e.g. a bare state in a unit test)."""
    ds = getattr(state, "datasets", None)
    if ds is None:
        return dict(fallback)
    try:
        names = ds.members("IBMUSER", dsn)
    except Exception:
        return dict(fallback)
    out: dict[str, str] = {}
    for name in names:
        try:
            out[name.upper()] = ds.read("IBMUSER", f"{dsn}({name})")
        except Exception:
            continue
    return out or dict(fallback)


def _live_apf(state: Any) -> list[str]:
    """Prefer the APF list parsed from the live PROG00 member; fall back to the
    runtime apf_libraries list (which escalation labs mutate)."""
    runtime = list(getattr(state, "apf_libraries", []))
    members = _live_members(state, "SYS1.PARMLIB", {})
    prog = members.get("PROG00", "")
    parsed: list[str] = []
    for line in prog.splitlines():
        s = line.strip().upper()
        if s.startswith("APF ADD") and "DSNAME(" in s:
            try:
                parsed.append(s.split("DSNAME(", 1)[1].split(")", 1)[0].strip())
            except Exception:
                continue
    # Union: real PROG00 APF entries plus any runtime-added (rogue) libraries.
    merged = parsed[:]
    for dsn in runtime:
        if dsn not in merged:
            merged.append(dsn)
    return merged or runtime


def _live_linklist(state: Any) -> list[str]:
    members = _live_members(state, "SYS1.PARMLIB", {})
    body = members.get("LNKLST00") or members.get("PROG00", "")
    out: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("/*", "*", "LNKLST DEFINE", "LNKLST ACTIVATE")):
            continue
        if s.upper().startswith("LNKLST ADD") and "DSNAME(" in s.upper():
            out.append(s.upper().split("DSNAME(", 1)[1].split(")", 1)[0].strip())
        elif "." in s and " " not in s:          # plain DSN-per-line LNKLST00
            out.append(s)
    return out or ["SYS1.LINKLIB", "SYS1.MIGLIB", "SYS1.CSSLIB", "CEE.SCEERUN"]


def _live_iplinfo(state: Any) -> dict[str, str]:
    sysname = str(getattr(getattr(state, "network", None), "hostname", "") or "GIBSON").upper()
    members = _live_members(state, "SYS1.PARMLIB", {})
    ieasys = "00"
    ipl_vol = "SBSYS1"
    load = members.get("LOAD00", "")
    for line in load.splitlines():
        s = line.strip().upper()
        if s.startswith("SYSPARM"):
            ieasys = (s.split()[1] if len(s.split()) > 1 else ieasys)
        elif s.startswith("IODF") and len(s.split()) >= 5:
            ipl_vol = s.split()[3]
    return {"sysname": sysname, "ieasys": ieasys, "ipl_volume": ipl_vol, "nucleus": "IEANUC01"}


def system_config_state(state: Any) -> dict[str, Any]:
    return {
        "parmlib": _live_members(state, "SYS1.PARMLIB", PARMLIB_MEMBERS),
        "proclib": _live_members(state, "SYS1.PROCLIB", PROCLIB_MEMBERS),
        "apf": _live_apf(state),
        "linklist": _live_linklist(state),
        "lpa": ["SYS1.LPALIB", "SYS1.SIEALNKE", "CEE.SCEELPA", "ISP.SISPLPA"],
        "iplinfo": _live_iplinfo(state),
    }


def _list_members(title: str, members: dict[str, str]) -> str:
    return title + "\nMEMBER    DESCRIPTION\n" + "\n".join(f"{k:<8} {v.splitlines()[0][:56]}" for k, v in sorted(members.items()))


def parmlib_command(state: Any, userid: str, cmd: str) -> str | None:
    u = (cmd or "").strip().upper()
    if not u or not (u.startswith("PARMLIB") or u.startswith("PROCLIB") or u.startswith("APF") or u.startswith("LINKLIST") or u.startswith("IPLINFO")):
        return None
    cfg = system_config_state(state)
    parts = u.split()
    if parts[0] == "PARMLIB":
        if len(parts) > 1 and parts[1] in cfg["parmlib"]:
            return f"SYS1.PARMLIB({parts[1]})\n" + cfg["parmlib"][parts[1]]
        return _list_members("SYS1.PARMLIB EXPLORER", cfg["parmlib"])
    if parts[0] == "PROCLIB":
        if len(parts) > 1 and parts[1] in cfg["proclib"]:
            return f"SYS1.PROCLIB({parts[1]})\n" + cfg["proclib"][parts[1]]
        return _list_members("SYS1.PROCLIB EXPLORER", cfg["proclib"])
    if parts[0] == "APF":
        lines = ["APF AUTHORIZED LIBRARY LIST", "DSNAME                              VOLUME   PROTECTION"]
        for dsn in cfg["apf"]:
            weak = "REVIEW" if "VULN" in dsn or dsn.startswith("SYS1.PARMLIB") else "OK"
            lines.append(f"{dsn:<36} SBSYS1   {weak}")
        return "\n".join(lines)
    if parts[0] == "LINKLIST":
        return "LINKLIST LNKLST00\n" + "\n".join(cfg["linklist"])
    if parts[0] == "IPLINFO":
        info = cfg["iplinfo"]
        return f"IEE254I IPLINFO\nSYSNAME={info['sysname']} IEASYS={info['ieasys']} IPLVOL={info['ipl_volume']} NUCLEUS={info['nucleus']}"
    return None
