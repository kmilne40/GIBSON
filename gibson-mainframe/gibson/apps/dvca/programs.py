from __future__ import annotations
from gibson.apps.dvca.store import DvcaSession, DvcaStore
from gibson.core import dvcapin
from gibson.apps.pin_bruteforce import _normalise_pin_candidates, MAX_PIN_ATTEMPTS
SUPERVISOR_PIN = "1337"  # documented fallback when DVCAPIN is unset


def _record_field_denial(store, sess, field_name, value):
    """In --secure mode, a tampered protected field is caught server-side and
    recorded as a RACF/SAF denial (SMF80) - the before/after the class compares
    against the vulnerable-mode acceptance."""
    store.log("CICS", sess.sid, "DVCA_FIELD_TAMPER", "DENIED", field=field_name,
              payload=value, screen=sess.screen, scenario="SERVER_SIDE_VALIDATION", user=sess.user)
    try:
        from gibson.core.cics_region import get_cics_region
        region = get_cics_region(store.state)
        region.record_security(
            sess.user or "DVCA", "CICS FIELD TAMPER REJECTED",
            f"DVCA rejected tampered protected field {field_name}={value} - "
            f"server-side validation (RACF) blocked a presentation-layer bypass",
            result="FAILURE", transid="DVCA", resource=field_name,
            cls="TCICSTRN", profile="DVCA")
    except Exception:
        pass

