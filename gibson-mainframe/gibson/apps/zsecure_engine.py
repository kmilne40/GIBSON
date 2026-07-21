from __future__ import annotations

from datetime import datetime
from typing import Any

from gibson.apps.racf_admin import get_racf_store

_ZSEC_VER = "V3.1.0"   # IBM Security zSecure Audit for RACF release shown in headers


def _all_findings(state: Any) -> list[dict[str, str]]:
    st = get_racf_store(state)
    rows: list[dict[str, str]] = []
    seq = 1
    for uid, rec in sorted(st.users.items()):
        attrs = set(rec.get('ATTRS', set()))
        if 'SPECIAL' in attrs or 'OPERATIONS' in attrs:
            rows.append({'id': f'ZS-{seq:03d}', 'sev': 'HIGH' if 'SPECIAL' in attrs else 'MED', 'area': 'RACF', 'res': uid, 'evidence': 'ATTRIBUTES=' + ','.join(sorted(attrs)), 'risk': 'Privileged authority can administer or bypass controls', 'rec': f'ALTUSER {uid} NOSPECIAL NOOPERATIONS', 'cmd': f'LISTUSER {uid}'}); seq += 1
        if str((rec.get('OMVS') or {}).get('UID', '')).strip() == '0':
            rows.append({'id': f'ZS-{seq:03d}', 'sev': 'HIGH', 'area': 'OMVS', 'res': uid, 'evidence': 'OMVS UID(0)', 'risk': 'Unix superuser equivalence', 'rec': f'ALTUSER {uid} OMVS(UID(nonzero))', 'cmd': f'LISTUSER {uid} OMVS'}); seq += 1
        if (rec.get('MFA') or {}).get('ENABLED') != 'Y' and ('SPECIAL' in attrs or 'OPERATIONS' in attrs):
            rows.append({'id': f'ZS-{seq:03d}', 'sev': 'MED', 'area': 'MFA', 'res': uid, 'evidence': 'MFA ENABLED=N', 'risk': 'Privileged identity without simulated MFA', 'rec': f'ALTUSER {uid} MFA(ENABLE)', 'cmd': f'LISTUSER {uid}'}); seq += 1
    for cls, profiles in sorted(st.profiles.items()):
        for prof, data in sorted(profiles.items()):
            if str(data.get('UACC','NONE')).upper() in {'READ','UPDATE','ALTER'}:
                rows.append({'id': f'ZS-{seq:03d}', 'sev': 'MED', 'area': cls, 'res': prof, 'evidence': 'UACC=' + str(data.get('UACC')), 'risk': 'Broad public access to protected resource', 'rec': f'RALTER {cls} {prof} UACC(NONE)', 'cmd': f'RLIST {cls} {prof} ALL'}); seq += 1
    for lib in getattr(state, 'apf_libraries', []):
        if 'VULN' in lib or lib.startswith('SYS1.PARMLIB'):
            rows.append({'id': f'ZS-{seq:03d}', 'sev': 'HIGH', 'area': 'APF', 'res': lib, 'evidence': 'APF library requires protection review', 'risk': 'APF-authorized code can affect system integrity', 'rec': f"PERMIT '{lib}' ID(SYS1) ACCESS(READ); review UPDATE access", 'cmd': 'APF'}); seq += 1
    try:
        for ev in getattr(getattr(state, 'audit', None), 'events', [])[-80:]:
            blob = (str(getattr(ev, 'command', '')) + ' ' + str(getattr(ev, 'result', '')) + ' ' + str(getattr(ev, 'extra', {}))).upper()
            if 'TOMCAT' in blob:
                rows.append({'id': f'ZS-{seq:03d}', 'sev': 'HIGH' if '31337' in blob or 'WAR' in blob else 'MED', 'area': 'TOMCAT', 'res': ev.extra.get('CONTEXT', ev.extra.get('RESOURCE', 'MANAGER')), 'evidence': (ev.result or blob)[:80], 'risk': 'Tomcat Manager weak credentials, WAR deployment or simulated bind shell activity requires review', 'rec': 'Disable weak Manager credentials; remove unapproved WAR; review lab evidence', 'cmd': 'ZSEC TOMCAT'}); seq += 1
    except Exception:
        pass
    if not rows:
        rows.append({'id': 'ZS-000', 'sev': 'INFO', 'area': 'BASELINE', 'res': 'FIBS', 'evidence': 'No high-risk simulated findings', 'risk': 'None', 'rec': 'Continue monitoring', 'cmd': 'ZSEC COMPLIANCE'})
    return rows


