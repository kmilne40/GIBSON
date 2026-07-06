#!/usr/bin/env python3
# rss_reader.py — TUI-ish RSS reader for terminal with email & open-link actions
#
# Requires: feedparser, rich, httpx
#   pip install feedparser rich httpx
#
# Usage:
#   python3 rss_reader.py
#   python3 rss_reader.py --email-config email.json
#
# From dang-dns.py:
#   import rss_reader; rss_reader.main(email_config="email.json")

import json, os, sys, webbrowser, time, ssl, smtplib, mimetypes
from dataclasses import dataclass
from typing import List, Dict, Optional
from email.message import EmailMessage

import httpx
import feedparser
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

DEFAULT_RSS_FILE = "rss.json"
DEFAULT_EMAIL_CFG = "email.json"
FETCH_TIMEOUT = 12
MAX_ITEMS = 10

console = Console()

@dataclass
class Item:
    title: str
    link: str
    published: str
    summary: str

@dataclass
class FeedData:
    name: str
    url: str
    items: List[Item]

# ------------- Email helpers (compatible with your SMTP2GO config) -------------

def load_email_config(cfg_path: str) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Normalize keys to internal form
    if "username" not in cfg and "smtp_username" in cfg:
        cfg["username"] = cfg["smtp_username"]
    if "host" not in cfg and "smtp_server" in cfg:
        cfg["host"] = cfg["smtp_server"]
    if "port" not in cfg and "smtp_port" in cfg:
        cfg["port"] = cfg["smtp_port"]
    if "from" not in cfg and "sender" in cfg:
        cfg["from"] = cfg["sender"]
    if "to" not in cfg:
        if "recipient" in cfg and cfg["recipient"]:
            cfg["to"] = [cfg["recipient"]]
        else:
            cfg["to"] = []
    pw_env = os.getenv("GDDC_SMTP_PASSWORD")
    if pw_env: cfg["password"] = pw_env
    to_env = os.getenv("GDDC_SMTP_TO")
    if to_env: cfg["to"] = [x.strip() for x in to_env.split(",") if x.strip()]
    return cfg

