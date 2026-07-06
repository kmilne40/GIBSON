from __future__ import annotations
from gibson.apps.dvca.models import Screen, Field
from gibson.apps.dvca.store import DvcaSession, DvcaStore


def _empty() -> list[str]:
    return [" " * 80 for _ in range(24)]


def _put(lines: list[str], row: int, col: int, text: str) -> None:
    row = max(1, min(24, row)); col = max(1, min(80, col))
    base = list(lines[row-1])
    for i, ch in enumerate(str(text)):
        pos = col - 1 + i
        if 0 <= pos < 80:
            base[pos] = ch
    lines[row-1] = "".join(base)


def _base(lines: list[str]) -> list[str]:
    return [line[:80].ljust(80) for line in lines]


def mcgm(sess: DvcaSession, store: DvcaStore) -> Screen:
    return Screen("MCGM", "Mel's Cargo", _base([
        "MCGM", "", "           __  __      _   ____",
        r"          |  \/  | ___| | / ___|__ _ _ __ __ _  ___",
        r"          | |\/| |/ _ \ | | |   / _` | APP MENU",
        r"          | |  | |  __/ | | |__| (_| | | | (_| | (_) |",
        r"          |_|  |_|\___|_|  \____\__,_|_|  \__, |\___/",
        "                                           |___/",
        "        ================================================",
        "        | DAMN VULNERABLE CICS APPLICATION (DVCA)       |",
        "        | Mel's Cargo - Office Supply Store             |",
        "        ================================================", "",
        "              Transaction: DVCA", "",
        "        PF1 - Help          PF3 - Quit",
        "        PF5 - Main Menu     PA3 - Secret",
        "        PRESS PF5 TO ENTER MEL'S CARGO MAIN MENU",
    ]), message=sess.last_message or "PA3 IS NOT A STANDARD KEYBOARD KEY - USE HACK3270 TO INJECT AID")


def menu(sess: DvcaSession, store: DvcaStore) -> Screen:
    lines = _empty()
    _put(lines, 1, 1, "DVCA - MEL'S CARGO MAIN MENU")
    _put(lines, 4, 5, "1  ORDER OFFICE SUPPLIES")
    _put(lines, 5, 5, "2  UPDATE SHIPPING ADDRESS")
    _put(lines, 6, 5, "3  VIEW ORDER HISTORY")
    _put(lines, 7, 5, "H  HELP")
    # Hidden option 99 is deliberately not printed in normal terminal rendering.
    _put(lines, 12, 5, "PF1 Help   PF3 Quit   PF5 Main Menu   PA3 Secret")
    _put(lines, 20, 1, "Selection ===>")
    fields = [
        Field("SELECT", 20, 17, 2, sess.fields.get("SELECT", ""), source="MCMENU.bms"),
        Field("OPT99", 9, 5, 2, "99", protected=True, hidden=True, source="MCMENU.bms"),
    ]
    return Screen("MCMM", "DVCA Main Menu", lines, fields=fields, message=sess.last_message)


def orders(sess: DvcaSession, store: DvcaStore) -> Screen:
    keys = sorted(store.products)
    if keys:
        sess.catalog_index = max(0, min(getattr(sess, "catalog_index", 0), len(keys)-1))
        item = sess.fields.get("ITEM") or keys[sess.catalog_index]
        if item in store.products:
            sess.catalog_index = keys.index(item)
    else:
        item = "00001"
    p = store.products.get(item, store.products.get("00001", {}))
    page = f"{sess.catalog_index + 1}/{max(1, len(keys))}"
    lines = _empty()
    _put(lines, 1, 1, "DVCA - MEL'S CARGO ORDER SCREEN")
    _put(lines, 3, 1, "Enter item number and BUY=Y to purchase.   PF7/PF8 scroll catalog.")
    _put(lines, 4, 1, "Catalog page      :")
    _put(lines, 6, 1, "Item number       :")
    _put(lines, 8, 1, "Description       :")
    _put(lines, 9, 1, "Price             :")
    _put(lines, 11, 1, "Shipping          :")
    _put(lines, 15, 1, "Can buy hidden    :")
    _put(lines, 20, 1, "Buy item (Y/N)    :")
    _put(lines, 22, 1, "PF1 Help  PF3 Back  PF5 Menu  PF7 Up  PF8 Down  ENTER Process")
    hack = bool(sess.hack.get("enabled", False))
    price = sess.fields.get("PRICE", p.get("price", "")) if hack else p.get("price", "")
    ship = sess.fields.get("SHIP", p.get("shipping", "")) if hack else p.get("shipping", "")
    canbuy = sess.fields.get("CANBUY", p.get("canbuy", "N")) if hack else p.get("canbuy", "N")
    fields = [
        Field("PAGE", 4, 21, 5, page, protected=True, source="MCORDER.bms"),
        Field("ITEM", 6, 21, 5, item, numeric=True, source="MCORDER.bms"),
        Field("NAME", 8, 21, 35, p.get("name", ""), protected=True, source="MCORDER.bms"),
        Field("PRICE", 9, 20, 35, price, protected=True, numeric=True, mdt=True, fset=True, source="MCORDER.bms"),
        Field("SHIP", 11, 20, 35, ship, protected=True, numeric=True, mdt=True, fset=True, source="MCORDER.bms"),
        Field("CANBUY", 15, 20, 1, canbuy, protected=True, hidden=True, mdt=True, fset=True, source="MCORDER.bms"),
        Field("BUY", 20, 19, 1, sess.fields.get("BUY", "N"), source="MCORDER.bms"),
    ]
    return Screen("MCOR", "Order Screen", lines, fields=fields, message=sess.last_message)


