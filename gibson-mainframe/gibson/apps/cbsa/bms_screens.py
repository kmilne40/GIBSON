def panel(title, lines, status=""):
    body=["\x1b[2J", f"{status[:79]:<79}", f"{title[:79]:<79}", " "*79]
    overlay = "FIELD LEGEND" in (status or "").upper() or "HACK" in (status or "").upper() or "TRAINING" in title.upper()
    src_lines = list(lines)
    if overlay:
        # Right-side training overlay: compact 80x24 safe version. HACK/Training mode uses RED labels.
        legend = ["UNPROTECTED: RED", "PROTECTED  : BLUE", "HIDDEN     : AMBER"]
        for idx, val in enumerate(legend):
            if idx < len(src_lines):
                base = src_lines[idx][:50].ljust(50) + val
                src_lines[idx] = base[:79]
            else:
                src_lines.append(" "*50 + val)
    for line in src_lines: body.append(f"{line[:79]:<79}")
    while len(body)<22: body.append(" "*79)
    body.append("PF 1 HELP       3 END       5 UPDATE       10 APPLY       ENTER PROCESS")
    return "\n".join(body)+"\n"

def main_menu(status=""):
    return panel("CBSA MAIN MENU - CICS BANKING SAMPLE APPLICATION", [
        "  1 DISPLAY CUSTOMER",
        "  2 DISPLAY ACCOUNT",
        "  A LIST ACCOUNTS FOR CUSTOMER",
        "  3 CREATE CUSTOMER        Syntax: 3 NAME=<name>",
        "  4 CREATE ACCOUNT         Syntax: 4 CUSTOMER=<id> BALANCE=<amount>",
        "  5 UPDATE CUSTOMER        Syntax: 5 CUSTOMER=<id> NAME=<name>",
        "  6 CREDIT/DEBIT ACCOUNT   Syntax: 6 ACCOUNT=<acct> AMOUNT=<signed>",
        "  7 TRANSFER FUNDS         Syntax: 7 FROM=<acct> TO=<acct> AMOUNT=<amount>",
        "  8 DELETE ACCOUNT         Syntax: 8 ACCOUNT=<acct>",
        "  V CBSA SECURITY TRAINING MODE",
        "  B BRUTE FORCE PIN          Syntax: B DATASET=GUEST.4CHAR.PIN",
        "",
        "Examples: 1 1001    2 00000101    A 1001",
    ], status or "OMEN READY")


def main_menu_screenbuffer(status=""):
    """Fielded CBSA/OMEN menu used by Operation 3270 Fidelity tests."""
    from gibson.render.screen3270 import ScreenBuffer
    from gibson.render import colors
    s = ScreenBuffer()
    s.put(1,1,(status or "OMEN READY")[:79], colors.GREEN)
    s.put(2,1,"CBSA MAIN MENU - CICS BANKING SAMPLE APPLICATION", colors.BLUE)
    s.put(4,1,"Option ===>", colors.BLUE)
    s.add_field("OPTION",4,13,12,value="",protected=False,color=colors.RED,role="cics_option",tab_order=1)
    rows=["1 DISPLAY CUSTOMER", "2 DISPLAY ACCOUNT", "A LIST ACCOUNTS FOR CUSTOMER", "3 CREATE CUSTOMER", "4 CREATE ACCOUNT", "5 UPDATE CUSTOMER", "6 CREDIT/DEBIT ACCOUNT", "7 TRANSFER FUNDS", "8 DELETE ACCOUNT", "V CBSA SECURITY TRAINING MODE"]
    for i,line in enumerate(rows,6):
        s.put(i,3,line,colors.TURQUOISE)
    s.put(24,1,"PF1 HELP       3 END       5 UPDATE       10 APPLY       ENTER PROCESS", colors.BLUE)
    s.set_cursor_field("OPTION")
    return s