def _zsec_status_audit(state: Any) -> str:
    """Authentic zSecure Audit 'Status Audit' report: SETROPTS audit concerns,
    a privileged-user census, resource exposure, and the predefined SMF event
    reports (USEOPER / CMDSPEC / CMDFAIL), with audit priorities, as a CKRCARLA
    operator would recognise."""
    st = get_racf_store(state)
    sysid = (getattr(getattr(state, "config", None), "smfid", None) or "GIBS")
    now = datetime.now().strftime("%d %b %Y %H:%M")
    L: list[str] = []
    L.append(f"CKRCARLA   IBM Security zSecure Audit for RACF   {_ZSEC_VER}")
    L.append(f"Status Audit Report - audit concerns by priority      "
             f"SYSTEM={sysid}  COMPLEX={sysid}PLEX")
    L.append(f"Generated {now}")
    L.append("=" * 78)

    concerns: list[tuple[int, str]] = []   # (priority, text)

    # -- SETROPTS / system-wide settings audit concerns ----------------------
    so = {k.upper(): str(v).upper() for k, v in st.setropts.items()}
    pw = so.get("PASSWORD", "")
    if "PROTECTALL" not in so and "PROTECTALL" not in " ".join(so.values()):
        concerns.append((40, "PROTECTALL is not in effect - data sets without a "
                              "profile are unprotected"))
    if "HISTORY" not in pw:
        concerns.append((30, "SETROPTS PASSWORD HISTORY not set - password reuse "
                              "is not prevented"))
    if "INTERVAL" not in pw:
        concerns.append((25, "SETROPTS PASSWORD INTERVAL not set - passwords need "
                              "not expire"))
    if "REVOKE" not in so.get("PASSWORD", "") and "REVOKE" not in " ".join(so.values()):
        concerns.append((25, "No SETROPTS PASSWORD REVOKE count - failed logons do "
                              "not revoke the userid"))
    if "MIXEDCASE" not in pw:
        concerns.append((15, "Mixed-case passwords not enforced"))

    L.append("")
    L.append("SYSTEM-WIDE SETTINGS (SETROPTS) - AUDIT CONCERNS")
    L.append(f"  CLASSACT : {st.setropts.get('CLASSACT', '')}")
    L.append(f"  RACLIST  : {st.setropts.get('RACLIST', '')}")
    L.append(f"  PASSWORD : {st.setropts.get('PASSWORD', '')}")
    L.append(f"  AUDIT    : {st.setropts.get('AUDIT', '')}")
    so_concerns = [c for c in concerns]
    if so_concerns:
        L.append("  Pri  Concern")
        for pri, txt in sorted(so_concerns, reverse=True):
            L.append(f"  {pri:<4} {txt}")
    else:
        L.append("  No SETROPTS audit concerns.")

    # -- privileged-user census ----------------------------------------------
    users = st.users
    def _holders(pred):
        return sorted(u for u, r in users.items() if pred(r))
    special = _holders(lambda r: "SPECIAL" in (r.get("ATTRS") or set()))
    operations = _holders(lambda r: "OPERATIONS" in (r.get("ATTRS") or set()))
    auditor = _holders(lambda r: "AUDITOR" in (r.get("ATTRS") or set()))
    uid0 = _holders(lambda r: str((r.get("OMVS") or {}).get("UID", "")).strip() == "0")
    revoked = _holders(lambda r: str(r.get("REVOKED", "N")).upper() == "Y")

    L.append("")
    L.append("PRIVILEGED USER CENSUS")
    L.append("  Attribute       Count  Userids")
    for label, holders in (("system-SPECIAL", special), ("OPERATIONS", operations),
                           ("AUDITOR", auditor), ("UID(0)", uid0), ("REVOKED", revoked)):
        L.append(f"  {label:<15} {len(holders):<5}  {', '.join(holders[:8]) or '(none)'}")

    # -- privileged users, per-id audit concern ------------------------------
    L.append("")
    L.append("PRIVILEGED USERS - AUDIT CONCERNS")
    L.append("  Pri  Userid    Attributes                Concern")
    both = [u for u in special if u in operations]
    for u in sorted(set(special) | set(operations)):
        attrs = sorted(users[u].get("ATTRS") or set())
        if u in both:
            pri, c = 35, "Single id holds both SPECIAL and OPERATIONS"
        elif u in special:
            pri, c = 30, "System-SPECIAL - can administer all of RACF"
        else:
            pri, c = 25, "OPERATIONS - can access all data sets"
        concerns.append((pri, f"{u} {c}"))
        L.append(f"  {pri:<4} {u:<9} {','.join(attrs)[:24]:<24} {c}")
    for u in uid0:
        concerns.append((30, f"{u} OMVS UID(0) superuser"))
        L.append(f"  30   {u:<9} {'UID(0)':<24} z/OS UNIX superuser equivalence")

    # -- resource exposure ----------------------------------------------------
    L.append("")
    L.append("RESOURCE / DATA SET PROFILE CONCERNS")
    L.append("  Pri  Class     Profile               UACC    Concern")
    exposure = 0
    for cls, profs in sorted(st.profiles.items()):
        for prof, data in sorted(profs.items()):
            uacc = str(data.get("UACC", "NONE")).upper()
            warn = str(data.get("WARNING", "")).upper() in ("YES", "Y", "TRUE")
            if uacc in ("READ", "UPDATE", "ALTER"):
                pri = 30 if uacc in ("UPDATE", "ALTER") else 20
                concerns.append((pri, f"{cls} {prof} UACC({uacc})"))
                L.append(f"  {pri:<4} {cls:<9} {prof[:20]:<20}  {uacc:<6}  "
                         f"universal {uacc} access")
                exposure += 1
            if warn:
                concerns.append((20, f"{cls} {prof} in WARNING mode"))
                L.append(f"  20   {cls:<9} {prof[:20]:<20}  -       "
                         f"profile in WARNING mode (access allowed + logged)")
                exposure += 1
    if exposure == 0:
        L.append("  No high-UACC or WARNING-mode profile concerns.")

    # -- predefined SMF event reports ----------------------------------------
    ev_blobs = []
    for e in _audit_events(state):
        ev_blobs.append((str(getattr(e, "command", "")) + " " +
                         str(getattr(e, "result", "")) + " " +
                         str(getattr(e, "action", ""))).upper())
    useoper = sum(1 for b in ev_blobs if "OPER" in b)
    cmdspec = sum(1 for b in ev_blobs if "SPECIAL" in b or "ALTUSER" in b or "SETROPTS" in b)
    cmdfail = sum(1 for b in ev_blobs if "FAIL" in b or "VIOLAT" in b or "DENIED"
                  in b or "ICH408" in b)
    L.append("")
    L.append("SMF EVENT REPORTS (predefined)")
    L.append(f"  USEOPER   access granted via OPERATIONS attribute      : {useoper} event(s)")
    L.append(f"  CMDSPEC   commands issued by SPECIAL users             : {cmdspec} event(s)")
    L.append(f"  CMDFAIL   RACF command / access violations             : {cmdfail} event(s)")

    # -- priority summary -----------------------------------------------------
    crit = sum(1 for p, _ in concerns if p >= 40)
    high = sum(1 for p, _ in concerns if 30 <= p < 40)
    med = sum(1 for p, _ in concerns if 20 <= p < 30)
    low = sum(1 for p, _ in concerns if p < 20)
    L.append("")
    L.append("AUDIT PRIORITY SUMMARY")
    L.append(f"  Priority >= 40  (critical) : {crit}")
    L.append(f"  Priority 30-39  (high)     : {high}")
    L.append(f"  Priority 20-29  (medium)   : {med}")
    L.append(f"  Priority <  20  (low)      : {low}")
    L.append(f"  Total audit concerns       : {len(concerns)}")
    L.append("=" * 78)
    L.append("Use RA.S to review SETROPTS, AU.S for status audit detail, "
             "RE for resource reports.")
    return "\n".join(L)


