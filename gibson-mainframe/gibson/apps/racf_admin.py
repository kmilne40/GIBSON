from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def _opt(raw: str, key: str, default: str = "") -> str:
    m = re.search(rf"{key}\(([^)]*)\)", raw, re.I)
    if m:
        return m.group(1).strip().strip("'\"")
    m = re.search(rf"{key}=([^\s]+)", raw, re.I)
    return m.group(1).strip().strip("'\"") if m else default

@dataclass
class RacfSimStore:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    groups: dict[str, set[str]] = field(default_factory=dict)
    profiles: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    setropts: dict[str, str] = field(default_factory=lambda: {
        "GENERIC": "ACTIVE", "CLASSACT": "DATASET FACILITY CICS DSNR",
        "RACLIST": "FACILITY PTKTDATA STARTED", "PASSWORD": "MIXEDCASE MINLEN(8)",
        "MFA": "SIMULATED", "AUDIT": "FAILURES(READ) SUCCESS(UPDATE)"})
    changes: list[str] = field(default_factory=list)


def get_racf_store(state: Any) -> RacfSimStore:
    st = getattr(state, 'fibs_racf_store', None)
    if st is None:
        st = RacfSimStore()
        # Seed from repository where possible.
        try:
            for uid, rec in state.racf.users.items():
                attrs = set()
                if getattr(rec, 'special', False): attrs.add('SPECIAL')
                if getattr(rec, 'operations', False): attrs.add('OPERATIONS')
                if getattr(rec, 'auditor', False): attrs.add('AUDITOR')
                dflt = getattr(rec, 'default_group', 'SYS1') or 'SYS1'
                st.users[uid.upper()] = {
                    'USERID': uid.upper(), 'NAME': getattr(rec, 'name', uid.upper()),
                    'DFLTGRP': dflt.upper(), 'ATTRS': attrs,
                    'OMVS': {'UID': str(getattr(rec, 'uid', '') or '')},
                    'TSO': {}, 'CICS': {}, 'MFA': {'ENABLED': 'N'}, 'REVOKED': 'N'}
                st.groups.setdefault(dflt.upper(), set()).add(uid.upper())
        except Exception:
            pass
        for uid, attrs, grp in [('IBMUSER', {'SPECIAL','OPERATIONS'}, 'SYS1'), ('FIBSADM', {'SPECIAL'}, 'FIBS'), ('FIBSUSR', set(), 'FIBS'), ('TRAINEE', set(), 'STUDENT')]:
            st.users.setdefault(uid, {'USERID': uid, 'NAME': uid, 'DFLTGRP': grp, 'ATTRS': set(attrs), 'OMVS': {'UID': '1000'}, 'TSO': {}, 'CICS': {}, 'MFA': {'ENABLED': 'N'}, 'REVOKED': 'N'})
            st.groups.setdefault(grp, set()).add(uid)
        st.profiles.setdefault('DATASET', {'FIBS.**': {'UACC': 'NONE', 'PERMITS': {'FIBSADM': 'ALTER', 'FIBSUSR': 'READ'}}})
        st.profiles.setdefault('FACILITY', {'BPX.SERVER': {'UACC': 'NONE', 'PERMITS': {'IBMUSER': 'READ'}}})
        st.profiles.setdefault('CICS', {'FIBS.*': {'UACC': 'NONE', 'PERMITS': {'FIBSUSR': 'READ'}}})
        st.profiles.setdefault('DSNR', {'DB2A.FIBS.*': {'UACC': 'NONE', 'PERMITS': {'FIBSUSR': 'READ'}}})
        setattr(state, 'fibs_racf_store', st)
    return st


def _changed(state: Any, userid: str, action: str, detail: str) -> None:
    st = get_racf_store(state)
    row = f"{action}|{userid.upper()}|{detail}"
    st.changes.append(row)
    try:
        state.datasets.allocate(userid, 'FIBS.RACF.CHANGES', org='PS', recfm='VB', lrecl=512)
    except Exception: pass
    try:
        state.datasets.write(userid, 'FIBS.RACF.CHANGES', '\n'.join(st.changes) + '\n')
    except Exception: pass


