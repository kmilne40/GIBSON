"""z/TPF prime CRAS operator terminal - reached from VTAM via ``L TPF``.

Line-mode console: the operator enters functional Z-messages (ZSTAT, ZACES,
ZTPTRACE, ...) and demo transactions (AVL, AUTH); each transaction creates and
dispatches an ECB whose trace can be displayed with ZTPTRACE.  No /SIGN screen -
the CRAS is the system operator terminal - but Z-message activity is logged to
SMF (service TPF) so it is visible in Gibson Sentry / PLONK.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from gibson.apps.ztpf.ztpf_engine import get_ztpf_state, z_message, run_transaction

_BANNER = "z/TPF  ENTERPRISE EDITION  V1.1.0   PRIME CRAS TERMINAL"


class ZtpfTerminalSession:
    def __init__(self, state: Any, peer_addr: str = "", lniata: str = "010040"):
        self.state = state
        self.addr = peer_addr or ""
        # A connecting terminal is assigned an LNIATA; default is a remote
        # reservations agent set (BASIC).  Authority resolves from the engine's
        # terminal table and, in the authentic default posture, is not enforced.
        self.lniata = (lniata or "010040").upper()

    def run_terminal(self, input_driver, send) -> None:
        from gibson.render import colors
        st = get_ztpf_state(self.state)
        send(colors.CLEAR)
        send(_BANNER + "\n")
        send(f"CPU-{st.cpu} SS-BSS  SYSTEM STATE {st.sys_state}  ONLINE {'YES' if st.online else 'NO'}\n")
        send(f"CSMP0097I PRIME CRAS READY  LNIATA={self.lniata} - ENTER Z-MESSAGE OR TRANSACTION (ZHELP/ZLAB, OFF to exit)\n\n")
        while True:
            res = input_driver.read_line("TPF >\n")
            if getattr(res, "key", "") == "EOF":
                return
            raw = (getattr(res, "text", "") or "").strip()
            if not raw:
                continue
            out = self.command(raw)
            if out is None:
                send("CSMP0096I CRAS TERMINAL SESSION ENDED\n")
                return
            send(out + "\n")

    def command(self, raw: str) -> Optional[str]:
        """Return response text, or None to end the session."""
        verb = raw.strip().split()[0].upper()
        if verb in ("OFF", "LOGOFF", "ZLOGOFF", "BYE", "/RCL"):
            return None
        if verb.startswith("Z") or verb in ("HELP", "?"):
            resp = z_message(self.state, raw, lniata=self.lniata)
            try:
                self.state.record_security_event(
                    "OPERATOR", "TPF ZMSG", f"MSG={raw.strip()[:40]}", service="TPF",
                    addr=self.addr, terminal=self.lniata)
            except Exception:
                pass
            return resp or f"CSMP0101E FUNCTIONAL MESSAGE {verb} NOT DEFINED"
        # otherwise treat as a transaction input message -> create an ECB
        parts = raw.split()
        trancode = parts[0].upper()
        data = raw[len(parts[0]):].strip()
        ecb = run_transaction(self.state, trancode, data)
        try:
            self.state.record_security_event(
                "OPERATOR", "TPF TXN", f"TRAN={trancode} ECB={ecb.ecb_id}", service="TPF",
                addr=self.addr, terminal="CRAS")
        except Exception:
            pass
        head = f"ECB {ecb.ecb_id} DISPATCHED ON I-STREAM {ecb.istream:02d}  (ZTPTRACE to trace)"
        return head + "\n" + "\n".join(ecb.response)