def _render(title: str, finds: list[dict[str, str]]) -> str:
    lines = [title, 'ID      SEV   AREA       RESOURCE        EVIDENCE', '-' * 78]
    for f in finds:
        lines.append(f"{f['id']:<7} {f['sev']:<5} {f['area']:<10} {str(f['res'])[:15]:<15} {str(f['evidence'])[:35]}")
        lines.append(f"        RISK: {str(f['risk'])[:68]}")
        lines.append(f"        RECOMMENDATION: {str(f['rec'])[:64]}")
        lines.append(f"        VALIDATE: {str(f.get('cmd',''))[:66]}")
    return '\n'.join(lines)


def _smf_records(state: Any):
    try:
        from gibson.core.smf.writer import get_smf_writer
        return list(get_smf_writer(state).records)
    except Exception:
        return list(getattr(state, 'smf_records', []) or [])


def _flat_smf(state: Any) -> list[dict[str, str]]:
    rows=[]
    for r in _smf_records(state):
        try:
            rows.append({str(k).upper(): str(v) for k,v in r.to_flat_fields().items()})
        except Exception:
            continue
    return rows


def _audit_events(state: Any) -> list[Any]:
    return list(getattr(getattr(state, 'audit', None), 'events', []) or [])


def _security_rows(state: Any, *, rare: bool = False, limit: int = 40) -> list[tuple[str,str,str,str,str]]:
    rows=[]
    rare_terms=("RACFDS","RACF_HASH","HASH","JOHN","RACF2JOHN","IND$FILE","INDFILE","SENSITIVE","PASSTICKET","PTKT","REPLAY","MFA","ICSF","MASTERKEY","SYS1.MAN","APF","SURROGAT","SETROPTS","UID(0)","SPECIAL","OPERATIONS")
    for f in _flat_smf(state):
        blob=' '.join(str(f.get(k,'')) for k in ('EVENT_NAME','EVENT','DETAIL','RESOURCE_NAME','RESULT','SOURCE_COMPONENT')).upper()
        if rare and not any(t in blob for t in rare_terms):
            continue
        rows.append((f.get('TIMESTAMP','')[:19], f.get('USERID','')[:8], (f.get('EVENT_NAME') or f.get('EVENT') or 'SMF')[:24], f.get('RESULT','')[:8], (f.get('RESOURCE_NAME') or f.get('DETAIL') or f.get('SUMMARY') or '')[:52]))
    for e in _audit_events(state):
        blob=(str(getattr(e,'command',''))+' '+str(getattr(e,'result',''))+' '+str(getattr(e,'extra',{}))).upper()
        if rare and not any(t in blob for t in rare_terms):
            continue
        try: ts=e.ts.strftime('%Y-%m-%d %H:%M:%S')
        except Exception: ts=''
        rows.append((ts, str(getattr(e,'userid',''))[:8], str(getattr(e,'command',''))[:24], str(getattr(e,'result',''))[:8], str(getattr(e,'extra',{}))[:52]))
    # de-duplicate simple duplicate mirrored audit/smf rows
    seen=set(); out=[]
    for r in rows:
        key=(r[1],r[2],r[3],r[4])
        if key in seen: continue
        seen.add(key); out.append(r)
    return out[-limit:]


