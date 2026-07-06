from __future__ import annotations
from gibson.tools.html_text_browser import dump_url, render_url
from gibson.tools.security_events import emit_omvs_tool_event

HELP = """lynx - Gibson safe text browser\nUsage:\n  lynx URL\n  lynx -dump URL\n  lynx -links URL\nControls in interactive pager: SPACE next page, ENTER line, b back, /term search, q quit.\nExternal HTTP/HTTPS is enabled by default. JavaScript is not executed; redirects/timeouts/max-size controls are enforced."""

def lynx_command(argv: list[str], state=None, userid: str = "IBMUSER") -> str:
    args = list(argv or [])
    if not args or args[0] in {'-h','--help','help','?'}:
        return HELP
    dump = False
    if args[0] == '-dump':
        dump = True; args = args[1:]
    elif args[0] == '-links':
        dump = True; args = args[1:]
    elif args[0] == '-source':
        return 'lynx: -source is not enabled in Gibson safe browser mode'
    if not args:
        return 'lynx: missing URL\n' + HELP
    url = args[0]
    try:
        out = dump_url(url, state=state) if dump else render_url(url, state=state)
        try:
            emit_omvs_tool_event(state=state, user=userid, tool="LYNX", script="BROWSE", target=url, result="OK", severity="LOW", details={"url": url}, command_line="lynx " + url)
        except Exception:
            pass
        return out
    except Exception as exc:
        try:
            emit_omvs_tool_event(state=state, user=userid, tool="LYNX", script="BROWSE", target=url, result="ERROR", severity="LOW", details={"error": str(exc), "url": url}, command_line="lynx " + url)
        except Exception:
            pass
        return f'lynx: {type(exc).__name__}: {exc}'



class LynxSession:
    """Stateful interactive Lynx browser driven one command at a time, so it can
    back BOTH the ASCII reader/writer loop and the EBCDIC 3270 sub-mode from a
    single command grammar (no drift between the two front-ends)."""
    PAGE_SIZE = 20

    def __init__(self, argv, state=None, userid: str = "IBMUSER"):
        self.state = state
        self.userid = userid
        self._argv = list(argv or [])
        self.url = self._argv[0] if self._argv else None
        self.page = None
        self.offset = 0
        self.history: list = []
        self.forward: list = []
        self._buf: list = []

    def prompt(self) -> str:
        return "lynx> "

    def has_url(self) -> bool:
        return bool(self._argv)

    def _w(self, s: str) -> None:
        self._buf.append(s)

    def _flush(self) -> str:
        out = "".join(self._buf)
        self._buf = []
        return out

    def _load(self, u: str) -> None:
        from gibson.tools.html_text_browser import fetch_url, render_html
        try:
            self.page = render_html(fetch_url(u, state=self.state), u)
            self.url = u
            self.offset = 0
            try:
                emit_omvs_tool_event(state=self.state, user=self.userid, tool="LYNX",
                                     script="BROWSE", target=u, result="OK", severity="LOW",
                                     details={"interactive": True}, command_line="lynx " + u)
            except Exception:
                pass
        except Exception as exc:
            self.page = None
            self._w(f"lynx: {type(exc).__name__}: {exc}\n")

    def _draw(self) -> None:
        if self.page is None:
            return
        lines = (f"Gibson Lynx: {self.page.title or self.url}\nURL: {self.url}\n"
                 + '-' * 72 + '\n' + self.page.text).splitlines()
        end = min(len(lines), self.offset + self.PAGE_SIZE)
        self._w("\n".join(lines[self.offset:end]) + "\n")
        self._w("--Lynx-- SPACE next  p previous  number open  g URL  b back  "
                "f forward  r reload  /search  q quit  ? help\n")

    def start(self) -> str:
        """Initial screen: HELP if no URL was given, else the first page."""
        if not self._argv:
            self._w(HELP + "\n")
            return self._flush()
        self._load(self._argv[0])
        self._draw()
        return self._flush()

    def handle(self, line: str):
        """Process one command. Returns rendered text, or None to quit."""
        key = (line or "").strip()
        k = key.lower()
        if k in {'q', 'quit', 'exit', 'pf3', 'f3', 'eof'}:
            return None
        if k in {'?', 'help', 'h'}:
            self._w('Keys: SPACE next page, p previous, number opens link, g URL, '
                    'b back, f forward, r reload, /term search, q quit.\n')
            return self._flush()
        if k in {'space', ' ', 'n', 'next', ''}:
            self.offset += self.PAGE_SIZE
            self._draw()
            return self._flush()
        if k in {'p', 'prev', 'previous', 'pgup'}:
            self.offset = max(0, self.offset - self.PAGE_SIZE)
            self._draw()
            return self._flush()
        if k == 'r':
            self._load(self.url)
            self._draw()
            return self._flush()
        if k == 'b' and self.history:
            self.forward.append(self.url)
            self._load(self.history.pop())
            self._draw()
            return self._flush()
        if k == 'f' and self.forward:
            self.history.append(self.url)
            self._load(self.forward.pop())
            self._draw()
            return self._flush()
        if k == 'g' or k.startswith('g '):
            new = key[1:].strip()
            if new:
                self.history.append(self.url)
                self.forward.clear()
                self._load(new)
                self._draw()
            else:
                self._w('Usage: g URL\n')
            return self._flush()
        if k.startswith('/') and self.page:
            term = k[1:].lower()
            lines = (self.page.text or '').splitlines()
            for i, ln in enumerate(lines):
                if i > self.offset and term in ln.lower():
                    self.offset = i
                    break
            self._draw()
            return self._flush()
        if k.isdigit() and self.page:
            idx = int(k) - 1
            if 0 <= idx < len(self.page.links):
                self.history.append(self.url)
                self.forward.clear()
                self._load(self.page.links[idx][1])
                self._draw()
            else:
                self._w('No such link.\n')
            return self._flush()
        self._w('Unknown Lynx command. ? for help.\n')
        return self._flush()


# Interactive Lynx-style sub-application. Used when OMVS has an input driver.
def run_lynx_interactive(argv: list[str], state=None, userid: str = "IBMUSER", reader=None, writer=None) -> None:
    if writer is None:
        return
    sess = LynxSession(argv, state=state, userid=userid)
    if not sess.has_url():           # `lynx` with no URL: print HELP and exit
        writer(HELP + "\n")
        return
    writer(sess.start())
    while True:
        try:
            res = reader.read_line("lynx> ") if hasattr(reader, 'read_line') else reader("lynx> ", False)
            key = (getattr(res, 'key', '') or getattr(res, 'text', '') or '').strip()
        except Exception:
            return
        if key.strip().lower() == 'g':           # preserve the original nested URL prompt
            res = reader.read_line('URL: ') if hasattr(reader, 'read_line') else reader('URL: ', False)
            new = (getattr(res, 'text', '') or '').strip()
            if not new:
                continue
            key = f"g {new}"
        out = sess.handle(key)
        if out is None:
            writer('Leaving Lynx.\n')
            return
        if out:
            writer(out)
