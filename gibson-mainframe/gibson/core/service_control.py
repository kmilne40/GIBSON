from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional


Starter = Callable[[], Any]
Stopper = Callable[[Any], None]


@dataclass
class ManagedService:
    name: str
    kind: str = "logical"
    port: Optional[int] = None
    description: str = ""
    state: str = "STARTED"
    listener_tokens: tuple[str, ...] = ()
    starter: Optional[Starter] = None
    stopper: Optional[Stopper] = None
    server: Any = None
    start_msgs: tuple[str, ...] = ()
    stop_msgs: tuple[str, ...] = ()
    pause_msgs: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


class ServiceManager:
    def __init__(self, state, console_log=None):
        self.state = state
        self.console_log = console_log
        self.services: Dict[str, ManagedService] = {}

    def register(self, svc: ManagedService) -> None:
        self.services[svc.name.upper()] = svc
        self._sync_listener_states(svc)

    def names(self) -> list[str]:
        return sorted(self.services)

    def get(self, name: str) -> Optional[ManagedService]:
        return self.services.get(name.upper())

    def is_available(self, name: str) -> bool:
        svc = self.get(name)
        if svc is None:
            return True
        return svc.state == "STARTED"

    def status_rows(self) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        for name in sorted(self.services):
            svc = self.services[name]
            port = str(svc.port) if svc.port is not None else "--"
            rows.append((svc.name, svc.state, port, svc.description))
        return rows

    def _log(self, text: str) -> None:
        if self.console_log:
            self.console_log.record(text)

    def _sync_listener_states(self, svc: ManagedService) -> None:
        try:
            listeners = getattr(self.state.network, "listeners", [])
        except Exception:
            listeners = []
        for listener in listeners:
            names = " ".join(
                [getattr(listener, "name", ""), getattr(listener, "jobname", ""), getattr(listener, "description", "")]
            ).upper()
            if svc.listener_tokens and any(tok.upper() in names for tok in svc.listener_tokens):
                listener.state = "LISTEN" if svc.state == "STARTED" else svc.state

    def _shutdown_server(self, svc: ManagedService) -> None:
        if svc.server is None:
            return
        try:
            if svc.stopper is not None:
                svc.stopper(svc.server)
            else:
                if hasattr(svc.server, "shutdown"):
                    svc.server.shutdown()
                if hasattr(svc.server, "server_close"):
                    svc.server.server_close()
        finally:
            svc.server = None

    def start(self, name: str) -> tuple[bool, str]:
        svc = self.get(name)
        if not svc:
            return False, f"IEE305I {name.upper()} NOT DEFINED TO GIBSON SERVICE TABLE"
        if svc.state == "STARTED" and svc.server is not None:
            return True, self._emit(svc.start_msgs or (f"IEE457I {svc.name} ALREADY ACTIVE",))
        if svc.starter is not None:
            svc.server = svc.starter()
        svc.state = "STARTED"
        self._sync_listener_states(svc)
        try:
            if svc.port is not None:
                self.state.allowed_high_ports.add(int(svc.port))
                self.state.register_open_port(int(svc.port), "TCP", svc.name)
        except Exception:
            pass
        try:
            from gibson.core import v26_features
            v26_features.security_event(self.state, "SERVICE", f"SERVICE {svc.name} STARTED", userid="CONSOLE", severity="INFO", resource=svc.name, result="STARTED")
        except Exception:
            pass
        return True, self._emit(svc.start_msgs or (f"IEE352I {svc.name} STARTED",))

    def stop(self, name: str) -> tuple[bool, str]:
        svc = self.get(name)
        if not svc:
            return False, f"IEE305I {name.upper()} NOT DEFINED TO GIBSON SERVICE TABLE"
        if svc.server is not None:
            self._shutdown_server(svc)
        svc.state = "STOPPED"
        self._sync_listener_states(svc)
        try:
            from gibson.core import v26_features
            v26_features.security_event(self.state, "SERVICE", f"SERVICE {svc.name} STOPPED", userid="CONSOLE", severity="INFO", resource=svc.name, result="STOPPED")
        except Exception:
            pass
        return True, self._emit(svc.stop_msgs or (f"IEE334I {svc.name} STOPPED",))

    def pause(self, name: str) -> tuple[bool, str]:
        svc = self.get(name)
        if not svc:
            return False, f"IEE305I {name.upper()} NOT DEFINED TO GIBSON SERVICE TABLE"
        if svc.server is not None:
            self._shutdown_server(svc)
        svc.state = "PAUSED"
        self._sync_listener_states(svc)
        return True, self._emit(svc.pause_msgs or (f"IEE341I {svc.name} PAUSED",))

    def stop_all(self, names: Optional[Iterable[str]] = None) -> None:
        targets = list(names) if names is not None else list(self.services)
        for name in targets:
            svc = self.get(name)
            if not svc:
                continue
            if svc.server is not None:
                try:
                    self._shutdown_server(svc)
                except Exception:
                    pass
            if svc.state != "STOPPED":
                svc.state = "STOPPED"
                self._sync_listener_states(svc)

    def _emit(self, lines: Iterable[str]) -> str:
        text = "\n".join(lines)
        self._log(text)
        return text