def handle_command(sess: DvcaSession, store: DvcaStore, command: str = "", aid: str = "ENTER", fields: dict | None = None, vulnerable: bool = True, trust_client_fields=None) -> None:
    c = (command or "").strip().upper(); a = (aid or "").upper()
    if fields:
        for k, v in fields.items():
            kk = str(k).upper(); vv = str(v).strip()
            # In normal mode the host ignores client-side attempts to modify
            # protected/hidden DVCA order fields.  In HACK ON mode those
            # changes are deliberately trusted for the lab and immediately
            # reflected when the map is repainted.
            if sess.screen == "MCOR" and kk in {"PRICE", "SHIP", "CANBUY"}:
                # Whether the host trusts a client-supplied value for a
                # protected/hidden field. trust_client_fields is set by the
                # TN3270 path (real hack3270): True in vulnerable mode (the
                # actual server-side-trust vulnerability), False in --secure
                # mode (server revalidates and rejects with a RACF denial).
                # When None (legacy web / internal-hack path) the original
                # internal-HACK-ON gate applies so existing tests are stable.
                if trust_client_fields is None:
                    trusted = sess.hack.get("enabled", False)
                else:
                    trusted = bool(trust_client_fields)
                if not trusted:
                    if trust_client_fields is False:
                        sess.last_message = f"DFHXS1111 {kk} TAMPER REJECTED - SERVER-SIDE VALIDATION (RACF)"
                        _record_field_denial(store, sess, kk, vv)
                    else:
                        sess.last_message = f"PROTECTED FIELD {kk} NOT ACCEPTED - USE HACK ON"
                        store.log("CICS", sess.sid, "DVCA_FIELD_TAMPER", "DENIED", field=kk, payload=vv, screen=sess.screen, scenario="FIELD_PROTECTION_BYPASS", user=sess.user)
                    continue
                oldv = sess.fields.get(kk, "")
                sess.fields[kk] = vv
                if vv != oldv:
                    action = "DVCA_PRICE_TAMPER" if kk in {"PRICE", "SHIP"} else "DVCA_BUY_FLAG_TAMPER"
                    store.log("CICS", sess.sid, action, "OK", field=kk, payload=vv, screen=sess.screen, scenario="FIELD_PROTECTION_BYPASS", user=sess.user)
                    # Attribute the override to the genuine wire injection
                    # (hack3270) or the CANBUY=Y command shortcut, so the two
                    # can coexist without conflating the audit trail.
                    src = getattr(sess, "_field_source", {}).get(kk)
                    via = "hack3270" if src == "wire" else ("command" if src == "command" else ("hack3270" if trust_client_fields else "HACK ON"))
                    if kk == "CANBUY":
                        sess.hack["canbuy_via"] = via
                    sess.last_message = f"{kk} TAMPER ACCEPTED (server trusted client field; {via})"
                continue
            sess.fields[kk] = vv
    

    # DVCA CICS command-line hack controls used by the classroom CICS path and web terminal input.
    if c == "HACK ON":
        sess.hack["enabled"] = True
        sess.last_message = "HACK ON - FIELD ATTRIBUTE TRAINING ENABLED"
        store.log("CICS", sess.sid, "HACK_ON", "OK", screen=sess.screen, scenario="HACK_MODE", user=sess.user)
        return
    if c == "HACK OFF":
        for key in list(sess.hack):
            sess.hack[key] = False
        sess.last_message = "HACK OFF - NORMAL DVCA TERMINAL MODE"
        store.log("CICS", sess.sid, "HACK_OFF", "OK", screen=sess.screen, scenario="HACK_MODE", user=sess.user)
        return
    if c in {"SHOW FIELDS", "START FIELD"}:
        if not sess.hack.get("enabled", False):
            sess.last_message = "SHOW FIELDS REQUIRES HACK ON"
            return
        sess.hack["show_start_field"] = True
        sess.last_message = "START FIELD BOUNDARIES ENABLED"
        store.log("CICS", sess.sid, "SHOW_FIELDS", "OK", screen=sess.screen, scenario="FIELD_ATTRIBUTES", user=sess.user)
        return
    if c in {"SHOW HIDDEN", "ENABLE HIDDEN", "ENABLE HIDDEN FIELDS"}:
        if not sess.hack.get("enabled", False):
            sess.last_message = "SHOW HIDDEN REQUIRES HACK ON"
            return
        sess.hack["reveal_hidden"] = True
        sess.last_message = "HIDDEN FIELDS REVEALED"
        store.log("CICS", sess.sid, "SHOW_HIDDEN", "OK", screen=sess.screen, scenario="HIDDEN_FIELD", user=sess.user)
        return
    if c in {"HIDE HIDDEN", "DISABLE HIDDEN"}:
        sess.hack["reveal_hidden"] = False
        sess.last_message = "HIDDEN FIELDS HIDDEN"
        return
    if c == "DISABLE PROTECTION":
        if not sess.hack.get("enabled", False):
            sess.last_message = "DISABLE PROTECTION REQUIRES HACK ON"
            return
        sess.hack["disable_protection"] = True
        sess.last_message = "FIELD PROTECTION BYPASS ENABLED"
        store.log("CICS", sess.sid, "DISABLE_PROTECTION", "OK", screen=sess.screen, scenario="FIELD_PROTECTION_BYPASS", user=sess.user)
        return
    if c == "ENABLE PROTECTION":
        sess.hack["disable_protection"] = False
        sess.last_message = "FIELD PROTECTION RESTORED"
        return
    if c == "REMOVE NUMERIC":
        if not sess.hack.get("enabled", False):
            sess.last_message = "REMOVE NUMERIC REQUIRES HACK ON"
            return
        sess.hack["remove_numeric"] = True
        sess.last_message = "NUMERIC-ONLY RESTRICTION BYPASS ENABLED"
        store.log("CICS", sess.sid, "REMOVE_NUMERIC", "OK", screen=sess.screen, scenario="NUMERIC_ONLY_BYPASS", user=sess.user)
        return
    if c == "RESTORE NUMERIC":
        sess.hack["remove_numeric"] = False
        sess.last_message = "NUMERIC-ONLY RESTRICTIONS RESTORED"
        return
    if c.startswith("PIN "):
        value = c.split(None, 1)[1].strip()
        sess.screen = "MCAD"
        if value in {"****", "####"}:
            sess.fields.pop("PIN", None)
            sess.last_message = "PIN DISPLAY MASKED"
            return
        if not sess.hack.get("enabled", False):
            sess.last_message = "PIN INJECTION REQUIRES HACK ON"
            store.log("CICS", sess.sid, "PIN_INJECT", "DENIED", field="PIN", payload="REDACTED", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
            return
        sess.fields["PIN"] = value[:4]
        sess.last_message = "PIN VALUE INJECTED"
        store.log("CICS", sess.sid, "PIN_INJECT", "OK", field="PIN", payload="REDACTED", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
        return
    if c.startswith("BRUTE FORCE PIN") or c.startswith("BRUTE PIN"):
        sess.screen = "MCAD"
        if not sess.hack.get("enabled", False):
            sess.last_message = "BRUTE FORCE PIN REQUIRES HACK ON"
            store.log("CICS", sess.sid, "PIN_BRUTE_START", "DENIED", field="PIN", payload="requires HACK ON", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
            return
        if not vulnerable:
            sess.last_message = "BRUTE FORCE PIN BLOCKED IN SECURE MODE - LOCKOUT/RATE LIMIT ACTIVE"
            store.log("CICS", sess.sid, "PIN_BRUTE_START", "DENIED", field="PIN", payload="secure mode", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
            return
        # Bounded educational PIN-file simulation.  A real deployment can bind
        # this to an OMVS/TSO dataset; here we parse inline PINFILE= candidates
        # or use a deterministic demo list that visibly walks the PIN field.
        candidates = []
        if "PINFILE=" in c:
            raw = c.split("PINFILE=", 1)[1].strip()
            candidates = [x.strip()[:4] for x in raw.replace(",", " ").split() if x.strip() and not x.startswith("#")]
        candidates = _normalise_pin_candidates(store.state, candidates)
        store.log("CICS", sess.sid, "PIN_BRUTE_START", "OK", field="PIN", payload=f"candidates={len(candidates)}", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
        found = None
        for idx, pin in enumerate(candidates, 1):
            sess.fields["PIN"] = pin
            if idx in {1, len(candidates)} or idx % 10 == 0:
                store.log("CICS", sess.sid, "PIN_BRUTE_ATTEMPT", "OK", field="PIN", payload=f"attempt={idx};candidate=REDACTED", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
            if dvcapin.verify(store.state, pin):
                found = idx
                break
        if found:
            sess.fields["PIN"] = dvcapin.active_training_pin(store.state)
            sess.last_message = f"PIN COUNTER FOUND TRAINING PIN AFTER {found} ATTEMPTS"
            store.log("CICS", sess.sid, "PIN_BRUTE_SUCCESS", "FOUND", field="PIN", payload=f"attempts={found};pin=REDACTED", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
        else:
            sess.last_message = f"PIN COUNTER EXHAUSTED {len(candidates)} ATTEMPTS - NOT FOUND"
            store.log("CICS", sess.sid, "PIN_BRUTE_FAILURE", "DENIED", field="PIN", payload=f"attempts={len(candidates)}", screen=sess.screen, scenario="HARDCODED_PIN", user=sess.user)
        return
    if c == "RESET DVCA":
        sess.screen = "MCGM"; sess.fields.clear(); sess.last_message = "DVCA SESSION RESET"; return
    if c == "HELP HACK":
        sess.screen = "HELP"; sess.last_message = "HACK COMMANDS: HACK ON/OFF, SHOW HIDDEN, DISABLE PROTECTION, PIN <DVCAPIN>, BRUTE FORCE PIN"; return

    if a in {"PF1","F1"} or c in {"PF1","F1","HELP","H"}: sess.screen="HELP"; sess.last_message="HELP REQUESTED"; return
    if a in {"PF10","F10"} or c in {"PF10","F10","INSTRUCTIONS","INSTR"}: sess.screen="HELP"; sess.last_message="INSTRUCTIONS REQUESTED - DVCA, HACK ON/OFF, CBSA AND CEMT TRAINING"; store.log("CICS", sess.sid, "CICS_INSTRUCTIONS_VIEWED", "OK", screen=sess.screen, scenario="INSTRUCTIONS", user=sess.user); return
    if a in {"PF3","F3"} or c in {"PF3","F3","END","QUIT"}: sess.screen="MCGM"; sess.last_message="RETURNED TO DVCA SPLASH"; return
    if a in {"PF5","F5"} or c in {"PF5","F5","MENU"}: sess.screen="MCMM"; sess.last_message="MAIN MENU"; return
    if a == "PA3" or c == "PA3":
        if vulnerable and store.scenarios.get("PA3_SECRET", True):
            sess.screen="SCRT"; sess.last_message="PA3 AID ACCEPTED - SECRET PATH"; store.log("CICS", sess.sid, "PA3_SECRET", "OK", screen=sess.screen, scenario="PA3_SECRET", user=sess.user)
        else:
            sess.last_message="PA3 SECRET PATH BLOCKED IN SECURE MODE"; store.log("CICS", sess.sid, "PA3_SECRET", "DENIED", screen=sess.screen, scenario="PA3_SECRET", user=sess.user)
        return
    if sess.screen == "MCGM": sess.screen="MCMM"; sess.last_message="MAIN MENU"; return
    if sess.screen == "MCMM":
        submitted = str((fields or {}).get("SELECT", "")).strip()
        sel = c or submitted.upper() or sess.fields.get("SELECT", "").upper()
        if sel == "1": sess.screen="MCOR"; sess.last_message="ORDER SCREEN"; return
        if sel == "2": sess.screen="MCAD"; sess.last_message="ADDRESS SCREEN"; return
        if sel == "3": sess.screen="MCHI"; sess.last_message="HISTORY"; return
        if sel == "99":
            if vulnerable and store.scenarios.get("HIDDEN_OPTION_99", True):
                store.history.clear(); sess.last_message="HIDDEN OPTION 99 ACCEPTED - HISTORY DELETED"; store.log("CICS", sess.sid, "HIDDEN_OPTION_99", "OK", payload=sel, screen="MCMM", scenario="HIDDEN_OPTION_99", user=sess.user)
            else:
                sess.last_message="OPTION 99 BLOCKED IN SECURE MODE"; store.log("CICS", sess.sid, "HIDDEN_OPTION_99", "DENIED", payload=sel, screen="MCMM", scenario="HIDDEN_OPTION_99", user=sess.user)
            return
        if sel in {"H","HELP"}: sess.screen="HELP"; sess.last_message="HELP"; return
        sess.last_message="INVALID SELECTION"; return
    if sess.screen == "MCOR":
        keys = sorted(store.products)
        if a in {"PF8","F8"} or c in {"PF8","F8","DOWN","NEXT"}:
            if sess.catalog_index < len(keys) - 1:
                sess.catalog_index += 1; sess.last_message = "SCROLLED FORWARD"
            else:
                sess.last_message = "END OF CATALOG"
            sess.fields["ITEM"] = keys[sess.catalog_index]
            return
        if a in {"PF7","F7"} or c in {"PF7","F7","UP","PREV"}:
            if sess.catalog_index > 0:
                sess.catalog_index -= 1; sess.last_message = "SCROLLED BACKWARD"
            else:
                sess.last_message = "TOP OF CATALOG"
            sess.fields["ITEM"] = keys[sess.catalog_index]
            return
        if c.isdigit():
            want = c.zfill(5)
            if want in store.products:
                sess.catalog_index = keys.index(want)
        item = sess.fields.get("ITEM", keys[sess.catalog_index] if keys else "00001").zfill(5); p = store.products.get(item)
        if not p: sess.last_message="ITEM NOT FOUND"; store.log("CICS", sess.sid, "ORDER", "NOTFND", payload=item, screen="MCOR", user=sess.user); return
        sess.fields["ITEM"] = item
        buy = sess.fields.get("BUY", "N").upper(); canbuy = sess.fields.get("CANBUY", p.get("canbuy", "N")).upper(); price = sess.fields.get("PRICE", p["price"]); ship = sess.fields.get("SHIP", p["shipping"])
        if buy == "Y":
            legit = p.get("canbuy") == "Y"
            override = bool(vulnerable and canbuy == "Y" and store.scenarios.get("HIDDEN_CANBUY_BYPASS", True))
            if not legit and not override:
                sess.last_message="PURCHASE BLOCKED - ITEM IS NOT OFFICE SUPPLY"; store.log("CICS", sess.sid, "BUY", "DENIED", field="CANBUY", payload=item, screen="MCOR", scenario="HIDDEN_CANBUY_BYPASS", user=sess.user); return
            if not vulnerable: price = p["price"]; ship = p["shipping"]
            store.history.append({"item": item, "name": p["name"], "price": price, "shipping": ship, "status": "ORDERED"})
            if legit:
                # Genuine office-supply purchase - no protection bypass involved.
                sess.last_message=f"ORDER ACCEPTED ITEM {item} PRICE {price} SHIP {ship}"
                store.log("CICS", sess.sid, "BUY", "OK", field="PRICE/SHIP/CANBUY", payload=f"{item} {price} {ship} {canbuy}", screen="MCOR", scenario="OFFICE_SUPPLY_PURCHASE", user=sess.user)
            else:
                # Restricted item bought by overriding the protected CANBUY flag.
                # Primary path: a genuine hack3270 injection of Y into the wire
                # field. Secondary path: the CANBUY=Y command shortcut. Both are
                # honoured but logged distinctly so the audit trail is unambiguous.
                src = getattr(sess, "_field_source", {}).get("CANBUY")
                via = sess.hack.get("canbuy_via") or ("command" if src == "command" else "hack3270")
                if via == "hack3270":
                    scenario, label = "FIELD_INJECTION_BYPASS", "FIELD INJECTION via hack3270"
                else:
                    scenario, label = "HACK_COMMAND_BYPASS", f"CANBUY={canbuy} command override"
                sess.last_message=f"ORDER ACCEPTED ITEM {item} PRICE {price} SHIP {ship} ({label})"
                store.log("CICS", sess.sid, "BUY", "OK", field="PRICE/SHIP/CANBUY", payload=f"{item} {price} {ship} CANBUY={canbuy} via={via}", screen="MCOR", scenario=scenario, user=sess.user)
            return
        sess.last_message="ENTER BUY=Y TO PURCHASE"; return
    if sess.screen == "MCAD":
        pin = sess.fields.get("PIN", "")
        if vulnerable and dvcapin.verify(store.state, pin):
            for k in ["NAME","LINE1","LINE2","POSTCODE"]:
                if k in sess.fields: store.address[k.lower() if k != "POSTCODE" else "postcode"] = sess.fields[k]
            sess.last_message="ADDRESS UPDATED WITH SUPERVISOR PIN"; store.log("CICS", sess.sid, "PIN_UPDATE", "OK", field="PIN", payload="PIN REDACTED", screen="MCAD", scenario="HARDCODED_PIN", user=sess.user)
        else:
            sess.last_message="ADDRESS UPDATE DENIED - INVALID OR SECURE AUTHORIZATION"; store.log("CICS", sess.sid, "PIN_UPDATE", "DENIED", field="PIN", payload="PIN REDACTED", screen="MCAD", scenario="HARDCODED_PIN", user=sess.user)
