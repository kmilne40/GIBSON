from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Optional
import re


class RexxInterpreter:
    """Bounded REXX training interpreter.

    Supports the historic Gibson subset plus a careful uplift:
    SAY, EXIT, ADDRESS TSO, limited ADDRESS ISPEXEC, PARSE ARG, PULL,
    assignment, IF/THEN/ELSE, DO/END loops, CALL/RETURN, simple arithmetic,
    EXECIO, and OUTTRAP.
    """

    def __init__(
        self,
        tso_runner: Optional[Callable[[str], str]] = None,
        userid: str = "IBMUSER",
        *,
        dataset_read: Optional[Callable[[str], str]] = None,
        dataset_write: Optional[Callable[[str, str], None]] = None,
        ispexec: Optional[Callable[[str], str]] = None,
        pull_provider: Optional[Callable[[], str]] = None,
    ):
        self.tso_runner = tso_runner
        self.userid = userid.upper()
        self.dataset_read = dataset_read
        self.dataset_write = dataset_write
        self.ispexec = ispexec
        self.pull_provider = pull_provider
        self.vars: dict[str, str] = {"USERID": self.userid, "SYSUID": self.userid, "RC": "0", "RESULT": ""}
        self.labels: dict[str, int] = {}
        self.lines: list[str] = []
        self.outtrap_stem: str | None = None
        self.max_steps = 2000
        self._steps = 0
        self._pull_buffer: list[str] = []
        self._last_output: list[str] = []

    # ---------------- basic evaluation ----------------
    def _capture(self, text: str) -> None:
        self._last_output.append(text)
        if not self.outtrap_stem:
            return
        stem = self.outtrap_stem.upper()
        lines = text.splitlines() or [""]
        count = int(self.vars.get(f"{stem}0", "0") or "0")
        for line in lines:
            count += 1
            self.vars[f"{stem}{count}"] = line
        self.vars[f"{stem}0"] = str(count)

    def _set_rc(self, value: int | str) -> None:
        self.vars["RC"] = str(value)

    def _lookup_var(self, name: str, args: str = "") -> str:
        n = name.strip().upper()
        if not n:
            return ""
        if n in self.vars:
            return str(self.vars[n])
        if '.' in n and not n.startswith('SYSVAR('):
            head, *tail = n.split('.')
            suffix = []
            for part in tail:
                if not part:
                    suffix.append('')
                elif part in self.vars:
                    suffix.append(str(self.vars.get(part, '')))
                else:
                    suffix.append(part)
            compound = '.'.join([head] + suffix)
            if compound in self.vars:
                return str(self.vars[compound])
        if n.startswith("ARG("):
            try:
                idx = int(n[n.find("(")+1:n.rfind(")")]) - 1
                parts = args.split()
                return parts[idx] if 0 <= idx < len(parts) else ""
            except Exception:
                return ""
        return name

    def _replace_vars_for_eval(self, expr: str, args: str = "") -> str:
        protected: list[str] = []
        def keep(m: re.Match[str]) -> str:
            protected.append(m.group(0))
            return f"§{len(protected)-1}§"
        work = re.sub(r"'[^']*'|\"[^\"]*\"", keep, expr)

        def repl(m: re.Match[str]) -> str:
            token = m.group(0)
            up = token.upper()
            if up in {"AND", "OR", "NOT", "TO", "BY", "WHILE"}:
                return token
            if up.startswith("SYSVAR") or up.startswith("TIME") or up.startswith("DATE") or up.startswith("ARG"):
                value = self._eval_token(token, args=args)
            else:
                value = self._lookup_var(token, args=args)
            if re.fullmatch(r"-?\d+(?:\.\d+)?", str(value).strip()):
                return str(value).strip()
            return repr(str(value))

        work = re.sub(r"\b[A-Za-z@#$][A-Za-z0-9@#$._]*\b(?:\([0-9]+\))?", repl, work)
        work = work.replace("\\=", "!=").replace("<>", "!=")
        work = re.sub(r"(?<![<>!])=(?!=)", "==", work)
        work = re.sub(r"\bAND\b", " and ", work, flags=re.I)
        work = re.sub(r"\bOR\b", " or ", work, flags=re.I)
        work = re.sub(r"\bNOT\b", " not ", work, flags=re.I)
        def restore(m: re.Match[str]) -> str:
            idx = int(m.group(1))
            return protected[idx]
        work = re.sub(r"§(\d+)§", restore, work)
        return work

    def _eval_token(self, token: str, args: str = "") -> str:
        t = token.strip()
        if not t:
            return ""
        if (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
            return t[1:-1]
        u = t.upper()
        if u == "TIME()":
            return datetime.now().strftime("%H:%M:%S")
        if u == "DATE()":
            return datetime.now().strftime("%Y-%m-%d")
        if re.match(r"^(LEFT|RIGHT|SUBSTR|WORD|WORDS|STRIP|TRANSLATE|POS|LENGTH|DATATYPE|COPIES|SPACE|SUBWORD|DELWORD|RANDOM)\(", u):
            return self._eval_function(t, args=args)
        if u.startswith("SYSVAR("):
            inner = t[t.find("(") + 1 : t.rfind(")")].strip().strip("'").strip('"').upper()
            return {
                "SYSUID": self.userid,
                "SYSNAME": "MVSC",
                "SYSNODE": "MVSC",
                "SYSJES": "JES2",
                "SYSPLEX": "GIBPLEX",
            }.get(inner, self.vars.get(inner, ""))
        if u.startswith("ARG("):
            return self._lookup_var(u, args=args)
        if re.fullmatch(r"-?\d+(?:\.\d+)?", t):
            return t
        return self._lookup_var(t, args=args)

    def _split_args(self, text: str) -> list[str]:
        args_out: list[str] = []
        cur = ""; quote = ""; depth = 0
        for ch in text:
            if quote:
                cur += ch
                if ch == quote:
                    quote = ""
                continue
            if ch in "'\"":
                quote = ch; cur += ch; continue
            if ch == "(":
                depth += 1; cur += ch; continue
            if ch == ")" and depth:
                depth -= 1; cur += ch; continue
            if ch == "," and depth == 0:
                args_out.append(cur.strip()); cur = ""; continue
            cur += ch
        if cur.strip() or text.endswith(","):
            args_out.append(cur.strip())
        return args_out

    def _eval_function(self, token: str, args: str = "") -> str:
        m = re.match(r"([A-Za-z]+)\((.*)\)$", token.strip(), re.S)
        if not m:
            return token
        name = m.group(1).upper(); raw_args = self._split_args(m.group(2))
        vals = [self._eval_expr(a, args=args) for a in raw_args]
        def iv(i: int, default: int = 0) -> int:
            try: return int(float(vals[i]))
            except Exception: return default
        s0 = vals[0] if vals else ""
        if name == "LEFT": return s0[:iv(1)] if len(vals) > 1 else s0
        if name == "RIGHT": return s0[-iv(1):].rjust(iv(1)) if len(vals) > 1 else s0
        if name == "SUBSTR":
            start = max(1, iv(1,1)) - 1; length = iv(2,-1)
            return s0[start:] if length < 0 else s0[start:start+length]
        if name == "WORD":
            words = s0.split(); n = iv(1,1) - 1
            return words[n] if 0 <= n < len(words) else ""
        if name == "WORDS": return str(len(s0.split()))
        if name == "STRIP": return s0.strip()
        if name == "TRANSLATE": return s0.upper()
        if name == "POS": return str((vals[1] if len(vals)>1 else "").find(s0) + 1) if len(vals)>1 else "0"
        if name == "LENGTH": return str(len(s0))
        if name == "DATATYPE": return "NUM" if re.fullmatch(r"-?\d+(?:\.\d+)?", s0.strip()) else "CHAR"
        if name == "COPIES": return s0 * max(0, iv(1,0))
        if name == "SPACE": return " ".join(s0.split())
        if name == "SUBWORD":
            words=s0.split(); start=max(1,iv(1,1))-1; length=iv(2,-1)
            return " ".join(words[start:] if length<0 else words[start:start+length])
        if name == "DELWORD":
            words=s0.split(); start=max(1,iv(1,1))-1; length=iv(2,1)
            return " ".join(words[:start]+words[start+length:])
        if name == "RANDOM":
            import random
            lo = iv(0,0) if len(vals)>1 else 0; hi = iv(1,999) if len(vals)>1 else iv(0,999)
            return str(random.randint(lo, hi))
        return token

    def _eval_expr(self, expr: str, args: str = "") -> str:
        expr = expr.strip()
        if not expr:
            return ""
        # Only attempt Python-style evaluation when the expression looks like
        # arithmetic or comparison logic. Plain SAY-style token lists often
        # contain function-like tokens such as TIME() or SYSVAR('SYSUID') and
        # should be handled by the token concatenation path below. Trying to
        # eval those token lists can raise SyntaxWarning under newer Python
        # versions even though we immediately fall back to the normal path.
        # Ignore operators that only appear inside quoted text, such as the
        # hyphen in 'USER-ID' or a banner line made of dashes.
        expr_for_hint = re.sub(r"'[^']*'|\"[^\"]*\"", "", expr)
        arithmetic_hint = bool(
            re.search(r"(?:\bAND\b|\bOR\b|\bNOT\b|\\=|<>|<=|>=|==|!=|[+\-*/<>]=?|(?<![A-Za-z0-9_])=(?!=))", expr_for_hint, re.I)
        )
        # Arithmetic/comparison style expression
        if arithmetic_hint and "||" not in expr:
            safe = self._replace_vars_for_eval(expr, args=args)
            try:
                result = eval(safe, {"__builtins__": {}}, {})
                if isinstance(result, bool):
                    return "1" if result else "0"
                if isinstance(result, float) and result.is_integer():
                    return str(int(result))
                return str(result)
            except Exception:
                pass
        def _func_repl(m: re.Match[str]) -> str:
            return repr(self._eval_function(m.group(0), args=args))
        expr = re.sub(r"\b(?:LEFT|RIGHT|SUBSTR|WORD|WORDS|STRIP|TRANSLATE|POS|LENGTH|DATATYPE|COPIES|SPACE|SUBWORD|DELWORD|RANDOM)\((?:[^()'\"]+|'[^']*'|\"[^\"]*\")*\)", _func_repl, expr, flags=re.I)
        tokens = re.findall(r"'[^']*'|\"[^\"]*\"|SYSVAR\([^)]*\)|TIME\(\)|DATE\(\)|ARG\([0-9]+\)|\|\||[^\s]+", expr, flags=re.I)
        out: List[str] = []
        pending_concat = False
        for token in tokens:
            if token == "||":
                pending_concat = True
                continue
            value = self._eval_token(token, args=args)
            if not out:
                out.append(value)
            elif pending_concat:
                out[-1] = out[-1] + value
            else:
                out.append(value)
            pending_concat = False
        return " ".join([part for part in out if part != ""]).replace("  ", " ").strip()

    def _eval_condition(self, expr: str, args: str = "") -> bool:
        safe = self._replace_vars_for_eval(expr, args=args)
        try:
            return bool(eval(safe, {"__builtins__": {}}, {}))
        except Exception:
            return bool(self._eval_expr(expr, args=args))

    # ---------------- control flow ----------------
    def _load(self, source: str) -> None:
        self.lines = [raw.rstrip() for raw in source.splitlines()]
        self.labels = {}
        for idx, raw in enumerate(self.lines):
            line = raw.strip()
            if line.endswith(":") and re.fullmatch(r"[A-Za-z@#$][A-Za-z0-9@#$._-]*:", line):
                self.labels[line[:-1].upper()] = idx

    def _find_matching_end(self, start: int) -> int:
        depth = 0
        for idx in range(start + 1, len(self.lines)):
            u = self.lines[idx].strip().upper()
            if not u or u.startswith("/*"):
                continue
            if u.startswith("DO"):
                depth += 1
            elif u == "END":
                if depth == 0:
                    return idx
                depth -= 1
        return len(self.lines) - 1

    def _execute_line(self, line: str, args: str, stack: list[int | dict], pc: int) -> tuple[Optional[int], Optional[str]]:
        # returns (jump_pc, return_flag)
        self._steps += 1
        if self._steps > self.max_steps:
            self._capture("IRX9999I EXECUTION LIMIT REACHED")
            return None, "RETURN"
        stripped = line.strip()
        if not stripped or stripped.startswith("/*"):
            return None, None
        if stripped.endswith(":") and re.fullmatch(r"[A-Za-z@#$][A-Za-z0-9@#$._-]*:", stripped):
            return None, None
        u = stripped.upper()

        if u.startswith("PARSE ARG "):
            names = [n for n in re.split(r"\s+", stripped[10:].strip()) if n]
            values = args.split()
            for idx, name in enumerate(names):
                self.vars[name.upper()] = values[idx] if idx < len(values) else ""
            return None, None

        if u.startswith("PARSE VAR "):
            m = re.match(r"PARSE\s+VAR\s+([A-Za-z@#$][A-Za-z0-9@#$._]*)\s+(.+)$", stripped, re.I)
            if m:
                text = self._lookup_var(m.group(1), args=args)
                names = [n for n in re.split(r"\s+", m.group(2).strip()) if n]
                vals = text.split()
                for idx, name in enumerate(names):
                    self.vars[name.upper()] = vals[idx] if idx < len(vals) else ""
            return None, None

        if u.startswith("PARSE VALUE "):
            m = re.match(r"PARSE\s+VALUE\s+(.+?)\s+WITH\s+(.+)$", stripped, re.I)
            if m:
                text = self._eval_expr(m.group(1), args=args)
                names = [n for n in re.split(r"\s+", m.group(2).strip()) if n]
                vals = text.split()
                for idx, name in enumerate(names):
                    self.vars[name.upper()] = vals[idx] if idx < len(vals) else ""
            return None, None

        if u.startswith("PARSE SOURCE"):
            self.vars[".PARSE_SOURCE"] = f"TSO COMMAND {self.userid} GIBSON REXX"
            return None, None

        if u.startswith("PULL "):
            names = [n for n in re.split(r"\s+", stripped[5:].strip()) if n]
            if self._pull_buffer:
                pulled = self._pull_buffer.pop(0)
            elif self.pull_provider:
                pulled = self.pull_provider() or ""
            else:
                pulled = ""
            parts = pulled.split()
            for idx, name in enumerate(names):
                self.vars[name.upper()] = parts[idx] if idx < len(parts) else ""
            return None, None

        if u.startswith("OUTTRAP"):
            arg = stripped[7:].strip().strip("'").strip('"')
            if arg.upper() in {"OFF", "0", "NO"} or not arg:
                self.outtrap_stem = None
            else:
                stem = arg.rstrip(".").upper()
                self.outtrap_stem = stem
                self.vars[f"{stem}0"] = "0"
            return None, None

        if u.startswith("IF ") and " THEN " in u:
            m = re.match(r"IF\s+(.+?)\s+THEN\s+(.+?)(?:\s+ELSE\s+(.+))?$", stripped, re.I)
            if m:
                cond, then_part, else_part = m.group(1), m.group(2), m.group(3)
                branch = then_part if self._eval_condition(cond, args=args) else (else_part or "")
                if branch:
                    return self._execute_line(branch, args, stack, pc)
                return None, None

        if u.startswith("DO "):
            end_idx = self._find_matching_end(stack[-1] if stack else 0)
            header = stripped[3:].strip()
            if m := re.match(r"([A-Za-z@#$][A-Za-z0-9@#$]*)\s*=\s*(.+?)\s+TO\s+(.+?)(?:\s+BY\s+(.+))?$", header, re.I):
                var, start_v, end_v, by_v = m.group(1), m.group(2), m.group(3), m.group(4) or "1"
                start_i = int(float(self._eval_expr(start_v, args=args) or "0"))
                end_i = int(float(self._eval_expr(end_v, args=args) or "0"))
                by_i = int(float(self._eval_expr(by_v, args=args) or "1")) or 1
                stack.append({"type": "DO", "var": var.upper(), "end": end_i, "by": by_i, "line": pc})
                self.vars[var.upper()] = str(start_i)
                return None, None
            if m := re.match(r"WHILE\s+(.+)$", header, re.I):
                cond = m.group(1)
                if self._eval_condition(cond, args=args):
                    stack.append({"type": "WHILE", "cond": cond, "line": pc})
                    return None, None
                return end_idx + 1, None
            if header.isdigit():
                count = int(header)
                if count <= 0:
                    return end_idx + 1, None
                stack.append({"type": "COUNT", "remaining": count, "line": pc})
                return None, None

        if u == "END":
            ctx = stack[-1] if stack else None
            if isinstance(ctx, dict):
                if ctx.get("type") == "DO":
                    var = str(ctx["var"])
                    cur = int(float(self.vars.get(var, "0") or "0")) + int(ctx.get("by", 1))
                    self.vars[var] = str(cur)
                    end_v = int(ctx.get("end", cur))
                    by_v = int(ctx.get("by", 1))
                    if (by_v > 0 and cur <= end_v) or (by_v < 0 and cur >= end_v):
                        return int(ctx.get("line", 0)) + 1, None
                    stack.pop()
                    return None, None
                if ctx.get("type") == "COUNT":
                    remaining = int(ctx.get("remaining", 1)) - 1
                    if remaining > 0:
                        ctx["remaining"] = remaining
                        return int(ctx.get("line", 0)) + 1, None
                    stack.pop()
                    return None, None
                if ctx.get("type") == "WHILE":
                    cond = str(ctx.get("cond", "0"))
                    if self._eval_condition(cond, args=args):
                        return int(ctx.get("line", 0)) + 1, None
                    stack.pop()
                    return None, None
            return None, None

        if u.startswith("CALL "):
            rest = stripped[5:].strip()
            parts = rest.split(None, 1)
            label = parts[0].rstrip(":").upper()
            call_args = parts[1] if len(parts) > 1 else ""
            if label == "CHAROUT":
                self._capture(self._eval_expr(call_args, args=args))
                self._set_rc(0)
                return None, None
            if label in self.labels:
                stack.append(-1)
                result = self._run_from(self.labels[label] + 1, call_args, stack)
                if stack and stack[-1] == -1:
                    stack.pop()
                self.vars["RESULT"] = result or ""
                self._set_rc(0)
                return None, None
            self._capture(f"IRX0043I ROUTINE {label} NOT FOUND")
            self._set_rc(16)
            return None, None

        if u.startswith("DROP "):
            target = stripped[5:].strip().upper()
            for key in list(self.vars):
                if key == target or key.startswith(target.rstrip(".") + "."):
                    self.vars.pop(key, None)
            return None, None

        if u.startswith("UPPER "):
            for name in stripped[6:].split():
                n = name.upper(); self.vars[n] = self.vars.get(n, "").upper()
            return None, None

        if u.startswith("RETURN"):
            self.vars["RESULT"] = self._eval_expr(stripped[6:].strip(), args=args) if len(stripped) > 6 else ""
            return None, "RETURN"

        if u.startswith("SAY "):
            self._capture(self._eval_expr(stripped[4:].strip(), args=args))
            self._set_rc(0)
            return None, None

        if u.startswith("ADDRESS TSO"):
            cmd = self._eval_expr(stripped[len("ADDRESS TSO"):].strip(), args=args)
            result = self.tso_runner(cmd) if self.tso_runner else f"IKJ56500I COMMAND {cmd} NOT FOUND"
            self._capture(result)
            self._set_rc(0 if "NOT FOUND" not in result.upper() else 8)
            return None, None

        if u.startswith("ADDRESS ISPEXEC"):
            payload = stripped[len("ADDRESS ISPEXEC"):].strip().strip("'").strip('"')
            result = ""
            up = payload.upper()
            if up.startswith("VGET"):
                names = re.findall(r"\(([^)]*)\)", payload)
                vars_text = names[0] if names else payload[4:]
                for name in re.split(r"\s+", vars_text.strip()):
                    if not name:
                        continue
                    n = name.upper()
                    self.vars[n] = self.vars.get(n) or {"ZUSER": self.userid, "ZSCREEN": "ISR@PRIM", "ZENVIR": "FORE"}.get(n, "")
                result = "ISPEXEC VGET COMPLETE"
            elif up.startswith("VPUT"):
                result = "ISPEXEC VPUT COMPLETE"
            elif up.startswith("DISPLAY"):
                result = f"ISPEXEC DISPLAY {payload}"
            elif up.startswith("SELECT"):
                result = f"ISPEXEC SELECT {payload}"
            elif self.ispexec:
                result = self.ispexec(payload)
            else:
                result = f"ISPEXEC {payload}"
            self._set_rc(0)
            if result:
                self._capture(result)
            return None, None

        if u.startswith("EXECIO"):
            m = re.match(r"EXECIO\s+(\*|\d+)\s+(DISKR|DISKW)\s+('?[^'\s]+'?|\S+)\s+\(\s*STEM\s+([A-Za-z@#$][A-Za-z0-9@#$.]*)", stripped, re.I)
            if m:
                count_token, mode, target, stem = m.group(1), m.group(2).upper(), m.group(3), m.group(4).rstrip(".").upper()
                dsn = self._eval_expr(target.strip().strip("'").strip('"'), args=args)
                if mode == "DISKR" and self.dataset_read:
                    text = self.dataset_read(dsn)
                    lines = text.splitlines()
                    count = len(lines) if count_token == "*" else min(len(lines), int(count_token))
                    for idx, item in enumerate(lines[:count], 1):
                        self.vars[f"{stem}.{idx}"] = item
                    self.vars[f"{stem}.0"] = str(count)
                    self._set_rc(0)
                    return None, None
                if mode == "DISKW" and self.dataset_write:
                    count = int(self.vars.get(f"{stem}.0", "0") or "0") if count_token == "*" else int(count_token)
                    data = "\n".join(self.vars.get(f"{stem}.{idx}", "") for idx in range(1, count + 1))
                    self.dataset_write(dsn, data)
                    self._set_rc(0)
                    return None, None
            self._capture(f"IRX0010I EXECIO SYNTAX ACCEPTED BUT NOT EXECUTED: {stripped}")
            self._set_rc(8)
            return None, None

        if re.match(r"[A-Za-z@#$][A-Za-z0-9@#$._]*\s*=", stripped):
            name, expr = stripped.split("=", 1)
            self.vars[name.strip().upper()] = self._eval_expr(expr.strip(), args=args)
            return None, None

        if u.startswith("EXIT"):
            return None, "RETURN"

        self._capture(f"IRX0006I EXEC statement simulated: {stripped}")
        return None, None

    def _run_from(self, start: int, args: str, stack: list[int | dict]) -> str:
        pc = start
        result = ""
        while pc < len(self.lines):
            line = self.lines[pc]
            if line.strip().upper().startswith("SELECT"):
                end = pc + 1; chosen: list[str] = []; active = False; matched = False
                while end < len(self.lines):
                    cur = self.lines[end].strip(); cu = cur.upper()
                    if cu == "END":
                        break
                    if cu.startswith("WHEN ") and " THEN " in cu:
                        cond, stmt = re.split(r"\s+THEN\s+", cur[5:], maxsplit=1, flags=re.I)
                        active = (not matched) and self._eval_condition(cond, args=args)
                        if active:
                            matched = True; chosen.append(stmt)
                        end += 1; continue
                    if cu.startswith("OTHERWISE"):
                        active = not matched; matched = True; end += 1; continue
                    if active:
                        chosen.append(cur)
                    end += 1
                for stmt in chosen:
                    self._execute_line(stmt, args, stack, pc)
                pc = end + 1
                continue
            line = self.lines[pc]
            jump, flag = self._execute_line(line, args, stack, pc)
            if flag == "RETURN":
                return result
            if jump is not None:
                pc = jump
                continue
            pc += 1
        return result

    def run(self, source: str, args: str = "") -> str:
        self._steps = 0
        self._last_output = []
        self._pull_buffer = []
        self._load(source)
        self._run_from(0, args, [])
        return "\n".join(self._last_output)
