from __future__ import annotations

import asyncio
import logging
import socketserver
import threading
from typing import Optional

from gibson.apps.db2_sim import Db2Simulator, SYSTEM_INFO
from gibson.core.state import GibsonState
from gibson.core.issues import is_expected_disconnect

DB2_SIGNATURE = b"DB2DAS"


def build_db2das_response(state: GibsonState) -> bytes:
    profile = (
        ";DB2 Server Database Access Profile\r\n"
        "[File_Description]\r\n"
        f"Application=DB2/ZOS {SYSTEM_INFO['VERSION']}\r\n"
        "File_Type=CommonServer\r\n"
        "File_Format_Version=1.0\r\n"
        f"DB2System={SYSTEM_INFO['SUBSYSTEM']}\r\n"
        "ServerVersion=QDB2\r\n"
        "[inst>DB2A]\r\n"
        "DB2Comm=TCPIP\r\n"
        f"PortNumber={state.config.db2_tcp_port}\r\n"
        f"LocationName={SYSTEM_INFO['LOCATION']}\r\n"
    ).encode("ascii", errors="ignore")
    header = bytearray(41)
    header[0:4] = b"\x00\x00\x00\x00"
    header[4:10] = b"DB2DAS"
    header[10:16] = b" " * 6
    header[16:18] = b"\x01\x04"
    header[18:23] = b"\x00\x00\x00\x10\x39"
    header[23:25] = b"\x7A\x00"
    header[25:38] = b"\x00" * 13
    header[38:41] = len(profile).to_bytes(3, "little")
    header.append(0x00)
    return bytes(header) + profile


class Db2DasHandler(socketserver.BaseRequestHandler):
    state: GibsonState

    def handle(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], self.state.config.db2_tcp_port, service="DB2")
        except Exception:
            pass
        try:
            from gibson.net import drda
        except Exception:
            drda = None
        try:
            self.request.settimeout(8.0)
            # A real DB2 DRDA server sends nothing on connect; it waits for the
            # client EXCSAT, then replies EXCSATRD.  Read first, then decide.
            data = self.request.recv(4096)
            if not data:
                return
            drda_reply = drda.respond(data, self.state) if drda is not None else None
            if drda_reply is not None:
                # Authentic DRDA path: answer EXCSAT->EXCSATRD, then keep serving
                # any follow-on DRDA requests (ACCSEC->ACCSECRD, etc.).
                try:
                    self.state.record_security_event(
                        self.client_address[0], "DB2 DRDA", "EXCSAT exchange",
                        service="DB2", addr=self.client_address[0], terminal="DRDA")
                except Exception:
                    pass
                self.request.sendall(drda_reply)
                while True:
                    try:
                        more = self.request.recv(4096)
                    except Exception:
                        break
                    if not more:
                        break
                    reply = drda.respond(more, self.state)
                    if reply is None:
                        break
                    self.request.sendall(reply)
                return
            # Fallback: legacy DB2 DAS text profile for non-DRDA / text probes.
            if DB2_SIGNATURE in data or b"\x00" in data:
                self.request.sendall(build_db2das_response(self.state))
            else:
                self.request.sendall(
                    (
                        "DSN7100I -DB2A DB2DAS GIBSON PROFILE\n"
                        f"LOCATION={SYSTEM_INFO['LOCATION']} PORT={self.state.config.db2_tcp_port}\n"
                    ).encode("utf-8")
                )
        except Exception:
            pass


class ThreadedDb2DasServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_db2das(state: GibsonState) -> ThreadedDb2DasServer:
    Db2DasHandler.state = state
    server = ThreadedDb2DasServer((state.config.host, state.config.db2_tcp_port), Db2DasHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonDB2DAS").start()
    return server


async def _ws_handler(ws, state: GibsonState):
    db2 = Db2Simulator(state)
    authenticated = False
    userid: Optional[str] = None
    await ws.send("Welcome to DB2/zOS simulator.\nLogin: LOGIN <username> <password>")
    async for msg in ws:
        cmd = msg.strip()
        if not authenticated:
            parts = cmd.split()
            if len(parts) == 3 and parts[0].upper() == "LOGIN":
                u, pw = parts[1].upper(), parts[2]
                state.racf.load(merge=True)
                if state.racf.verify_password(u, pw):
                    rec = state.racf.get(u)
                    if rec and rec.has_omvs:
                        authenticated = True
                        userid = u
                        state.record_security_event(u, "LOGON", "PASSWORD", service="DB2WS")
                        await ws.send(f"Login successful. Welcome, {u}. Type HELP")
                    else:
                        state.record_security_event(u, "LOGON", "OMVS SEGMENT MISSING", result="FAILURE", service="DB2WS")
                        await ws.send("Login failed: OMVS segment missing.")
                else:
                    state.record_security_event(u, "LOGON", "PASSWORD FAILURE", result="FAILURE", service="DB2WS")
                    await ws.send("Login failed: Unknown user or bad password.")
            else:
                await ws.send("Please login first. Format: LOGIN <username> <password>")
            continue
        assert userid is not None
        out = db2.shell_command(cmd, userid)
        await ws.send(out)
        if out.startswith("Goodbye"):
            break


class Db2WebSocketService:
    def __init__(self, state: GibsonState):
        self.state = state
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.server = None
        self._stop_event: Optional[asyncio.Event] = None

    def start(self) -> "Db2WebSocketService":
        def run_loop():
            try:
                import websockets
            except Exception as exc:  # pragma: no cover
                print(f"DB2 WebSocket disabled: {exc}")
                return
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            async def main():
                async def handler(ws):
                    await _ws_handler(ws, self.state)
                ws_logger = logging.getLogger("gibson.db2ws")
                ws_logger.propagate = False
                ws_logger.handlers[:] = []
                ws_logger.addHandler(logging.NullHandler())
                ws_logger.setLevel(logging.CRITICAL)
                self._stop_event = asyncio.Event()
                self.server = await websockets.serve(
                    handler,
                    self.state.config.host,
                    self.state.config.db2_ws_port,
                    logger=ws_logger,
                )
                await self._stop_event.wait()
                self.server.close()
                await self.server.wait_closed()

            try:
                self.loop.run_until_complete(main())
            finally:
                self.loop.close()

        self.thread = threading.Thread(target=run_loop, daemon=True, name="GibsonDB2WS")
        self.thread.start()
        return self

    def shutdown(self):
        if self.loop and self._stop_event:
            self.loop.call_soon_threadsafe(self._stop_event.set)


def serve_db2ws(state: GibsonState) -> Db2WebSocketService:
    return Db2WebSocketService(state).start()