def _zsec_events(state: Any) -> str:
    lines=['ZSECURE SECURITY EVENT REVIEW','TIME                USER     EVENT                    RESULT   DETAIL']
    rows=_security_rows(state, rare=False, limit=60)
    if not rows: lines.append('NO SECURITY EVENTS RECORDED')
    for t,u,e,r,d in rows:
        lines.append(f'{t:<19} {u:<8} {e:<24} {r:<8} {d}')
    return '\n'.join(lines)


def _zsec_rare(state: Any) -> str:
    lines=['ZSECURE RARE / HIGH-RISK EVENT REVIEW','TIME                USER     EVENT                    RESULT   DETAIL']
    rows=_security_rows(state, rare=True, limit=40)
    if not rows: lines.append('NO RARE OR HIGH-RISK EVENTS RECORDED')
    for t,u,e,r,d in rows:
        lines.append(f'{t:<19} {u:<8} {e:<24} {r:<8} {d}')
    lines.append('RARE FILTERS: RACFDS HASH IND$FILE PASSTICKET ICSF SYS1.MAN APF PRIVILEGE')
    return '\n'.join(lines)


def _zsec_summary(state: Any) -> str:
    rows=_security_rows(state, rare=False, limit=500)
    rare=_security_rows(state, rare=True, limit=500)
    users={r[1] for r in rows if r[1]}
    lines=['ZSECURE SECURITY SUMMARY', f'EVENTS={len(rows)} RARE={len(rare)} USERS={len(users)}']
    cats={}
    for _t,_u,e,_r,d in rows:
        cat='RACFDS' if 'RACFDS' in (e+d).upper() else ('IND$FILE' if 'IND' in (e+d).upper() else ('PASSTICKET' if 'PASS' in (e+d).upper() or 'PTKT' in (e+d).upper() else ('ICSF' if 'ICSF' in (e+d).upper() else 'OTHER')))
        cats[cat]=cats.get(cat,0)+1
    for k in sorted(cats): lines.append(f'{k:<12} {cats[k]:05d}')
    return '\n'.join(lines)


