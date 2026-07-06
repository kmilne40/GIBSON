from __future__ import annotations
import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

MAX_RESPONSE = 1_000_000
ALLOWED_SCHEMES = {'http','https'}

@dataclass
class RenderedPage:
    url: str
    title: str
    text: str
    links: list[tuple[str, str]] = field(default_factory=list)

class _HTMLToText(HTMLParser):
    def __init__(self, base_url: str = ''):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self._title = ''
        self._in_title = False
        self._skip = 0
    def handle_starttag(self, tag, attrs):
        t = tag.lower(); d = dict(attrs)
        if t in {'script','style','noscript'}: self._skip += 1; return
        if t == 'title': self._in_title = True
        if t in {'p','div','section','article','header','footer','br','tr','li','h1','h2','h3'}: self.parts.append('\n')
        if t == 'li': self.parts.append(' * ')
        if t == 'a' and d.get('href'):
            self._link_href = urljoin(self.base_url, d.get('href',''))
            self._link_text = []
    def handle_endtag(self, tag):
        t = tag.lower()
        if t in {'script','style','noscript'} and self._skip: self._skip -= 1; return
        if t == 'title': self._in_title = False
        if t == 'a' and self._link_href:
            label = re.sub(r'\s+', ' ', ''.join(self._link_text)).strip() or self._link_href
            self.links.append((label[:100], self._link_href))
            self.parts.append(f' [{len(self.links)}]')
            self._link_href = None; self._link_text = []
        if t in {'p','div','section','article','tr','h1','h2','h3'}: self.parts.append('\n')
    def handle_data(self, data):
        if self._skip: return
        s = html.unescape(data or '')
        if self._in_title: self._title += s
        if self._link_href: self._link_text.append(s)
        self.parts.append(s)
    @property
    def title(self):
        return re.sub(r'\s+', ' ', self._title).strip()[:120]

def _valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ALLOWED_SCHEMES and bool(p.netloc)
    except Exception:
        return False

def render_html(html_bytes: bytes | str, url: str = '') -> RenderedPage:
    raw = html_bytes.decode('utf-8', 'replace') if isinstance(html_bytes, (bytes, bytearray)) else str(html_bytes or '')
    parser = _HTMLToText(url)
    parser.feed(raw[:MAX_RESPONSE])
    text = re.sub(r'[\t\r\f]+', ' ', ''.join(parser.parts))
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if parser.links:
        text += '\n\nLinks:\n' + '\n'.join(f'[{i}] {label} -> {href}' for i,(label,href) in enumerate(parser.links,1))
    return RenderedPage(url=url, title=parser.title, text=text or '(empty page)', links=parser.links)

def _maybe_render_insim(url: str, state=None):
    """Render Gibson's own in-sim sites (localhost / mainframe / the configured
    hostname on port 80) directly via the welcome router, with no real HTTP.
    Returns body bytes, or None if the URL is not an in-sim site."""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
    except Exception:
        return None
    host = (p.hostname or "").lower()
    insim = {"localhost", "127.0.0.1", "mainframe", "gibson"}
    try:
        hn = (getattr(getattr(state, "network", None), "hostname", "") or "").lower()
        if hn:
            insim.add(hn)
    except Exception:
        pass
    if host not in insim:
        return None
    port = p.port or 80
    if port not in (80, None):
        return None
    path = (p.path or "/")
    if p.query:
        path += "?" + p.query
    try:
        from gibson.apps.welcome.routes import render_page
        _code, _ctype, body = render_page(path, state=state)
        if isinstance(body, str):
            body = body.encode("utf-8", "replace")
        return body
    except Exception:
        return None


def fetch_url(url: str, *, timeout: float = 12.0, max_bytes: int = MAX_RESPONSE, state=None) -> bytes:
    if not _valid_url(url):
        raise ValueError('only http/https URLs are allowed')
    insim = _maybe_render_insim(url, state)
    if insim is not None:
        return insim[:max_bytes]
    try:
        import httpx  # type: ignore
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={'User-Agent':'Gibson-Lynx/1.0'}) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.content[:max_bytes]
    except ImportError:
        from urllib.request import Request, urlopen
        req = Request(url, headers={'User-Agent':'Gibson-Lynx/1.0'})
        with urlopen(req, timeout=timeout) as resp:  # nosec - URL scheme validated above
            return resp.read(max_bytes)

def dump_url(url: str, *, state=None) -> str:
    page = render_html(fetch_url(url, state=state), url)
    head = f'Gibson Lynx dump: {page.title or url}\nURL: {url}\n' + '-'*72
    return head + '\n' + page.text

def render_url(url: str, *, page_size: int = 22, state=None) -> str:
    from gibson.tools.terminal_pager import page_text
    return page_text(dump_url(url, state=state), page_size=page_size)

# ---------------------------------------------------------------------------
# ISPF-friendly clean rendering
#
# The ISPF RSS reader and the ISPF Lynx browser need plain, EBCDIC-safe text
# that a 3270 ScrollList can page with PF7/PF8.  They must NOT use the line-mode
# terminal pager (no "--More--" prompt) and must not carry ANSI escapes or
# bracketed link markers (square brackets render as garble on a 3270).  These
# helpers produce clean, word-wrapped ASCII lines for exactly that purpose.
# ---------------------------------------------------------------------------

_UNICODE_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
    "\u2014": "--", "\u2026": "...", "\u00a0": " ", "\u00ab": '"', "\u00bb": '"',
    "\u2022": "*", "\u2192": "->", "\u00e2": "a", "\u20ac": "EUR", "\u00a3": "GBP",
}


def _ascii_safe(text: str) -> str:
    """Normalise common unicode punctuation to ASCII and drop anything that is
    not printable ASCII, so the result renders cleanly through the EBCDIC 3270
    path.  Square brackets become parentheses (brackets garble on a 3270)."""
    for u, a in _UNICODE_MAP.items():
        text = text.replace(u, a)
    text = text.replace("[", "(").replace("]", ")")
    out = []
    for ch in text:
        if ch in "\n\t":
            out.append(ch)
        elif 0x20 <= ord(ch) <= 0x7e:
            out.append(ch)
        # everything else (control chars, residual unicode) is dropped
    return "".join(out)


def clean_render_lines(text: str, width: int = 78) -> list[str]:
    """Strip ANSI, make EBCDIC-safe, and word-wrap to ``width`` columns."""
    import textwrap
    try:
        from gibson.render.ansi3270 import strip_ansi
        text = strip_ansi(text)
    except Exception:
        text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    text = _ascii_safe(text)
    lines: list[str] = []
    for raw in text.split("\n"):
        raw = raw.replace("\t", "    ").rstrip()
        if not raw:
            lines.append("")
            continue
        for seg in textwrap.wrap(raw, width=width, break_long_words=True,
                                 break_on_hyphens=False) or [""]:
            lines.append(seg)
    return lines


def render_clean_lines(url: str, *, width: int = 78, state=None,
                       header: bool = True) -> list[str]:
    """Fetch a URL and return clean, ISPF-ready scrollable lines (Lynx in ISPF)."""
    if not _valid_url(url):
        return ["LYNX011E ONLY http:// and https:// URLs are allowed.", f"  ({url})"]
    try:
        page = render_html(fetch_url(url, state=state), url)
    except Exception as exc:
        return [f"LYNX013E FETCH/RENDER FAILED - {type(exc).__name__}: {str(exc)[:90]}"]
    out: list[str] = []
    if header:
        out += [f"URL  : {url}", f"TITLE: {page.title}", "-" * width, ""]
    out += clean_render_lines(page.text, width=width)
    return out
