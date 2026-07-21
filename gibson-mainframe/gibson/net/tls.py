from __future__ import annotations

import os
import ssl
import subprocess
from pathlib import Path
from types import MethodType


def _write_dev_cert(cert_file: Path, key_file: Path) -> bool:
    cert_file.parent.mkdir(parents=True, exist_ok=True)
    if cert_file.exists() and key_file.exists():
        return True
    openssl = os.environ.get("OPENSSL", "openssl")
    cmd = [
        openssl, "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "365",
        "-nodes", "-subj", "/CN=gibson.local/O=Gibson Simulator/OU=Training",
        "-keyout", str(key_file), "-out", str(cert_file),
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=10)
        try:
            key_file.chmod(0o600); cert_file.chmod(0o644)
        except Exception:
            pass
        return True
    except Exception:
        return False


def server_context(sim_root: Path) -> ssl.SSLContext | None:
    cert_dir = Path(sim_root).expanduser() / "certs"
    cert_file = Path(os.environ.get("GIBSON_TLS_CERT", str(cert_dir / "gibson-selfsigned.crt"))).expanduser()
    key_file = Path(os.environ.get("GIBSON_TLS_KEY", str(cert_dir / "gibson-selfsigned.key"))).expanduser()
    if not _write_dev_cert(cert_file, key_file):
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
    return ctx


def wrap_server_socket(server, state, service_name: str):
    """Enable TLS for a socketserver instance without replacing the listener.

    Gibson's terminal services need the accepted client socket to be handed to
    the normal ANSI VTAM/Telnet session handler.  Wrapping the listening socket
    can work for simple clients, but it makes the application flow brittle and
    caused the secure 1023 listener to complete TLS without reliably entering
    the same terminal path as the working plaintext 2023 listener.

    Instead, keep the TCP listening socket unchanged and wrap each accepted
    client socket in ``get_request()``.  The request handler then receives an
    ``ssl.SSLSocket`` and runs the existing terminal/dashboard code unchanged.
    """
    ctx = server_context(state.config.sim_root)
    if ctx is None:
        try:
            state.record_security_event(
                "SYSTEM",
                "TLS UNAVAILABLE",
                f"SERVICE={service_name} OPENSSL/CERT GENERATION FAILED",
                result="FAILURE",
                service=service_name,
            )
        except Exception:
            pass
        return server

    raw_get_request = server.get_request

    def tls_get_request(self):
        raw_sock, client_addr = raw_get_request()
        try:
            tls_sock = ctx.wrap_socket(raw_sock, server_side=True)
            return tls_sock, client_addr
        except Exception as exc:
            try:
                raw_sock.close()
            except Exception:
                pass
            try:
                state.record_security_event(
                    "SYSTEM",
                    "TLS HANDSHAKE FAILURE",
                    f"SERVICE={service_name} CLIENT={client_addr} ERROR={exc}",
                    result="FAILURE",
                    service=service_name,
                )
            except Exception:
                pass
            raise

    server.get_request = MethodType(tls_get_request, server)
    try:
        state.record_security_event("SYSTEM", "TLS LISTENER STARTUP", f"SERVICE={service_name} PORT={server.server_address[1]}", service=service_name)
        state.raise_dashboard_alert(f"TLS listener active for {service_name} on port {server.server_address[1]}", severity="INFO", port=server.server_address[1], event_type="TLS")
    except Exception:
        pass
    return server
