from __future__ import annotations
from gibson.apps.dvca.store import get_dvca_store
from gibson.apps.dvca.programs import handle_command
from gibson.apps.dvca.screen_model import screen_for
from gibson.render import colors
from gibson.apps.pin_bruteforce import run_pin_bruteforce, get_active_pin_bruteforce
from gibson.core import dvcapin

def execute_dvca(state, userid="DVCA", command="", aid="ENTER", event=None, sid=None):
    st = get_dvca_store(state)
    # Preserve CICS conversational state between ENTER/PF key submissions.
    sid_map = getattr(state, "dvca_cics_sessions", None)
    if sid_map is None:
        sid_map = {}; setattr(state, "dvca_cics_sessions", sid_map)
    key = (userid or "DVCA").upper()
    sid = sid or sid_map.get(key)
    sess = st.session(sid, user=userid or "DVCA")
    sid_map[key] = sess.sid
    vulnerable = getattr(state.config, "security_mode", "vuln") != "secure" and bool(getattr(state.config, "dvca_vuln", True))
    uc = (command or "").strip().upper()
    fields = {}
    field_source = {}
    if event is not None:
        try:
            for k, v in (getattr(event, "fields_by_name", {}) or {}).items():
                fields[str(k).upper()] = str(v); field_source[str(k).upper()] = "wire"
        except Exception:
            pass
        try:
            ev_aid = getattr(event, "aid", "") or ""
            if ev_aid:
                aid = ev_aid
        except Exception:
            pass
    for tok in (command or "").split():
        if "=" in tok:
            k, v = tok.split("=", 1); fields[k.upper()] = v; field_source[k.upper()] = "command"
    # Record where each protected-field value originated so the purchase logic
    # can tell a genuine hack3270 wire injection from the CANBUY=Y command path.
    sess._field_source = field_source
    active_brute = get_active_pin_bruteforce(state, userid or "GUEST", "DVCA MCAD")
    if active_brute is not None and (not uc or uc in {"ENTER", ""}):
        active_brute.maybe_tick(state, reveal_success=True)
        return (active_brute.frames[-1] if active_brute.frames else active_brute.render_frame()) + "\n"
    if uc.startswith("BRUTE FORCE PIN") or uc.startswith("BRUTE PIN") or uc.startswith("PINBRUTE"):
        if not vulnerable:
            return "BRUTE FORCE PIN BLOCKED IN SECURE MODE - LOCKOUT/RATE LIMIT ACTIVE\n"
        ds = fields.get("DSN") or fields.get("DATASET") or fields.get("DATASET_NAME")
        if not ds:
            parts=(command or "").split()
            ds = parts[-1] if parts and "." in parts[-1] else f"{(userid or 'GUEST').upper()}.4CHAR.PIN"
        sess = run_pin_bruteforce(state, userid or "GUEST", "DVCA MCAD", ds)
        try:
            from gibson.core.smf.records.type110 import cics_monitor
            cics_monitor(state, userid=userid or "GUEST", transaction_id="MCAD",
                         program="DVCAMCAD", result="WARNING",
                         applid="DVCA", terminal_id="TERM",
                         correlation_id=getattr(sess, "correlation_id", ""),
                         detail=f"DVCA PIN BRUTE FORCE DATASET={ds}")
        except Exception:
            pass
        if "PINFILE=" in uc:
            try:
                st.log("CICS", getattr(sess, "session_id", "PINBRUTE"), "PIN_BRUTE_SUCCESS", "OK", field="PIN", payload="REDACTED", screen="MCAD", scenario="HARDCODED_PIN", user=userid)
            except Exception:
                pass
        return (sess.frames[-1] if sess.frames else sess.render_frame()) + "\n"
    if uc.startswith("PIN ") or uc.startswith("DVCAPIN "):
        pin=(command or "").split(None,1)[1].strip() if len((command or "").split(None,1))>1 else ""
        if dvcapin.verify(state, pin):
            return "DVCA PIN CHALLENGE\nENTERED PIN ACCEPTED - ACCESS GRANTED\n"
        return "DVCA PIN CHALLENGE\nPIN INVALID - ACCESS DENIED\n"
    _aid_u = (aid or "ENTER").upper()
    if uc in {"DVCA", "MCGM"}: sess.screen = "MCGM"; sess.last_message = "DVCA STARTED"
    elif uc in {"MCMM", "MENU"}: sess.screen = "MCMM"; sess.last_message = "MAIN MENU"
    elif uc in {"MCOR", "ORDER"}: sess.screen = "MCOR"; sess.last_message = "ORDER SCREEN"
    elif uc in {"MCAD", "ADDR", "ADDRESS"}: sess.screen = "MCAD"; sess.last_message = "ADDRESS SCREEN"
    elif uc in {"MCHI", "MCHS", "HISTORY"}: sess.screen = "MCHI"; sess.last_message = "HISTORY"
    elif uc == "" and _aid_u in {"ENTER", ""} and sess.screen == "":
        sess.screen = "MCGM"; sess.last_message = sess.last_message or "DVCA STARTED"
    elif uc == "SCRT":
        if vulnerable and st.scenarios.get("DIRECT_SCRT", True): sess.screen = "SCRT"; sess.last_message = "DIRECT SCRT ACCESS ACCEPTED"; st.log("CICS", sess.sid, "DIRECT_SCRT", "OK", screen="SCRT", scenario="DIRECT_SCRT", user=userid)
        else: sess.last_message = "DIRECT SCRT ACCESS DENIED"; st.log("CICS", sess.sid, "DIRECT_SCRT", "DENIED", screen=sess.screen, scenario="DIRECT_SCRT", user=userid)
    else:
        handle_command(sess, st, command=command, aid=aid, fields=fields, vulnerable=vulnerable, trust_client_fields=vulnerable)
    scr = screen_for(sess, st)
    reveal = bool(sess.hack.get("enabled") and sess.hack.get("reveal_hidden", False))
    rendered = scr.render(reveal_hidden=reveal, show_fields=bool(sess.hack.get("enabled")))
    if sess.hack.get("enabled"):
        rendered = rendered.replace("TRAINING LEGEND HACK OFF", "TRAINING LEGEND HACK ON ")
    if sess.hack.get("enabled"):
        lines = rendered.splitlines()
        for f in scr.fields:
            r = f.row - 1; c = f.col - 1
            if not (0 <= r < len(lines) and c < len(lines[r])):
                continue
            raw = f.render_value(True if reveal or f.hidden else False)[:f.length]
            if not raw:
                continue
            fname = f.name.upper()
            # Readable training colours: foreground/boundary cues, not
            # reverse-video red background blocks.  HACK ON vulnerable fields
            # are red foreground; hidden fields are amber unless explicitly
            # revealed, then red foreground.
            if f.hidden:
                colour = colors.YELLOW
                coloured = colour + raw + colors.RESET + colors.GREEN
            elif fname in {"PRICE", "SHIP", "CANBUY"}:
                coloured = colors.RED + raw + colors.RESET + colors.GREEN
            elif f.protected:
                coloured = colors.LIGHT_BLUE + raw + colors.RESET + colors.GREEN
            else:
                coloured = colors.GREEN + raw + colors.RESET
            lines[r] = lines[r][:c] + coloured + lines[r][c+len(raw):]
        rendered = "\n".join(lines) + "\n"
    if sess.hack.get("enabled") and sess.screen == "MCOR":
        try:
            fmap = scr.field_map()
            compat = []
            if "PRICE" in fmap:
                compat.append("Price             :" + str(fmap["PRICE"].value).strip())
            if "BUY" in fmap:
                compat.append("Buy item (Y/N)    " + str(fmap["BUY"].value).strip())
            if compat:
                rendered = rendered.rstrip() + "\n" + "\n".join(compat) + "\n"
        except Exception:
            pass
    return rendered


