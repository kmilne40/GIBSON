from __future__ import annotations

from gibson.apps.dvca.store import get_dvca_store
from gibson.apps.dvca.screen_model import screen_for
from gibson.apps.dvca.programs import handle_command
from gibson.apps.dvca.render_html import render_terminal_html


def is_vulnerable(state) -> bool:
    return getattr(state.config, "security_mode", "vuln") != "secure" and bool(getattr(state.config, "dvca_vuln", True))


def _show_flags(sess):
    return sess.hack.get("enabled", False) and (
        sess.hack.get("show_start_field", False) or sess.hack.get("show_sfe", False)
    )


def _reveal_hidden(sess):
    return bool(sess.hack.get("enabled") and sess.hack.get("reveal_hidden"))


def _snapshot_payload(state, sid: str | None = None) -> tuple[object, object, object]:
    st = get_dvca_store(state)
    sess = st.session(sid)
    scr = screen_for(sess, st)
    return st, sess, scr


def snapshot(state, sid: str | None = None) -> dict:
    st, sess, scr = _snapshot_payload(state, sid)
    reveal = _reveal_hidden(sess)
    show = _show_flags(sess)
    show_sfe = bool(sess.hack.get("enabled") and sess.hack.get("show_sfe"))
    return {
        "session_id": sess.sid,
        "transaction": "DVCA",
        "screen_id": scr.screen_id,
        "title": scr.title,
        "mode": "VULNERABLE" if is_vulnerable(state) else "SECURE",
        "hack": dict(sess.hack),
        "rendered": scr.render(reveal_hidden=reveal, show_fields=show),
        "rendered_html": render_terminal_html(scr, reveal_hidden=reveal, show_fields=show, show_sfe=show_sfe),
        "fields": [f.as_dict(reveal or bool(sess.hack.get("reveal_hidden"))) for f in scr.fields],
        "message": sess.last_message,
    }


def start(state, user="DVCA"):
    st = get_dvca_store(state)
    sess = st.session(None, user)
    st.log("WEB", sess.sid, "SESSION_START", "OK", screen=sess.screen, user=user)
    return snapshot(state, sess.sid)


def hack_on(state, sid):
    st = get_dvca_store(state)
    sess = st.session(sid)
    sess.hack["enabled"] = True
    st.log("HACK3270", sess.sid, "HACK_ON", "OK", screen=sess.screen, scenario="HACK_MODE", user=sess.user)
    return snapshot(state, sess.sid)


def hack_off(state, sid):
    st = get_dvca_store(state)
    sess = st.session(sid)
    for key in list(sess.hack):
        sess.hack[key] = False
    st.log("HACK3270", sess.sid, "HACK_OFF", "OK", screen=sess.screen, scenario="HACK_MODE", user=sess.user)
    return snapshot(state, sess.sid)


def send_aid(state, sid, aid):
    st = get_dvca_store(state)
    sess = st.session(sid)
    exploit_aid = str(aid or "").upper() in {"PA1", "PA2", "PA3"}
    if exploit_aid and not sess.hack.get("enabled", False) and is_vulnerable(state):
        st.log("HACK3270", sess.sid, "SEND_AID", "DENIED", payload=aid, screen=sess.screen, scenario="AID_INJECTION", user=sess.user)
        return {"error": "AID injection requires HACK ON", **snapshot(state, sess.sid)}
    handle_command(sess, st, aid=aid, vulnerable=is_vulnerable(state))
    st.log("HACK3270", sess.sid, "SEND_AID", "OK", payload=aid, screen=sess.screen, scenario="AID_INJECTION", user=sess.user)
    return snapshot(state, sess.sid)


def send_input(state, sid, command="", fields=None):
    st = get_dvca_store(state)
    sess = st.session(sid)
    handle_command(sess, st, command=command, fields=fields or {}, vulnerable=is_vulnerable(state))
    st.log("WEB", sess.sid, "INPUT", "OK", payload=command or fields, screen=sess.screen, user=sess.user)
    return snapshot(state, sess.sid)


def toggle(state, sid, opts):
    st = get_dvca_store(state)
    sess = st.session(sid)
    mapping = {
        "enabled": "enabled",
        "disable_field_protection": "disable_protection",
        "enable_hidden_fields": "reveal_hidden",
        "remove_numeric_only": "remove_numeric",
        "start_field": "show_start_field",
        "start_field_extended": "show_sfe",
        "modify_field": "modify_field",
    }
    previous_enabled = sess.hack.get("enabled", False)
    for k, v in (opts or {}).items():
        key = mapping.get(k, k)
        if key in sess.hack:
            sess.hack[key] = bool(v)
    # Individual switches may be staged while HACK is OFF, but all exploit
    # effects remain gated by sess.hack["enabled"] in snapshot/render/mutation.
    action = "HACK_ON" if sess.hack.get("enabled") and not previous_enabled else "TOGGLE"
    if previous_enabled and not sess.hack.get("enabled"):
        action = "HACK_OFF"
    st.log("HACK3270", sess.sid, action, "OK", payload=opts, screen=sess.screen, scenario="FIELD_ATTRIBUTE_TOGGLE", user=sess.user)
    return snapshot(state, sess.sid)


