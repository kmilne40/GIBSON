from __future__ import annotations

from typing import Any
from gibson.apps.racf_admin import get_racf_store, racf_admin_command

MENU = """RACF - SERVICES OPTION MENU
OPTION ===>

SELECT ONE OF THE FOLLOWING:

 1  DATA SET PROFILES
 2  GENERAL RESOURCE PROFILES
 3  GROUP PROFILES AND USER-TO-GROUP CONNECTIONS
 4  USER PROFILES AND YOUR OWN PASSWORD
 5  SYSTEM OPTIONS
 6  REMOTE SHARING FACILITY
 7  DIGITAL CERTIFICATES, KEY RINGS, AND TOKENS
 8  AUDIT REPORTS (IRRADU00 / IRRDBU00 UNLOAD)
99  EXIT

PF1=HELP  PF3=END  PF12=CANCEL"""

USER_MENU = """RACF - USER PROFILE SERVICES
OPTION ===>
USER   ===>

SELECT ONE OF THE FOLLOWING:

 1  ADD
 2  CHANGE
 3  DELETE
 4  PASSWORD
 5  AUDIT
 D  DISPLAY
 8  DISPLAY
 S  SEARCH
 9  SEARCH

PF1=HELP  PF3=END  PF12=CANCEL"""

SYSTEM_MENU = """RACF - SYSTEM SECURITY OPTIONS MENU
OPTION ===>

SELECT ONE OF THE FOLLOWING:

 1  DISPLAY                  Display current SETROPTS status
 2  AUDIT                    Set auditing options
 3  CLASS OPTIONS            Set class-related options
 4  PASSWORD                 Set password control options
 5  OTHER OPTIONS            Set other system security options
 6  REFRESH                  Refresh in-storage information
 7  LANGUAGE                 Set default national languages
 8  KERBLVL                  Set level of Kerberos processing

PF1=HELP  PF3=END  PF12=CANCEL"""

def render_racf_services_menu() -> str:
    return MENU

def _profile_table(state: Any, cls: str) -> str:
    if cls == 'PTKTDATA':
        try:
            from gibson.core.passticket import get_passticket_service
            rows = get_passticket_service(state).profile_rows()
            lines = ['RACF - GENERAL RESOURCE PROFILES - PTKTDATA', 'APPLID     REPLAY APPLCHK  LABLEAK VALIDSECS KEYMASKED', '-' * 72]
            for r in rows:
                lines.append(f"{r['PROFILE']:<10} {r['REPLAY']:<6} {r['APPLCHK']:<8} {r['LABLEAK']:<7} {r['VALIDSECS']:<8} {r['KEYMASKED']}")
            return '\n'.join(lines)
        except Exception:
            return 'RACF - GENERAL RESOURCE PROFILES - PTKTDATA\nNO LIVE PASSTICKET SERVICE AVAILABLE'
    st = get_racf_store(state)
    lines = [f'RACF SERVICES - {cls} PROFILES', 'PROFILE                         UACC     PERMITS', '-' * 72]
    for prof, data in sorted(st.profiles.get(cls, {}).items()):
        permits = ', '.join(f'{k}({v})' for k, v in sorted(data.get('PERMITS', {}).items())) or 'NONE'
        lines.append(f"{prof:<31} {data.get('UACC','NONE'):<8} {permits}")
    if len(lines) == 3: lines.append('NO PROFILES DEFINED')
    return '\n'.join(lines)