def dvca_buffer(state, userid="DVCA", reveal_hidden=False):
    """Return the current DVCA screen as a genuine fielded ScreenBuffer.

    This is what makes the real hack3270 MITM proxy work: the DVCA BMS fields
    (PRICE/SHIP/CANBUY/OPT99/PIN) are emitted with their true 3270 attribute
    bytes - protected, non-display (hidden), numeric, MDT/FSET - so hack3270
    can reveal hidden fields and unlock protected ones in the data stream.

    ``reveal_hidden`` is only used by Gibson's own internal HACK ON teaching
    mode (for students without an external proxy); by default the true
    attributes are emitted so an external hack3270 does the revealing.
    """
    from gibson.render import colors
    st = get_dvca_store(state)
    sid_map = getattr(state, "dvca_cics_sessions", {}) or {}
    sid = sid_map.get((userid or "DVCA").upper())
    sess = st.session(sid, user=userid or "DVCA")
    scr = screen_for(sess, st)
    internal = bool(sess.hack.get("enabled") and sess.hack.get("reveal_hidden", False))
    sb = scr.to_screenbuffer(reveal_hidden=reveal_hidden or internal)
    if sess.last_message:
        sb.put(23, 1, str(sess.last_message)[:79], colors.YELLOW, protected=True)
    return sb