def _menu() -> str:
    return '\n'.join([
        'RACF ADMINISTRATION - FIBS SECURITY SERVICES',
        '',
        '1  User administration        ADDUSER ALTUSER DELUSER LISTUSER',
        '2  Group administration       ADDGROUP LISTGRP CONNECT REMOVE',
        '3  Dataset profiles           ADDSD LISTDSD PERMIT',
        '4  General resources          RDEFINE RLIST PERMIT',
        '5  CICS resource security     CLASS(CICS)',
        '6  DB2 resource security      CLASS(DSNR)',
        '7  Started task profiles      CLASS(STARTED)',
        '8  SURROGAT and delegation    CLASS(SURROGAT)',
        '9  PassTicket / PTKTDATA      PTKTDATA profiles',
        'A  MFA administration         enable/disable simulated MFA',
        'B  Digital certificates       RACDCERT simulated panels',
        'C  SETROPTS options           CLASSACT RACLIST PASSWORD MFA',
        'D  Audit / SMF options        SMF80 and audit review',
        'E  Search / list profiles     SEARCH CLASS(class)',
        'F  Command shell              RACFADMIN <command>',
        'X  Exit',
    ])


def _list_user(st: RacfSimStore, uid: str) -> str:
    uid = uid.upper()
    if uid not in st.users:
        return f'ICH30001I USER {uid} NOT DEFINED'
    r = st.users[uid]
    attrs = ' '.join(sorted(r.get('ATTRS', set()))) or 'NONE'
    return '\n'.join([
        f'LISTUSER {uid}',
        f'USER={uid} NAME={r.get("NAME", uid)} DFLTGRP={r.get("DFLTGRP", "SYS1")}',
        f'ATTRIBUTES={attrs} REVOKED={r.get("REVOKED", "N")}',
        f'OMVS UID={r.get("OMVS",{}).get("UID","")} HOME={r.get("OMVS",{}).get("HOME","")}',
        f'TSO ACCTNUM={r.get("TSO",{}).get("ACCTNUM","")} PROC={r.get("TSO",{}).get("PROC","")}',
        f'CICS OPIDENT={r.get("CICS",{}).get("OPIDENT","")}',
        f'MFA ENABLED={r.get("MFA",{}).get("ENABLED","N")}',
    ])


