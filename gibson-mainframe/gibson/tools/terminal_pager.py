from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class PagerResult:
    text: str
    position: int = 0
    quit: bool = False
    searches: list[str] = field(default_factory=list)

class TerminalPager:
    def __init__(self, text: str, *, page_size: int = 22):
        self.lines = (text or '').splitlines() or ['']
        self.page_size = max(1, int(page_size or 22))
        self.position = 0

    def page(self) -> str:
        end = min(len(self.lines), self.position + self.page_size)
        body = '\n'.join(self.lines[self.position:end])
        if end < len(self.lines):
            body += '\n--More-- SPACE next page  ENTER line  b back  /search  q quit  ? help'
        return body

    def handle(self, key: str) -> str:
        k = (key or '').strip()
        if k in {' ', 'SPACE', 'PGDN', 'PAGEDOWN'}:
            self.position = min(len(self.lines)-1, self.position + self.page_size)
        elif k in {'', 'ENTER', 'DOWN'}:
            self.position = min(len(self.lines)-1, self.position + 1)
        elif k.lower() in {'b','back','pgup','pageup'}:
            self.position = max(0, self.position - self.page_size)
        elif k.startswith('/') and len(k) > 1:
            term = k[1:].lower()
            for i in range(self.position + 1, len(self.lines)):
                if term in self.lines[i].lower():
                    self.position = i
                    break
        elif k in {'?','h','H','HELP'}:
            return 'Pager help: SPACE next page, ENTER next line, b previous page, /term search, q quit.'
        return self.page()

def page_text(text: str, *, page_size: int = 22, keys: list[str] | None = None) -> str:
    pager = TerminalPager(text, page_size=page_size)
    if not keys:
        return pager.page()
    out = []
    for key in keys:
        if str(key).lower() == 'q':
            out.append('[pager quit]')
            break
        out.append(pager.handle(key))
    return '\n'.join(out) if out else pager.page()
