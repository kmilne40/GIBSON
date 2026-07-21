"""CBSA / OMEN fielded transfer-approval lab for the real hack3270 proxy.

CBSA's banking vulnerabilities are mostly command/COMMAREA driven, but the
classic 3270 presentation-layer attack - a protected/hidden APPROVAL flag that
the COBOL program trusts from the terminal map - is best demonstrated as a
genuine fielded screen.  This module renders the high-value transfer screen with
real 3270 field attributes (so hack3270 can reveal the hidden APPROVED flag and
unlock the protected MAXLIMIT field) and applies server-side trust:

  * vulnerable mode  -> the server trusts the client-supplied APPROVED flag, so
    a high-value transfer that should require a second authoriser is approved
    (the BNKTFR "TRUSTED CLIENT FIELD" finding hack3270 targets).
  * --secure mode    -> the server recomputes approval from the amount and the
    server-side limit, rejects the tampered flag and records a RACF/SMF80 denial.

The lab is intentionally self-contained (transid CBTR) so it does not disturb
the existing OMEN/CBPP text flow or its tests.
"""
from __future__ import annotations

# Server-side authorisation limit. A transfer at or above this needs a second
# authoriser; the client must never be trusted to set the APPROVED flag itself.
APPROVAL_LIMIT = 10000.00


def _sessions(state):
    s = getattr(state, "cbsa_transfer_sessions", None)
    if s is None:
        s = {}
        setattr(state, "cbsa_transfer_sessions", s)
    return s


def _session(state, userid):
    sessions = _sessions(state)
    key = (userid or "OMEN").upper()
    sess = sessions.get(key)
    if sess is None:
        sess = {"FROMACC": "00000101", "TOACC": "00000777", "AMOUNT": "0.00",
                "APPROVED": "N", "MAXLIMIT": f"{APPROVAL_LIMIT:.2f}", "message": "CBSA HIGH-VALUE TRANSFER",
                "STATETOK": "", "expected_tok": ""}
        sessions[key] = sess
    return sess


def _new_token(sess):
    """Issue the next pseudo-conversational COMMAREA migration token."""
    import hashlib
    seq = sess.get("_seq", 0) + 1
    sess["_seq"] = seq
    tok = hashlib.sha1(f"CBTR{seq}{sess.get('FROMACC','')}".encode()).hexdigest()[:8].upper()
    sess["expected_tok"] = tok
    sess["STATETOK"] = tok
    return tok


def _is_vulnerable(state):
    # Dedicated hack3270 training transaction: vulnerable by default, hardened
    # only under --secure (mirrors the DVCA lab's effective behaviour).
    return getattr(state.config, "security_mode", "vuln") != "secure"


def transfer_buffer(state, userid="OMEN"):
    """Render the current CBSA transfer screen as a genuine fielded ScreenBuffer."""
    from gibson.render.screen3270 import ScreenBuffer
    from gibson.render import colors
    sess = _session(state, userid)
    tok = _new_token(sess)
    sb = ScreenBuffer()
    sb.put(1, 1, "CBTR  CBSA HIGH-VALUE FUNDS TRANSFER (BNKTFR)", colors.BLUE)
    sb.put(3, 1, "Enter the transfer details and press ENTER to PROCESS.", colors.GREEN)
    sb.put(5, 1, "From account  :", colors.GREEN)
    sb.put(7, 1, "To account    :", colors.GREEN)
    sb.put(9, 1, "Amount        :", colors.GREEN)
    sb.put(11, 1, "Server limit  :", colors.GREEN)
    sb.put(13, 1, "Approved      :", colors.GREEN)
    # Unprotected input fields.
    sb.add_field("FROMACC", 5, 17, 8, value=sess.get("FROMACC", ""), protected=False, numeric=True, color=colors.TURQUOISE, role="cbsa_field")
    sb.add_field("TOACC", 7, 17, 8, value=sess.get("TOACC", ""), protected=False, numeric=True, color=colors.TURQUOISE, role="cbsa_field")
    sb.add_field("AMOUNT", 9, 17, 15, value=sess.get("AMOUNT", ""), protected=False, numeric=True, color=colors.TURQUOISE, role="cbsa_field")
    # Protected server limit (hack3270 can unlock it to probe).
    sb.add_field("MAXLIMIT", 11, 17, 15, value=sess.get("MAXLIMIT", ""), protected=True, numeric=True, mdt=True, fset=True, color=colors.LIGHT_BLUE, role="cbsa_field")
    # Hidden, protected approval flag - the COBOL program trusts this from the map.
    sb.add_field("APPROVED", 13, 17, 1, value=sess.get("APPROVED", "N"), protected=True, hidden=True, mdt=True, fset=True, color=colors.YELLOW, role="cbsa_field")
    # Hidden pseudo-conversational COMMAREA migration token (state carried in the
    # map between turns).  hack3270 can reveal/replay/fuzz it; --secure validates.
    sb.add_field("STATETOK", 15, 17, 8, value=tok, protected=True, hidden=True, mdt=True, fset=True, color=colors.YELLOW, role="cbsa_field")
    if sess.get("message"):
        sb.put(23, 1, str(sess["message"])[:79], colors.YELLOW)
    sb.put(24, 1, "CLEAR=Exit  PF3=Back to OMEN   ENTER=Process transfer", colors.BLUE)
    sb.set_cursor(9, 17)
    return sb