def _zsec_smf_review(state: Any, topic: str) -> str:
    try:
        from gibson.core.smf.formatters import format_list
        rt = None
        if topic.startswith('SMF') and topic[3:].isdigit(): rt=topic[3:]
        elif topic == 'SMF80': rt='80'
        elif topic in {'PASSTICKET','PTKT'}: rt='80'
        elif topic == 'CICS': rt='110'
        elif topic == 'DB2': rt='101'
        elif topic == 'NETWORK': rt='119'
        elif topic == 'USS': rt='92'
        title = f'ZSECURE {topic} SMF REVIEW'
        if rt:
            title += f' - SMF TYPE {rt}'
        return title+'\n'+format_list(state, rt)
    except Exception as e:
        return f'ZSECURE SMF REVIEW UNAVAILABLE: {e}'


def _zsec_racfds(state: Any, userid: str) -> str:
    try:
        from gibson.core.racf_database import status
        base=status(state)
    except Exception:
        base='RACFDB STATUS UNAVAILABLE'
    related=[r for r in _security_rows(state, rare=False, limit=80) if 'RACFDS' in (r[2]+r[4]).upper() or 'SYS1.RACFDS' in (r[2]+r[4]).upper()]
    lines=[base,'','ZSECURE RACFDS EXPOSURE EVIDENCE','TIME                USER     EVENT                    RESULT   DETAIL']
    if not related: lines.append('NO RECENT RACFDS ACCESS EVIDENCE')
    for t,u,e,r,d in related[-20:]: lines.append(f'{t:<19} {u:<8} {e:<24} {r:<8} {d}')
    return '\n'.join(lines)


def _zsec_offlinehash(state: Any, userid: str, title: str='ZSECURE OFFLINE RACF HASH REVIEW') -> str:
    lines=[title,'USERID   ALG             STATUS              PROVIDER']
    try:
        from gibson.core.racf_database import materialise_racfds
        materialise_racfds(state)
        text=state.datasets.read(userid,'SYS1.RACFDS(DATABASE)')
        import re
        count=0
        for line in text.splitlines():
            if not line.startswith('USER '): continue
            uid=re.search(r'USERID=([^\s]+)',line); alg=re.search(r'ALG=([^\s]+)',line); prov=re.search(r'PROVIDER=([^\s]+)',line)
            algv=(alg.group(1) if alg else 'UNKNOWN').upper()
            if algv in {'LEGACY-DES','LEGACY-DES-SIM'}:
                status='CRACKABLE-REAL' if algv=='LEGACY-DES' else 'CRACKABLE-SIM'
            else:
                status='PROTECTED'
            lines.append(f"{(uid.group(1) if uid else 'UNKNOWN'):<8} {algv:<15} {status:<19} {(prov.group(1) if prov else '-')[:12]}")
            count+=1
        if count==0: lines.append('NO RACFDS USER RECORDS AVAILABLE')
    except Exception as e:
        lines.append('RACFDS UNAVAILABLE: '+str(e))
    hash_events=[r for r in _security_rows(state, rare=False, limit=60) if any(x in (r[2]+r[4]).upper() for x in ['RACF2JOHN','JOHN','HASH'])]
    lines.extend(['','RECENT HASH EXTRACTION / CRACK EVENTS','TIME                USER     EVENT                    RESULT   DETAIL'])
    if not hash_events: lines.append('NO HASH EXTRACTION OR CRACKING EVENTS RECORDED')
    for t,u,e,r,d in hash_events[-15:]: lines.append(f'{t:<19} {u:<8} {e:<24} {r:<8} {d}')
    lines.append('M4M=MF-TTP08 MITRE=T1110.002 REVIEW SMF80/30/92 TIMELINE')
    return '\n'.join(lines)


