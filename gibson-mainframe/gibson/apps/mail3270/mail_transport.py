"""Transport for the Gibson Office Mail facility.

Sending uses SMTP with optional STARTTLS/SSL and AUTH (smtplib).  Receiving can
use either POP3 (download) or IMAP (read on the server, non-destructive) - the
choice is the RECV_PROTO config key.  Credentials may be stored base64-encoded
(set CREDS_B64=YES), matching common provider config formats; they are decoded
only at the moment of use.  Everything is Python standard library, and every
call is wrapped so a failure or a closed-network lab never raises into the
panel: it returns a status string and the facility keeps working from its
local mailbox.
"""
from __future__ import annotations

import base64
from datetime import datetime
from typing import List, Tuple

from .mail_store import Message


def _now() -> str:
    return datetime.now().strftime("%d %b %Y %H:%M").upper()


def _cred(config: dict, key: str) -> str:
    """Return a credential, base64-decoded if CREDS_B64 is set."""
    val = (config.get(key, "") or "").strip()
    if not val:
        return ""
    if str(config.get("CREDS_B64", "NO")).upper() in {"YES", "Y", "1", "TRUE"}:
        try:
            return base64.b64decode(val).decode("utf-8", "ignore").strip()
        except Exception:
            return val
    return val


def _tls_mode(config: dict) -> str:
    v = str(config.get("TLS", "STARTTLS")).upper()
    if v in {"SSL", "TLS_SSL", "IMPLICIT"}:
        return "SSL"
    if v in {"NO", "NONE", "OFF", "PLAIN", "FALSE", ""}:
        return "NONE"
    return "STARTTLS"  # YES / STARTTLS / default


def send_smtp(config: dict, to: str, subj: str, body: List[str]) -> Tuple[bool, str]:
    """Send one note via SMTP.  Returns (ok, status_message)."""
    host = (config.get("SMTP_HOST", "") or "").strip()
    if not host:
        return (False, "NO SMTP HOST CONFIGURED - SET ONE IN CONFIGURE (SYS1.EMAIL)")
    frm = (config.get("FROM", "ibmuser@gibson.test") or "").strip()
    port = int(config.get("SMTP_PORT", "587") or 587)
    mode = _tls_mode(config)
    user = _cred(config, "SMTP_USER")
    pw = _cred(config, "SMTP_PASS")
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText("\n".join(body))
        msg["Subject"] = subj
        msg["From"] = frm
        msg["To"] = to
        if mode == "SSL":
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
        with server as s:
            s.ehlo()
            if mode == "STARTTLS":
                s.starttls(); s.ehlo()
            if user and pw:
                s.login(user, pw)
            s.sendmail(frm, [a.strip() for a in to.split(",") if a.strip()], msg.as_string())
        return (True, f"NOTE SENT TO {to} VIA {host}:{port}")
    except Exception as exc:
        return (False, f"SMTP UNAVAILABLE ({type(exc).__name__}) - NOTE FILED IN SENT ONLY")


def poll(config: dict, limit: int = 25) -> Tuple[List[Message], str]:
    """Receive new notes using the configured protocol (POP3 or IMAP)."""
    proto = str(config.get("RECV_PROTO", "IMAP")).upper()
    if proto == "NONE":
        return ([], "RECEIVE DISABLED (RECV_PROTO=NONE) - SET POP3 OR IMAP IN CONFIGURE")
    if proto == "POP3":
        return poll_pop(config, limit)
    return poll_imap(config, limit)


def _recv_creds(config: dict) -> Tuple[str, str]:
    user = _cred(config, "RECV_USER") or _cred(config, "SMTP_USER")
    pw = _cred(config, "RECV_PASS") or _cred(config, "SMTP_PASS")
    return user, pw


def poll_pop(config: dict, limit: int = 25) -> Tuple[List[Message], str]:
    """Download new notes via POP3 (SSL on 995, plain otherwise)."""
    host = (config.get("POP_HOST", "") or "").strip()
    if not host:
        return ([], "NO POP HOST CONFIGURED - SET ONE IN CONFIGURE (SYS1.EMAIL)")
    port = int(config.get("POP_PORT", "995") or 995)
    user, pw = _recv_creds(config)
    try:
        import poplib
        from email import message_from_bytes
        box = (poplib.POP3_SSL(host, port, timeout=15) if port == 995
               else poplib.POP3(host, port, timeout=15))
        if user:
            box.user(user)
            if pw:
                box.pass_(pw)
        count = len(box.list()[1])
        out: List[Message] = []
        for i in range(max(1, count - limit + 1), count + 1):
            raw = b"\n".join(box.retr(i)[1])
            out.append(_to_message(message_from_bytes(raw)))
        box.quit()
        return (out, f"DOWNLOADED {len(out)} NOTE(S) FROM {host}:{port} (POP3)")
    except Exception as exc:
        return ([], f"NO NEW MAIL ({type(exc).__name__}) - WORKING FROM LOCAL MAILBOX")


def poll_imap(config: dict, limit: int = 25) -> Tuple[List[Message], str]:
    """Read notes via IMAP without removing them from the server (BODY.PEEK)."""
    host = (config.get("IMAP_HOST", "") or "").strip()
    if not host:
        return ([], "NO IMAP HOST CONFIGURED - SET ONE IN CONFIGURE (SYS1.EMAIL)")
    port = int(config.get("IMAP_PORT", "993") or 993)
    user, pw = _recv_creds(config)
    try:
        import imaplib
        from email import message_from_bytes
        box = (imaplib.IMAP4_SSL(host, port) if port == 993
               else imaplib.IMAP4(host, port))
        if user:
            box.login(user, pw)
        box.select("INBOX", readonly=True)
        typ, data = box.search(None, "ALL")
        ids = data[0].split() if data and data[0] else []
        ids = ids[-limit:]
        out: List[Message] = []
        for num in ids:
            # BODY.PEEK does not set the Seen flag - non-destructive read
            typ, msgdata = box.fetch(num, "(BODY.PEEK[])")
            if not msgdata or not msgdata[0]:
                continue
            raw = msgdata[0][1]
            out.append(_to_message(message_from_bytes(raw)))
        box.logout()
        return (out, f"READ {len(out)} NOTE(S) FROM {host}:{port} (IMAP, left on server)")
    except Exception as exc:
        return ([], f"NO NEW MAIL ({type(exc).__name__}) - WORKING FROM LOCAL MAILBOX")


def _to_message(em) -> Message:
    return Message(
        frm=em.get("From", ""), to=em.get("To", ""),
        subj=em.get("Subject", "(no subject)"), date=em.get("Date", _now()),
        flag="NEW", body=_extract_body(em))


def _extract_body(em) -> List[str]:
    try:
        if em.is_multipart():
            for part in em.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode("utf-8", "ignore").splitlines()
            return ["(no plain-text body)"]
        payload = em.get_payload(decode=True)
        if payload is None:
            return [str(em.get_payload())]
        return payload.decode("utf-8", "ignore").splitlines()
    except Exception:
        return ["(unable to render body)"]
