from __future__ import annotations
import hashlib, time
from gibson.core.passticket import get_passticket_service


def _arg(args, names, default=''):
    for i,a in enumerate(args):
        u=a.upper()
        if u in names and i+1 < len(args): return args[i+1]
        for n in names:
            if u.startswith(n+'='): return a.split('=',1)[1]
    return default


def genptkt_command(state, userid: str, args: list[str]) -> str:
    if not args or any(a.upper() in {'HELP','?','-H','--HELP'} for a in args):
        return 'genptkt - Generate simulated RACF PassTicket\nSyntax: genptkt -u USER -a APPL [--key HEX]\nExample: genptkt -u IBMUSER -a CICS'
    user=(_arg(args, {'-U','--USER','USER'}, userid) or userid).upper()
    appl=(_arg(args, {'-A','--APPL','APPL'}, 'CICS') or 'CICS').upper()
    svc=get_passticket_service(state)
    res=svc.generate(user, appl, userid, source='OMVS')
    tok=res.get('ticket') or res.get('passticket') or res.get('TOKEN') or res.get('value') or hashlib.sha1(f'{user}:{appl}:{int(time.time())}'.encode()).hexdigest()[:8].upper()
    return f'IRRPT100I PASSTICKET GENERATED\nUSER={user}\nAPPL={appl}\nPASSTICKET={tok}\nNOTE: Gibson simulated PassTicket; use PTKTUSE or application login to validate.'


def unmaskptkt_command(state, userid: str, args: list[str]) -> str:
    if not args or any(a.upper() in {'HELP','?','-H','--HELP'} for a in args):
        return 'unmaskptkt - Demonstrate KEYMASKED PTKTDATA weakness in Gibson\nSyntax: unmaskptkt MASKEDKEY\nExample: unmaskptkt BBFCD18E826660B6'
    masked=args[0].strip().upper()
    if len(masked)!=16 or any(c not in '0123456789ABCDEF' for c in masked):
        return 'IRRPT207E MASKED KEY MUST BE 16 HEX CHARACTERS'
    # Training deterministic reverse mapping; this is not a real host operation.
    plain=''.join('0123456789ABCDEF'['FEDCBA9876543210'.find(c) % 16] if c in 'FEDCBA9876543210' else '0' for c in masked)
    return f'IRRPT200I KEYMASKED VALUE DECODED\nMASKED={masked}\nPLAINTEXT KEY={plain}\nTRAINING NOTE: vulnerable simulator demonstrates why PTKTDATA key protection matters.'


def parseptkt_command(state, userid: str, args: list[str]) -> str:
    if args and any(a.upper() in {'HELP','?','-H','--HELP'} for a in args):
        return 'parseptkt - List Gibson simulated RACF PTKTDATA profiles\nSyntax: parseptkt [dataset]\nExample: parseptkt SYS1.RACFDS'
    svc=get_passticket_service(state)
    try:
        rows=svc.profile_rows()
    except Exception:
        rows=[]
    lines=['Passtickets:','PROFILE/APPL            KEYMASKED        REPLAY  APPLCHK  VALIDSECS']
    for r in rows:
        lines.append(f"{r.get('PROFILE',''):<22} {str(r.get('KEYMASKED','')):<16} {str(r.get('REPLAY','')):<7} {str(r.get('APPLCHK','')):<8} {str(r.get('VALIDSECS',''))}")
    if len(lines)==2:
        lines.append('NO PTKTDATA PROFILES FOUND')
    return '\n'.join(lines)