def send_email(cfg: dict, subject: str, body: str, links: List[str], to_addrs: Optional[List[str]]=None):
    to_list = to_addrs or cfg.get("to") or []
    if not to_list:
        raise ValueError("No recipients configured. Add 'recipient' in email.json or use --to override.")

    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject.strip()

    body_lines = [body.strip()] if body else []
    if links:
        body_lines.append("")
        body_lines.append("Links:")
        for i, url in enumerate(links, 1):
            body_lines.append(f"{i:>2}. {url}")
    msg.set_content("\n".join([line for line in body_lines if line is not None]))

    host = cfg["host"]; port = int(cfg.get("port", 587))
    security = (cfg.get("security","starttls") or "starttls").lower()
    username = cfg.get("username"); password = cfg.get("password","")
    timeout = int(cfg.get("timeout_seconds", 20))
    context = ssl.create_default_context()

    if security == "ssl":
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as s:
            if username: s.login(username, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as s:
            if security == "starttls":
                s.starttls(context=context)
            if username: s.login(username, password)
            s.send_message(msg)

# ---------------- RSS core ----------------

def load_rss_config(path: str) -> List[Dict]:
    if not os.path.exists(path):
        sample = {
            "feeds": [
                {"name": "KrebsOnSecurity", "url": "https://krebsonsecurity.com/feed/"},
                {"name": "Hacker News Front Page", "url": "https://hnrss.org/frontpage"},
                {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2)
        console.print(Panel.fit(f"[yellow]Created sample {path}[/yellow]. Edit it to add your feeds."))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    feeds = data.get("feeds") or []
    return feeds

def fetch_feed(url: str) -> List[Item]:
    # Use httpx to fetch (handles TLS better than feedparser’s builtin fetch)
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT, headers={"User-Agent":"kev-rss/1.0"}) as c:
            r = c.get(url)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
    except Exception as e:
        console.print(f"[red]Fetch failed for {url}: {e}[/red]")
        return []

    out: List[Item] = []
    for entry in parsed.entries[:MAX_ITEMS]:
        title = getattr(entry, "title", "(no title)") or "(no title)"
        link = getattr(entry, "link", "")
        published = ""
        if hasattr(entry, "published"):
            published = entry.published
        elif hasattr(entry, "updated"):
            published = entry.updated
        summary = getattr(entry, "summary", "")
        out.append(Item(title=title, link=link, published=published, summary=summary))
    return out

def fetch_all(feeds_cfg: List[Dict]) -> List[FeedData]:
    result: List[FeedData] = []
    for f in feeds_cfg:
        name = f.get("name") or f.get("url")
        url = f.get("url")
        items = fetch_feed(url) if url else []
        result.append(FeedData(name=name, url=url, items=items))
    return result

def render_feed(feed: FeedData):
    title = Text(f"{feed.name}", style="bold cyan")
    subtitle = Text(f"{feed.url}", style="dim")
    console.print(Panel(title + Text("\n") + subtitle, box=box.ROUNDED))

    table = Table(title="Latest 10 items", box=box.SIMPLE_HEAVY)
    table.add_column("#", justify="right", style="bold")
    table.add_column("Title", overflow="fold")
    table.add_column("Published", style="dim")
    for i, item in enumerate(feed.items, 1):
        table.add_row(str(i), item.title, item.published or "")
    console.print(table)

def choose_feed(feeds: List[FeedData]) -> Optional[int]:
    console.print("\n[b]Feeds:[/b]")
    for i, f in enumerate(feeds, 1):
        console.print(f"  [bold]{i}[/bold]. {f.name} [dim]({f.url})[/dim]")
    choice = Prompt.ask("\nSelect feed number (or [b]R[/b] to refresh all, [b]Q[/b] to quit)", default="1")
    if choice.lower() == "q":
        return None
    if choice.lower() == "r":
        return -1
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(feeds):
            return idx
    except:
        pass
    console.print("[red]Invalid selection.[/red]")
    return choose_feed(feeds)

def choose_item(feed: FeedData) -> Optional[int]:
    if not feed.items:
        console.print("[yellow]No items.[/yellow]")
        return None
    choice = Prompt.ask("\nSelect item # (O=open, E=email, A=email all in this feed, B=back, Q=quit)", default="B")
    c = choice.strip().lower()
    if c == "q":
        return None
    if c == "b":
        return -2
    if c == "o":
        return -3
    if c == "e":
        return -4
    if c == "a":
        return -5
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(feed.items):
            return idx
    except:
        pass
    console.print("[red]Invalid choice.[/red]")
    return choose_item(feed)

def open_link(url: str):
    console.print(f"[green]Opening:[/green] {url}")
    try:
        webbrowser.open(url, new=2)
    except Exception as e:
        console.print(f"[red]Failed to open:[/red] {e}")

def email_links(email_cfg_path: str, subject: str, links: List[str], to_override: Optional[str]=None):
    cfg = load_email_config(email_cfg_path)
    to_list = None
    if to_override:
        to_list = [x.strip() for x in to_override.split(",") if x.strip()]
    send_email(cfg, subject=subject, body="", links=links, to_addrs=to_list)
    console.print(f"[green]Sent email[/green] to {', '.join(to_list or cfg.get('to', []))}.")

def run(email_config: str = DEFAULT_EMAIL_CFG, rss_path: str = DEFAULT_RSS_FILE):
    feeds_cfg = load_rss_config(rss_path)
    feeds = fetch_all(feeds_cfg)

    while True:
        idx = choose_feed(feeds)
        if idx is None:
            break
        if idx == -1:
            console.print("[blue]Refreshing feeds…[/blue]")
            feeds = fetch_all(feeds_cfg)
            continue

        feed = feeds[idx]
        render_feed(feed)

        while True:
            sel = choose_item(feed)
            if sel is None:  # quit
                return
            if sel == -2:    # back to feed list
                break
            if sel == -3:    # open mode
                num = Prompt.ask("Open which item number?", default="1")
                try:
                    i = int(num) - 1
                    open_link(feed.items[i].link)
                except Exception:
                    console.print("[red]Invalid number.[/red]")
                continue
            if sel == -4:    # email one
                num = Prompt.ask("Email which item number?", default="1")
                try:
                    i = int(num) - 1
                    to = Prompt.ask("To (blank=use email.json)", default="")
                    subj = f"[RSS] {feed.name} — {feed.items[i].title}"
                    email_links(email_config, subj, [feed.items[i].link], to_override=to or None)
                except Exception as e:
                    console.print(f"[red]Email failed:[/red] {e}")
                continue
            if sel == -5:    # email all in feed (visible top 10)
                to = Prompt.ask("To (blank=use email.json)", default="")
                subj = f"[RSS] {feed.name} — latest {len(feed.items)}"
                links = [it.link for it in feed.items]
                try:
                    email_links(email_config, subj, links, to_override=to or None)
                except Exception as e:
                    console.print(f"[red]Email failed:[/red] {e}")
                continue
            # open specific numbered item
            try:
                i = int(sel)
                open_link(feed.items[i].link)
            except Exception as e:
                console.print(f"[red]Open failed:[/red] {e}")

def main(email_config: Optional[str] = None, rss_path: Optional[str] = None):
    # Allow simple CLI use
    import argparse
    ap = argparse.ArgumentParser(description="Terminal RSS reader with email & open actions.")
    ap.add_argument("--rss-file", default=rss_path or DEFAULT_RSS_FILE, help="Path to rss.json (default: rss.json)")
    ap.add_argument("--email-config", default=email_config or DEFAULT_EMAIL_CFG, help="Path to email.json (default: email.json)")
    args = ap.parse_args()
    run(email_config=args.email_config, rss_path=args.rss_file)

if __name__ == "__main__":
    main()