def _zsec_indfile(state: Any, broad: bool=False) -> str:
    title='ZSECURE TRANSFER / EXFILTRATION REVIEW' if broad else 'ZSECURE IND$FILE TRANSFER REVIEW'
    lines=[title,'TIME                USER     DIR DATASET                                      RESULT']
    hist=list(getattr(state, 'indfile_history', []) or [])
    if not hist: lines.append('NO IND$FILE TRANSFER HISTORY AVAILABLE')
    for e in hist[-30:]:
        lines.append(f"{str(e.get('TIME',''))[:19]:<19} {str(e.get('USER',''))[:8]:<8} {str(e.get('DIRECTION',''))[:3]:<3} {str(e.get('TARGET', e.get('DSN','')))[:44]:<44} {str(e.get('RESULT','SUCCESS'))[:8]}")
    if broad:
        for t,u,e,r,d in _security_rows(state, rare=False, limit=80):
            if any(x in (e+d).upper() for x in ['FTP','TRANSFER','EXFIL','IND$FILE']):
                lines.append(f'{t:<19} {u:<8} --- {d[:44]:<44} {r[:8]}')
    lines.append('REVIEW SMF80/92/119 AND MASTER CONSOLE GIBSSEC4A FOR SENSITIVE DATASET TRANSFERS')
    return '\n'.join(lines)


def _zsec_snapshot(state: Any) -> dict:
    """Capture the current security posture for baseline/drift comparison:
    APF list, SPECIAL/OPERATIONS holders, OMVS UID(0) holders, and the public
    (UACC>=READ) general-resource profiles."""
    st = get_racf_store(state)
    try:
        from gibson.apps.parmlib.explorer import system_config_state
        apf = sorted(system_config_state(state)["apf"])
    except Exception:
        apf = sorted(getattr(state, "apf_libraries", []))
    special, operations, uid0 = [], [], []
    for uid, rec in st.users.items():
        attrs = {a.upper() for a in (rec.get("ATTRS", set()) or set())}
        if "SPECIAL" in attrs:
            special.append(uid)
        if "OPERATIONS" in attrs:
            operations.append(uid)
        if str((rec.get("OMVS") or {}).get("UID", "")).strip() == "0":
            uid0.append(uid)
    public = []
    for cls, profiles in st.profiles.items():
        for prof, data in profiles.items():
            if str(data.get("UACC", "NONE")).upper() in {"READ", "UPDATE", "ALTER"}:
                public.append(f"{cls}/{prof}=UACC({data.get('UACC')})")
    return {
        "captured": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "apf": apf,
        "special": sorted(special),
        "operations": sorted(operations),
        "uid0": sorted(uid0),
        "public": sorted(public),
    }


_ZSEC_BASELINE_DSN = "IBMUSER.ZSECURE.BASELINE"


def _zsec_baseline(state: Any, userid: str) -> str:
    import json
    snap = _zsec_snapshot(state)
    try:
        state.datasets.write(userid, _ZSEC_BASELINE_DSN, json.dumps(snap, indent=2) + "\n")
    except Exception:
        pass
    return "\n".join([
        f"CKRCARLA   IBM Security zSecure - Compliance Baseline   {_ZSEC_VER}",
        "=" * 60,
        f"BASELINE CAPTURED: {snap['captured']}",
        f"SAVED TO: {_ZSEC_BASELINE_DSN}",
        "",
        f"  APF LIBRARIES ............ {len(snap['apf'])}",
        f"  SPECIAL USERS ............ {len(snap['special'])}  ({', '.join(snap['special']) or 'none'})",
        f"  OPERATIONS USERS ......... {len(snap['operations'])}  ({', '.join(snap['operations']) or 'none'})",
        f"  OMVS UID(0) USERS ........ {len(snap['uid0'])}  ({', '.join(snap['uid0']) or 'none'})",
        f"  PUBLIC (UACC>=READ) ...... {len(snap['public'])}",
        "",
        "Run ZSEC DRIFT after changes to see what moved against this baseline.",
    ])