def racf_admin_command(state: Any, userid: str, cmd: str) -> str | None:
    raw = (cmd or '').strip()
    u = raw.upper()
    if not (u == 'RACFADMIN' or u.startswith('RACFADMIN ') or u in {'RACF R','RACFADMIN MENU'}):
        return None
    st = get_racf_store(state)
    body = raw.split(None, 1)[1] if ' ' in raw else 'MENU'
    parts = body.split()
    op = parts[0].upper() if parts else 'MENU'
    if op in {'MENU','HELP','?'}:
        return _menu()
    if op == 'ADDUSER':
        if len(parts) < 2: return 'ICH01000I ADDUSER userid [PASSWORD(pw)] [DFLTGRP(group)]'
        uid = parts[1].upper(); grp = (_opt(body,'DFLTGRP','STUDENT') or 'STUDENT').upper(); name = _opt(body,'NAME',uid)
        attrs = {a for a in ['SPECIAL','OPERATIONS','AUDITOR','ROAUDIT','UAUDIT'] if re.search(rf'\b{a}\b', body, re.I)}
        uidnum = _opt(body,'UID','10077') or '10077'
        st.users[uid] = {'USERID': uid, 'NAME': name, 'DFLTGRP': grp, 'ATTRS': attrs, 'OMVS': {'UID': uidnum, 'HOME': f'/u/{uid.lower()}'}, 'TSO': {}, 'CICS': {}, 'MFA': {'ENABLED': 'N'}, 'REVOKED': 'N'}
        st.groups.setdefault(grp, set()).add(uid); _changed(state, userid, 'ADDUSER', uid)
        # Also try to update native stores without failing the panel.
        try:
            from gibson.apps.tso import TsoCommandProcessor
            TsoCommandProcessor(state, userid).execute(f"ADDUSER {uid} PASS(PASS123) DFLTGRP({grp})")
        except Exception: pass
        return f'IRR010I USER {uid} ADDED\nICH70001I COMMAND COMPLETE'
    if op == 'ALTUSER':
        if len(parts) < 2: return 'ICH01020I ALTUSER userid operands'
        uid = parts[1].upper(); rec = st.users.setdefault(uid, {'USERID':uid,'NAME':uid,'DFLTGRP':'STUDENT','ATTRS':set(),'OMVS':{},'TSO':{},'CICS':{},'MFA':{'ENABLED':'N'},'REVOKED':'N'})
        attrs = rec.setdefault('ATTRS', set())
        for a in ['SPECIAL','OPERATIONS','AUDITOR','ROAUDIT','UAUDIT']:
            if re.search(rf'\bNO{a}\b', body, re.I): attrs.discard(a)
            elif re.search(rf'\b{a}\b', body, re.I): attrs.add(a)
        if 'REVOKE' in body.upper(): rec['REVOKED']='Y'
        if 'RESUME' in body.upper() or 'NOREVOKE' in body.upper(): rec['REVOKED']='N'
        m = re.search(r'OMVS\(([^)]*)\)', body, re.I)
        if m:
            omvs = rec.setdefault('OMVS', {})
            uidm = re.search(r'UID\(([^)]*)\)|UID\s*\(?([^\s)]*)\)?', m.group(1), re.I)
            if uidm: omvs['UID'] = (uidm.group(1) or uidm.group(2) or '').strip()
            homem = re.search(r"HOME\('([^']*)'\)|HOME\(([^)]*)\)", m.group(1), re.I)
            if homem: omvs['HOME'] = (homem.group(1) or homem.group(2) or '').strip()
        if 'MFA(' in body.upper() or 'MFA' in body.upper(): rec.setdefault('MFA', {})['ENABLED']='N' if 'NOMFA' in body.upper() else 'Y'
        _changed(state, userid, 'ALTUSER', uid)
        return f'IRR521I USER {uid} UPDATED\nICH70001I COMMAND COMPLETE\n' + _list_user(st, uid)
    if op in {'LISTUSER','LU'}:
        uid = parts[1].upper() if len(parts) > 1 else userid.upper()
        if uid in {'*','ALL'}:
            return 'RACF USER LIST\n' + '\n'.join(f"{u:<8} {r.get('DFLTGRP',''):<8} {' '.join(sorted(r.get('ATTRS',set()))) or 'NONE'}" for u,r in sorted(st.users.items()))
        return _list_user(st, uid)
    if op == 'DELUSER':
        uid = parts[1].upper() if len(parts) > 1 else ''
        if uid in st.users:
            st.users.pop(uid)
            for g in st.groups.values(): g.discard(uid)
            _changed(state, userid, 'DELUSER', uid)
            return f'IRR012I USER {uid} DELETED\nICH70001I COMMAND COMPLETE'
        return f'ICH30001I USER {uid} NOT DEFINED'
    if op == 'ADDGROUP':
        grp = parts[1].upper() if len(parts) > 1 else 'NEWGRP'
        st.groups.setdefault(grp, set()); _changed(state, userid, 'ADDGROUP', grp)
        return f'IRR020I GROUP {grp} ADDED\nICH70001I COMMAND COMPLETE'
    if op in {'LISTGRP','LG'}:
        lines=['RACF GROUP LIST','GROUP     CONNECTED USERS']
        for g, users in sorted(st.groups.items()): lines.append(f'{g:<9} {", ".join(sorted(users))}')
        return '\n'.join(lines)
    if op == 'CONNECT':
        uid = parts[1].upper() if len(parts)>1 else userid.upper(); grp = (_opt(body,'GROUP','STUDENT') or 'STUDENT').upper()
        st.groups.setdefault(grp,set()).add(uid); st.users.setdefault(uid, {'USERID':uid,'NAME':uid,'DFLTGRP':grp,'ATTRS':set(),'OMVS':{},'TSO':{},'CICS':{},'MFA':{'ENABLED':'N'},'REVOKED':'N'})['DFLTGRP']=grp
        _changed(state, userid, 'CONNECT', f'{uid}.{grp}'); return f'ICH06011I {uid} CONNECTED TO {grp}'
    if op == 'REMOVE':
        uid = parts[1].upper() if len(parts)>1 else userid.upper(); grp = (_opt(body,'GROUP','STUDENT') or 'STUDENT').upper()
        st.groups.setdefault(grp,set()).discard(uid); _changed(state, userid, 'REMOVE', f'{uid}.{grp}'); return f'ICH06012I {uid} REMOVED FROM {grp}'
    if op in {'RDEFINE','ADDSD'}:
        cls = 'DATASET' if op=='ADDSD' else (parts[1].upper() if len(parts)>1 else 'FACILITY')
        prof = parts[1].upper() if op=='ADDSD' else (parts[2].upper() if len(parts)>2 else 'FIBS.*')
        st.profiles.setdefault(cls,{})[prof] = {'UACC': _opt(body,'UACC','NONE').upper(), 'PERMITS': {}}
        _changed(state, userid, op, f'{cls}.{prof}')
        return f'ICH10001I {cls} PROFILE {prof} DEFINED\nICH70001I COMMAND COMPLETE'
    if op in {'RLIST','LISTDSD'}:
        cls = 'DATASET' if op=='LISTDSD' else (parts[1].upper() if len(parts)>1 else 'FACILITY')
        lines=[f'RACF {cls} PROFILE LIST','PROFILE                  UACC    PERMITS']
        for p,v in sorted(st.profiles.get(cls,{}).items()): lines.append(f'{p:<24} {v.get("UACC","NONE"):<7} {v.get("PERMITS",{})}')
        return '\n'.join(lines)
    if op == 'PERMIT':
        prof = parts[1].upper() if len(parts)>1 else 'FIBS.*'; cls = _opt(body,'CLASS','DATASET').upper(); ident = _opt(body,'ID','IBMUSER').upper(); acc = _opt(body,'ACCESS','READ').upper()
        st.profiles.setdefault(cls,{}).setdefault(prof,{'UACC':'NONE','PERMITS':{}})['PERMITS'][ident]=acc
        _changed(state, userid, 'PERMIT', f'{cls}.{prof}.{ident}')
        return f'ICH06013I {ident} PERMITTED {acc} TO {cls} {prof}\nICH70001I COMMAND COMPLETE'
    if op == 'SETROPTS':
        if 'LIST' in body.upper(): return 'SETROPTS LIST\n' + '\n'.join(f'{k}={v}' for k,v in sorted(st.setropts.items()))
        for key in ['CLASSACT','RACLIST','PASSWORD','MFA','GENERIC','AUDIT']:
            val = _opt(body, key, '')
            if val or key in body.upper(): st.setropts[key] = val or 'ENABLED'
        _changed(state, userid, 'SETROPTS', 'SYSTEM'); return 'ICH70001I SETROPTS OPTIONS UPDATED'
    if op == 'PTKTDATA' or 'PTKTDATA' in body.upper():
        try:
            from gibson.core.passticket import get_passticket_service
            rows = get_passticket_service(state).profile_rows()
            lines = ['PTKTDATA PROFILE DISPLAY', 'APPLID     REPLAY APPLCHK  LABLEAK VALIDSECS KEY']
            for r in rows:
                lines.append(f"{r['PROFILE']:<10} {r['REPLAY']:<6} {r['APPLCHK']:<8} {r['LABLEAK']:<7} {r['VALIDSECS']:<8} {r['KEYMASKED']}")
            return '\n'.join(lines)
        except Exception:
            return 'PTKTDATA PROFILE DISPLAY\nNO LIVE PASSTICKET SERVICE AVAILABLE'
    if op == 'MFA' or 'MFA' in body.upper(): return 'RACF MFA ADMINISTRATION\nUSERS WITH MFA: ' + ', '.join(k for k,v in sorted(st.users.items()) if (v.get('MFA') or {}).get('ENABLED')=='Y')
    if op == 'RACDCERT' or 'RACDCERT' in body.upper(): return 'RACDCERT SIMULATED CERTIFICATE PANEL\nCERTAUTH FIBSCA VALID\nRING FIBS.KEYRING OWNER FIBSADM'
    return _menu() + '\n\nRACFADMIN: ENTER ADDUSER, ALTUSER, LISTUSER, CONNECT, RDEFINE, RLIST, PERMIT, SETROPTS or MENU'
