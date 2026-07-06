from __future__ import annotations
from typing import Any

MANX = ["SYS1.MANA", "SYS1.MANB", "SYS1.MANC"]


def ensure_smf_datasets(state: Any) -> None:
    try:
        for d in MANX:
            if not state.datasets.ds_path("IBMUSER", d).exists():
                state.datasets.allocate("IBMUSER", d, org="PS", recfm="VB", lrecl=4096)
        if not state.datasets.ds_path("IBMUSER", "SYS1.PARMLIB(SMFPRM00)").exists():
            state.datasets.write("IBMUSER", "SYS1.PARMLIB(SMFPRM00)", "ACTIVE\n  RECORDING(DATASET)\n  DSNAME(SYS1.MANA,SYS1.MANB,SYS1.MANC)\n")
    except Exception:
        pass


def get_recording_state(state: Any) -> dict:
    st = getattr(state, "smf_recording", None)
    if st is None:
        st = {"mode": "DATASET", "active": "SYS1.MANA", "sequence": 0, "threshold": 50, "logstreams": {}}
        setattr(state, "smf_recording", st)
    return st


def append_to_active_store(state: Any, record) -> None:
    ensure_smf_datasets(state)
    st = get_recording_state(state)
    st["sequence"] = int(st.get("sequence", 0)) + 1
    row = record.to_unload_row() if hasattr(record, "to_unload_row") else str(record)
    if str(st.get("mode", "DATASET")).upper() == "LOGSTREAM":
        typ = str(getattr(getattr(record, "header", None), "record_type", "0"))
        stream = "IFASMF.RACF.LOG" if typ in {"80","83"} else "IFASMF.CICS.LOG" if typ == "110" else "IFASMF.DB2.LOG" if typ in {"100","101","102"} else "IFASMF.NET.LOG"
        st.setdefault("logstreams", {}).setdefault(stream, []).append(row)
        return
    active = st.get("active", "SYS1.MANA")
    try:
        old = state.datasets.read("IBMUSER", active)
    except Exception:
        old = ""
    try:
        state.datasets.write("IBMUSER", active, old + row + "\n")
    except Exception:
        pass
    if st["sequence"] % int(st.get("threshold", 50)) == 0:
        smf_switch(state)


def smf_switch(state: Any) -> str:
    st = get_recording_state(state)
    cur = st.get("active", "SYS1.MANA")
    try:
        idx = MANX.index(cur)
    except ValueError:
        idx = 0
    st["active"] = MANX[(idx + 1) % len(MANX)]
    return f"IEE362I SMF SWITCH COMPLETE - ACTIVE DATA SET {st['active']}"


def smf_status(state: Any, detail: str = "") -> str:
    ensure_smf_datasets(state)
    st = get_recording_state(state)
    mode = str(st.get("mode", "DATASET")).upper()
    lines = ["IEE974I SMF STATUS", f"  RECORDING({mode})"]
    if mode == "DATASET":
        lines += [f"  ACTIVE({st.get('active','SYS1.MANA')})", "  DSNAME(SYS1.MANA,SYS1.MANB,SYS1.MANC)", "  IFASMFDP AVAILABLE FOR MAN DATA SET DUMP/CLEAR"]
    else:
        lines += ["  LSNAME(IFASMF.RACF.LOG,IFASMF.CICS.LOG,IFASMF.DB2.LOG,IFASMF.NET.LOG)", "  IFASMFDL AVAILABLE FOR LOG STREAM EXTRACT"]
    if detail.upper() in {"DS", "O"}:
        for d in MANX:
            try:
                count = len(state.datasets.read("IBMUSER", d).splitlines())
            except Exception:
                count = 0
            lines.append(f"  {d:<10} RECORDS={count}")
    if detail.upper() == "LS":
        for k,v in sorted(st.get("logstreams", {}).items()):
            lines.append(f"  {k:<24} RECORDS={len(v)}")
    return "\n".join(lines)


def smf_command(state: Any, userid: str, cmd: str) -> str | None:
    u=(cmd or '').strip().upper()
    if u in {"D SMF", "D SMF,O", "D SMF,DS", "D SMF,LS", "SMF STATUS", "SMF MAN", "SMF LOGSTREAM"}:
        if u.startswith("D SMF,"):
            return smf_status(state, u.split(',',1)[1])
        return smf_status(state)
    if u == "SMF SWITCH":
        return smf_switch(state)
    if u.startswith("SMF DUMP MAN("):
        d=u.split('MAN(',1)[1].split(')',1)[0]
        try:
            text=state.datasets.read(userid, d)
            out=f"{userid.upper()}.SMF.DUMP.{d.split('.')[-1]}"
            state.datasets.write(userid,out,text)
            state.datasets.write("IBMUSER",d,"")
            return f"IFASMFDP COMPLETE - {d} DUMPED TO {out} AND CLEARED"
        except Exception as e:
            return f"IFASMFDP FAILED: {e}"
    if u.startswith("SMF RECORDING(LOGSTREAM"):
        get_recording_state(state)["mode"]="LOGSTREAM"; return smf_status(state)
    if u.startswith("SMF RECORDING(DATASET"):
        get_recording_state(state)["mode"]="DATASET"; return smf_status(state)
    if u.startswith("SMF DUMP LOGSTREAM("):
        name=u.split('LOGSTREAM(',1)[1].split(')',1)[0]
        rows=get_recording_state(state).get('logstreams',{}).get(name,[])
        out=f"{userid.upper()}.SMF.LOGSTREAM.DUMP"
        state.datasets.write(userid,out,"\n".join(rows)+("\n" if rows else ""))
        return f"IFASMFDL COMPLETE - {name} EXTRACTED TO {out} RECORDS={len(rows)}"
    return None
