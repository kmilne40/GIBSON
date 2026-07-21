"""IMS message-region terminal session - reached from VTAM via ``L IMS`` /
``LOGON APPLID(IMS1)``.

This is the 3270/line-mode terminal a user is connected to when they log on to
the IMS control region as a VTAM application (the analogue of ``L TSO`` for
TSO).  It presents the IMS ``DFS`` greeting, requires ``/SIGN ON`` (authenticated
against RACF), then accepts transaction codes - which run through the existing
IMS transaction model and DL/I back-ends - and ``/DIS`` operator commands,
ending on ``/SIGN OFF``.  Logon/sign events are written to SMF (service ``IMS``)
so the session is visible in Gibson Sentry / PLONK.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from gibson.apps.ims.ims_connect import (
    get_ims_state, _submit_transaction, _run_command, _CMD_RESOURCE,
)

_IMSID = "IMS1"


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


class ImsTerminalSession:
    """A VTAM-attached IMS terminal (control-region message terminal)."""

    def __init__(self, state: Any, peer_addr: str = "", userid: str = ""):
        self.state = state
        self.addr = peer_addr or ""
        self.user = ""          # signed-on userid ("" until /SIGN ON)

    # -- ASCII / telnet line-mode -------------------------------------------
    def run_terminal(self, input_driver, send) -> None:
        from gibson.render import colors
        ims = get_ims_state(self.state)
        send(colors.CLEAR)
        send("DFS3650I  *** IMS/VS  CONTROL REGION ***\n")
        send(f"DFS3650I  {_IMSID}  MESSAGE-REGION TERMINAL READY  {_now()}\n")
        send("DFS3649A  /SIGN COMMAND REQUIRED FOR THIS TERMINAL\n\n")
        send("    Enter:  /SIGN ON userid password   then a transaction code.\n")
        send("            /DIS A  to display regions;  /SIGN OFF  to exit.\n\n")
        while True:
            prompt = f"{(self.user or 'IMS')} >\n"
            res = input_driver.read_line(prompt)
            if getattr(res, "key", "") == "EOF":
                return
            raw = (getattr(res, "text", "") or "").strip()
            if not raw:
                continue
            out = self.command(raw)
            if out is None:                 # /SIGN OFF or logoff
                send("DFS058I  SIGN OFF COMPLETED\n")
                return
            send(out + "\n")

    # -- command processing (shared by ASCII and 3270 paths) ----------------
    def command(self, raw: str) -> Optional[str]:
        """Return the response text, or ``None`` to end the session."""
        ims = get_ims_state(self.state)
        parts = raw.split()
        verb = parts[0].upper()

        if verb == "/SIGN":
            sub = parts[1].upper() if len(parts) > 1 else ""
            if sub == "OFF":
                if self.user:
                    self.state.record_security_event(
                        self.user, "SIGN OFF", "IMS /SIGN OFF", service="IMS",
                        addr=self.addr, terminal="VTAM")
                    self.user = ""
                return None
            if sub == "ON":
                who = parts[2].upper() if len(parts) > 2 else ""
                pw = parts[3] if len(parts) > 3 else ""
                if not who:
                    return "DFS3645I  /SIGN ON SYNTAX:  /SIGN ON userid password"
                if not self.state.racf.exists(who):
                    self.state.record_security_event(
                        who, "LOGON", "IMS /SIGN ON - USERID NOT DEFINED",
                        result="FAILURE", service="IMS", addr=self.addr, terminal="VTAM")
                    return f"DFS3649A  SIGN-ON FAILED FOR {who} - USERID NOT DEFINED TO RACF"
                if pw and not self.state.racf.verify_password(who, pw):
                    try:
                        self.state.note_failed_logon(who, self.addr, service="IMS")
                    except Exception:
                        pass
                    self.state.record_security_event(
                        who, "LOGON", "IMS /SIGN ON - PASSWORD FAILURE",
                        result="FAILURE", service="IMS", addr=self.addr, terminal="VTAM")
                    return f"DFS3649A  SIGN-ON FAILED FOR {who} - PASSWORD INCORRECT"
                self.user = who
                self.state.record_security_event(
                    who, "LOGON", f"IMS /SIGN ON APPLID={_IMSID}", service="IMS",
                    addr=self.addr, terminal="VTAM")
                return f"DFS058I  {_now()}  SIGN COMMAND COMPLETED FOR {who}"
            return "DFS3645I  /SIGN: specify ON or OFF"

        if verb in ("LOGOFF", "/RCL", "/EXIT", "BYE", "/QUIT"):
            return None

        if verb in ("/HELP", "?", "HELP"):
            return ("IMS TERMINAL COMMANDS:\n"
                    "  /SIGN ON userid pw    sign on to IMS (RACF authenticated)\n"
                    "  /SIGN OFF             sign off and exit\n"
                    "  /DIS A                display active regions\n"
                    "  /DIS TRAN code        display a transaction\n"
                    "  trancode [data]       run a transaction\n"
                    "  Transactions: " + " ".join(sorted(ims.transactions)))

        if not self.user:
            return "DFS3649A  /SIGN COMMAND REQUIRED - ENTER /SIGN ON userid password"

        if verb.startswith("/"):
            if verb in _CMD_RESOURCE:
                return _run_command(ims, parts)
            return f"DFS1292E  COMMAND {verb} NOT RECOGNISED"

        # a transaction code (optionally followed by input data)
        data = raw[len(parts[0]):].strip()
        return _submit_transaction(self.state, ims, self.user, verb, "", data)
