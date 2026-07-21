from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
import re

@dataclass
class JclStatement:
    name: str
    operation: str
    operands: str
    raw: str

@dataclass
class JclDD:
    name: str
    operands: Dict[str, str]
    raw: str
    instream: str = ""

@dataclass
class JclStep:
    name: str
    program: str = ""
    proc: str = ""
    operands: Dict[str, str] = field(default_factory=dict)
    dds: List[JclDD] = field(default_factory=list)

@dataclass
class JclJob:
    name: str
    operands: Dict[str, str] = field(default_factory=dict)
    steps: List[JclStep] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)

class JclParser:
    """JCL parser for Gibson training workloads."""
    def parse(self, text: str) -> List[JclStatement]:
        stmts: List[JclStatement] = []
        for raw in text.splitlines():
            if not raw.startswith("//") or raw.startswith("//*"):
                continue
            body = raw[2:]
            if body.strip() == "":
                continue
            parts = body.split(None, 2)
            if len(parts) == 1:
                stmts.append(JclStatement(parts[0], "", "", raw))
            elif len(parts) == 2:
                stmts.append(JclStatement(parts[0], parts[1].upper(), "", raw))
            else:
                stmts.append(JclStatement(parts[0], parts[1].upper(), parts[2], raw))
        return stmts

    def parse_job(self, text: str) -> JclJob:
        stmts = self.parse(text)
        job = JclJob("JOB")
        current: JclStep | None = None
        instream_name: str | None = None
        instream_lines: list[str] = []
        lines = text.splitlines()
        # First pass for structured statement parse
        for st in stmts:
            if st.operation == "JOB":
                job.name = st.name.upper()[:8]
                job.operands = self.parse_operands(st.operands)
            elif st.operation == "EXEC":
                ops = self.parse_operands(st.operands)
                pgm = ops.get("PGM", "")
                proc = "" if pgm else st.operands.split(",",1)[0].strip().upper()
                current = JclStep(st.name.upper(), pgm.upper(), proc, ops, [])
                job.steps.append(current)
            elif st.operation == "DD" and current is not None:
                current.dds.append(JclDD(st.name.upper(), self.parse_operands(st.operands), st.raw))
        # Second pass for in-stream blocks
        current_dd = None
        for raw in lines:
            m = re.match(r"^//([A-Z0-9#$@]+)\s+DD\s+(\*|DATA)(?:\s|$)", raw, re.I)
            if m:
                current_dd = m.group(1).upper(); instream_lines=[]; continue
            if current_dd and raw.startswith("/*"):
                for step in job.steps:
                    for dd in step.dds:
                        if dd.name == current_dd:
                            dd.instream = "\n".join(instream_lines)
                current_dd = None; continue
            if current_dd:
                instream_lines.append(raw)
        return job

    def parse_operands(self, text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        cur=""; depth=0; quote=""
        parts=[]
        for ch in text.strip():
            if quote:
                cur += ch
                if ch == quote: quote=""
                continue
            if ch in "'\"": quote=ch; cur+=ch; continue
            if ch == "(": depth += 1
            if ch == ")" and depth: depth -= 1
            if ch == "," and depth == 0:
                if cur.strip(): parts.append(cur.strip())
                cur=""; continue
            cur += ch
        if cur.strip(): parts.append(cur.strip())
        for part in parts:
            if "=" in part:
                k,v = part.split("=",1)
                out[k.strip().upper()] = v.strip().strip("'")
            elif part:
                out.setdefault("_POSITIONAL", part.strip())
        return out