def _user_services(state: Any, userid: str, choice: str) -> str:
    if not choice or choice in {'MENU','?','HELP'}: return USER_MENU
    parts=choice.split()
    op=parts[0].upper(); user=(parts[1].upper() if len(parts)>1 else userid.upper())
    if op in {'D','8','DISPLAY'}: return racf_admin_command(state, userid, f'RACFADMIN LISTUSER {user}') or 'NO USER DATA'
    if op in {'S','9','SEARCH'}: return racf_admin_command(state, userid, 'RACFADMIN LISTUSER *') or 'NO USER DATA'
    if op in {'1','ADD'}: return racf_admin_command(state, userid, f'RACFADMIN ADDUSER {user} NAME(Training User) DFLTGRP(STUDENT) PASSWORD(PASS123)') or 'ADDUSER NOT AVAILABLE'
    if op in {'2','CHANGE'}: return racf_admin_command(state, userid, f'RACFADMIN ALTUSER {user} OMVS(UID(10077))') or 'ALTUSER NOT AVAILABLE'
    if op in {'3','DELETE'}: return racf_admin_command(state, userid, f'RACFADMIN DELUSER {user}') or 'DELUSER NOT AVAILABLE'
    if op in {'4','PASSWORD'}: return racf_admin_command(state, userid, f'RACFADMIN ALTUSER {user} PASSWORD(PASS123)') or 'PASSWORD CHANGE NOT AVAILABLE'
    if op in {'5','AUDIT'}: return racf_admin_command(state, userid, f'RACFADMIN ALTUSER {user} UAUDIT') or 'AUDIT CHANGE NOT AVAILABLE'
    return USER_MENU + f'\n\nINVALID USER PROFILE OPTION {choice}'

def _system_services(state: Any, userid: str, choice: str) -> str:
    if not choice or choice in {'MENU','?','HELP'}: return SYSTEM_MENU
    op=choice.split()[0].upper()
    if op in {'1','DISPLAY'}: return racf_admin_command(state, userid, 'RACFADMIN SETROPTS LIST') or 'SETROPTS DISPLAY NOT AVAILABLE'
    if op in {'2','AUDIT'}: return 'RACF - SYSTEM AUDIT OPTIONS\nGLOBALAUDIT: SELECTED CLASSES AUDITED\nSMF80: ACTIVE\nCOMMAND EQUIVALENT: SETROPTS AUDIT(class)'
    if op in {'3','CLASS'}: return 'RACF - CLASS OPTIONS\nACTIVE: DATASET FACILITY APPL PTKTDATA SURROGAT OPERCMDS JESSPOOL STARTED\nCOMMAND EQUIVALENT: SETROPTS CLASSACT(class) RACLIST(class)'
    if op in {'4','PASSWORD'}: return 'RACF - PASSWORD CONTROL OPTIONS\nMIXED CASE: ACTIVE\nREVOKE AFTER: 5 UNSUCCESSFUL ATTEMPTS\nPASSWORD INTERVAL: 90 DAYS'
    if op in {'5','OTHER'}: return 'RACF - OTHER SYSTEM SECURITY OPTIONS\nGENERICOWNER: ACTIVE\nPROTECTALL: WARNING\nERASE: SIMULATED'
    if op in {'6','REFRESH'}: return racf_admin_command(state, userid, 'RACFADMIN SETROPTS RACLIST REFRESH') or 'ICH70001I RACLIST REFRESH COMPLETE'
    if op in {'7','LANGUAGE'}: return 'RACF - LANGUAGE OPTIONS\nDEFAULT LANGUAGE: ENU\nNATIONAL LANGUAGE SUPPORT: SIMULATED'
    if op in {'8','KERBLVL'}: return 'RACF - KERBEROS PROCESSING\nKERBLVL: 2\nKERBSEG: SIMULATED'
    return SYSTEM_MENU + f'\n\nINVALID SYSTEM OPTION {choice}'

def _owns_racf_services_command(u: str) -> bool:
    if u in {'RACFSERV','RACF SERVICES','RACF SERVICES MENU','RACFMENU'}:
        return True
    if u.startswith('RACFSERV '):
        return True
    if u == 'RACFUSER' or u.startswith('RACFUSER '):
        return True
    if u == 'RACFSYS' or u.startswith('RACFSYS '):
        return True
    return False


