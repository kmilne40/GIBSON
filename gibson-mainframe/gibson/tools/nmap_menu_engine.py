from __future__ import annotations
import contextlib, importlib, io, shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MENU = """Gibson nmap-sim guided menu\n\n1  Quick screen grab\n2  TSO user enumeration\n3  Safe CICS information gathering\n4  CICS transaction enumeration\n5  CICSPWN simulation: safe forensic mode\n6  Bounded TSO credential audit\n7  Bounded CICS credential audit\n8  Full Gibson classroom smoke run\n9  Export last results\nX  Exit\n\nUse: nmap -M <option> [advanced options]\nExamples:\n  nmap -M 2\n  nmap -M 2 -u users.txt --script-args tso-enum.commands='L TSO'\n  nmap -M 9 -oN last.txt -oJ last.json"""

@dataclass
class NmapMenuState:
    last_text: str = ''
    last_json: str = ''
    last_action: str = ''

ACTION_SCRIPTS = {
    '1': ['--script','tn3270-screen'],
    '2': ['--script','tso-enum'],
    '3': ['--script','cics-info'],
    '4': ['--script','cics-enum'],
    '5': ['--script','cicspwn','--script-args','cicspwn.mode=forensic,cicspwn.safe=true'],
    '6': ['--script','tso-brute'],
    '7': ['--script','cics-user-brute'],
    '8': ['--script','tn3270-screen,tso-enum,cics-info,cics-enum,cicspwn','--script-args','cicspwn.mode=forensic,cicspwn.safe=true'],
}

def render_menu() -> str:
    return MENU

def _engine_main(argv: list[str]) -> tuple[int, str]:
    mod = importlib.import_module('gibson.tools.omvs_nmap_sim')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            rc = mod.main(argv)
        except SystemExit as exc:
            rc = int(exc.code or 0) if isinstance(exc.code, int) else 1
    return rc, buf.getvalue().rstrip()

def run_action(selection: str, extra_args: list[str] | None = None, *, state: NmapMenuState | None = None) -> str:
    sel = (selection or '').strip().upper()
    st = state or NmapMenuState()
    extra = list(extra_args or [])
    if sel in {'X','EXIT','END','Q','QUIT'}:
        return 'NMAP menu exited.'
    if sel == '9':
        return export_last(extra, st)
    if sel not in ACTION_SCRIPTS:
        return render_menu()
    argv = list(ACTION_SCRIPTS[sel]) + extra
    # Ensure target and port defaults match the classroom simulator.
    if not any(a in {'-p','--port'} or a.startswith('--port=') for a in argv):
        argv = ['-p','2023'] + argv
    if not any(a in {'127.0.0.1','mainframe'} for a in argv) and not any(a.startswith('--host=') for a in argv):
        argv.append('127.0.0.1')
    if '--offline' not in argv:
        # OMVS/TSO menus must remain useful when the listener is not running.
        argv.append('--offline')
    rc, text = _engine_main(argv)
    mode = 'Transport mode: FALLBACK simulator classification (--offline).'
    text = f'NMAP MENU OPTION {sel}\n{mode}\n\n{text}'
    st.last_text = text; st.last_action = sel
    return text + ('' if rc == 0 else f'\n[nmap simulator exit status {rc}]')

def export_last(extra_args: list[str], state: NmapMenuState) -> str:
    if not state.last_text:
        return 'NMAP009E NO LAST RESULTS TO EXPORT'
    normal = None; js = None
    args = list(extra_args or [])
    i = 0
    while i < len(args):
        if args[i] == '-oN' and i+1 < len(args): normal = args[i+1]; i += 2; continue
        if args[i] == '-oJ' and i+1 < len(args): js = args[i+1]; i += 2; continue
        i += 1
    written = []
    if normal:
        Path(normal).write_text(state.last_text + '\n', encoding='utf-8'); written.append(normal)
    if js:
        import json
        Path(js).write_text(json.dumps({'tool':'nmap-menu','last_action':state.last_action,'text':state.last_text}, indent=2) + '\n', encoding='utf-8'); written.append(js)
    return 'NMAP009I EXPORTED ' + ', '.join(written) if written else state.last_text