def send_field(state, sid, field, value):
    st = get_dvca_store(state)
    sess = st.session(sid)
    scr = screen_for(sess, st)
    f = scr.field_map().get(str(field).upper())
    if not f:
        return {"error": "field not found", "field": str(field).upper(), **snapshot(state, sess.sid)}
    hack_enabled = bool(sess.hack.get("enabled"))
    needs_hack = f.protected or f.hidden or (f.numeric and not str(value).replace(".", "", 1).isdigit())
    if needs_hack and not hack_enabled:
        st.log("HACK3270", sess.sid, "MODIFY_FIELD", "DENIED", field=f.name, payload=value, screen=sess.screen, scenario="FIELD_MUTATION", user=sess.user)
        return {"error": "field mutation requires HACK ON", **snapshot(state, sess.sid)}
    if f.protected and not sess.hack.get("disable_protection", False):
        st.log("HACK3270", sess.sid, "MODIFY_FIELD", "DENIED", field=f.name, payload=value, screen=sess.screen, scenario="FIELD_PROTECTION_BYPASS", user=sess.user)
        return {"error": "field is protected; enable Disable Field Protection", **snapshot(state, sess.sid)}
    if f.hidden and not sess.hack.get("reveal_hidden", False):
        st.log("HACK3270", sess.sid, "MODIFY_FIELD", "DENIED", field=f.name, payload=value, screen=sess.screen, scenario="HIDDEN_FIELD", user=sess.user)
        return {"error": "field is hidden; enable hidden field reveal", **snapshot(state, sess.sid)}
    if f.numeric and not sess.hack.get("remove_numeric", False) and not str(value).replace(".", "", 1).isdigit():
        return {"error": "field is numeric-only; enable Remove Numeric Only Restrictions", **snapshot(state, sess.sid)}
    sess.fields[f.name.upper()] = str(value)[:f.length]
    st.log("HACK3270", sess.sid, "MODIFY_FIELD", "OK", field=f.name, payload=value, screen=sess.screen, scenario="FIELD_MUTATION", user=sess.user)
    return snapshot(state, sess.sid)


def batch_pin(state, sid, max_attempts=1500, start_pin=0, end_pin=None, inject=True, require_hack=False):
    st = get_dvca_store(state)
    sess = st.session(sid)
    if require_hack and not sess.hack.get("enabled", False):
        st.log("HACK3270", sess.sid, "BATCH_PIN", "DENIED", field="PIN", payload="requires HACK ON", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
        return {"error": "Batch PIN requires HACK ON", "found": "", "attempts": 0, **snapshot(state, sess.sid)}
    if not is_vulnerable(state):
        st.log("HACK3270", sess.sid, "BATCH_PIN", "DENIED", field="PIN", payload="secure mode", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
        return {"error": "Batch PIN blocked in secure mode", "found": "", "attempts": 0, **snapshot(state, sess.sid)}
    attempts = 0
    found = ""
    max_attempts = max(0, min(int(max_attempts), 10000))
    start_pin = max(0, min(int(start_pin), 9999))
    end = 9999 if end_pin is None else max(0, min(int(end_pin), 9999))
    for i in range(start_pin, end + 1):
        attempts += 1
        pin = f"{i:04d}"
        if pin == "1337":
            found = pin
            break
        if attempts >= max_attempts:
            break
    if found and inject:
        sess.fields["PIN"] = found
        sess.screen = "MCAD"
    st.log("HACK3270", sess.sid, "BATCH_PIN", "FOUND" if found else "NOT_FOUND", field="PIN", payload=f"attempts={attempts}", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
    return {"found": found, "attempts": attempts, "injected": bool(found and inject), **snapshot(state, sess.sid)}


def aid_scan(state, sid):
    st = get_dvca_store(state)
    sess = st.session(sid)
    if not sess.hack.get("enabled", False):
        return {"error": "AID scan requires HACK ON", **snapshot(state, sid)}
    aids = ["ENTER", "PF1", "PF3", "PF5", "PA1", "PA2", "PA3"]
    st.log("HACK3270", sid, "AID_SCAN", "OK", payload=str(aids), scenario="AID_INJECTION", user=sess.user)
    return {"aids": [{"aid": a, "effect": "SECRET" if a == "PA3" and is_vulnerable(state) else "OBSERVED"} for a in aids], **snapshot(state, sid)}


def logs(state, sid=None):
    st = get_dvca_store(state)
    return {"events": [e.row() for e in st.events if not sid or e.session_id == sid]}


def stats(state, sid=None):
    ev = logs(state, sid)["events"]
    return {
        "events": len(ev),
        "field_mutations": sum(1 for e in ev if e["action"] == "MODIFY_FIELD"),
        "aid_injections": sum(1 for e in ev if e["action"] == "SEND_AID"),
        "pin_attempts": sum(1 for e in ev if e["action"] == "BATCH_PIN"),
        "hack_toggles": sum(1 for e in ev if e["action"] in {"HACK_ON", "HACK_OFF", "TOGGLE"}),
    }
