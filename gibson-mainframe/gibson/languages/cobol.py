from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import re

@dataclass
class CobolCompileResult:
    rc: int
    listing: str
    display_lines: List[str]

@dataclass
class CobolDataItem:
    level: str
    name: str
    pic: str = ""
    value: str = ""

@dataclass
class CobolProgram:
    program_id: str = "NONAME"
    data_items: Dict[str, CobolDataItem] = field(default_factory=dict)
    paragraphs: Dict[str, List[str]] = field(default_factory=dict)
    procedure: List[str] = field(default_factory=list)

class CobolSimulator:
    """Bounded Enterprise COBOL-flavoured training simulator.

    This is not a real compiler. It recognises a safe educational subset and
    produces z/OS-style listings/output while preserving Gibson's old API.
    """
    def __init__(self, max_steps: int = 1000):
        self.max_steps = max_steps
        self.vars: Dict[str, str] = {}
        self.display_lines: List[str] = []
        self.diagnostics: List[str] = []

    def compile(self, source: str) -> CobolCompileResult:
        self.vars = {}
        self.display_lines = []
        self.diagnostics = []
        upper = source.upper()
        rc = 0
        messages: List[str] = [
            "IGYCRCTL Enterprise COBOL for z/OS SIMULATOR",
            "GIBSON SOURCE-AWARE COBOL TRAINING COMPILE",
            "SOURCE LISTING FOLLOWS",
        ]
        for idx, line in enumerate(source.splitlines(), 1):
            messages.append(f"{idx:06d} {line.rstrip()}")
        for req in ["IDENTIFICATION DIVISION", "PROCEDURE DIVISION"]:
            if req not in upper:
                messages.append(f"IGYDS1089-S REQUIRED DIVISION MISSING: {req}")
                rc = max(rc, 8)
        if rc >= 8:
            messages.append(f"MAXIMUM CONDITION CODE WAS {rc}")
            return CobolCompileResult(rc, "\n".join(messages), [])
        program = self._parse(source)
        messages.extend(self._data_map(program))
        exec_rc = self._execute(program)
        rc = max(rc, exec_rc)
        if "EXEC CICS" in upper:
            for stmt in self._exec_blocks(source, "CICS"):
                messages.append(f"IGYPS2121-I EXEC CICS STATEMENT RECOGNISED: {stmt}")
        if "EXEC SQL" in upper:
            for stmt in self._exec_blocks(source, "SQL"):
                messages.append(f"DSNH104I EXEC SQL STATEMENT RECOGNISED: {stmt}")
        if self.diagnostics:
            messages.append("DIAGNOSTICS")
            messages.extend(self.diagnostics)
        messages.append("PROCEDURE MAP")
        for para in sorted(program.paragraphs):
            messages.append(f"  {para:<20} {len(program.paragraphs[para])} STATEMENT(S)")
        messages.append(f"MAXIMUM CONDITION CODE WAS {rc}")
        return CobolCompileResult(rc, "\n".join(messages), self.display_lines)

    def _strip_seq(self, line: str) -> str:
        return line[6:] if len(line) > 6 and re.match(r"^[0-9 ]{6}", line[:6]) else line

    def _parse(self, source: str) -> CobolProgram:
        pgm = CobolProgram()
        section = ""
        current_para: Optional[str] = None
        for raw in source.splitlines():
            line = self._strip_seq(raw).strip()
            if not line or line.startswith("*"):
                continue
            u = line.upper().rstrip(".")
            if u.startswith("PROGRAM-ID"):
                m = re.search(r"PROGRAM-ID\s*\.\s*([A-Z0-9_-]+)", u) or re.search(r"PROGRAM-ID\s+([A-Z0-9_-]+)", u)
                if m: pgm.program_id = m.group(1)
            if "WORKING-STORAGE SECTION" in u:
                section = "WS"; continue
            if "PROCEDURE DIVISION" in u:
                section = "PROC"; continue
            if section == "WS":
                m = re.match(r"(\d{2})\s+([A-Z0-9-]+)(?:\s+PIC\s+([^\s.]+))?(?:\s+VALUE\s+(.+?))?\.?$", line, re.I)
                if m:
                    value = (m.group(4) or "").strip().rstrip(".")
                    value = value.strip("'").strip('"')
                    name = m.group(2).upper()
                    pgm.data_items[name] = CobolDataItem(m.group(1), name, (m.group(3) or "").upper(), value)
                    self.vars[name] = value or ("0" if (m.group(3) or "").upper().startswith(("9", "S9")) else "")
            elif section == "PROC":
                if re.match(r"^[A-Z0-9-]+\.$", line.strip(), re.I):
                    current_para = line.strip().rstrip(".").upper()
                    pgm.paragraphs[current_para] = []
                    continue
                statements = [s.strip() for s in re.split(r"\.\s*", line) if s.strip()]
                for stmt in statements:
                    if current_para:
                        pgm.paragraphs[current_para].append(stmt)
                    else:
                        pgm.procedure.append(stmt)
        return pgm

    def _data_map(self, program: CobolProgram) -> List[str]:
        out = ["DATA MAP"]
        if not program.data_items:
            out.append("  NO WORKING-STORAGE ITEMS FOUND")
            return out
        for item in program.data_items.values():
            out.append(f"  {item.level:<2} {item.name:<24} PIC {item.pic or '-':<10} VALUE {item.value!r}")
        return out

    def _exec_blocks(self, source: str, kind: str) -> List[str]:
        return [" ".join(m.group(1).split())[:120] for m in re.finditer(rf"EXEC\s+{kind}\s+(.*?)\s+END-EXEC", source, re.I | re.S)] or [f"EXEC {kind}"]

    def _value(self, token: str) -> str:
        t = token.strip().rstrip(".")
        if (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
            return t[1:-1]
        return self.vars.get(t.upper(), t)

    def _num(self, token: str) -> int:
        try: return int(float(self._value(token) or 0))
        except Exception: return 0

    def _condition(self, cond: str) -> bool:
        m = re.match(r"(.+?)\s+(=|>|<|>=|<=|NOT\s*=)\s+(.+)$", cond.strip(), re.I)
        if not m:
            return bool(self._value(cond))
        left, op, right = m.group(1), m.group(2).upper().replace(" ", ""), m.group(3)
        lv, rv = self._value(left), self._value(right)
        if re.fullmatch(r"-?\d+", lv) and re.fullmatch(r"-?\d+", rv):
            li, ri = int(lv), int(rv)
            return {"=":li==ri,"<":li<ri,">":li>ri,"<=":li<=ri,">=":li>=ri,"NOT=":li!=ri}[op]
        return {"=":lv==rv,"<":lv<rv,">":lv>rv,"<=":lv<=rv,">=":lv>=rv,"NOT=":lv!=rv}[op]

    def _execute(self, program: CobolProgram) -> int:
        steps = 0
        def run_list(stmts: List[str]) -> int:
            nonlocal steps
            idx = 0
            while idx < len(stmts):
                steps += 1
                if steps > self.max_steps:
                    self.diagnostics.append("IGY9999-E EXECUTION LIMIT REACHED")
                    return 8
                stmt = stmts[idx].strip()
                u = stmt.upper()
                if u in {"STOP RUN", "GOBACK"}: return 0
                if u.startswith("DISPLAY "):
                    payload = stmt[8:].strip()
                    parts = re.findall(r"'[^']*'|\"[^\"]*\"|[A-Z0-9-]+", payload, re.I)
                    self.display_lines.append(" ".join(self._value(p) for p in parts))
                elif u.startswith("MOVE "):
                    m = re.match(r"MOVE\s+(.+?)\s+TO\s+([A-Z0-9-]+)$", stmt, re.I)
                    if m: self.vars[m.group(2).upper()] = self._value(m.group(1))
                elif u.startswith("ADD "):
                    m = re.match(r"ADD\s+(.+?)\s+TO\s+([A-Z0-9-]+)$", stmt, re.I)
                    if m: self.vars[m.group(2).upper()] = str(self._num(m.group(2)) + self._num(m.group(1)))
                elif u.startswith("SUBTRACT "):
                    m = re.match(r"SUBTRACT\s+(.+?)\s+FROM\s+([A-Z0-9-]+)$", stmt, re.I)
                    if m: self.vars[m.group(2).upper()] = str(self._num(m.group(2)) - self._num(m.group(1)))
                elif u.startswith("COMPUTE "):
                    m = re.match(r"COMPUTE\s+([A-Z0-9-]+)\s*=\s*(.+)$", stmt, re.I)
                    if m:
                        expr = re.sub(r"\b[A-Z][A-Z0-9-]*\b", lambda mm: self.vars.get(mm.group(0).upper(), mm.group(0)), m.group(2), flags=re.I)
                        if re.fullmatch(r"[0-9+\-*/ ().]+", expr):
                            self.vars[m.group(1).upper()] = str(int(eval(expr, {"__builtins__": {}}, {})))
                elif u.startswith("IF "):
                    # inline: IF A > 0 DISPLAY 'X' ELSE DISPLAY 'Y'
                    m = re.match(r"IF\s+(.+?)\s+(DISPLAY|MOVE|ADD|SUBTRACT|COMPUTE|PERFORM)\s+(.+?)(?:\s+ELSE\s+(.+))?$", stmt, re.I)
                    if m:
                        branch = f"{m.group(2)} {m.group(3)}" if self._condition(m.group(1)) else (m.group(4) or "")
                        if branch: run_list([branch])
                elif u.startswith("EVALUATE "):
                    var = self._value(stmt[9:].strip())
                    block=[]; j=idx+1; chosen=None
                    while j < len(stmts) and not stmts[j].strip().upper().startswith("END-EVALUATE"):
                        su=stmts[j].strip().upper()
                        if su.startswith("WHEN "):
                            chosen = (su[5:].strip()==var.upper() or su.startswith("WHEN OTHER"))
                        elif chosen:
                            block.append(stmts[j])
                        j += 1
                    run_list(block); idx=j
                elif u.startswith("PERFORM "):
                    m = re.match(r"PERFORM\s+([A-Z0-9-]+)(?:\s+(\d+)\s+TIMES)?", stmt, re.I)
                    if m and m.group(1).upper() in program.paragraphs:
                        times = int(m.group(2) or 1)
                        for _ in range(times): run_list(program.paragraphs[m.group(1).upper()])
                idx += 1
            return 0
        return run_list(program.procedure)
