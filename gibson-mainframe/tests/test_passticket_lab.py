from __future__ import annotations

import http.client
import json
import threading

from gibson.apps.cics import CicsSimulator
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.passticket import get_passticket_service
from gibson.services.rest_gateway import serve_rest

from tests.test_banking_tn3270_web_lab import _free_port, _wait_for_rest, make_state


def _post_json(port: int, path: str, payload: dict) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    body = json.loads(resp.read().decode("utf-8", errors="ignore"))
    conn.close()
    assert resp.status == 200, body
    return body


def test_passticket_generate_and_use_via_rest(tmp_path):
    st = make_state(tmp_path, rest_port=_free_port())
    t = threading.Thread(target=serve_rest, args=(st,), daemon=True)
    t.start()
    _wait_for_rest(st)

    generated = _post_json(st.config.rest_port, "/bank/passticket/generate", {"sid": "pt1", "userid": "IBMUSER", "applid": "CICS", "requester": "WEBBANK"})
    block = generated["passticket"]
    ticket = block["current_ticket"]

    assert ticket
    assert block["profiles"]
    assert any(row["TICKET"] == ticket for row in block["issued"])

    used = _post_json(st.config.rest_port, "/bank/passticket/use", {"sid": "pt1", "userid": "IBMUSER", "applid": "CICS", "ticket": ticket})
    assert used["authenticated"] is True
    assert used["current_screen"] == "MENU"
    assert "PASS TICKET ACCEPTED" in used["status"].upper()



def test_passticket_replay_blocked_then_allowed_via_scenario_toggle(tmp_path):
    st = make_state(tmp_path, rest_port=_free_port())
    t = threading.Thread(target=serve_rest, args=(st,), daemon=True)
    t.start()
    _wait_for_rest(st)

    generated = _post_json(st.config.rest_port, "/bank/passticket/generate", {"sid": "pt2", "userid": "IBMUSER", "applid": "CICS", "requester": "WEBBANK"})
    ticket = generated["passticket"]["current_ticket"]

    first = _post_json(st.config.rest_port, "/bank/passticket/use", {"sid": "pt2", "userid": "IBMUSER", "applid": "CICS", "ticket": ticket})
    assert first["authenticated"] is True
    second = _post_json(st.config.rest_port, "/bank/passticket/use", {"sid": "pt2", "userid": "IBMUSER", "applid": "CICS", "ticket": ticket})
    assert second["authenticated"] is False
    assert "REPLAY" in second["status"].upper()

    scenario = _post_json(st.config.rest_port, "/bank/passticket/scenario", {"sid": "pt2", "applid": "CICS", "replay_protection": False, "appl_mismatch": False, "leak": False})
    assert any(row["PROFILE"] == "CICS" and row["REPLAY"] == "OFF" for row in scenario["passticket"]["profiles"])

    generated2 = _post_json(st.config.rest_port, "/bank/passticket/generate", {"sid": "pt2", "userid": "IBMUSER", "applid": "CICS", "requester": "WEBBANK"})
    ticket2 = generated2["passticket"]["current_ticket"]
    third = _post_json(st.config.rest_port, "/bank/passticket/use", {"sid": "pt2", "userid": "IBMUSER", "applid": "CICS", "ticket": ticket2})
    fourth = _post_json(st.config.rest_port, "/bank/passticket/use", {"sid": "pt2", "userid": "IBMUSER", "applid": "CICS", "ticket": ticket2})
    assert third["authenticated"] is True
    assert fourth["authenticated"] is True



def test_cics_cesn_accepts_valid_passticket(tmp_path):
    st = make_state(tmp_path)
    svc = get_passticket_service(st)
    generated = svc.generate("IBMUSER", "CICS", "WEBBANK")
    assert generated["ok"] is True
    ticket = generated["ticket"]

    cics = CicsSimulator(st, "GUEST")
    output = cics.execute(f"CESN USER(IBMUSER) PTKT({ticket}) APPL(CICS)")
    assert "SIGNED ON SUCCESSFULLY WITH PASSTICKET" in output



def test_tso_passticket_commands_and_rlist_show_profile_attributes(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")

    gen = tso.run("PTKTGEN USER(IBMUSER) APPL(CICS)")
    assert "PASSTICKET =" in gen
    stat = tso.run("PTKTSTAT APPL(CICS)")
    assert "PTKTDATA PROFILES" in stat
    assert "CICS" in stat

    rlist = tso.run("RLIST PTKTDATA CICS")
    assert "PROFILE ATTRIBUTES" in rlist
    assert "KEYMASKED" in rlist
    assert "APPLDATA" in rlist



def test_legacy_password_logon_still_works_after_passticket_additions(tmp_path):
    st = make_state(tmp_path, rest_port=_free_port())
    t = threading.Thread(target=serve_rest, args=(st,), daemon=True)
    t.start()
    _wait_for_rest(st)

    logged_in = _post_json(st.config.rest_port, "/bank/terminal", {"sid": "pt3", "fields": {"USERID": "IBMUSER", "PASSWORD": "SYS1", "PASSTICKET": "", "APPLID": "CICS"}})
    assert logged_in["authenticated"] is True
    assert logged_in["current_screen"] == "MENU"
    assert "SIGNED ON AS IBMUSER" in logged_in["status"].upper()