def _zsec_drift(state: Any, userid: str) -> str:
    import json
    try:
        prior = json.loads(state.datasets.read(userid, _ZSEC_BASELINE_DSN))
    except Exception:
        return ("CKRCARLA   IBM Security zSecure - Compliance Drift\n" + "=" * 60 +
                "\nNO BASELINE CAPTURED. Run ZSEC BASELINE first to record the "
                "current posture, then re-run ZSEC DRIFT after changes.")
    cur = _zsec_snapshot(state)
    L = [f"CKRCARLA   IBM Security zSecure - Compliance Drift   {_ZSEC_VER}",
         "=" * 60,
         f"BASELINE: {prior.get('captured','?')}    CURRENT: {cur['captured']}",
         ""]
    any_drift = False
    labels = {"apf": "APF LIBRARY", "special": "SPECIAL USER",
              "operations": "OPERATIONS USER", "uid0": "OMVS UID(0) USER",
              "public": "PUBLIC PROFILE"}
    for key, label in labels.items():
        before, after = set(prior.get(key, [])), set(cur.get(key, []))
        added, removed = sorted(after - before), sorted(before - after)
        for a in added:
            sev = "HIGH" if key in ("apf", "special", "uid0") else "MED"
            L.append(f"  + ADDED   [{sev}] {label}: {a}")
            any_drift = True
        for r in removed:
            L.append(f"  - REMOVED       {label}: {r}")
            any_drift = True
    if not any_drift:
        L.append("  NO DRIFT DETECTED - posture matches the captured baseline.")
    else:
        L.append("")
        L.append("ADDED HIGH-severity items are the priority - e.g. a new APF")
        L.append("library or a freshly-granted SPECIAL is a classic escalation IOC.")
    return "\n".join(L)


