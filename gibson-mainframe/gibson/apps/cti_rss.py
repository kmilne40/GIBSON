from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

FEEDS_DSN = "FIBS.CTI.RSS.FEEDS"
CACHE_DSN = "FIBS.CTI.RSS.CACHE"
LASTRUN_DSN = "FIBS.CTI.RSS.LASTRUN"
REPORT_DSN = "FIBS.CTI.RSS.REPORT"
MAX_ITEMS = 5
FETCH_TIMEOUT = 12

DEFAULT_FEEDS = [
    {"name": "KrebsOnSecurity", "url": "https://krebsonsecurity.com/feed/"},
    {"name": "Hacker News Front Page", "url": "https://hnrss.org/frontpage"},
    {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
    {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews"},
    {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml"},
    {"name": "Sophos News", "url": "https://news.sophos.com/en-us/feed/"},
    {"name": "HackRead", "url": "https://hackread.com/feed/"},
    {"name": "Cyble Blog", "url": "https://cyble.com/feed/"},
    {"name": "IT Security Guru", "url": "https://www.itsecurityguru.org/feed/"},
    {"name": "SearchSecurity (TechTarget)", "url": "https://www.techtarget.com/searchsecurity/rss"},
    {"name": "CSO Online", "url": "https://www.csoonline.com/feed/"},
    {"name": "GBHackers on Security", "url": "https://gbhackers.com/feed/"},
    {"name": "Planet Mainframe", "url": "https://planetmainframe.com/feed/"},
]

@dataclass
class RssItem:
    feed: str
    title: str
    link: str
    published: str = ""
    summary: str = ""

@dataclass
class FeedStatus:
    name: str
    url: str
    status: str
    items: int = 0
    error: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _norm_name(name: str) -> str:
    clean = re.sub(r"[^A-Z0-9_-]", "", (name or "").upper().replace(" ", "_"))
    return clean[:32] or "FEED"


def _display_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())[:64] or "Feed"


def _valid_url(url: str) -> bool:
    try:
        p = urlparse((url or "").strip())
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def _clean(text: Any, limit: int = 180) -> str:
    s = html.unescape(str(text or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def _alloc(state: Any, userid: str, dsn: str, text: str = "") -> None:
    try:
        state.datasets.allocate(userid, dsn, org="PS", recfm="VB", lrecl=1024)
    except Exception:
        pass
    if text:
        try:
            state.datasets.write(userid, dsn, text)
        except Exception:
            pass


def ensure_rss_datasets(state: Any, userid: str = "IBMUSER") -> None:
    try:
        current = state.datasets.read(userid, FEEDS_DSN)
    except Exception:
        current = ""
    if not current.strip():
        lines = [
            f"{_norm_name(f['name'])}|{f['url']}|{_display_name(f['name'])}"
            for f in DEFAULT_FEEDS
        ]
        _alloc(state, userid, FEEDS_DSN, "\n".join(lines) + "\n")
    for dsn in (CACHE_DSN, LASTRUN_DSN, REPORT_DSN):
        try:
            state.datasets.read(userid, dsn)
        except Exception:
            _alloc(state, userid, dsn, "")


def list_feeds(state: Any, userid: str = "IBMUSER") -> list[dict[str, str]]:
    ensure_rss_datasets(state, userid)
    try:
        text = state.datasets.read(userid, FEEDS_DSN)
    except Exception:
        text = ""
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("{"):
            try:
                data = json.loads(line)
                name = _norm_name(data.get("name", ""))
                url = data.get("url", "")
                title = _display_name(data.get("title") or data.get("name") or name)
            except Exception:
                continue
        else:
            parts = line.split("|")
            if len(parts) < 2:
                continue
            name = _norm_name(parts[0])
            url = parts[1].strip()
            title = _display_name(parts[2] if len(parts) > 2 else parts[0])
        if _valid_url(url):
            rows.append({"name": name, "url": url, "title": title})
    return rows


def save_feeds(state: Any, feeds: Iterable[dict[str, str]], userid: str = "IBMUSER") -> None:
    ensure_rss_datasets(state, userid)
    text = "\n".join(
        f"{_norm_name(f.get('name',''))}|{f.get('url','')}|{_display_name(f.get('title') or f.get('name',''))}"
        for f in feeds
    ) + "\n"
    state.datasets.write(userid, FEEDS_DSN, text)


def _feed_by_name(state: Any, userid: str, name: str) -> dict[str, str] | None:
    wanted = _norm_name(name)
    for f in list_feeds(state, userid):
        if f["name"] == wanted or _norm_name(f["title"]) == wanted:
            return f
    return None


def _parse_feed(content: bytes, feed_name: str) -> list[RssItem]:
    import feedparser  # type: ignore
    parsed = feedparser.parse(content)
    out: list[RssItem] = []
    for entry in getattr(parsed, "entries", [])[:MAX_ITEMS]:
        out.append(RssItem(
            feed=feed_name,
            title=_clean(getattr(entry, "title", "(no title)"), 180),
            link=str(getattr(entry, "link", ""))[:240],
            published=_clean(getattr(entry, "published", getattr(entry, "updated", "")), 80),
            summary=_clean(getattr(entry, "summary", ""), 220),
        ))
    return out


def fetch_feed(url: str, feed_name: str, fetcher: Any = None) -> tuple[list[RssItem], str]:
    if not _valid_url(url):
        return [], "INVALID-URL"
    try:
        if fetcher is not None:
            content = fetcher(url)
        else:
            import httpx  # type: ignore
            with httpx.Client(
                timeout=FETCH_TIMEOUT,
                headers={"User-Agent": "Gibson-FIBS-RSS/2.0"},
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                content = response.content
        return _parse_feed(content, feed_name), "OK"
    except Exception as exc:
        return [], f"{type(exc).__name__}: {_clean(exc, 80)}"


def fetch_all(state: Any, userid: str = "IBMUSER", fetcher: Any = None) -> tuple[list[RssItem], list[FeedStatus]]:
    feeds = list_feeds(state, userid)
    items: list[RssItem] = []
    status: list[FeedStatus] = []
    live = fetcher is not None or os.getenv("GIBSON_RSS_LIVE_FETCH", "").upper() in {"1", "Y", "YES", "TRUE"}
    for feed in feeds:
        if live:
            feed_items, stat = fetch_feed(feed["url"], feed["name"], fetcher)
        else:
            feed_items = [RssItem(feed["name"], f"Offline cached training headline for {feed['title']}", feed["url"], "", "Live fetch disabled by default; set GIBSON_RSS_LIVE_FETCH=YES.")]
            stat = "OFFLINE-CACHE"
        items.extend(feed_items)
        status.append(FeedStatus(feed["name"], feed["url"], "OK" if stat in {"OK", "OFFLINE-CACHE"} else "ERROR", len(feed_items), "" if stat in {"OK", "OFFLINE-CACHE"} else stat))
    cache = {
        "time": _now(),
        "items": [asdict(i) for i in items[:500]],
        "status": [asdict(s) for s in status],
    }
    state.datasets.write(userid, CACHE_DSN, json.dumps(cache, indent=2))
    state.datasets.write(userid, LASTRUN_DSN, cache["time"] + "\n")
    return items, status


def load_cache(state: Any, userid: str = "IBMUSER") -> dict[str, Any]:
    ensure_rss_datasets(state, userid)
    try:
        text = state.datasets.read(userid, CACHE_DSN)
        return json.loads(text) if text.strip() else {"items": [], "status": [], "time": "NEVER"}
    except Exception:
        return {"items": [], "status": [], "time": "NEVER"}


def render_panel() -> str:
    return "\n".join([
        "FIBS CTI/RSS FEED READER",
        "",
        "1  List configured feeds",
        "2  Fetch / refresh feeds",
        "3  Show cached headlines",
        "4  Add feed                 RSS ADD <name> <url>",
        "5  Delete feed              RSS DELETE <name>",
        "6  Export report            RSS EXPORT <dataset>",
        "7  Edit/display feed dataset",
        "8  Last run status",
        "O  Open cached item          disabled unless enabled",
        "E  Email cached item         disabled unless configured",
        "X  Exit",
        "",
        "COMMAND ===>",
    ])


def render_feeds(state: Any, userid: str = "IBMUSER") -> str:
    feeds = list_feeds(state, userid)
    lines = ["CTI RSS / FIBS CTI-RSS CONFIGURED FEEDS", "", "FEED NAME                        TITLE                         URL"]
    for f in feeds:
        lines.append(f"{f['name']:<32} {f['title'][:28]:<28} {f['url']}")
    return "\n".join(lines) if len(lines) > 3 else "NO RSS FEEDS CONFIGURED"


def render_headlines(state: Any, userid: str = "IBMUSER", feed_filter: str = "") -> str:
    cache = load_cache(state, userid)
    items = cache.get("items") or []
    filt = _norm_name(feed_filter) if feed_filter else ""
    lines = ["FIBS CTI/RSS HEADLINES", f"LAST FETCH: {cache.get('time','NEVER')}", "", "NO  FEED                 PUBLISHED              TITLE"]
    idx = 0
    for it in items:
        feed = _norm_name(it.get("feed", ""))
        if filt and feed != filt:
            continue
        idx += 1
        lines.append(f"{idx:02d}  {feed[:20]:<20} {str(it.get('published',''))[:20]:<20} {str(it.get('title',''))[:96]}")
        if it.get("link"):
            lines.append(f"    LINK: {str(it.get('link'))[:110]}")
    return "\n".join(lines) if idx else "RSS HEADLINES - NO CACHE. RUN RSS FETCH FIRST."


def render_status(state: Any, userid: str = "IBMUSER") -> str:
    cache = load_cache(state, userid)
    lines = ["FIBS CTI/RSS LAST RUN STATUS", f"LAST RUN: {cache.get('time','NEVER')}", "", "FEED NAME                        STATUS  ITEMS ERROR"]
    for s in cache.get("status") or []:
        lines.append(f"{s.get('name','')[:32]:<32} {s.get('status',''):<7} {s.get('items',0):>5} {str(s.get('error',''))[:60]}")
    return "\n".join(lines) if len(lines) > 4 else "RSS LAST RUN STATUS: NEVER"


def rss_command(state: Any, userid: str, command: str) -> str:
    ensure_rss_datasets(state, userid)
    cmd = (command or "RSS").strip()
    upper = cmd.upper()
    if upper in {"RSS", "RSS HELP", "RSS ?", "RSS MENU"}:
        return render_panel()
    if upper in {"RSS LIST", "RSS FEEDS"}:
        return render_feeds(state, userid)
    if upper.startswith("RSS ADD "):
        parts = cmd.split(None, 3)
        if len(parts) < 4:
            return "RSS001E USAGE: RSS ADD <name> <url>"
        name, url = _norm_name(parts[2]), parts[3].strip()
        if not _valid_url(url):
            return "RSS002E URL REJECTED - ONLY HTTP/HTTPS FEEDS ARE ALLOWED"
        feeds = [f for f in list_feeds(state, userid) if f["name"] != name]
        feeds.append({"name": name, "url": url, "title": name})
        save_feeds(state, feeds, userid)
        return f"RSS003I FEED {name} ADDED TO {FEEDS_DSN}"
    if upper.startswith("RSS DELETE "):
        parts = cmd.split(None, 2)
        if len(parts) < 3:
            return "RSS004E USAGE: RSS DELETE <name>"
        name = _norm_name(parts[2])
        feeds = list_feeds(state, userid)
        kept = [f for f in feeds if f["name"] != name]
        save_feeds(state, kept, userid)
        return f"RSS004I FEED {name} DELETED COUNT({len(feeds) - len(kept)})"
    if upper in {"RSS CONFIG", "RSS DATASET", "RSS EDIT"}:
        return f"RSS CONFIG DATA SET {FEEDS_DSN}\n" + state.datasets.read(userid, FEEDS_DSN).rstrip()
    if upper.startswith("RSS FETCH") or upper.startswith("RSS REFRESH"):
        items, statuses = fetch_all(state, userid)
        errors = sum(1 for s in statuses if s.status != "OK")
        return "\n".join([
            "RSS005I REFRESH COMPLETE",
            f"FEEDS({len(statuses)}) ITEMS({len(items)}) ERRORS({errors})",
            f"CACHE({CACHE_DSN}) LASTRUN({LASTRUN_DSN})",
            "",
            render_status(state, userid),
        ])
    if upper.startswith("RSS SHOW") or upper.startswith("RSS HEADLINES"):
        parts = cmd.split(None, 2)
        return render_headlines(state, userid, parts[2] if len(parts) > 2 else "")
    if upper.startswith("RSS STATUS") or upper == "RSS LASTRUN":
        return render_status(state, userid)
    if upper.startswith("RSS EXPORT"):
        parts = cmd.split(None, 2)
        dsn = parts[2].strip().upper() if len(parts) > 2 else REPORT_DSN
        report = render_headlines(state, userid)
        try:
            state.datasets.allocate(userid, dsn, org="PS", recfm="VB", lrecl=1024)
        except Exception:
            pass
        state.datasets.write(userid, dsn, report + "\n")
        return f"RSS006I RSS REPORT EXPORTED TO {dsn}"
    if upper.startswith("RSS OPEN"):
        if os.getenv("GIBSON_RSS_ENABLE_OPEN", "").upper() not in {"1", "Y", "YES", "TRUE"}:
            return "RSS007E OPEN-LINK DISABLED BY DEFAULT. SET GIBSON_RSS_ENABLE_OPEN=YES TO ENABLE."
        return "RSS008I OPEN-LINK REQUEST ACCEPTED BY CONFIGURATION"
    if upper.startswith("RSS EMAIL"):
        if os.getenv("GIBSON_RSS_ENABLE_EMAIL", "").upper() not in {"1", "Y", "YES", "TRUE"}:
            return "RSS009E EMAIL DISABLED BY DEFAULT. SET GIBSON_RSS_ENABLE_EMAIL=YES AND CONFIGURE SMTP."
        return "RSS010I EMAIL REQUEST ACCEPTED BY CONFIGURATION"
    return render_panel()

# Backward-compatible helper used by v26 operations dataset seeding.
def _ensure_dataset(state, userid: str = 'IBMUSER') -> None:
    ensure_rss_datasets(state, userid)


# ---------------------------------------------------------------------------
# Full CTI-RSS client integration: live fetch on explicit RSS FETCH LIVE,
# XML fallback when feedparser is absent, and rss.json compatible datasets.
# ---------------------------------------------------------------------------
def _parse_feed_xml_fallback(content: bytes, feed_name: str) -> list[RssItem]:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(content)
    except Exception:
        return []
    def strip(tag: str) -> str:
        return tag.rsplit('}', 1)[-1].lower()
    items: list[RssItem] = []
    # RSS item elements
    for node in root.iter():
        if strip(node.tag) not in {'item', 'entry'}:
            continue
        vals: dict[str, str] = {}
        for child in list(node):
            name = strip(child.tag)
            if name == 'link':
                vals['link'] = child.attrib.get('href') or (child.text or '')
            elif name in {'title', 'published', 'updated', 'pubdate', 'summary', 'description'}:
                vals[name] = child.text or ''
        items.append(RssItem(feed_name, _clean(vals.get('title') or '(no title)'),
                             str(vals.get('link') or '')[:240],
                             _clean(vals.get('published') or vals.get('updated') or vals.get('pubdate') or '', 80),
                             _clean(vals.get('summary') or vals.get('description') or '', 220)))
        if len(items) >= MAX_ITEMS:
            break
    return items

# Preserve original names for tests that monkeypatch them.
_RSS_ORIG_FETCH_FEED = fetch_feed

def _load_uploaded_rss_json() -> list[dict[str, str]]:
    for candidate in ('/mnt/data/rss.json', 'assets/rss.json', 'rss.json'):
        try:
            with open(candidate, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            out = []
            for f in data.get('feeds') or []:
                if _valid_url(f.get('url', '')):
                    out.append({'name': _norm_name(f.get('name') or f.get('url')),
                                'url': f.get('url'),
                                'title': _display_name(f.get('name') or f.get('url'))})
            if out:
                return out
        except Exception:
            pass
    return [{'name': _norm_name(f['name']), 'url': f['url'], 'title': _display_name(f['name'])} for f in DEFAULT_FEEDS]

def ensure_rss_datasets(state: Any, userid: str = 'IBMUSER') -> None:  # type: ignore[override]
    try:
        current = state.datasets.read(userid, FEEDS_DSN)
    except Exception:
        current = ''
    if not current.strip():
        lines = [f"{f['name']}|{f['url']}|{f['title']}" for f in _load_uploaded_rss_json()]
        _alloc(state, userid, FEEDS_DSN, '\n'.join(lines) + '\n')
    for dsn in (CACHE_DSN, LASTRUN_DSN, REPORT_DSN):
        try: state.datasets.read(userid, dsn)
        except Exception: _alloc(state, userid, dsn, '')

def fetch_feed(url: str, feed_name: str, fetcher: Any = None) -> tuple[list[RssItem], str]:  # type: ignore[override]
    if not _valid_url(url):
        return [], 'INVALID-URL'
    try:
        if fetcher is not None:
            content = fetcher(url)
            if isinstance(content, str): content = content.encode('utf-8')
        else:
            try:
                import httpx  # type: ignore
            except Exception as exc:
                return [], 'DEPENDENCY-MISSING: httpx: ' + str(exc)
            with httpx.Client(timeout=FETCH_TIMEOUT,
                              headers={'User-Agent':'Gibson-FIBS-RSS/3.0'},
                              follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                content = response.content
        try:
            import feedparser  # type: ignore
            parsed = feedparser.parse(content)
            out: list[RssItem] = []
            for entry in getattr(parsed, 'entries', [])[:MAX_ITEMS]:
                out.append(RssItem(feed_name, _clean(getattr(entry, 'title', '(no title)'), 180),
                                   str(getattr(entry, 'link', ''))[:240],
                                   _clean(getattr(entry, 'published', getattr(entry, 'updated', '')), 80),
                                   _clean(getattr(entry, 'summary', ''), 220)))
            if out:
                return out, 'OK'
        except Exception:
            pass
        out = _parse_feed_xml_fallback(content, feed_name)
        return out, 'OK' if out else 'NO-ITEMS'
    except Exception as exc:
        return [], f'{type(exc).__name__}: {_clean(exc, 80)}'

def fetch_all(state: Any, userid: str = 'IBMUSER', fetcher: Any = None,
              live: bool | None = None) -> tuple[list[RssItem], list[FeedStatus]]:  # type: ignore[override]
    feeds = list_feeds(state, userid)
    items: list[RssItem] = []
    status: list[FeedStatus] = []
    if live is None:
        live = fetcher is not None or os.getenv('GIBSON_RSS_LIVE_FETCH','YES').upper() not in {'0','N','NO','FALSE'}
    for feed in feeds:
        if live:
            feed_items, stat = fetch_feed(feed['url'], feed['name'], fetcher)
        else:
            feed_items, stat = [], 'OFFLINE-NO-FETCH'
        items.extend(feed_items)
        status.append(FeedStatus(feed['name'], feed['url'], 'OK' if stat == 'OK' else ('OFFLINE' if stat.startswith('OFFLINE') else 'ERROR'), len(feed_items), '' if stat == 'OK' else stat))
    cache = {'time': _now(), 'items': [asdict(i) for i in items[:500]], 'status': [asdict(s) for s in status], 'live': bool(live)}
    state.datasets.write(userid, CACHE_DSN, json.dumps(cache, indent=2))
    state.datasets.write(userid, LASTRUN_DSN, cache['time'] + '\n')
    return items, status

def render_panel() -> str:  # type: ignore[override]
    return '\n'.join(['FIBS CTI/RSS FEED READER','',
        '1  List configured feeds','2  Fetch all feeds live','3  Show cached headlines',
        '4  Show feed                 RSS SHOW <feed>','5  Add feed                  RSS ADD <name> <url>',
        '6  Delete feed               RSS DELETE <name>','7  Export report             RSS EXPORT <dataset>',
        '8  Edit/display feed dataset','9  Last run status',
        'O  Open link status          disabled unless enabled','E  Email status              disabled unless configured','X  Exit','',
        'COMMAND ===>'])

def rss_command(state: Any, userid: str, command: str) -> str:  # type: ignore[override]
    ensure_rss_datasets(state, userid)
    cmd = (command or 'RSS').strip()
    upper = cmd.upper()
    if upper in {'RSS','RSS HELP','RSS ?','RSS MENU'}: return render_panel()
    if upper in {'RSS LIST','RSS FEEDS'}: return render_feeds(state, userid)
    if upper.startswith('RSS ADD '):
        parts=cmd.split(None,3)
        if len(parts)<4: return 'RSS001E USAGE: RSS ADD <name> <url>'
        name,url=_norm_name(parts[2]),parts[3].strip()
        if not _valid_url(url): return 'RSS002E URL REJECTED - ONLY HTTP/HTTPS FEEDS ARE ALLOWED'
        feeds=[f for f in list_feeds(state,userid) if f['name'] != name]
        feeds.append({'name':name,'url':url,'title':name})
        save_feeds(state,feeds,userid)
        return f'RSS003I FEED {name} ADDED TO {FEEDS_DSN}'
    if upper.startswith('RSS DELETE '):
        name=_norm_name(cmd.split(None,2)[2] if len(cmd.split(None,2))>=3 else '')
        feeds=list_feeds(state,userid); kept=[f for f in feeds if f['name'] != name]
        save_feeds(state,kept,userid)
        return f'RSS004I FEED {name} DELETED COUNT({len(feeds)-len(kept)})'
    if upper in {'RSS CONFIG','RSS DATASET','RSS EDIT'}:
        return f'RSS CONFIG DATA SET {FEEDS_DSN}\n' + state.datasets.read(userid, FEEDS_DSN).rstrip()
    if upper.startswith('RSS FETCH') or upper.startswith('RSS REFRESH'):
        live = ' LIVE' in (' ' + upper) or upper.endswith(' LIVE') or upper == 'RSS FETCH LIVE'
        items, statuses = fetch_all(state, userid, live=live)
        errors=sum(1 for s in statuses if s.status == 'ERROR')
        return '\n'.join(['RSS005I REFRESH COMPLETE' if live else 'RSS005I REFRESH COMPLETE',
            f'FEEDS({len(statuses)}) ITEMS({len(items)}) ERRORS({errors}) LIVE({"YES" if live else "NO"})',
            f'CACHE({CACHE_DSN}) LASTRUN({LASTRUN_DSN})','',render_status(state,userid)])
    if upper.startswith('RSS SHOW') or upper.startswith('RSS HEADLINES'):
        parts=cmd.split(None,2); return render_headlines(state,userid,parts[2] if len(parts)>2 else '')
    if upper.startswith('RSS STATUS') or upper == 'RSS LASTRUN': return render_status(state,userid)
    if upper.startswith('RSS EXPORT'):
        parts=cmd.split(None,2); dsn=parts[2].strip().upper() if len(parts)>2 else REPORT_DSN
        report=render_headlines(state,userid)
        try: state.datasets.allocate(userid,dsn,org='PS',recfm='VB',lrecl=1024)
        except Exception: pass
        state.datasets.write(userid,dsn,report+'\n')
        return f'RSS006I RSS REPORT EXPORTED TO {dsn}'
    if upper.startswith('RSS OPEN'):
        if os.getenv('GIBSON_RSS_ENABLE_OPEN','').upper() not in {'1','Y','YES','TRUE'}:
            return 'RSS007E OPEN-LINK DISABLED BY DEFAULT. SET GIBSON_RSS_ENABLE_OPEN=YES TO ENABLE.'
        return 'RSS008I OPEN-LINK REQUEST ACCEPTED BY CONFIGURATION'
    if upper.startswith('RSS EMAIL'):
        if os.getenv('GIBSON_RSS_ENABLE_EMAIL','').upper() not in {'1','Y','YES','TRUE'}:
            return 'RSS009E EMAIL DISABLED BY DEFAULT. SET GIBSON_RSS_ENABLE_EMAIL=YES AND CONFIGURE SMTP.'
        return 'RSS010I EMAIL REQUEST ACCEPTED BY CONFIGURATION'
    return render_panel()

# Compatibility: always render the headline panel header, even when the cache is empty.
_RSS_RENDER_HEADLINES_PREV = render_headlines

def render_headlines(state: Any, userid: str = 'IBMUSER', feed_filter: str = '') -> str:  # type: ignore[override]
    cache = load_cache(state, userid)
    items = cache.get('items') or []
    filt = _norm_name(feed_filter) if feed_filter else ''
    lines = ['FIBS CTI/RSS HEADLINES', f"LAST FETCH: {cache.get('time','NEVER')}", '', 'NO  FEED                 PUBLISHED              TITLE']
    idx = 0
    for it in items:
        feed = _norm_name(it.get('feed', ''))
        if filt and feed != filt:
            continue
        idx += 1
        lines.append(f"{idx:02d}  {feed[:20]:<20} {str(it.get('published',''))[:20]:<20} {str(it.get('title',''))[:96]}")
        if it.get('link'):
            lines.append(f"    LINK: {str(it.get('link'))[:110]}")
    if idx == 0:
        lines.append('NO CACHED ITEMS. RUN RSS FETCH LIVE TO RETRIEVE FEEDS OR RSS FETCH FOR STATUS ONLY.')
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# Golden baseline OMVS CTI-RSS implementation.
# Uses rss.json as feed authority, performs live bounded fetches by default for
# explicit --fetch/FETCH, supports JSON output, and has urllib/XML fallback.
# ---------------------------------------------------------------------------
from pathlib import Path as _Path
from urllib.request import Request as _Request, urlopen as _urlopen
from urllib.error import URLError as _URLError, HTTPError as _HTTPError
import ssl as _ssl
import shlex as _shlex

_DEFAULT_RSS_JSON_PATHS = [
    _Path(__file__).resolve().parents[1] / 'assets' / 'cti' / 'rss.json',
    _Path.cwd() / 'rss.json',
]


def _rss_json_feeds(path: str = '') -> list[dict[str, str]]:
    candidates = [_Path(path)] if path else list(_DEFAULT_RSS_JSON_PATHS)
    for candidate in candidates:
        try:
            data = json.loads(candidate.read_text(encoding='utf-8'))
            out: list[dict[str, str]] = []
            for f in data.get('feeds') or []:
                name = _display_name(f.get('name') or f.get('url') or 'Feed')
                url = str(f.get('url') or '').strip()
                if _valid_url(url):
                    out.append({'name': _norm_name(name), 'title': name, 'url': url})
            if out:
                return out
        except Exception:
            continue
    return [{'name': _norm_name(f['name']), 'title': _display_name(f['name']), 'url': f['url']} for f in DEFAULT_FEEDS]


def ensure_rss_datasets(state: Any, userid: str = 'IBMUSER') -> None:  # type: ignore[override]
    try:
        current = state.datasets.read(userid, FEEDS_DSN)
    except Exception:
        current = ''
    if not current.strip():
        feeds = _rss_json_feeds()
        _alloc(state, userid, FEEDS_DSN, '\n'.join(f"{f['name']}|{f['url']}|{f['title']}" for f in feeds) + '\n')
    for dsn in (CACHE_DSN, LASTRUN_DSN, REPORT_DSN):
        try:
            state.datasets.read(userid, dsn)
        except Exception:
            _alloc(state, userid, dsn, '')


def _fetch_bytes_urllib(url: str, timeout: int = FETCH_TIMEOUT) -> tuple[bytes, str]:
    try:
        req = _Request(url, headers={'User-Agent': 'Gibson-CTI-RSS/4.0'})
        with _urlopen(req, timeout=max(1, min(int(timeout), 30)), context=_ssl.create_default_context()) as r:  # nosec - http/https validated
            data = r.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            return data[:1024 * 1024], 'TRUNCATED'
        return data, 'OK'
    except _HTTPError as exc:
        return b'', f'HTTP {exc.code}: {exc.reason}'
    except _URLError as exc:
        return b'', str(exc.reason)
    except Exception as exc:
        return b'', f'{type(exc).__name__}: {_clean(exc, 80)}'


def fetch_feed(url: str, feed_name: str, fetcher: Any = None) -> tuple[list[RssItem], str]:  # type: ignore[override]
    if not _valid_url(url):
        return [], 'INVALID-URL'
    try:
        if fetcher is not None:
            content = fetcher(url)
            if isinstance(content, str):
                content = content.encode('utf-8')
            stat = 'OK'
        else:
            # Prefer httpx when present, but never require it for OMVS.
            try:
                import httpx  # type: ignore
                with httpx.Client(timeout=FETCH_TIMEOUT, headers={'User-Agent': 'Gibson-CTI-RSS/4.0'}, follow_redirects=True) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    content = response.content
                    stat = 'OK'
            except ModuleNotFoundError:
                content, stat = _fetch_bytes_urllib(url)
            except Exception:
                content, stat = _fetch_bytes_urllib(url)
        if stat not in {'OK', 'TRUNCATED'}:
            return [], stat
        try:
            import feedparser  # type: ignore
            parsed = feedparser.parse(content)
            out: list[RssItem] = []
            for entry in getattr(parsed, 'entries', [])[:MAX_ITEMS]:
                out.append(RssItem(feed_name,
                                   _clean(getattr(entry, 'title', '(no title)'), 180),
                                   str(getattr(entry, 'link', ''))[:240],
                                   _clean(getattr(entry, 'published', getattr(entry, 'updated', '')), 80),
                                   _clean(getattr(entry, 'summary', ''), 220)))
            if out:
                return out, 'OK'
        except Exception:
            pass
        out = _parse_feed_xml_fallback(content, feed_name)
        return out, 'OK' if out else 'NO-ITEMS'
    except Exception as exc:
        return [], f'{type(exc).__name__}: {_clean(exc, 80)}'


def fetch_all(state: Any, userid: str = 'IBMUSER', fetcher: Any = None, live: bool | None = None) -> tuple[list[RssItem], list[FeedStatus]]:  # type: ignore[override]
    feeds = list_feeds(state, userid)
    live = True if live is None else bool(live)
    items: list[RssItem] = []
    status: list[FeedStatus] = []
    for feed in feeds:
        if live:
            feed_items, stat = fetch_feed(feed['url'], feed['name'], fetcher)
        else:
            feed_items, stat = [], 'NOT-FETCHED'
        items.extend(feed_items)
        status.append(FeedStatus(feed['name'], feed['url'], 'OK' if stat == 'OK' else 'ERROR', len(feed_items), '' if stat == 'OK' else stat))
    cache = {'time': _now(), 'items': [asdict(i) for i in items[:500]], 'status': [asdict(s) for s in status], 'live': live}
    state.datasets.write(userid, CACHE_DSN, json.dumps(cache, indent=2))
    state.datasets.write(userid, LASTRUN_DSN, cache['time'] + '\n')
    return items, status


def _render_items(items: list[dict[str, Any]] | list[RssItem], *, limit: int = 10) -> str:
    lines = ['CTI RSS HEADLINES', '', 'NO  FEED                 PUBLISHED              TITLE']
    for idx, raw in enumerate(items[:limit], 1):
        it = asdict(raw) if isinstance(raw, RssItem) else raw
        feed = _norm_name(it.get('feed', ''))[:20]
        title = str(it.get('title', ''))[:96]
        pub = str(it.get('published', ''))[:20]
        lines.append(f'{idx:02d}  {feed:<20} {pub:<20} {title}')
        if it.get('link'):
            lines.append(f"    LINK: {str(it.get('link'))[:110]}")
    if len(lines) == 3:
        lines.append('NO ITEMS RETURNED. SEE RSS STATUS FOR PER-FEED ERRORS.')
    return '\n'.join(lines)


def _parse_cli_options(tokens: list[str]) -> dict[str, Any]:
    opts: dict[str, Any] = {'limit': 10, 'json': False, 'rss_file': '', 'feed': '', 'action': ''}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        u = t.upper()
        if u in {'FETCH', 'REFRESH', '--FETCH'}:
            opts['action'] = 'fetch'
        elif u in {'LIST', 'FEEDS', '--LIST-FEEDS'}:
            opts['action'] = 'list'
        elif u in {'SHOW', 'HEADLINES'}:
            opts['action'] = 'show'
        elif t == '--json':
            opts['json'] = True
        elif t in {'--limit', '-n'} and i + 1 < len(tokens):
            i += 1
            try: opts['limit'] = max(1, min(50, int(tokens[i])))
            except Exception: opts['limit'] = 10
        elif t.startswith('--limit='):
            try: opts['limit'] = max(1, min(50, int(t.split('=',1)[1])))
            except Exception: opts['limit'] = 10
        elif t == '--feed' and i + 1 < len(tokens):
            i += 1; opts['feed'] = tokens[i]; opts['action'] = opts['action'] or 'fetch'
        elif t.startswith('--feed='):
            opts['feed'] = t.split('=',1)[1]; opts['action'] = opts['action'] or 'fetch'
        elif t == '--rss-file' and i + 1 < len(tokens):
            i += 1; opts['rss_file'] = tokens[i]
        elif t.startswith('--rss-file='):
            opts['rss_file'] = t.split('=',1)[1]
        i += 1
    return opts


def rss_command(state: Any, userid: str, command: str) -> str:  # type: ignore[override]
    ensure_rss_datasets(state, userid)
    try:
        tokens = _shlex.split((command or 'RSS').strip())
    except Exception as exc:
        return f'RSS000E SYNTAX ERROR: {exc}'
    if tokens and tokens[0].lower() in {'rss', 'cti-rss'}:
        tokens = tokens[1:]
    upper = ' '.join(tokens).upper()
    if not tokens or upper in {'HELP', '?', 'MENU'}:
        return '\n'.join(['CTI RSS READER', '', 'rss --list-feeds', 'rss --fetch [--limit N] [--feed NAME] [--json]', 'cti-rss --feed "KrebsOnSecurity" --limit 5', 'rss show', 'rss status', 'rss export <dataset>', '', f'Default feed dataset: {FEEDS_DSN}', 'Feeds sourced from packaged rss.json'])
    if tokens[0].upper() == 'ADD':
        if len(tokens) < 3: return 'RSS001E USAGE: RSS ADD <name> <url>'
        name,url=_norm_name(tokens[1]),tokens[2]
        if not _valid_url(url): return 'RSS002E URL REJECTED - ONLY HTTP/HTTPS FEEDS ARE ALLOWED'
        feeds=[f for f in list_feeds(state,userid) if f['name'] != name]
        feeds.append({'name':name,'url':url,'title':name})
        save_feeds(state,feeds,userid); return f'RSS003I FEED {name} ADDED TO {FEEDS_DSN}'
    if tokens[0].upper() == 'DELETE':
        name=_norm_name(tokens[1]) if len(tokens)>1 else ''
        feeds=list_feeds(state,userid); kept=[f for f in feeds if f['name'] != name]
        save_feeds(state,kept,userid); return f'RSS004I FEED {name} DELETED COUNT({len(feeds)-len(kept)})'
    if tokens[0].upper() in {'STATUS','LASTRUN'}:
        return render_status(state, userid)
    if tokens[0].upper() == 'EXPORT':
        dsn = tokens[1].upper() if len(tokens)>1 else REPORT_DSN
        report = render_headlines(state, userid)
        try: state.datasets.allocate(userid, dsn, org='PS', recfm='VB', lrecl=1024)
        except Exception: pass
        state.datasets.write(userid, dsn, report + '\n')
        return f'RSS006I RSS REPORT EXPORTED TO {dsn}'
    opts = _parse_cli_options(tokens)
    if opts.get('rss_file'):
        feeds = _rss_json_feeds(str(opts['rss_file']))
        save_feeds(state, feeds, userid)
    if opts['action'] == 'list':
        feeds = list_feeds(state, userid)
        if opts['json']:
            return json.dumps({'feeds': feeds}, indent=2)
        return render_feeds(state, userid).replace('FIBS CTI/RSS', 'CTI RSS')
    if opts['action'] == 'show':
        return render_headlines(state, userid, str(opts.get('feed') or ''))
    if opts['action'] == 'fetch' or tokens[0].upper() in {'FETCH','REFRESH'} or any(t.startswith('--') for t in tokens):
        items, statuses = fetch_all(state, userid, live=True)
        feed_filter = _norm_name(str(opts.get('feed') or ''))
        item_dicts = [asdict(i) for i in items]
        if feed_filter:
            item_dicts = [i for i in item_dicts if _norm_name(i.get('feed','')) == feed_filter or feed_filter in _norm_name(i.get('feed',''))]
        lim = int(opts.get('limit') or 10)
        if opts['json']:
            return json.dumps({'generated_at': _now(), 'items': item_dicts[:lim], 'status': [asdict(s) for s in statuses]}, indent=2)
        errors = sum(1 for s in statuses if s.status != 'OK')
        return '\n'.join(['RSS005I LIVE REFRESH COMPLETE', f'FEEDS({len(statuses)}) ITEMS({len(items)}) ERRORS({errors})', '', _render_items(item_dicts, limit=lim), '', render_status(state, userid)])
    return render_panel().replace('FIBS CTI/RSS', 'CTI RSS')

# ---------------------------------------------------------------------------
# Article opening / Lynx-like rendering integration.  This final override keeps
# existing RSS behaviour but makes RSS OPEN/READ fetch and render article URLs.
# ---------------------------------------------------------------------------
_RSS_COMMAND_BEFORE_ARTICLE = rss_command

def _cached_items(state: Any, userid: str) -> list[dict[str, Any]]:
    cache = load_cache(state, userid)
    return list(cache.get('items') or [])

def _select_cached_item(state: Any, userid: str, args: list[str]) -> dict[str, Any] | None:
    items = _cached_items(state, userid)
    if not items:
        return None
    if not args:
        return items[0]
    # rss --open 3 / rss --open FEED 2
    if len(args) == 1:
        try:
            idx = int(args[0]) - 1
            return items[idx] if 0 <= idx < len(items) else None
        except Exception:
            wanted = _norm_name(args[0])
            for it in items:
                if _norm_name(it.get('feed','')) == wanted:
                    return it
            return None
    wanted = _norm_name(args[0])
    try: ordinal = int(args[1])
    except Exception: ordinal = 1
    matches = [it for it in items if _norm_name(it.get('feed','')) == wanted or wanted in _norm_name(it.get('feed',''))]
    return matches[ordinal - 1] if 0 < ordinal <= len(matches) else None

def render_article_lines(state: Any, userid: str, num: Any, width: int = 78) -> list[str]:
    """Clean, ISPF-ready article render for the scrollable RSS reader: no ANSI,
    no line-mode pager, EBCDIC-safe, word-wrapped.  Returns a list of lines for
    a ScrollList (PF7/PF8 paging).  This is the panel path; the line-mode
    ``_open_item`` below is kept for the TSO ``rss --open`` command."""
    item = _select_cached_item(state, userid, [str(num)])
    if not item:
        return ["RSS011E ITEM NOT FOUND.  REFRESH THE FEED LIST (PF6) FIRST."]
    link = str(item.get("link") or "")
    header = [
        "CTI RSS ARTICLE VIEW",
        f"FEED : {item.get('feed','')}",
        f"TITLE: {item.get('title','')}",
        f"URL  : {link}",
        "-" * width,
        "",
    ]
    if not _valid_url(link):
        return header + ["(this item has no safe http/https link to open)"]
    try:
        from gibson.tools.html_text_browser import fetch_url, render_html, clean_render_lines
        page = render_html(fetch_url(link, state=state), link)
        body = clean_render_lines(page.text, width=width)
    except Exception as exc:
        return header + [f"RSS013E ARTICLE FETCH/RENDER FAILED - "
                         f"{type(exc).__name__}: {_clean(exc, 110)}"]
    # Cache the clean article for repeat viewing/export.
    try:
        state.datasets.allocate(userid, "FIBS.CTI.RSS.ARTICLE", org="PS", recfm="VB", lrecl=1024)
        state.datasets.write(userid, "FIBS.CTI.RSS.ARTICLE", "\n".join(header + body) + "\n")
    except Exception:
        pass
    return header + body


def _open_item(state: Any, userid: str, args: list[str]) -> str:
    item = _select_cached_item(state, userid, args)
    if not item:
        return 'RSS011E ITEM NOT FOUND. RUN RSS --fetch --limit 10 FIRST.'
    link = str(item.get('link') or '')
    if not _valid_url(link):
        return 'RSS012E ITEM HAS NO SAFE HTTP/HTTPS LINK'
    try:
        from gibson.tools.html_text_browser import fetch_url, render_html
        from gibson.tools.terminal_pager import page_text
        page = render_html(fetch_url(link), link)
        rendered = '\n'.join([
            'CTI RSS ARTICLE VIEW',
            f"FEED : {item.get('feed','')}",
            f"TITLE: {item.get('title','')}",
            f"URL  : {link}",
            '-'*72,
            page.text,
        ])
        # Cache rendered article in a dataset for repeat viewing/export.
        try:
            state.datasets.allocate(userid, 'FIBS.CTI.RSS.ARTICLE', org='PS', recfm='VB', lrecl=1024)
        except Exception:
            pass
        try: state.datasets.write(userid, 'FIBS.CTI.RSS.ARTICLE', rendered + '\n')
        except Exception: pass
        return page_text(rendered, page_size=22)
    except Exception as exc:
        return f'RSS013E ARTICLE FETCH/RENDER FAILED - {type(exc).__name__}: {_clean(exc, 120)}'

def rss_command(state: Any, userid: str, command: str) -> str:  # type: ignore[override]
    try:
        tokens = _shlex.split((command or 'RSS').strip())
    except Exception as exc:
        return f'RSS000E SYNTAX ERROR: {exc}'
    if tokens and tokens[0].lower() in {'rss', 'cti-rss'}:
        tokens = tokens[1:]
    if tokens and tokens[0].upper() in {'OPEN','READ','--OPEN','--READ'}:
        return _open_item(state, userid, tokens[1:])
    out = _RSS_COMMAND_BEFORE_ARTICLE(state, userid, command)
    if 'rss --fetch' in out and 'rss --open' not in out:
        out += '\n  rss --open <number>        open cached article in scrollable viewer'
    return out


# ---------------------------------------------------------------------------
# RSS/CTI-RSS v1 final override: external fetch is enabled by default for RSS
# commands, latest five stories are grouped per feed, and OPEN/LYNX renders the
# selected article through the Gibson native Lynx renderer.
# ---------------------------------------------------------------------------
def _items_grouped_by_feed(state: Any, userid: str) -> dict[str, list[dict[str, Any]]]:
    cache = load_cache(state, userid)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for it in cache.get('items') or []:
        grouped.setdefault(_norm_name(it.get('feed','FEED')), []).append(it)
    return grouped

def _render_latest_five_by_feed(state: Any, userid: str, *, feed_filter: str = '') -> str:
    grouped = _items_grouped_by_feed(state, userid)
    filt = _norm_name(feed_filter) if feed_filter else ''
    cache = load_cache(state, userid)
    lines = ['CTI/RSS LATEST FIVE STORIES PER FEED', f"LAST FETCH: {cache.get('time','NEVER')}", '', 'Use RSS LYNX <feed-number> <item-number> or CTI-RSS --LYNX <feed-number> <item-number> to read a story.', '']
    feeds = list_feeds(state, userid)
    any_items = False
    for fidx, feed in enumerate(feeds, 1):
        name = feed['name']
        if filt and filt not in {name, _norm_name(feed.get('title',''))}:
            continue
        items = grouped.get(name, [])[:5]
        lines.append(f'[{fidx}] {feed.get("title", name)} ({name})')
        if not items:
            lines.append('    No cached stories for this feed.')
        for iidx, it in enumerate(items, 1):
            any_items = True
            lines.append(f"    {iidx}. {str(it.get('title',''))[:100]}")
            if it.get('published'):
                lines.append(f"       Date: {str(it.get('published'))[:80]}")
            if it.get('summary'):
                lines.append(f"       {str(it.get('summary'))[:160]}")
            lines.append(f"       Link: {str(it.get('link',''))[:180]}")
        lines.append('')
    if not any_items:
        lines.append('No stories are cached. Run RSS REFRESH or CTI-RSS --REFRESH.')
    return '\n'.join(lines).rstrip()

def _select_feed_item_by_numbers(state: Any, userid: str, feed_no: int, item_no: int) -> dict[str, Any] | None:
    feeds = list_feeds(state, userid)
    if feed_no < 1 or feed_no > len(feeds):
        return None
    name = feeds[feed_no - 1]['name']
    items = _items_grouped_by_feed(state, userid).get(name, [])[:5]
    return items[item_no - 1] if 0 < item_no <= len(items) else None

def _open_feed_number_item(state: Any, userid: str, args: list[str]) -> str:
    if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
        item = _select_feed_item_by_numbers(state, userid, int(args[0]), int(args[1]))
    else:
        item = _select_cached_item(state, userid, args)
    if not item:
        return 'RSS011E ITEM NOT FOUND. RUN RSS REFRESH FIRST.'
    link = str(item.get('link') or '')
    if not _valid_url(link):
        return 'RSS012E ITEM HAS NO HTTP/HTTPS LINK'
    try:
        from gibson.tools.html_text_browser import fetch_url, render_html
        from gibson.tools.terminal_pager import page_text
        try:
            from gibson.tools.security_events import emit_omvs_tool_event
            emit_omvs_tool_event(state=state, user=userid, tool='RSS', script='LYNX_OPEN', target=link, result='OK', severity='LOW', details={'title': item.get('title',''), 'feed': item.get('feed','')}, command_line='RSS LYNX ' + link)
        except Exception:
            pass
        page = render_html(fetch_url(link), link)
        rendered = '\n'.join(['CTI RSS ARTICLE VIEW', 'GIBSON LYNX - RSS ARTICLE', f"FEED : {item.get('feed','')}", f"TITLE: {item.get('title','')}", f"URL  : {link}", '-'*72, page.text])
        try:
            state.datasets.allocate(userid, 'FIBS.CTI.RSS.ARTICLE', org='PS', recfm='VB', lrecl=1024)
        except Exception: pass
        try: state.datasets.write(userid, 'FIBS.CTI.RSS.ARTICLE', rendered + '\n')
        except Exception: pass
        return page_text(rendered, page_size=22)
    except Exception as exc:
        return f'RSS013E ARTICLE FETCH/RENDER FAILED - {type(exc).__name__}: {_clean(exc, 120)}'

def rss_command(state: Any, userid: str, command: str) -> str:  # type: ignore[override]
    ensure_rss_datasets(state, userid)
    try:
        tokens = _shlex.split((command or 'RSS').strip())
    except Exception as exc:
        return f'RSS000E SYNTAX ERROR: {exc}'
    raw0 = tokens[0].lower() if tokens else 'rss'
    if tokens and raw0 in {'rss', 'cti-rss'}:
        tokens = tokens[1:]
    upper = ' '.join(tokens).upper()
    if not tokens or upper in {'LATEST', '--LATEST'}:
        items, statuses = fetch_all(state, userid, live=True)
        try:
            from gibson.tools.security_events import emit_omvs_tool_event
            emit_omvs_tool_event(state=state, user=userid, tool=raw0.upper(), script='REFRESH', target='RSS_FEEDS', result='OK', severity='LOW', details={'feeds': len(statuses), 'items': len(items)}, command_line=raw0)
        except Exception: pass
        return '\n'.join(['RSS005I LIVE REFRESH COMPLETE', f'FEEDS({len(statuses)}) ITEMS({len(items)})', '', _render_latest_five_by_feed(state, userid)])
    if tokens[0].upper() in {'HELP','?','MENU'}:
        return '\n'.join(['CTI/RSS READER', '', 'RSS or CTI-RSS                  fetch and show latest 5 stories per feed', 'RSS REFRESH                      refresh live feeds', 'RSS LIST                         list feeds', 'RSS FEED <name>                  show one feed', 'RSS LYNX <feed-no> <item-no>     open story in Gibson Lynx', 'CTI-RSS --LYNX <feed-no> <item-no>', 'RSS ADD <name> <url>             add feed', 'RSS DELETE <name>                delete feed', 'RSS EXPORT <dataset>             export cached headlines'])
    if tokens[0].upper() in {'OPEN','READ','LYNX','--OPEN','--READ','--LYNX'}:
        return _open_feed_number_item(state, userid, tokens[1:])
    if tokens[0].upper() in {'FEED','--FEED'} and len(tokens) > 1:
        return _render_latest_five_by_feed(state, userid, feed_filter=tokens[1])
    if tokens[0].upper() in {'SHOW','HEADLINES'}:
        return _render_latest_five_by_feed(state, userid, feed_filter=tokens[1] if len(tokens)>1 else '')
    if tokens[0].upper() in {'FETCH','REFRESH','--REFRESH','--FETCH'}:
        items, statuses = fetch_all(state, userid, live=True)
        errors = sum(1 for s in statuses if s.status != 'OK')
        try:
            from gibson.tools.security_events import emit_omvs_tool_event
            emit_omvs_tool_event(state=state, user=userid, tool=raw0.upper(), script='REFRESH', target='RSS_FEEDS', result='OK' if errors == 0 else 'WARNING', severity='LOW', details={'feeds': len(statuses), 'items': len(items), 'errors': errors}, command_line=raw0 + ' REFRESH')
        except Exception: pass
        return '\n'.join(['RSS005I LIVE REFRESH COMPLETE', f'FEEDS({len(statuses)}) ITEMS({len(items)}) ERRORS({errors})', '', _render_latest_five_by_feed(state, userid), '', render_status(state, userid)])
    if tokens[0].upper() in {'LIST','FEEDS','--FEEDS','--LIST-FEEDS'}:
        return render_feeds(state, userid)
    if tokens[0].upper() == 'ADD':
        if len(tokens) < 3: return 'RSS001E USAGE: RSS ADD <name> <url>'
        name, url = _norm_name(tokens[1]), tokens[2]
        if not _valid_url(url): return 'RSS002E URL REJECTED - ONLY HTTP/HTTPS FEEDS ARE ALLOWED'
        feeds=[f for f in list_feeds(state,userid) if f['name'] != name]
        feeds.append({'name':name,'url':url,'title':name})
        save_feeds(state,feeds,userid); return f'RSS003I FEED {name} ADDED TO {FEEDS_DSN}'
    if tokens[0].upper() == 'DELETE':
        name=_norm_name(tokens[1]) if len(tokens)>1 else ''
        feeds=list_feeds(state,userid); kept=[f for f in feeds if f['name'] != name]
        save_feeds(state,kept,userid); return f'RSS004I FEED {name} DELETED COUNT({len(feeds)-len(kept)})'
    if tokens[0].upper() in {'STATUS','LASTRUN'}:
        return render_status(state, userid)
    if tokens[0].upper() == 'EXPORT':
        dsn = tokens[1].upper() if len(tokens)>1 else REPORT_DSN
        report = _render_latest_five_by_feed(state, userid)
        try: state.datasets.allocate(userid, dsn, org='PS', recfm='VB', lrecl=1024)
        except Exception: pass
        state.datasets.write(userid, dsn, report + '\n')
        return f'RSS006I RSS REPORT EXPORTED TO {dsn}'
    return _render_latest_five_by_feed(state, userid)


def _cached_link_by_numbers(state: Any, userid: str, feed_no: int, item_no: int) -> str:
    cache=load_cache(state, userid); grouped={}
    for it in cache.get('items') or []: grouped.setdefault(_norm_name(it.get('feed','')), []).append(it)
    feeds=sorted(grouped)
    if 1 <= feed_no <= len(feeds):
        items=grouped[feeds[feed_no-1]][:MAX_ITEMS]
        if 1 <= item_no <= len(items): return str(items[item_no-1].get('link') or '')
    return ''

class CtiRssSession:
    """Stateful interactive CTI-RSS reader driven one command at a time, so it can
    back BOTH the ASCII reader/writer loop and the EBCDIC 3270 sub-mode from a
    single command grammar.  The heavy lifting stays in the shared module helpers
    (render_headlines / render_feeds / fetch_all), so there is no logic drift."""
    HELP = 'cti-rss> commands: r refresh, o <feed-no> <item-no> open in Lynx, f feeds, q quit\n'

    def __init__(self, state: Any, userid: str = 'IBMUSER'):
        self.state = state
        self.userid = userid

    def prompt(self) -> str:
        return 'cti-rss> '

    def banner(self) -> str:
        """Greeting line + lazy initial fetch (matches the ASCII preamble)."""
        if not (load_cache(self.state, self.userid).get('items') or []):
            fetch_all(self.state, self.userid, live=True)
        return 'FIBS CTI-RSS interactive feed reader\n'

    def preamble(self) -> str:
        """Headlines + the command help line, shown before every prompt."""
        return render_headlines(self.state, self.userid) + '\n' + self.HELP

    def step(self, line: str):
        """EBCDIC turn handler: command output followed by the next preamble,
        or None to quit.  `o` shows the article inline (the EBCDIC counterpart of
        the ASCII path's nested interactive Lynx)."""
        parts = (line or '').strip().split()
        if not parts:
            return self.preamble()
        op = parts[0].lower()
        if op in {'q', 'quit', 'exit', 'pf3', 'f3'}:
            return None
        if op in {'r', 'refresh'}:
            items, statuses = fetch_all(self.state, self.userid, live=True)
            return f'Refreshed feeds={len(statuses)} items={len(items)}\n' + self.preamble()
        if op in {'f', 'feeds'}:
            return render_feeds(self.state, self.userid) + '\n' + self.preamble()
        if op in {'o', 'open', 'lynx'} and len(parts) >= 3:
            link = (_cached_link_by_numbers(self.state, self.userid, int(parts[1]), int(parts[2]))
                    if parts[1].isdigit() and parts[2].isdigit() else '')
            if link:
                from gibson.tools.html_text_browser import render_url
                try:
                    art = render_url(link)
                except Exception as exc:
                    art = f'lynx: {type(exc).__name__}: {exc}'
                return art + '\n' + self.preamble()
            return 'No such feed/item link.\n' + self.preamble()
        return 'Unknown command.\n' + self.preamble()


def run_cti_rss_interactive(state: Any, userid: str='IBMUSER', reader=None, writer=None) -> None:
    if writer is None: return
    sess = CtiRssSession(state, userid)
    writer(sess.banner())
    while True:
        writer(sess.preamble())
        res = reader.read_line('cti-rss> ') if hasattr(reader,'read_line') else reader('cti-rss> ', False)
        cmd=(getattr(res,'text','') or getattr(res,'key','') or '').strip(); parts=cmd.split()
        if not parts: continue
        op=parts[0].lower()
        if op in {'q','quit','exit','pf3','f3'}: writer('Leaving CTI-RSS.\n'); return
        if op in {'r','refresh'}:
            items, statuses=fetch_all(state, userid, live=True); writer(f'Refreshed feeds={len(statuses)} items={len(items)}\n'); continue
        if op in {'f','feeds'}: writer(render_feeds(state, userid)+'\n'); continue
        if op in {'o','open','lynx'} and len(parts)>=3:
            link=_cached_link_by_numbers(state, userid, int(parts[1]), int(parts[2])) if parts[1].isdigit() and parts[2].isdigit() else ''
            if link:
                from gibson.apps.omvs_lynx import run_lynx_interactive
                run_lynx_interactive([link], state, userid, reader, writer)
            else: writer('No such feed/item link.\n')
            continue
        writer('Unknown command.\n')


# ---------------------------------------------------------------------------
# CTI/RSS performance patch: cache-first background refresh, single-feed refresh,
# bounded parallel fetching and stricter URL guardrails. These definitions are
# intentionally final overrides for the legacy accumulated implementations above.
# ---------------------------------------------------------------------------
import time as _time
import threading as _threading
import concurrent.futures as _futures
import socket as _socket
import ipaddress as _ipaddress

MAX_FEED_WORKERS = int(os.getenv('GIBSON_RSS_MAX_WORKERS', '4') or '4')
MAX_RESPONSE_BYTES = int(os.getenv('GIBSON_RSS_MAX_RESPONSE_BYTES', str(1024 * 1024)) or str(1024 * 1024))
CONNECT_TIMEOUT = float(os.getenv('GIBSON_RSS_CONNECT_TIMEOUT', '2') or '2')
READ_TIMEOUT = float(os.getenv('GIBSON_RSS_READ_TIMEOUT', '3') or '3')
JOB_TTL_SECONDS = 3600

@dataclass
class RssJob:
    job_id: str
    status: str = 'RUNNING'
    started: str = ''
    finished: str = ''
    feed: str = ''
    items: int = 0
    errors: int = 0
    message: str = ''


def _host_is_private_or_local(host: str) -> tuple[bool, str]:
    h=(host or '').strip().lower().strip('[]')
    if not h:
        return True, 'missing host'
    if h in {'localhost','localhost.localdomain'} or h.endswith('.localhost'):
        return True, 'localhost blocked'
    # Literal IP checks are cheap and deterministic.
    try:
        ip=_ipaddress.ip_address(h)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return True, 'private/loopback/link-local/reserved target blocked'
        return False, ''
    except Exception:
        pass
    # Optional DNS resolution guardrail.  Fail closed only if the host resolves
    # to local/private addresses; do not require DNS to work for tests.
    if os.getenv('GIBSON_RSS_RESOLVE_GUARD','0').upper() in {'1','Y','YES','TRUE'}:
        try:
            infos=_socket.getaddrinfo(h, None)
            for info in infos:
                ip=_ipaddress.ip_address(info[4][0])
                if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                    return True, 'resolved private/loopback/link-local target blocked'
        except Exception:
            pass
    return False, ''


def validate_feed_url(url: str) -> tuple[bool, str]:
    try:
        p=urlparse((url or '').strip())
        if p.scheme not in {'http','https'} or not p.netloc:
            return False, 'Only http/https feed URLs are allowed.'
        bad, reason=_host_is_private_or_local(p.hostname or '')
        if bad:
            return False, reason
        return True, ''
    except Exception as exc:
        return False, f'Invalid URL: {exc}'


def _valid_url(url: str) -> bool:  # type: ignore[override]
    ok,_=validate_feed_url(url)
    return ok


def _httpx_fetcher_client(client: Any):
    def _fetch(url: str) -> bytes:
        r=client.get(url)
        r.raise_for_status()
        data=r.content[:MAX_RESPONSE_BYTES+1]
        if len(data) > MAX_RESPONSE_BYTES:
            data=data[:MAX_RESPONSE_BYTES]
        return data
    return _fetch


def fetch_feed(url: str, feed_name: str, fetcher: Any = None) -> tuple[list[RssItem], str]:  # type: ignore[override]
    ok, reason=validate_feed_url(url)
    if not ok:
        return [], 'INVALID-URL: ' + reason
    try:
        if fetcher is not None:
            content=fetcher(url)
            if isinstance(content,str): content=content.encode('utf-8')
        else:
            try:
                import httpx  # type: ignore
                timeout=httpx.Timeout(timeout=CONNECT_TIMEOUT+READ_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)
                with httpx.Client(timeout=timeout, headers={'User-Agent':'Gibson-CTI-RSS/5.0'}, follow_redirects=True) as client:
                    content=_httpx_fetcher_client(client)(url)
            except ModuleNotFoundError:
                content, stat = _fetch_bytes_urllib(url, timeout=int(CONNECT_TIMEOUT+READ_TIMEOUT))
                if not content:
                    return [], stat
        try:
            import feedparser  # type: ignore
            parsed=feedparser.parse(content)
            out=[]
            for entry in getattr(parsed,'entries',[])[:MAX_ITEMS]:
                out.append(RssItem(feed_name, _clean(getattr(entry,'title','(no title)'),180),
                                   str(getattr(entry,'link',''))[:240],
                                   _clean(getattr(entry,'published', getattr(entry,'updated','')),80),
                                   _clean(getattr(entry,'summary',''),220)))
            if out:
                return out, 'OK' if not getattr(parsed,'bozo',False) else 'OK-BOZO'
        except Exception:
            pass
        out=_parse_feed_xml_fallback(content, feed_name)
        return out, 'OK' if out else 'NO-ITEMS'
    except Exception as exc:
        return [], f'{type(exc).__name__}: {_clean(exc, 80)}'


def _merge_feed_cache(old_cache: dict[str, Any], new_items: list[RssItem], statuses: list[FeedStatus], feed_filter: str = '') -> dict[str, Any]:
    old_items=old_cache.get('items') or []
    filt=_norm_name(feed_filter) if feed_filter else ''
    if filt:
        kept=[i for i in old_items if _norm_name(i.get('feed','')) != filt]
    else:
        kept=[]
    merged=kept + [asdict(i) for i in new_items]
    return {'time': _now(), 'items': merged[:500], 'status': [asdict(s) for s in statuses], 'live': True, 'background': True}


def fetch_all(state: Any, userid: str = 'IBMUSER', fetcher: Any = None,
              live: bool | None = None, feed_name: str = '') -> tuple[list[RssItem], list[FeedStatus]]:  # type: ignore[override]
    feeds=list_feeds(state, userid)
    if feed_name:
        wanted=_norm_name(feed_name)
        feeds=[f for f in feeds if f['name'] == wanted or _norm_name(f.get('title','')) == wanted]
    if live is None:
        live = fetcher is not None or os.getenv('GIBSON_RSS_LIVE_FETCH','YES').upper() not in {'0','N','NO','FALSE'}
    if not live:
        statuses=[FeedStatus(f['name'], f['url'], 'OFFLINE', 0, 'OFFLINE-NO-FETCH') for f in feeds]
        cache={'time': _now(), 'items': (load_cache(state, userid).get('items') or []), 'status': [asdict(s) for s in statuses], 'live': False}
        state.datasets.write(userid, CACHE_DSN, json.dumps(cache, indent=2)); state.datasets.write(userid, LASTRUN_DSN, cache['time']+'\n')
        return [], statuses
    items=[]; statuses=[]
    # One shared httpx client per refresh where possible; custom fetcher remains deterministic for tests.
    def run_one(feed: dict[str,str]) -> tuple[list[RssItem], FeedStatus]:
        t0=_time.monotonic()
        feed_items, stat=fetch_feed(feed['url'], feed['name'], fetcher)
        dur=int((_time.monotonic()-t0)*1000)
        status='OK' if stat.startswith('OK') else 'ERROR'
        return feed_items, FeedStatus(feed['name'], feed['url'], status, len(feed_items), '' if status=='OK' else f'{stat} ({dur}ms)')
    workers=max(1,min(MAX_FEED_WORKERS, len(feeds) or 1))
    with _futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs=[pool.submit(run_one,f) for f in feeds]
        for fut in _futures.as_completed(futs):
            feed_items, st=fut.result()
            items.extend(feed_items); statuses.append(st)
    cache=_merge_feed_cache(load_cache(state, userid), items, statuses, feed_name)
    state.datasets.write(userid, CACHE_DSN, json.dumps(cache, indent=2)); state.datasets.write(userid, LASTRUN_DSN, cache['time']+'\n')
    return items, statuses


def _jobs(state: Any) -> dict[str, RssJob]:
    if not hasattr(state, 'cti_rss_jobs'):
        setattr(state, 'cti_rss_jobs', {})
    return getattr(state, 'cti_rss_jobs')


def start_refresh_job(state: Any, userid: str = 'IBMUSER', feed_name: str = '', fetcher: Any = None, live: bool | None = None) -> str:
    ensure_rss_datasets(state, userid)
    jobs=_jobs(state)
    jid=f'RSS-{int(_time.time()*1000)}-{len(jobs)+1}'
    jobs[jid]=RssJob(jid, started=_now(), feed=_norm_name(feed_name) if feed_name else 'ALL')
    effective_live = os.getenv('GIBSON_RSS_LIVE_FETCH','NO').upper() in {'1','Y','YES','TRUE'} if live is None else bool(live)
    def run_body():
        items,statuses=fetch_all(state, userid, fetcher=fetcher, live=effective_live, feed_name=feed_name)
        err=sum(1 for s in statuses if s.status!='OK')
        jobs[jid].status='COMPLETE'; jobs[jid].finished=_now(); jobs[jid].items=len(items); jobs[jid].errors=err; jobs[jid].message=f'feeds={len(statuses)} items={len(items)} errors={err}'
    def worker():
        try: run_body()
        except Exception as exc:
            jobs[jid].status='ERROR'; jobs[jid].finished=_now(); jobs[jid].errors=1; jobs[jid].message=f'{type(exc).__name__}: {_clean(exc, 120)}'
    if effective_live:
        _threading.Thread(target=worker, name=f'GibsonRSSRefresh-{jid}', daemon=True).start()
    else:
        worker()
    return jid


def rss_job_status(state: Any) -> dict[str, Any]:
    jobs=_jobs(state)
    return {'jobs':[asdict(j) for j in jobs.values()][-20:], 'cache': load_cache(state, 'IBMUSER')}


def render_status(state: Any, userid: str = 'IBMUSER') -> str:  # type: ignore[override]
    cache=load_cache(state, userid); jobs=rss_job_status(state).get('jobs', [])
    lines=['FIBS CTI/RSS LAST RUN STATUS', f"LAST RUN: {cache.get('time','NEVER')}", '', 'FEED                 STATUS     ITEMS  ERROR']
    for s in cache.get('status') or []:
        lines.append(f"{str(s.get('name',''))[:20]:<20} {str(s.get('status','')):<10} {str(s.get('items','')):<6} {str(s.get('error',''))[:80]}")
    if jobs:
        lines += ['', 'BACKGROUND JOBS']
        for j in jobs[-5:]:
            lines.append(f"{j.get('job_id')} {j.get('status')} FEED({j.get('feed')}) {j.get('message')}")
    return '\n'.join(lines)


def rss_command(state: Any, userid: str, command: str) -> str:  # type: ignore[override]
    ensure_rss_datasets(state, userid)
    try: tokens=_shlex.split((command or 'RSS').strip())
    except Exception as exc: return f'RSS000E SYNTAX ERROR: {exc}'
    raw0=tokens[0].lower() if tokens else 'rss'
    if tokens and raw0 in {'rss','cti-rss'}: tokens=tokens[1:]
    if not tokens or tokens[0].upper() in {'LATEST','--LATEST'}:
        return _render_latest_five_by_feed(state, userid)
    op=tokens[0].upper()
    if op in {'REFRESH','FETCH','--REFRESH','--FETCH'}:
        feed=''
        if len(tokens) >= 3 and tokens[1].upper() in {'FEED','--FEED'}: feed=tokens[2]
        if '--WAIT' in [t.upper() for t in tokens]:
            items,statuses=fetch_all(state, userid, live=True, feed_name=feed)
            return '\n'.join(['RSS005I LIVE REFRESH COMPLETE', f'FEEDS({len(statuses)}) ITEMS({len(items)}) ERRORS({sum(1 for s in statuses if s.status!="OK")})', '', render_status(state, userid)])
        jid=start_refresh_job(state, userid, feed, live=(' LIVE' in (' '+upper) or '--LIVE' in upper))
        return f'RSS005I REFRESH JOB STARTED {jid}\nRSS006I USE RSS STATUS TO CHECK PROGRESS; CACHED HEADLINES REMAIN AVAILABLE.'
    if op in {'STATUS','LASTRUN'}: return render_status(state, userid)
    if op in {'LIST','FEEDS','--FEEDS','--LIST-FEEDS'}: return render_feeds(state, userid)
    if op in {'FEED','--FEED'} and len(tokens)>1: return _render_latest_five_by_feed(state, userid, feed_filter=tokens[1])
    if op in {'SHOW','HEADLINES'}: return _render_latest_five_by_feed(state, userid, feed_filter=tokens[1] if len(tokens)>1 else '')
    if op in {'OPEN','READ','LYNX','--OPEN','--READ','--LYNX'}: return _open_feed_number_item(state, userid, tokens[1:])
    if op == 'ADD':
        if len(tokens)<3: return 'RSS001E USAGE: RSS ADD <name> <url>'
        name,url=_norm_name(tokens[1]),tokens[2]
        ok, reason=validate_feed_url(url)
        if not ok: return 'RSS002E URL REJECTED - ' + reason
        feeds=[f for f in list_feeds(state,userid) if f['name'] != name]; feeds.append({'name':name,'url':url,'title':name}); save_feeds(state,feeds,userid)
        return f'RSS003I FEED {name} ADDED TO {FEEDS_DSN}'
    if op == 'DELETE':
        name=_norm_name(tokens[1]) if len(tokens)>1 else ''; feeds=list_feeds(state,userid); kept=[f for f in feeds if f['name'] != name]; save_feeds(state,kept,userid)
        return f'RSS004I FEED {name} DELETED COUNT({len(feeds)-len(kept)})'
    if op == 'EXPORT':
        dsn=tokens[1].upper() if len(tokens)>1 else REPORT_DSN; state.datasets.write(userid, dsn, _render_latest_five_by_feed(state,userid)+'\n'); return f'RSS006I RSS REPORT EXPORTED TO {dsn}'
    if op in {'HELP','?','MENU'}:
        return '\n'.join(['CTI/RSS READER','','RSS                         show cached latest stories','RSS REFRESH                 start background refresh','RSS REFRESH FEED <name>     refresh one feed','RSS REFRESH --WAIT          run bounded synchronous refresh','RSS STATUS                  show refresh jobs and feed health','RSS ADD <name> <url>        add feed','RSS DELETE <name>           delete feed','RSS LYNX <feed-no> <item-no> open article'])
    return _render_latest_five_by_feed(state, userid)