def _record_denial(state, userid, field_name, value, detail):
    try:
        from gibson.core.cics_region import get_cics_region
        get_cics_region(state).record_security(
            userid or "OMEN", "CICS FIELD TAMPER REJECTED", detail,
            result="FAILURE", transid="CBTR", resource=field_name,
            cls="TCICSTRN", profile="CBSA")
    except Exception:
        pass


def handle_transfer(state, userid, fields, aid="ENTER"):
    """Process a transfer submit. ``fields`` are the inbound 3270 field values."""
    sess = _session(state, userid)
    vulnerable = _is_vulnerable(state)
    fv = {str(k).upper(): str(v).strip() for k, v in (fields or {}).items()}

    # Unprotected fields are always accepted from the client.
    for k in ("FROMACC", "TOACC", "AMOUNT"):
        if k in fv:
            sess[k] = fv[k]

    # Protected/hidden fields: trusted in vulnerable mode, revalidated in secure.
    tampered = {}
    for k in ("APPROVED", "MAXLIMIT"):
        if k in fv and fv[k] != sess.get(k, ""):
            tampered[k] = fv[k]

    try:
        amount = float(str(sess.get("AMOUNT", "0") or "0").replace(",", ""))
    except ValueError:
        amount = -1.0
    if amount < 0:
        sess["message"] = "GIBCBSA TRANSFER REJECTED - AMOUNT NOT NUMERIC"
        return transfer_buffer(state, userid)

    # Pseudo-conversational COMMAREA state check. The map carries a migration
    # token that must match what the server issued on the prior turn. In secure
    # mode a fuzzed/replayed token is a state-confusion attempt and is rejected;
    # in vulnerable mode the server trusts whatever token the client returns.
    returned_tok = fv.get("STATETOK", sess.get("expected_tok", ""))
    if not vulnerable and sess.get("expected_tok") and returned_tok != sess.get("expected_tok"):
        _record_denial(state, userid, "STATETOK", returned_tok,
                       f"CBSA rejected fuzzed pseudo-conversational COMMAREA token {returned_tok} "
                       f"(expected a server-issued token) - state-confusion attempt")
        sess["message"] = "DFHXS1111 PSEUDO-CONVERSATIONAL STATE TOKEN INVALID - TURN REJECTED (RACF)"
        return transfer_buffer(state, userid)

    if not vulnerable:
        # Secure: ignore any client-supplied protected fields, recompute approval.
        if tampered:
            for k, v in tampered.items():
                _record_denial(state, userid, k, v,
                               f"CBSA recomputed approval server-side; rejected tampered protected field {k}={v}")
        sess["APPROVED"] = "Y" if amount < APPROVAL_LIMIT else "N"
        sess["MAXLIMIT"] = f"{APPROVAL_LIMIT:.2f}"
        if amount >= APPROVAL_LIMIT:
            sess["message"] = (f"DFHXS1111 REJECTED - {amount:.2f} OVER LIMIT "
                               f"{APPROVAL_LIMIT:.2f} - 2ND AUTHORISER REQD (RACF)")
        else:
            sess["message"] = f"TRANSFER OF {amount:.2f} APPROVED WITHIN SERVER LIMIT"
        return transfer_buffer(state, userid)

    # Vulnerable: trust the client-supplied approval flag (the vulnerability).
    if "APPROVED" in fv:
        sess["APPROVED"] = fv["APPROVED"].upper()[:1] or "N"
    if "MAXLIMIT" in fv:
        sess["MAXLIMIT"] = fv["MAXLIMIT"]
    approved = sess.get("APPROVED", "N").upper() == "Y"
    if amount >= APPROVAL_LIMIT and approved and tampered.get("APPROVED"):
        sess["message"] = (f"BNKTFR HIGH-VALUE TRANSFER {amount:.2f} APPROVED "
                           f"(server trusted client APPROVAL flag; hack3270)")
        try:
            from gibson.core.cics_region import get_cics_region
            get_cics_region(state).record_security(
                userid or "OMEN", "CICS PROTECTED FIELD TRUSTED",
                f"CBSA trusted client APPROVED=Y on a {amount:.2f} transfer above the "
                f"{APPROVAL_LIMIT:.2f} limit - presentation-layer authorisation bypass",
                result="WARNING", transid="CBTR", resource="APPROVED",
                cls="TCICSTRN", profile="CBSA")
        except Exception:
            pass
    elif approved:
        sess["message"] = f"TRANSFER OF {amount:.2f} APPROVED"
    else:
        sess["message"] = f"TRANSFER OF {amount:.2f} PENDING - APPROVED FLAG IS N"
    return transfer_buffer(state, userid)