def address(sess: DvcaSession, store: DvcaStore) -> Screen:
    a = store.address
    lines = _empty()
    _put(lines, 1, 1, "DVCA - ADDRESS UPDATE")
    _put(lines, 3, 1, "Supervisor PIN required to update address.")
    _put(lines, 6, 1, "Name              :")
    _put(lines, 8, 1, "Address line 1    :")
    _put(lines, 10, 1, "Address line 2    :")
    _put(lines, 14, 1, "Postcode          :")
    _put(lines, 18, 1, "Supervisor PIN    :")
    _put(lines, 22, 1, "PF3 Back  PF5 Menu  ENTER Update")
    return Screen("MCAD", "Address", lines, fields=[
        Field("NAME", 6, 23, 44, a["name"], source="MCADDR.bms"),
        Field("LINE1", 8, 23, 44, a["line1"], source="MCADDR.bms"),
        Field("LINE2", 10, 23, 44, a["line2"], source="MCADDR.bms"),
        Field("POSTCODE", 14, 23, 44, a["postcode"], source="MCADDR.bms"),
        Field("PIN", 18, 23, 4, sess.fields.get("PIN", "####"), numeric=True, masked=("PIN" not in sess.fields), mdt=True, fset=True, source="MCADDR.bms"),
    ], message=sess.last_message)


def history(sess: DvcaSession, store: DvcaStore) -> Screen:
    lines = ["DVCA - ORDER HISTORY", "", "Current order history records:", ""]
    for i, h in enumerate(store.history[:12], 1):
        lines.append(f" {i:02d} {h.get('item',''):<5} {h.get('name','')[:28]:<28} {h.get('price',''):>10} {h.get('status','')}")
    lines += ["", "PF3 Back  PF5 Menu"]
    return Screen("MCHI", "History", _base(lines), message=sess.last_message)


def help_screen(sess, store):
    return Screen("HELP", "Help", _base([
        "CICS / DVCA / CBSA INSTRUCTIONS",
        "DVCA HELP",
        "",
        "DVCA teaches 3270 protected-field tampering and CICS BMS trust issues.",
        "Use HACK ON then SHOW HIDDEN/DISABLE PROTECTION to reveal lab fields.",
        "In HACK ON, edits to BUY, PRICE, SHIP and CANBUY are repainted after ENTER.",
        "CBSA/CBPP teaches pre-auth bypass, PA-key handling and COBOL/CICS flaws.",
        "CEMT/CEDA/CECI/CEDF/CEBR/CSMT are CICS-supplied transaction simulations.",
        "Evidence can be reviewed in CICS logs, SDSF/SMF, zSecure and dashboards.",
        "",
        "PF3 Back  PF5 Menu  PF10 Instructions"
    ]), message=sess.last_message)


def secret(sess, store):
    return Screen("SCRT", "Secret", _base(["DVCA SECRET SCREEN", "", "You reached the hidden PA3/SCRT path.", "This is a simulated training finding, not a real host escape.", "", "DFHAC2001 SECRET TRAINING PATH REACHED", "", "PF3 Back  PF5 Menu"]), message=sess.last_message)


def screen_for(sess: DvcaSession, store: DvcaStore) -> Screen:
    return {"MCGM": mcgm, "MCMM": menu, "MCOR": orders, "MCAD": address, "MCHI": history, "HELP": help_screen, "SCRT": secret}.get(sess.screen, mcgm)(sess, store)
