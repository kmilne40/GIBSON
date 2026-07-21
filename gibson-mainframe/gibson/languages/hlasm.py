from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
import re

@dataclass
class AsmStatement:
    label: str
    operation: str
    operands: str
    comment: str = ""
    raw: str = ""

@dataclass
class HlasmResult:
    rc: int
    listing: str
    symbols: Dict[str, int] = field(default_factory=dict)
    registers: Dict[int, int] = field(default_factory=dict)
    condition_code: int = 0

class HlasmSimulator:
    """Safe High Level Assembler training simulator."""
    def __init__(self, max_steps: int = 1000):
        self.max_steps = max_steps
        self.symbols: Dict[str, int] = {}
        self.registers: Dict[int, int] = {i: 0 for i in range(16)}
        self.memory: Dict[str, str] = {}
        self.cc = 0

    def parse(self, source: str) -> List[AsmStatement]:
        stmts: List[AsmStatement] = []
        for raw in source.splitlines():
            line = raw.rstrip()
            if not line or line.lstrip().startswith(".*") or line.lstrip().startswith("*"):
                continue
            comment = ""
            if "  .*" in line:
                line, comment = line.split("  .*",1)
            parts = line.split(None, 2)
            label=""; op=""; operands=""
            if len(parts) == 1:
                op = parts[0]
            elif len(parts) == 2:
                if line.startswith((" ", "\t")):
                    op, operands = parts[0], parts[1]
                else:
                    label, op = parts[0], parts[1]
            else:
                if line.startswith((" ", "\t")):
                    op, operands = parts[0], parts[1] + " " + parts[2]
                else:
                    label, op, operands = parts[0], parts[1], parts[2]
            stmts.append(AsmStatement(label.upper(), op.upper(), operands.strip(), comment, raw))
        return stmts

    def assemble(self, source: str) -> HlasmResult:
        self.symbols={}; self.registers={i:0 for i in range(16)}; self.memory={}; self.cc=0
        stmts = self.parse(source)
        loc = 0; listing=["ASMA90 High Level Assembler SIMULATOR", "SOURCE LISTING"]
        for idx, st in enumerate(stmts,1):
            if st.label:
                self.symbols[st.label] = loc
            listing.append(f"{idx:06d} {loc:06X} {st.raw}")
            op=st.operation
            if op in {"DC","DS"}: loc += 4
            elif op in {"CSECT","DSECT","USING","DROP","TITLE","PRINT","EQU","LTORG"}: pass
            elif op == "END": break
            else: loc += 4
        rc = self._simulate(stmts)
        listing.append("SYMBOL TABLE")
        for k,v in sorted(self.symbols.items()): listing.append(f"  {k:<16} {v:06X}")
        listing.append("BASE REGISTER TABLE")
        listing.append("  USING/DROP simulated for training only")
        listing.append(f"FINAL CONDITION CODE {self.cc}")
        listing.append(f"MAXIMUM CONDITION CODE WAS {rc}")
        return HlasmResult(rc, "\n".join(listing), dict(self.symbols), dict(self.registers), self.cc)

    def _reg(self, token: str) -> int:
        token=token.strip().upper().lstrip("R")
        try: return int(token)
        except Exception: return 0

    def _resolve(self, token: str) -> int:
        t=token.strip().upper().strip("'")
        if t in self.symbols: return self.symbols[t]
        try: return int(t,0)
        except Exception: return 0

    def _simulate(self, stmts: List[AsmStatement]) -> int:
        labels = {s.label:i for i,s in enumerate(stmts) if s.label}
        pc=0; steps=0
        while pc < len(stmts):
            steps += 1
            if steps > self.max_steps: return 8
            st=stmts[pc]; op=st.operation; ops=[o.strip() for o in st.operands.split(',') if o.strip()]
            if op in {"END","RETURN"}: break
            if op == "LA" and len(ops)>=2: self.registers[self._reg(ops[0])] = self._resolve(ops[1])
            elif op == "L" and len(ops)>=2: self.registers[self._reg(ops[0])] = self._resolve(ops[1])
            elif op == "ST" and len(ops)>=2: self.memory[ops[1].upper()] = str(self.registers.get(self._reg(ops[0]),0))
            elif op == "MVC" and len(ops)>=2: self.memory[ops[0].upper()] = self.memory.get(ops[1].upper(), ops[1])
            elif op in {"CLC","CLI","C"} and len(ops)>=2:
                a = self.memory.get(ops[0].upper(), ops[0]); b = self.memory.get(ops[1].upper(), ops[1])
                self.cc = 0 if a == b else (1 if a < b else 2)
            elif op == "A" and len(ops)>=2: self.registers[self._reg(ops[0])] += self._resolve(ops[1])
            elif op == "S" and len(ops)>=2: self.registers[self._reg(ops[0])] -= self._resolve(ops[1])
            elif op in {"B","BE","BNE","BH","BL"} and ops:
                take = op == "B" or (op == "BE" and self.cc == 0) or (op == "BNE" and self.cc != 0) or (op == "BH" and self.cc == 2) or (op == "BL" and self.cc == 1)
                if take and ops[0].upper() in labels:
                    pc = labels[ops[0].upper()]; continue
            elif op in {"BALR","BR","SAVE","USING","DROP","CSECT","DSECT","DC","DS","EQU","TITLE","PRINT","LTORG"}: pass
            pc += 1
        return 0