def racf_services_command(state: Any, userid: str, cmd: str) -> str | None:
    """Handle explicit RACF Services commands only.

    RACFBLOCKER root cause: earlier builds returned the RACF Services menu for
    every unrecognised command.  Because this handler is called early by the
    TSO command processor, that hijacked HELP, LISTUSER, NETSTAT, SUBMIT, OMVS,
    SDSF, DB2, PassTicket, zSecure, and PF-key commands.  A global command
    handler must return None unless it owns the command.  Invalid panel input
    belongs in the active RACF ISPF panel controller, not here.
    """
    raw=(cmd or '').strip(); u=raw.upper()
    if not _owns_racf_services_command(u):
        return None
    if u.startswith('RACFUSER'):
        return _user_services(state, userid, raw[len('RACFUSER'):].strip())
    if u.startswith('RACFSYS'):
        return _system_services(state, userid, raw[len('RACFSYS'):].strip())
    choice = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1))>1 else 'MENU'
    cu=choice.upper()
    if cu in {'MENU','HELP','?'}: return MENU
    if cu in {'1','DATASET','DATA SET'}: return _profile_table(state, 'DATASET') + '\n\nCommands: RACFUSER, RACFSYS, RACFADMIN ADDSD LISTDSD PERMIT'
    if cu in {'2','GENERAL','RESOURCE'}:
        classes=['FACILITY','OPERCMDS','APPL','SURROGAT','PTKTDATA','STARTED','JESJOBS','JESSPOOL']
        return '\n\n'.join(_profile_table(state, c) for c in classes)
    if cu in {'3','GROUP','GROUPS'}: return 'RACF - GROUP PROFILES AND USER-TO-GROUP CONNECTIONS\n\n' + (racf_admin_command(state, userid, 'RACFADMIN LISTGRP *') or 'NO GROUP DATA') + '\n\nCommands: CONNECT userid GROUP(group), REMOVE userid GROUP(group)'
    if cu in {'4','USER','USERS'}: return USER_MENU
    if cu in {'5','SYSTEM','SETROPTS'}: return SYSTEM_MENU
    if cu in {'6','RSF','RRSF','REMOTE'}: return 'RACF - REMOTE SHARING FACILITY\n\nNODE     STATUS              TRUST\nMVSC     ACTIVE              LOCAL\nLAB2     SIMULATED-OFFLINE   PENDING\n\nCOMMANDS: RDEFINE RRSFDATA, RLIST RRSFDATA, TARGET NODE(node)' 
    if cu in {'7','DIGTCERT','CERT','CERTS'}: return 'RACF - DIGITAL CERTIFICATES, KEY RINGS, AND TOKENS\n\n' + (racf_admin_command(state, userid, 'RACFADMIN RACDCERT') or 'LABEL              OWNER     STATUS\nGIBSON-TLS-CERT    IBMUSER   TRUSTED\nFIBS-APP-CERT      FIBSADM   TRUSTED')
    if cu in {'8','AUDIT','REPORTS','UNLOAD'}:
        try:
            from gibson.core.racf_database import export_irradu00, export_irrdbu00
            adu = export_irradu00(state).splitlines()[1]
            dbu = export_irrdbu00(state).splitlines()[0]
        except Exception:
            adu = dbu = ""
        return ("RACF - AUDIT AND DATABASE UNLOAD REPORTS\n\n"
                " IRRADU00  Unload the RACF SMF audit trail (type 80) to a flat file\n"
                "           for review in a SIEM or with DFSORT/ICETOOL.\n"
                " IRRDBU00  Unload the RACF database (users/groups/profiles) - no\n"
                "           password hashes - for offline analysis.\n\n"
                f" {adu}\n {dbu}\n\n"
                "Commands: IRRADU00 OUTDATASET(your.audit.unload)\n"
                "          IRRDBU00 OUTDATASET(your.db.unload)")
    if cu in {'99','X','EXIT','END'}: return 'RACF SERVICES ENDED'
    return MENU + f'\n\nINVALID OPTION {choice}'
