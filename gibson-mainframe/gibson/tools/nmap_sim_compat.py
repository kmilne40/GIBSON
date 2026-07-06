#!/usr/bin/env python3
"""Python 3.13-safe replacement for telnetlib-based nmap-sim enumeration."""
from __future__ import annotations
import argparse
import socket
import time


def recv_until(sock: socket.socket, marker: bytes, timeout: float = 10.0) -> bytes:
    sock.settimeout(timeout)
    buf = bytearray()
    end = time.time() + timeout
    while marker not in buf and time.time() < end:
        try:
            chunk = sock.recv(1)
        except socket.timeout:
            break
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


def test_login(host: str, port: int, username: str) -> str:
    with socket.create_connection((host, port), timeout=15) as s:
        recv_until(s, b"Logon Type:")
        s.sendall(b"L TSO\r\n")
        prompt = recv_until(s, b"ENTER USERID", timeout=10)
        if b"ENTER USERID" not in prompt.upper():
            return f"[-] Unexpected prompt for {username}"
        s.sendall(username.encode() + b"\r\n")
        resp = recv_until(s, b"PASSWORD", timeout=3)
        if b"PASSWORD" in resp.upper():
            return f"[+] User '{username}' EXISTS."
        if b"IKJ56420I" in resp:
            return f"[-] User '{username}' does NOT exist."
        return f"[?] Ambiguous response for '{username}'."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-H", "--host", required=True)
    ap.add_argument("-p", "--port", type=int, required=True)
    ap.add_argument("-u", "--userfile", required=True)
    args = ap.parse_args()
    for line in open(args.userfile, encoding="utf-8"):
        user = line.strip()
        if user:
            print(test_login(args.host, args.port, user))

if __name__ == "__main__":
    main()
