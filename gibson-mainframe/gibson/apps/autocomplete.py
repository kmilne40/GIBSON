from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple
import re

from gibson.apps.tso import TsoCommandProcessor
from gibson.core.state import GibsonState


@dataclass(frozen=True)
class CompletionItem:
    command: str
    syntax: str
    source: str = "builtin"
    description: str = ""


class TsoAutocomplete:
    """READY prompt autocomplete for Gibson TSO.

    Sources:
      * built-in legacy TSO commands from TsoCommandProcessor.LEGACY_HELP
      * explicit syntax definitions for commands whose operands matter
      * every command template file in ~/mfsim/f/commands and packaged assets
    """

    EXTRA_SYNTAX = {
        "ADDUSER": "ADDUSER userid PASS(password) [SPECIAL|NOSPECIAL] [OMVS|NOOMVS] [DFLTGRP(group)]",
        "ALTUSER": "ALTUSER userid [PASS(password)] [SPECIAL|NOSPECIAL] [OMVS|NOOMVS] [DFLTGRP(group)]",
        "RACLIST": "RACLIST CLASS(USER) ID(userid) [DETAIL]",
        "PROFILE": "PROFILE | PROFILE PREFIX(userid) | PROFILE NOPREFIX",
        "LISTDS": "LISTDS dataset STATUS HISTORY | LISTDS dataset MEMBERS",
        "LISTDSD": "LISTDSD DATASET('dataset') ALL",
        "RLIST": "RLIST class profile [ALL|AUTH]",
        "RDEFINE": "RDEFINE class profile UACC(access)",
        "PERMIT": "PERMIT profile CLASS(class) ID(userid) ACCESS(access)",
        "SEARCH ALL WARNING NOMASK": "SEARCH ALL WARNING NOMASK",
        "SEARCH CLASS(FACILITY) FILTER(BPX.**)": "SEARCH CLASS(FACILITY) FILTER(BPX.**)",
        "SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)": "SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)",
        "SEARCH CLASS(USER) UID(0)": "SEARCH CLASS(USER) UID(0)",
        "NETSTAT": "NETSTAT HOME|CONFIG|CONN|ALL|DEVLINKS|ROUTE|ARP|PORTLIST|TELNET|FTP",
        "NETSTAT HOME": "NETSTAT HOME",
        "NETSTAT CONN": "NETSTAT CONN",
        "DISPLAY TCPIP,,NETSTAT,HOME": "DISPLAY TCPIP,,NETSTAT,HOME",
        "DISPLAY SMF,O": "DISPLAY SMF,O",
        "SETPROG": "SETPROG APF,ADD,DSNAME=RUARIV.VULNAPF.LIB,VOLUME=SMS",
        "TRACERTE": "TRACERTE host-or-ip",
        "RVARY": "RVARY",
        "LISTUSER": "LISTUSER [userid|*]",
        "LISTCAT": "LISTCAT [LEVEL(prefix)]",
        "LISTCAT LEVEL(SYS1)": "LISTCAT LEVEL(SYS1)",
        "SEARCH CLASS(USER)": "SEARCH CLASS(USER)",
        "SEARCH": "SEARCH CLASS(DATASET) [MASK(dataset-mask)]",
        "SEND": "SEND 'message text' USER(userid) NOW|LOGON",
        "EDIT": "EDIT dataset.name | EDIT 'dataset.name(member)'",
        "VIEW": "VIEW dataset.name | VIEW 'dataset.name(member)'",
        "DEL": "DEL dataset.name",
        "DELETE": "DELETE dataset.name",
        "SUBMIT": "SUBMIT 'dataset.name(member)'",
        "REXX": "REXX execname | EXEC 'dataset(member)' EXEC | %execname",
        "EXEC": "EXEC 'dataset(member)' EXEC",
        "EX": "EX 'dataset(member)'",
        "JES": "JES STATUS | JES SUBMIT job-description",
        "SDSF": "SDSF [ST|DA|I|O|H|LOG|APF|NODE|LINE|MENU]",
        "ISF": "ISF [ST|DA|I|O|H|LOG|APF|NODE|LINE|MENU]",
        "DSN": "DSN SYSTEM(DB2A)",
        "SPUFI": "SPUFI",
        "RUN SQL": "RUN SQL SELECT * FROM SYSIBM.SYSTABLES",
        "OMVS": "OMVS",
        "CONSOLE": "CONSOLE",
        "DISPLAY": "DISPLAY TIME | DISPLAY IPLINFO | DISPLAY TCPIP | DISPLAY PROG,APF",
        "D R,R": "D R,R | DISPLAY R,R",
        "D R,L": "D R,L | DISPLAY R,L | D R,L,CN=(ALL)",
        "D SVC,L": "D SVC,L | DISPLAY SERVICES",
        "R nn,reply": "R nn,reply",
        "Z EOD": "Z EOD",
        "PING": "PING host-or-ip",
        "OEDIT": "OEDIT '/u/ibmuser/file'",
        "OGET": "OGET '/u/ibmuser/file' IBMUSER.DATA",
        "OPUT": "OPUT IBMUSER.DATA '/u/ibmuser/file'",
        "SETROPTS LIST": "SETROPTS LIST",
        "ACF2": "ACF2",
        "RACF": "RACF",
        "SET LID": "SET LID",
        "SET PROFILE(GROUP) DIV(OMVS)": "SET PROFILE(GROUP) DIV(OMVS)",
        "SET RULE": "SET RULE",
        "SET RESOURCE(FAC)": "SET RESOURCE(FAC)",
        "SET CONTROL(GSO)": "SET CONTROL(GSO)",
        "SHOW ACF2": "SHOW ACF2",
        "SHOW TSO": "SHOW TSO",
        "SHOW PSWD": "SHOW PSWD",
        "SHOW DDSN": "SHOW DDSN",
        "ACCESS": "ACCESS DSNAME('dataset') | ACCESS RESOURCE(name) TYPE(type)",
        "TEST": "TEST DSNAME('dataset') LID(userid) SERVICE(READ)",
        "RECKEY": "RECKEY key ADD( resource UID(userid) SERVICE(READ) ALLOW )",
        "SESSIONSTATS": "SESSIONSTATS",
        "HELP": "HELP [command]",
        "CLEAR": "CLEAR",
        "LOGOFF": "LOGOFF",
        "EXIT": "EXIT",
    }

    ALIASES = {
        "START": "START",
        "ISPF": "ISPF",
        "CICS": "CICS",
        "DB2": "DB2",
        "L CICS": "L CICS",
        "L DB2": "L DB2",
        "LOGON APPLID(CICS)": "LOGON APPLID(CICS)",
        "LOGON APPLID(DB2)": "LOGON APPLID(DB2)",
    }

    def __init__(self, state: GibsonState):
        self.state = state

    def items(self) -> List[CompletionItem]:
        items: dict[str, CompletionItem] = {}
        for command, desc in TsoCommandProcessor.LEGACY_HELP.items():
            key = command.upper()
            items[key] = CompletionItem(key, self.EXTRA_SYNTAX.get(key, key), "builtin", desc)
        for command, syntax in self.EXTRA_SYNTAX.items():
            key = command.upper()
            old = items.get(key)
            items[key] = CompletionItem(key, syntax, old.source if old else "builtin", old.description if old else "")
        for command, syntax in self.ALIASES.items():
            key = command.upper()
            items.setdefault(key, CompletionItem(key, syntax, "builtin", ""))
        for path in self._template_files():
            cmd = path.name.upper()
            stem = cmd[:-4] if cmd.endswith(".TXT") else cmd
            syntax, desc = self._extract_template_hint(path, stem)
            items[stem] = CompletionItem(stem, syntax or stem, "template", desc)
        return sorted(items.values(), key=lambda i: i.command)

    def _template_files(self) -> Iterable[Path]:
        roots = []
        for attr in ("commands_dir", "assets_dir"):
            try:
                roots.append(Path(getattr(self.state.config, attr)))
            except Exception:
                pass
        seen: set[Path] = set()
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for p in sorted(root.iterdir()):
                if p in seen or not p.is_file() or p.name.startswith('.'):
                    continue
                seen.add(p)
                yield p

    def _extract_template_hint(self, path: Path, command: str) -> Tuple[str, str]:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return command, ""
        meaningful = [ln.strip() for ln in lines if ln.strip()]
        for ln in meaningful[:30]:
            m = re.search(r"\b(?:USAGE|SYNTAX|COMMAND|FORMAT)\s*[:=]\s*(.+)$", ln, re.I)
            if m:
                return m.group(1).strip(), "template syntax"
        for ln in meaningful[:10]:
            if re.fullmatch(r"[-=*_./\\\s]+", ln):
                continue
            return command, ln[:70]
        return command, "template command"

    def complete(self, buffer: str) -> Tuple[str, str]:
        raw = buffer or ""
        prefix = raw.upper().strip()
        all_items = self.items()
        if not prefix:
            return raw, self._format_items(all_items[:80], "GIBSON TSO COMMANDS")
        matches = [i for i in all_items if i.command.startswith(prefix) or i.syntax.upper().startswith(prefix)]
        if not matches:
            first = prefix.split()[0]
            matches = [i for i in all_items if i.command.startswith(first)]
        if not matches:
            return raw, f"\nNO COMPLETION FOR: {buffer}\n"
        if len(matches) == 1:
            item = matches[0]
            new_buffer = raw if raw.endswith(" ") else item.command
            return new_buffer, self._format_items(matches, "COMMAND SYNTAX")
        common = self._common_prefix([m.command for m in matches])
        new_buffer = common if len(common) > len(prefix) else raw
        return new_buffer, self._format_items(matches[:80], f"MATCHING COMMANDS FOR {buffer!r}")

    def _common_prefix(self, values: List[str]) -> str:
        if not values:
            return ""
        prefix = values[0]
        for value in values[1:]:
            while not value.startswith(prefix) and prefix:
                prefix = prefix[:-1]
        return prefix

    def _format_items(self, items: List[CompletionItem], title: str) -> str:
        """Format autocomplete results as a clean two-column table.

        Internal source labels such as template/built-in are intentionally not
        shown. Operators only need the command or syntax and a concise
        description of the response/behaviour.
        """
        width = 79
        left_w = 43
        right_w = width - left_w - 3

        def wrap(text: str, max_len: int) -> List[str]:
            text = " ".join((text or "").split())
            if len(text) <= max_len:
                return [text]
            words = text.split()
            lines: List[str] = []
            cur = ""
            for word in words:
                if not cur:
                    cur = word[:max_len]
                elif len(cur) + 1 + len(word) <= max_len:
                    cur += " " + word
                else:
                    lines.append(cur)
                    cur = word[:max_len]
            if cur:
                lines.append(cur)
            return lines or [""]

        lines = ["", title[:width], "-" * min(width, max(len(title), 40))]
        lines.append(f"{'COMMAND / SYNTAX':<{left_w}}   DESCRIPTION")
        lines.append(f"{'-' * left_w}   {'-' * right_w}")

        if not items:
            lines.append("No matching commands.")
        for item in items:
            command_text = item.syntax.strip() if item.syntax and item.syntax.upper() != item.command.upper() else item.command
            desc = item.description.strip() if item.description else ""
            if desc.lower() in {"template command", "template syntax"}:
                desc = ""
            left_lines = wrap(command_text, left_w)
            right_lines = wrap(desc, right_w) if desc else [""]
            rows = max(len(left_lines), len(right_lines))
            for idx in range(rows):
                left = left_lines[idx] if idx < len(left_lines) else ""
                right = right_lines[idx] if idx < len(right_lines) else ""
                lines.append(f"{left:<{left_w}}   {right}")

        lines.append("")
        lines.append("Type a full command, or use a more specific prefix, for example SEARCH CLASS(USER).")
        lines.append("Use ? or a trailing ? if your terminal consumes the TAB key locally.")
        return "\n".join(lines) + "\n"
