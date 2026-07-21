"""NJE (Network Job Entry) TCP listener for Gibson.

Binds the real NJE ports - 175/tcp (clear, EBCDIC) and 2252/tcp (TLS) - and
answers the 33-byte OPEN handshake with ACK/NAK exactly as a JES2 NJE/TCP server
does, so that:

  * ``nmap -p 175`` shows ``175/tcp open nje`` (nmap-services maps 175 -> nje),
  * ``nmap -sV`` confirms the NJE service, and
  * ``nmap --script nje-node-brute`` enumerates node names via the OPEN/NAK
    reason-code side-channel (0x01 unknown OHOST, 0x04 valid OHOST).

Like a real NJE server, the listener is silent on connect: it sends nothing
until it receives the client's OPEN record. Node validation reuses the
Chapter-10 node fixtures in ``gibson.core.nje``.
"""
from __future__ import annotations

import socketserver
import threading

from gibson.core.issues import is_expected_disconnect
from gibson.core.nje import CHAPTER10_NODES
from gibson.core.security_mode import is_secure_mode
from gibson.net import nje_protocol


class NjeHandler(socketserver.BaseRequestHandler):
    state = None
    secure = False

    def handle(self) -> None:
        port = (self.state.config.nje_tls_port if self.secure
                else self.state.config.nje_port)
        try:
            self.state.note_port_touch(self.client_address[0], port, service="NJE")
        except Exception:
            pass
        try:
            self.request.settimeout(8.0)
            # Silent on connect: real NJE waits for the client OPEN record.
            data = self.request.recv(256)
            if not data:
                return
            result = nje_protocol.respond_open(data, CHAPTER10_NODES)
            if result is None:
                return  # not an OPEN; stay silent (matches real NJE)
            resp, info = result
            try:
                self.state.record_security_event(
                    self.client_address[0], "NJE OPEN",
                    f"OHOST={info['ohost']} RHOST={info['rhost']} -> "
                    f"{info['type']} R={info['r']:#04x}"
                    + ("/TLS" if self.secure else ""),
                    service="NJE",
                    result="SUCCESS" if info["type"] == "ACK" else "REJECTED",
                    addr=self.client_address[0], terminal="NJE")
            except Exception:
                pass
            self.request.sendall(resp)
            # If we accepted (ACK), the peer continues with SOH/ENQ then an
            # I-record sign-on carrying the node password.  This is what
            # nje-pass-brute exercises.
            if info["type"] != "ACK":
                try:
                    self.request.recv(64)
                except Exception:
                    pass
                return
            try:
                soh = self.request.recv(64)
            except Exception:
                return
            if not soh or not nje_protocol.is_soh_enq(soh):
                return
            self.request.sendall(nje_protocol.DLE_ACK)
            try:
                irec = self.request.recv(256)
            except Exception:
                return
            if not irec:
                return
            password = nje_protocol.parse_irecord_password(irec) or ""
            ok = nje_protocol.check_node_password(info["ohost"], password, CHAPTER10_NODES)
            try:
                self.state.record_security_event(
                    self.client_address[0], "NJE SIGNON",
                    f"OHOST={info['ohost']} I-RECORD PASSWORD "
                    + ("ACCEPTED" if ok else "REJECTED"),
                    service="NJE", result="SUCCESS" if ok else "FAILURE",
                    addr=self.client_address[0], terminal="NJE")
            except Exception:
                pass
            self.request.sendall(nje_protocol.signon_reply(ok))
        except Exception:
            pass


class _SecureNjeHandler(NjeHandler):
    secure = True


class ThreadedNjeServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_nje(state) -> ThreadedNjeServer:
    """Start the clear NJE listener on 175 and, where possible, TLS on 2252."""
    NjeHandler.state = state
    _SecureNjeHandler.state = state
    try:
        server = ThreadedNjeServer((state.config.host, state.config.nje_port), NjeHandler)
    except PermissionError:
        port = state.config.nje_port
        raise SystemExit(
            f"GIBSON: permission denied binding NJE port {port}.\n"
            f"Ports below 1024 are privileged. Grant the capability once with:\n"
            f"  sudo ./scripts/grant-port-capabilities.sh\n"
            f"(or run with sudo). The capability is not port-specific, so it covers\n"
            f"175 exactly as it covers TN3270 on 23 and FTP on 21."
        )
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonNJE").start()

    # TLS variant on 2252 - wrap accepted sockets with the shared cert context.
    tls_port = getattr(state.config, "nje_tls_port", 0)
    if tls_port:
        try:
            tls_server = ThreadedNjeServer((state.config.host, tls_port), _SecureNjeHandler)
            from gibson.net.tls import wrap_server_socket
            tls_server = wrap_server_socket(tls_server, state, "NJE/TLS")
            threading.Thread(target=tls_server.serve_forever, daemon=True,
                             name="GibsonNJE-TLS").start()
            server._tls_server = tls_server  # keep a handle alive
        except Exception:
            pass
    return server
