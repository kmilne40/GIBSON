from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import base64
import json
import re
from pathlib import Path
from typing import Any

from gibson.core.state import GibsonState
from gibson.core.smf.records.type80 import racf_event
from gibson.core.smf.records.type92 import uss_file
from gibson.core.smf.records.type119 import tcp_connection


SENSITIVE_PATTERNS = (
    "SYS1.RACFDS", "SYS1.RACFDS.BACKUP", "SYS1.MANA", "SYS1.MANB",
    "SYS1.MANC", "SYS1.PARMLIB", ".RACF.HASHES", ".IRRDBU00.",
)


@dataclass
class XmitPackage:
    name: str
    sender: str
    recipient: str
    source_dataset: str
    target_dataset: str
    created_at: str
    title: str
    payload_b64: str


def _corr(state: Any) -> str:
    return f"IND-{len(getattr(state, 'smf_records', []))+1:06d}"


class TransferManager:
    def __init__(self, state: GibsonState):
        self.state = state
        if not hasattr(state, "transmit_packages"):
            setattr(state, "transmit_packages", {})

    @property
    def packages(self) -> dict[str, dict[str, Any]]:
        return getattr(self.state, "transmit_packages")

    def _qualify_target(self, userid: str, dsname: str) -> str:
        raw = (dsname or "").strip().strip("'").strip('"').upper()
        if not raw:
            return ""
        # Preserve explicit PDS member notation but qualify unqualified DSNs.
        base, member = self.state.datasets.split_name(raw)
        if "." not in base:
            base = f"{userid.upper()}.{base}"
        return f"{base}({member})" if member else base

    def _extract_opt(self, cmd: str, name: str) -> str:
        m = re.search(r"\b" + re.escape(name) + r"\(", cmd or "", re.I)
        if not m:
            return ""
        i = m.end()
        depth = 1
        out = []
        while i < len(cmd) and depth > 0:
            ch = cmd[i]
            if ch == "(":
                depth += 1
                out.append(ch)
            elif ch == ")":
                depth -= 1
                if depth:
                    out.append(ch)
            else:
                out.append(ch)
            i += 1
        return "".join(out).strip().strip("'").strip('"')

    def _safe_local_path(self, filename: str) -> Path:
        raw = (filename or "DESKTOP.FILE").strip().strip("'\"")
        if not raw:
            raw = "DESKTOP.FILE"
        p = Path(raw.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("LOCAL filename must stay inside the Gibson transfer root")
        safe = re.sub(r"[^A-Za-z0-9._@#/-]", "_", str(p))
        root = self.state.config.transfer_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = (root / safe).resolve()
        if root not in path.parents and path != root:
            raise ValueError("LOCAL filename escapes Gibson transfer root")
        return path

    def _is_sensitive(self, dsn: str) -> bool:
        u = (dsn or "").upper()
        return any(p in u or (p.startswith(".") and u.endswith(p)) for p in SENSITIVE_PATTERNS)

    def _emit(self, userid: str, direction: str, dsn: str, *, bytes_in: int = 0, bytes_out: int = 0, result: str = "SUCCESS", corr: str = "", note: str = "") -> None:
        corr = corr or _corr(self.state)
        access = "READ" if direction.upper() == "GET" else "UPDATE"
        try:
            racf_event(self.state, userid=userid, event_name=f"IND$FILE-{direction.upper()}", result=result, class_name="DATASET", resource_name=dsn.upper(), profile_name=dsn.upper(), access_requested=access, access_allowed=access if result == "SUCCESS" else "NONE", reason_code="OK" if result == "SUCCESS" else "DENIED", correlation_id=corr, detail=note)
        except Exception:
            pass
        try:
            uss_file(self.state, userid=userid, path=dsn.upper(), operation="READ" if direction.upper()=="GET" else "WRITE", program="IND$FILE", result=result, bytes_count=bytes_in or bytes_out, correlation_id=corr, detail=note)
        except Exception:
            pass
        try:
            tcp_connection(self.state, userid=userid, application="IND$FILE", remote_ip="3270-CLIENT", result=result, bytes_out=bytes_out, resource=dsn.upper(), correlation_id=corr, detail=f"DIRECTION={direction.upper()} {note}")
        except Exception:
            pass
        try:
            self.state.record_security_event(userid, f"IND_FILE_TRANSFER", f"DIRECTION={direction.upper()} DATASET={dsn.upper()} CORR={corr}", service="IND$FILE", result=result)
        except Exception:
            pass
        if self._is_sensitive(dsn):
            msg = f"GIBSSEC4A SENSITIVE DATASET TRANSFER USER({userid.upper()}) DATASET({dsn.upper()}) METHOD(IND$FILE) CORR={corr}"
            try: self.state.notify_console(msg, severity="ALERT")
            except Exception: pass
            try: self.state.raise_dashboard_alert(msg, severity="ALERT", event_type="SENSITIVE_DATASET_TRANSFER")
            except Exception: pass
            try: self.state.record_security_event(userid, "SENSITIVE_DATASET_TRANSFER", f"DATASET={dsn.upper()} METHOD=IND$FILE CORR={corr}", service="IND$FILE", result="WARNING")
            except Exception: pass

    def read_local(self, filename: str) -> bytes:
        path = self._safe_local_path(filename)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(filename)
        return path.read_bytes()

    def write_local(self, filename: str, data: bytes) -> Path:
        path = self._safe_local_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def transmit(self, sender: str, recipient: str, source_dataset: str, *, outdsn: str = "", title: str = "") -> dict[str, str]:
        src = self._qualify_target(sender, source_dataset)
        rec = (recipient or sender).upper().split(".")[0]
        payload = self.state.datasets.read(sender, src)
        package_name = self._qualify_target(sender, outdsn or f"{sender.upper()}.XMIT.{src.split('.')[-1][:8]}")
        pkg = XmitPackage(package_name, sender.upper(), rec, src, src, datetime.now().isoformat(timespec="seconds"), title or f"TRANSMIT {src}", base64.b64encode(payload.encode("utf-8")).decode("ascii"))
        text = json.dumps(asdict(pkg), indent=2)
        self.state.datasets.allocate(sender, package_name, org="PS")
        self.state.datasets.write(sender, package_name, text)
        self.packages[package_name] = asdict(pkg)
        self.state.record_security_event(sender, "TRANSMIT", f"DATASET={src} OUTDSN={package_name} RECIPIENT={rec}", service="TSO")
        return {"package": package_name, "recipient": rec, "source": src}

    def receive(self, userid: str, indsn: str, *, target: str = "") -> dict[str, str]:
        src = self._qualify_target(userid, indsn)
        pkg = self.packages.get(src, {})
        if pkg:
            payload = base64.b64decode(pkg.get("payload_b64", "")).decode("utf-8")
            original = str(pkg.get("source_dataset", "RESTORED.DATA")).upper()
        else:
            raw = self.state.datasets.read(userid, src)
            try:
                pkg = json.loads(raw)
                payload = base64.b64decode(pkg["payload_b64"]).decode("utf-8")
                original = str(pkg.get("source_dataset", "")).upper()
            except Exception:
                payload = raw
                original = "RESTORED.DATA"
        dst = self._qualify_target(userid, target or original)
        self.state.datasets.allocate(userid, dst, org="PO" if self.state.datasets.split_name(dst)[1] else "PS")
        self.state.datasets.write(userid, dst, payload)
        self.state.record_security_event(userid, "RECEIVE", f"INDSN={src} TARGET={dst}", service="TSO")
        return {"restored": dst, "indsn": src}

    def _bytes_to_dataset_text(self, content: bytes, mode: str, cr: str = "KEEP", lrecl: int = 80) -> str:
        if mode.upper() == "BINARY":
            return "GIBSON-BINARY-BASE64:\n" + base64.b64encode(content).decode("ascii") + "\n"
        text = content.decode("utf-8", errors="replace")
        if cr.upper() in ("REMOVE", "CRLF"):
            text = text.replace("\r", "")
        elif cr.upper() == "ADD":
            text = "\n".join(line.rstrip("\r") for line in text.splitlines()) + ("\n" if text else "")
        return text

    def _dataset_text_to_bytes(self, text: str, mode: str, cr: str = "KEEP") -> bytes:
        if mode.upper() == "BINARY" and text.startswith("GIBSON-BINARY-BASE64:"):
            payload = "".join(text.splitlines()[1:])
            return base64.b64decode(payload.encode("ascii"))
        if cr.upper() in ("ADD", "CRLF"):
            text = "\r\n".join(text.splitlines()) + ("\r\n" if text else "")
        elif cr.upper() == "REMOVE":
            text = text.replace("\r", "")
        return text.encode("utf-8")

    def indfile_put(self, userid: str, target: str, content: bytes, *, note: str = "browser", options: dict[str, str] | None = None) -> dict[str, str]:
        opts = {k.upper(): v for k, v in (options or {}).items()}
        dsn = self._qualify_target(userid, target)
        exist = opts.get("EXIST", "REPLACE").upper()
        mode = opts.get("MODE", "ASCII").upper()
        cr = opts.get("CR", "KEEP").upper()
        try:
            old = self.state.datasets.read(userid, dsn)
            exists = True
        except Exception:
            old = ""
            exists = False
        if exists and exist == "KEEP":
            raise FileExistsError(f"DATASET {dsn} EXISTS AND EXIST(KEEP) WAS REQUESTED")
        text = self._bytes_to_dataset_text(content, mode, cr, int(opts.get("LRECL", "80") or 80))
        if exists and exist == "APPEND":
            text = old + ("" if old.endswith("\n") else "\n") + text
        self.state.datasets.allocate(userid, dsn, org="PO" if self.state.datasets.split_name(dsn)[1] else "PS")
        self.state.datasets.write(userid, dsn, text)
        self.state.add_indfile_event("PUT", dsn, userid, note)
        self._emit(userid, "PUT", dsn, bytes_in=len(content), result="SUCCESS", note=note)
        return {"target": dsn, "bytes": str(len(content)), "records": str(len(text.splitlines()))}

    def indfile_get(self, userid: str, source: str, *, note: str = "browser", options: dict[str, str] | None = None) -> tuple[str, bytes]:
        opts = {k.upper(): v for k, v in (options or {}).items()}
        dsn = self._qualify_target(userid, source)
        read_dsn = "SYS1.RACFDS(DATABASE)" if dsn.upper() == "SYS1.RACFDS" else dsn
        text = self.state.datasets.read(userid, read_dsn)
        data = self._dataset_text_to_bytes(text, opts.get("MODE", "ASCII"), opts.get("CR", "KEEP"))
        self.state.add_indfile_event("GET", dsn, userid, note)
        self._emit(userid, "GET", dsn, bytes_out=len(data), result="SUCCESS", note=note)
        filename = dsn.replace("(", ".").replace(")", "") + (".bin" if opts.get("MODE", "ASCII").upper() == "BINARY" else ".txt")
        return filename, data

    def parse_indfile(self, userid: str, cmd: str) -> tuple[str, dict[str, str]]:
        u = cmd.upper()
        opts: dict[str, str] = {}
        for key in ("DSN", "DATASET", "HOSTFILE", "LOCAL", "LOCALFILE", "MODE", "HOST", "CR", "EXIST", "RECFM", "LRECL", "BLKSIZE"):
            val = self._extract_opt(cmd, key)
            if val:
                opts[key] = val
        # Also parse x3270-like name=value when typed/pasted.
        for k, v in re.findall(r"\b([A-Za-z]+)=([^,\s)]+)", cmd):
            opts[k.upper()] = v.strip().strip("'").strip('"')
        # Canonical IND$FILE client syntax uses bare keywords:
        #   IND$FILE GET FOO.TEXT A:FOO.TXT ASCII CRLF
        tokens = re.findall(r"\b([A-Z]+)\b", u)
        if "MODE" not in opts:
            if "BINARY" in tokens:
                opts["MODE"] = "BINARY"
            elif "ASCII" in tokens:
                opts["MODE"] = "ASCII"
        if "CR" not in opts:
            if "NOCRLF" in tokens or "NOCR" in tokens:
                opts["CR"] = "REMOVE"
            elif "CRLF" in tokens:
                opts["CR"] = "CRLF"
        action = "PUT" if any(x in u for x in [" PUT", " SEND", "DIRECTION=SEND"]) or u.startswith("IND$FILE PUT") else "GET"
        target = opts.get("DSN") or opts.get("DATASET") or opts.get("HOSTFILE") or ""
        local = opts.get("LOCAL") or opts.get("LOCALFILE") or "DESKTOP.FILE"
        return action, {"dataset": self._qualify_target(userid, target or local), "local": local, **opts}


def get_transfer_manager(state: GibsonState) -> TransferManager:
    mgr = getattr(state, "transfer_manager", None)
    if mgr is None:
        mgr = TransferManager(state)
        setattr(state, "transfer_manager", mgr)
    return mgr