def zsecure_command(state: Any, userid: str, cmd: str) -> str | None:
    u=(cmd or '').strip().upper()
    if not (u == 'ZSEC' or u.startswith('ZSEC ') or u.startswith('ZSECURE')):
        return None
    topic='MENU' if u in {'ZSEC','ZSECURE'} else u.split(None,1)[1].strip().upper()
    if topic in {'HELP','MENU','?'}:
        return '\n'.join(['zSecure / Mainframe Security Monitor - HELP (COMMANDS)',
            '  ZSEC EVENTS        Recent security events',
            '  ZSEC RARE          Rare/high-risk events',
            '  ZSEC SUMMARY       Security summary counts',
            '  ZSEC BASELINE      Capture compliance baseline (APF/SPECIAL/UID0/UACC)',
            '  ZSEC DRIFT         Compare current posture against the baseline',
            '  ZSEC SMF|SMF7|SMF80 Structured SMF reviews',
            '  ZSEC PASSTICKET    PassTicket SMF80 review',
            '  ZSEC RACFDS        RACF database exposure review',
            '  ZSEC OFFLINEHASH   racf2john/john evidence',
            '  ZSEC HASHCRACK     Hash cracking attempts/results',
            '  ZSEC IND$FILE      IND$FILE transfer review',
            '  ZSEC TRANSFERS     Transfer/exfil review',
            '  ZSEC ICSF          ICSF / key-control evidence',
            '  ZSEC TIMELINE <id> Correlation timeline'])
    if topic.startswith('TIMELINE'):
        try:
            from gibson.core.smf.formatters import format_timeline
            parts=topic.split(); corr=parts[1] if len(parts)>1 else ''
            return 'ZSECURE CORRELATION TIMELINE\n'+format_timeline(state,corr)
        except Exception as e: return f'ZSECURE TIMELINE UNAVAILABLE: {e}'
    if topic in {'BASELINE', 'BASE', 'RE.B', 'CAPTURE'}:
        return _zsec_baseline(state, userid)
    if topic in {'DRIFT', 'RE.D', 'COMPARE'}:
        return _zsec_drift(state, userid)
    if topic in {'EVENTS','ALERTS'}: return _zsec_events(state)
    if topic in {'RARE','FIRST30'}: return _zsec_rare(state)
    if topic in {'SUMMARY','COMPLIANCE','H'}: return _zsec_summary(state)
    if topic in {'SMF','SMF7','SMF80','SMF30','SMF110','SMF119','SMF92','SMF101','SMF102','SMF123','PASSTICKET','PTKT','CICS','DB2','NETWORK','USS','ICSF','M4M'} or (topic.startswith('SMF') and topic[3:].isdigit()):
        return _zsec_smf_review(state, topic)
    if topic in {'RACFDS','DATASET','4'}: return _zsec_racfds(state, userid)
    if topic in {'OFFLINEHASH','RACF HASHES','RACFDS HASHES'}: return _zsec_offlinehash(state, userid)
    if topic in {'HASHCRACK'}: return _zsec_offlinehash(state, userid, title='ZSECURE RACF HASH CRACKING REVIEW')
    if topic in {'IND$FILE','INDFILE'}: return _zsec_indfile(state, broad=False)
    if topic in {'TRANSFERS','TRANSFER'}: return _zsec_indfile(state, broad=True)
    # Existing audit posture reviews still use findings, but no longer hijack EVENTS/RARE.
    if topic in {'AUDIT', 'STATUS', 'STATUSAUDIT', 'AU', 'STATUS AUDIT'}:
        return _zsec_status_audit(state)
    if topic in {'SETUP', 'SE'}:
        return ("\n".join([
            f"CKRCARLA   IBM Security zSecure - Setup (input files)   {_ZSEC_VER}",
            "=" * 60,
            "Input set     Status     Source",
            "  Live RACF   ACTIVE     primary RACF database (in-storage)",
            "  CKFREEZE    ACTIVE     point-in-time control-block snapshot",
            "  UNLOAD      AVAILABLE  IRRDBU00 database unload",
            "  SMF         ACTIVE     live SMF / type-80 records",
            "",
            "Run options : CONFIRM=YES  BACKGROUND=NO  SCOPE=COMPLEX",
            "Use AU for the status audit, RA.S for SETROPTS, EV for SMF events."]))
    finds=_all_findings(state)
    if topic in {'PRIVILEGE','PRIVILEGED','2','RACF'}:
        finds=[f for f in finds if f['area']=='RACF'] or finds
    elif topic in {'UID0','3'}:
        finds=[f for f in finds if f['area']=='OMVS'] or [{'id':'ZS-INFO','sev':'INFO','area':'OMVS','res':'GIBSON','evidence':'No UID(0) findings','risk':'None','rec':'Continue monitoring','cmd':'ZSEC UID0'}]
    elif topic in {'MFA','A'}:
        finds=[f for f in finds if f['area']=='MFA'] or [{'id':'ZS-INFO','sev':'INFO','area':'MFA','res':'GIBSON','evidence':'No MFA findings','risk':'None','rec':'Continue monitoring','cmd':'ZSEC MFA'}]
    elif topic in {'REPORTS','FINDINGS','J'}:
        text='FINDING_ID|SEVERITY|AREA|RESOURCE|EVIDENCE|RISK|RECOMMENDATION\n'+'\n'.join(f"{f['id']}|{f['sev']}|{f['area']}|{f['res']}|{f['evidence']}|{f['risk']}|{f['rec']}" for f in finds)+'\n'
        try:
            for dsn in ['FIBS.ZSEC.FINDINGS','FIBS.ZSEC.COMPLIANCE','FIBS.ZSEC.EVENTS']:
                try: state.datasets.allocate(userid, dsn, org='PS', recfm='VB', lrecl=1024)
                except Exception: pass
            state.datasets.write(userid, 'FIBS.ZSEC.FINDINGS', text)
        except Exception: pass
        return 'ZSECURE AUDIT REPORT - FINDINGS EXPORTED TO FIBS.ZSEC.FINDINGS\n'+text
    else:
        filtered=[f for f in finds if f['area'] in {topic}]
        if filtered: finds=filtered
        elif topic not in {'DRIFT','I'}:
            finds=[{'id':'ZS-INFO','sev':'INFO','area':topic,'res':'GIBSON','evidence':'Simulator state reviewed','risk':'No high-risk state in this control area','rec':'Continue monitoring','cmd':f'ZSEC {topic}'}]
    return _render(f'ZSECURE {topic} REVIEW', finds)
