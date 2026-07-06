"""Operation Summer Guest - CTF seed (activated by the --ctf start flag).

Injects the CTF users, clue datasets, fail-open / writable-APF vulnerabilities
and the DARVADER crackable credential into a freshly-created GibsonState. Every
step is defensive (its own try/except + log line) so a single failure can never
abort startup; whatever seeds, seeds.

Passwords: IBMUSER/SYS1  GUEST/SUMMER26  KEVIN01/KEVIN01  SYSPROG/SYSPROG
           DARVADER/STARWARS    (NJE node ORAC password ORACPW)
"""
from __future__ import annotations


def _log(msg: str) -> None:
    print(f"GIBSON-CTF: {msg}")


def seed_ctf(state) -> None:
    _log("seeding Operation Summer Guest CTF ...")
    racf = state.racf

    # ---- 1. Users -------------------------------------------------------
    def ensure(uid: str, pw: str, *, special: bool = False, ops: bool = False, omvs: bool = True) -> None:
        try:
            if not racf.exists(uid):
                racf.adduser(uid, pw, special=special, omvs=omvs, default_group="SYS1")
            u = racf.get(uid)
            if u is not None:
                # Store the PLAINTEXT password: verify_password accepts it and the
                # RACFDS materialiser needs it to compute the legacy DES hash.
                u.password = pw
                attrs = {a.upper() for a in (getattr(u, "attributes", []) or [])}
                attrs.discard("SPECIAL"); attrs.discard("OPERATIONS")
                if special:
                    attrs.add("SPECIAL")
                if ops:
                    attrs.add("OPERATIONS")
                u.attributes = sorted(attrs)
                try:
                    u.revoked = False
                except Exception:
                    pass
            _log(f"user {uid} ready ({'SPECIAL ' if special else ''}{'OPERATIONS' if ops else ''}".strip() + ")")
        except Exception as exc:
            _log(f"user {uid} FAILED: {exc}")

    ensure("GUEST", "SUMMER26", omvs=True)
    ensure("KEVIN01", "KEVIN01", omvs=True)
    ensure("SYSPROG", "SYSPROG", special=True, ops=True, omvs=True)
    ensure("DARVADER", "STARWARS", special=True, ops=True, omvs=True)

    # ---- 2. Clue datasets + wordlist -----------------------------------
    def write_ds(owner: str, dsname: str, text: str, *, pds: bool = False) -> None:
        try:
            base = dsname.split("(", 1)[0]
            try:
                if not state.datasets.exists(base):
                    state.datasets.allocate(owner, base, org="PO" if pds else "PS")
            except Exception:
                pass
            state.datasets.write(owner, dsname, text)
            _log(f"dataset {dsname} written")
        except Exception as exc:
            _log(f"dataset {dsname} FAILED: {exc}")

    write_ds("IBMUSER", "IBMUSER.ACLUE.TEXT",
             "A CLUE FOR THE CURIOUS.\n"
             "THIS ACCOUNT IS A KING WITH A PAUPER'S KEYS - YOU CAN SEE LITTLE.\n"
             "BUT SOME DOORS WERE LEFT ON THE LATCH. SEARCH FOR EVERY WARNING,\n"
             "MASKED OR NOT, AND READ WHAT THE CARELESS LEFT BEHIND.\n")
    write_ds("IBMUSER", "SYS1.CLUELIB(GUEST)",
             "BE MY GUEST THIS YEAR - IT'S A GREAT SUMMER.\n"
             "(the season and the year are your way in)\n", pds=True)
    write_ds("IBMUSER", "SYS2.CTF.APFLIB(ORACNOTE)",
             "FOUND IT - THIS AUTHORISED LIBRARY IS WRITABLE. NICE.\n"
             "NEXT: I WANT TO CONNECT TO ORAC (THE OTHER NJE NODE) AND GET THAT SET UP.\n"
             "KEVIN01 KNOWS THE LINK. SEND HIM A NOTE - ASK NICELY.\n", pds=True)
    write_ds("IBMUSER", "GIBSON.WORDLIST",
             "STARWARS\nSUMMER26\nSUMMER25\nPASSWORD\nWELCOME1\nVIPER1\nPASS123\nKEVIN01\nSYSPROG\n")

    # ---- 2b. IBMUSER becomes the weak foothold (AFTER the dataset writes,
    #          which need IBMUSER's default privilege) -----------------------
    try:
        u = racf.get("IBMUSER")
        if u is not None:
            u.attributes = []
        _log("IBMUSER weakened (no SPECIAL/OPERATIONS)")
    except Exception as exc:
        _log(f"IBMUSER weaken FAILED: {exc}")

    # ---- 3. Vulnerabilities: warning-mode clue + writable APF -----------
    try:
        state.dynamic_racf.define("DATASET", "SYS1.CLUELIB", "IBMUSER", "NONE", warning=True, volume="SBSYS1")
        state.dynamic_racf.define("DATASET", "SYS2.CTF.APFLIB", "IBMUSER", "UPDATE", volume="SBSYS1")
        try:
            state.dynamic_racf.permit("DATASET", "SYS2.CTF.APFLIB", "GUEST", "READ", save=False)
        except Exception:
            pass
        _log("profiles: SYS1.CLUELIB WARNING (fail-open), SYS2.CTF.APFLIB UACC(UPDATE) (writable)")
    except Exception as exc:
        _log(f"profiles FAILED: {exc}")

    # ---- 4. APF list ----------------------------------------------------
    try:
        if "SYS2.CTF.APFLIB" not in state.apf_libraries:
            state.apf_libraries.append("SYS2.CTF.APFLIB")
        _log("SYS2.CTF.APFLIB added to the APF list (D PROG,APF)")
    except Exception as exc:
        _log(f"APF list FAILED: {exc}")

    # ---- 5. DARVADER crackable + RACFDS materialise --------------------
    try:
        from gibson.core import racf_database as rdb
        rdb._cred_store(state)["DARVADER"] = rdb._make_credential(
            "DARVADER", "STARWARS", created_by="GIBSON", source_command="CTF-SEED")
        rdb.materialise_racfds(state)
        _log("DARVADER legacy-DES material recorded; SYS1.RACFDS materialised (racf2john-ready)")
    except Exception as exc:
        _log(f"RACFDS materialise FAILED: {exc}")

    # ---- 6. Win message queued for DARVADER ----------------------------
    try:
        state.pending_messages.setdefault("DARVADER", []).append(
            ("HMS", "Well Done! It's Game over!"))
        _log("win message queued for DARVADER logon")
    except Exception as exc:
        _log(f"win message FAILED: {exc}")

    _log("CTF seed complete.  IBMUSER/SYS1  GUEST/SUMMER26  KEVIN01/KEVIN01  "
         "SYSPROG/SYSPROG  DARVADER/STARWARS  (ORAC node pw ORACPW)")
