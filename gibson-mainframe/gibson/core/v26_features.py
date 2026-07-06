from __future__ import annotations

import csv, json, re, shutil, time, zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from gibson.apps.cti_rss import rss_command, FEEDS_DSN, CACHE_DSN, LASTRUN_DSN
from gibson.apps.sysview import sysview_command


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _hhmm() -> str:
    return datetime.now().strftime('%H:%M')


def _ensure_v26(state) -> dict[str, Any]:
    st = getattr(state, 'v26_state', None)
    if st is None:
        st = {
            'split_console': False,
            'split_refresh': 1.0,
            'smpe': {'CSI':'GLOBAL.CSI', 'zones':['GLOBAL','MVST100','DLIB100'], 'sysmods': {'HZSEC10': 'APPLIED', 'UGIB261': 'RECEIVED', 'UJES200': 'ACCEPTED', 'UZSEC80': 'HELD'}},
            'racftrace': False,
            'racftrace_entries': [],
            'security_events': [],
            'apf_history': [],
            'dataset_history': {},
            'scenarios': {},
            'active_scenario': None,
            'pfshow': False,
            'pfkeys': {'PF3':'END', 'PF12':'RETRIEVE', 'PF1':'HELP', 'PF7':'UP', 'PF8':'DOWN'},
            'detection': {
                'PORTSCAN': {'enabled': True, 'threshold': int(getattr(state.config, 'port_scan_threshold', 4)), 'window': int(getattr(state.config, 'port_scan_window', 8))},
                'UNKNOWNHIGHPORT': {'enabled': True, 'min_port': 1025},
                'SYS1EDIT': {'enabled': True, 'severity': 'HIGH'},
                'FAILEDLOGON': {'enabled': True, 'threshold': 5, 'window': 60},
                'SUPPRESS_LOCALHOST_SCAN': {'enabled': bool(getattr(state.config, 'suppress_localhost_scan', True)), 'severity': 'INFO'},
            },
        }
        setattr(state, 'v26_state', st)
    return st


def security_event(state, event_type: str, message: str, *, userid: str = 'SYSTEM', severity: str = 'INFO', resource: str = '', result: str = 'INFO', addr: str = '', service: str = '') -> dict[str, Any]:
    st = _ensure_v26(state)
    seq = len(st['security_events']) + 1
    entry = {'id': seq, 'time': _now(), 'userid': (userid or 'SYSTEM').upper(), 'type': event_type.upper(), 'severity': severity.upper(), 'resource': resource, 'result': result.upper(), 'addr': addr, 'service': service, 'message': message}
    st['security_events'].append(entry)
    st['security_events'] = st['security_events'][-500:]
    try:
        if severity.upper() in {'ALERT','HIGH','CRITICAL','WARNING'}:
            state.raise_dashboard_alert(message, severity='ALERT' if severity.upper() in {'ALERT','HIGH','CRITICAL'} else 'WARNING', addr=addr, event_type=event_type.upper())
            state.notify_console(message, severity='ALERT')
    except Exception:
        pass
    try:
        if state.audit is not None:
            state.audit.record(userid, event_type.upper(), message, 'SECURITY', extra={'EVENT_ID': str(seq), 'SEVERITY': severity, 'RESOURCE': resource, 'ADDR': addr})
    except Exception:
        pass
    return entry


def _audit_events(state):
    return list(getattr(getattr(state, 'audit', None), 'events', []) or [])


def _format_security(entries: list[dict[str, Any]], title='SECURITY EVENT TIMELINE') -> str:
    lines = [title, 'ID    TIME                 TYPE          SEV      USERID    RESOURCE             RESULT', '-'*86]
    for e in entries[-30:]:
        lines.append(f"{e.get('id',0):<5} {e.get('time',''):<19} {e.get('type','')[:12]:<12} {e.get('severity','')[:8]:<8} {e.get('userid','')[:8]:<8} {e.get('resource','')[:20]:<20} {e.get('result','')[:10]:<10}")
        if e.get('message'):
            lines.append(f"      {e['message'][:100]}")
    if len(lines) == 3:
        lines.append('NO SECURITY EVENTS RECORDED')
    return '\n'.join(lines)


def _sync_security_from_audit(state) -> None:
    st = _ensure_v26(state)
    seen = {(e.get('type'), e.get('time'), e.get('message')) for e in st['security_events']}
    for ev in _audit_events(state)[-200:]:
        if ev.component not in {'SMF80','SMF7','SECURITY','CONSOLE'}:
            continue
        typ = ev.extra.get('EVENT', ev.component).upper() if getattr(ev, 'extra', None) else ev.component
        msg = ev.result or ev.command
        key = (typ, ev.ts.strftime('%Y-%m-%d %H:%M:%S'), msg)
        if key in seen:
            continue
        st['security_events'].append({'id': len(st['security_events'])+1, 'time': ev.ts.strftime('%Y-%m-%d %H:%M:%S'), 'userid': ev.userid, 'type': typ, 'severity': 'WARNING' if 'FAIL' in ev.result.upper() or 'DEN' in ev.result.upper() else 'INFO', 'resource': ev.extra.get('RESOURCE','') if getattr(ev,'extra',None) else '', 'result': ev.extra.get('RESULT','') if getattr(ev,'extra',None) else ev.result[:10], 'addr': ev.extra.get('ADDR','') if getattr(ev,'extra',None) else '', 'service': ev.extra.get('SERVICE','') if getattr(ev,'extra',None) else ev.component, 'message': msg})
    st['security_events'] = st['security_events'][-500:]


def command_security(state, userid: str, cmd: str) -> str | None:
    u = cmd.upper().strip()
    if u in {'D SECURITY','DISPLAY SECURITY','SECURITY LIST','D SECURITY,RECENT','DISPLAY SECURITY,RECENT'}:
        _sync_security_from_audit(state)
        return _format_security(_ensure_v26(state)['security_events'])
    if u == 'SECURITY SUMMARY':
        _sync_security_from_audit(state)
        counts = {}
        for e in _ensure_v26(state)['security_events']:
            counts[e['type']] = counts.get(e['type'], 0) + 1
        lines = ['SECURITY EVENT SUMMARY', 'TYPE                 COUNT']
        lines += [f'{k:<20} {v:>5}' for k,v in sorted(counts.items())]
        return '\n'.join(lines) if len(lines) > 2 else 'NO SECURITY EVENTS RECORDED'
    m = re.match(r'^(?:D|DISPLAY) SECURITY,TYPE=([A-Z0-9_]+)$', u)
    if m:
        _sync_security_from_audit(state); typ=m.group(1)
        return _format_security([e for e in _ensure_v26(state)['security_events'] if e['type'].replace('_','') == typ.replace('_','')], f'SECURITY EVENTS TYPE={typ}')
    m = re.match(r'^(?:D|DISPLAY) SECURITY,USER=([A-Z0-9#$@]+)$', u)
    if m:
        _sync_security_from_audit(state); who=m.group(1)
        return _format_security([e for e in _ensure_v26(state)['security_events'] if e['userid'] == who], f'SECURITY EVENTS USER={who}')
    if u in {'D SECURITY,EXPORT','DISPLAY SECURITY,EXPORT'}:
        outdir = Path(getattr(state.config, 'sim_root', Path('~/mfsim').expanduser()))/'exports'
        outdir.mkdir(parents=True, exist_ok=True)
        path = outdir/'security_events.json'
        _sync_security_from_audit(state)
        path.write_text(json.dumps(_ensure_v26(state)['security_events'], indent=2), encoding='utf-8')
        return f'IEE600I SECURITY EVENTS EXPORTED TO {path}'
    return None


def command_smf(state, userid: str, cmd: str) -> str | None:
    u = cmd.upper().strip().replace('DISPLAY ', 'D ')
    if not (u.startswith('SMF') or u.startswith('D SMF')):
        return None
    events = _audit_events(state)
    if u in {'SMF SUMMARY','D SMF,SUMMARY','D SMF'}:
        counts = {}
        for e in events:
            if e.component.startswith('SMF'):
                typ = e.component.replace('SMF','TYPE ')
                counts[typ] = counts.get(typ, 0) + 1
        lines = ['IEE974I SMF SIMULATED RECORD SUMMARY', 'RECORD TYPE       COUNT']
        lines += [f'{k:<16} {v:>5}' for k,v in sorted(counts.items())]
        return '\n'.join(lines) if len(lines)>2 else 'IEE974I NO SIMULATED SMF RECORDS AVAILABLE'
    if u.startswith('SMF EXPORT'):
        fmt = 'CSV' if 'CSV' in u else 'JSON'
        outdir = Path(state.config.sim_root)/'exports'; outdir.mkdir(parents=True, exist_ok=True)
        rows = [{'time':e.ts.isoformat(), 'userid':e.userid, 'component':e.component, 'command':e.command, 'result':e.result, 'extra':e.extra} for e in events if e.component.startswith('SMF')]
        if fmt == 'JSON':
            p=outdir/'smf_records.json'; p.write_text(json.dumps(rows, indent=2, default=str), encoding='utf-8')
        else:
            p=outdir/'smf_records.csv'
            with p.open('w', newline='', encoding='utf-8') as fh:
                w=csv.DictWriter(fh, fieldnames=['time','userid','component','command','result']); w.writeheader(); w.writerows({k:r[k] for k in ['time','userid','component','command','result']} for r in rows)
        return f'IEE974I SMF {fmt} EXPORT WRITTEN TO {p}'
    if u.startswith('SMF SHOW'):
        recid = u.split()[-1]
        try: idx = int(re.sub(r'\D','',recid)) - 1
        except Exception: idx = -1
        smfs = [e for e in events if e.component.startswith('SMF')]
        if 0 <= idx < len(smfs):
            e=smfs[idx]
            lines=[f'SMF RECORD {idx+1:06d}', f'TYPE      : {e.component}', f'TIME      : {e.ts}', f'USERID    : {e.userid}', f'COMMAND   : {e.command}', f'RESULT    : {e.result}']
            for k,v in sorted(e.extra.items()): lines.append(f'{k:<10}: {v}')
            return '\n'.join(lines)
        return 'IEE974I SMF RECORD NOT FOUND'
    # list filters
    filt = [e for e in events if e.component.startswith('SMF')]
    m = re.search(r'TYPE\((\d+)\)|TYPE=(\d+)', u)
    if m:
        typ = m.group(1) or m.group(2); filt=[e for e in filt if e.component == f'SMF{typ}']
    m = re.search(r'USER\(([^)]+)\)|USER=([A-Z0-9#$@]+)', u)
    if m:
        who=(m.group(1) or m.group(2)).upper(); filt=[e for e in filt if e.userid==who]
    lines=['SMF RECORD LIST', 'ID     TIME      TYPE   USERID    EVENT/COMMAND']
    for i,e in enumerate(filt[-50:],1):
        lines.append(f'{i:<6} {e.ts.strftime("%H:%M:%S")} {e.component:<6} {e.userid[:8]:<8} {e.command[:52]}')
    return '\n'.join(lines) if len(lines)>2 else 'IEE974I NO SIMULATED SMF RECORDS MATCH REQUEST'


_ACCESS_RANK = {'NONE':0, 'READ':1, 'UPDATE':2, 'CONTROL':3, 'ALTER':4}

def explain_access(state, userid: str, cmd: str) -> str | None:
    u = cmd.upper().strip()
    st = _ensure_v26(state)
    if u == 'RACFTRACE ON': st['racftrace']=True; return 'IRR900I RACF TRACE ENABLED'
    if u == 'RACFTRACE OFF': st['racftrace']=False; return 'IRR901I RACF TRACE DISABLED'
    if u in {'D RACFTRACE','DISPLAY RACFTRACE','RACFTRACE SHOW'}:
        lines=['RACF TRACE STATUS: ' + ('ON' if st['racftrace'] else 'OFF')]
        lines += st['racftrace_entries'][-25:] or ['NO TRACE ENTRIES']
        return '\n'.join(lines)
    if u == 'RACFTRACE CLEAR': st['racftrace_entries'].clear(); return 'IRR902I RACF TRACE CLEARED'
    if not u.startswith('WHYACCESS '): return None
    parts = cmd.split()
    if len(parts) < 4:
        return 'WHYACCESS SYNTAX: WHYACCESS userid resource access [CLASS(class)]'
    who = parts[1].upper(); resource = parts[2].strip("'").upper(); req = parts[3].upper(); cls='DATASET'
    m = re.search(r'CLASS\(([^)]+)\)', cmd, re.I)
    if m: cls=m.group(1).upper()
    noracf = getattr(state.config, 'security_mode', 'vuln') == 'noracf'
    profile = resource; uacc='UNKNOWN'; userpermit='NONE'; grouppermit='NONE'; warning='NO'; allowed = noracf
    try:
        prof = state.dynamic_racf._find_profile(cls, resource)
        if prof:
            profile = prof.name; uacc = prof.uacc; warning = 'YES' if getattr(prof,'warning',False) else 'NO'; userpermit=prof.permits.get(who,'NONE')
            granted = max(_ACCESS_RANK.get(uacc,0), _ACCESS_RANK.get(userpermit,0), _ACCESS_RANK.get(grouppermit,0))
            allowed = granted >= _ACCESS_RANK.get(req,1) or warning == 'YES'
        else:
            allowed = cls != 'DATASET' or not resource.startswith('SYS1.')
            uacc = 'READ' if allowed else 'NONE'
    except Exception:
        allowed = noracf or not (cls == 'DATASET' and resource.startswith('SYS1.'))
    result = 'ALLOWED' if allowed else 'DENIED'
    reason = 'NORACF bypass active' if noracf else (f'{req} permitted by WARNING profile' if warning == 'YES' and allowed else (f'{req} access satisfied' if allowed else f'{req} required, insufficient permission'))
    lines=[f'ACCESS CHECK: {who} -> {resource} {req}', f'CLASS: {cls}', f'MATCHED PROFILE: {profile}', f'UACC: {uacc}', f'USER PERMIT: {userpermit}', f'GROUP PERMIT: {grouppermit}', f'WARNING: {warning}', f'NORACF: {"YES" if noracf else "NO"}', f'RESULT: {result}', f'REASON: {reason}']
    trace=' | '.join(lines)
    if st['racftrace']: st['racftrace_entries'].append(trace); st['racftrace_entries']=st['racftrace_entries'][-100:]
    try:
        if not allowed: security_event(state, 'RACF_DENY', trace, userid=who, severity='WARNING', resource=resource, result='DENIED')
    except Exception: pass
    return '\n'.join(lines)


def command_net(state, userid: str, cmd: str) -> str | None:
    u = cmd.upper().strip().replace('DISPLAY ', 'D ')
    if 'NETSTAT' in u:
        return None
    if not (u.startswith('D NET') or u in {'D TCPIP'} or u.startswith('D TCPIP,CONN') or u.startswith('D TCPIP,PORTS')):
        return None
    sessions = list(getattr(state.sessions, 'sessions', {}).values())
    ports=[]
    try:
        if state.service_manager:
            for name, st, port, desc in state.service_manager.status_rows(): ports.append((name, st, port, desc))
    except Exception: pass
    if 'PORTS' in u or u == 'D TCPIP':
        lines=['EZZ2500I TCP/IP PORT STATUS', 'SERVICE   STATE     PORT   DESCRIPTION']
        for name, st, port, desc in ports: lines.append(f'{name:<8} {st:<8} {str(port):<6} {desc}')
        return '\n'.join(lines)
    lines=['EZD0101I NETWORK SESSION DISPLAY', 'USERID    ADDRESS           SERVICE  AGE       FLAGS']
    for s in sessions:
        lines.append(f'{s.userid:<8} {s.addr:<16} TSO      CONNECTED {"ACTIVE" if s.connected else "ENDED"}')
    if len(lines)==2: lines.append('NO ACTIVE NETWORK SESSIONS')
    return '\n'.join(lines)


def command_apf(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip().replace('DISPLAY ', 'D ')
    if u not in {'D APF,RISK','D APF,HISTORY','APF RISK','APF HISTORY'} and not u.startswith('D APF,LIB='):
        return None
    st=_ensure_v26(state)
    if 'HISTORY' in u:
        lines=['APF CHANGE HISTORY','TIME                 USERID    ACTION  DATASET/VOLUME                    RISK']
        for h in st['apf_history'][-40:]: lines.append(f"{h.get('time',''):<19} {h.get('userid',''):<8} {h.get('action',''):<7} {h.get('dataset','')[:32]:<32} {','.join(h.get('risk',[]))}")
        return '\n'.join(lines) if len(lines)>2 else 'NO APF HISTORY RECORDED'
    libs = list(getattr(state,'apf_libraries',[]) or [])
    lines=['APF AUTHORIZATION RISK DISPLAY','DATASET                         RISK FLAGS']
    for lib in libs:
        flags=[]
        if not lib.startswith('SYS1.'): flags.append('NON-SYS1')
        if lib.startswith(userid.upper()+'.'): flags.append('USER-CONTROLLED')
        if 'VULN' in lib: flags.append('TRAINING-VULN')
        lines.append(f'{lib[:32]:<32} {",".join(flags) if flags else "BASELINE"}')
    return '\n'.join(lines)


def record_apf_change(state, userid: str, action: str, dataset: str, volume: str, result: str='SUCCESS') -> None:
    st=_ensure_v26(state); risk=[]
    if not dataset.upper().startswith('SYS1.'): risk.append('NON-SYS1')
    if getattr(state.config,'security_mode','') == 'noracf': risk.append('NORACF')
    st['apf_history'].append({'time':_now(), 'userid':userid.upper(), 'action':action.upper(), 'dataset':dataset.upper(), 'volume':volume.upper(), 'result':result, 'risk':risk})
    security_event(state, 'APF', f'APF {action.upper()} DSNAME={dataset.upper()} VOLUME={volume.upper()} RESULT={result}', userid=userid, severity='WARNING' if action.upper()=='ADD' else 'INFO', resource=dataset, result=result)


def command_detection(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip()
    st=_ensure_v26(state)
    if u in {'D DETECTION','DISPLAY DETECTION'}:
        lines=['GIBSON DETECTION RULES','RULE              ENABLED THRESHOLD WINDOW SEVERITY']
        for k,v in sorted(st['detection'].items()): lines.append(f"{k:<17} {str(v.get('enabled',True)):<7} {str(v.get('threshold','-')):<9} {str(v.get('window','-')):<6} {v.get('severity','INFO')}")
        return '\n'.join(lines)
    if u.startswith('SET DETECTION RESET'):
        st['detection'].clear(); _ensure_v26(state); return 'IEE600I DETECTION RULES RESET'
    m=re.match(r'SET DETECTION (\w+) THRESHOLD (\d+) WINDOW (\d+)', u)
    if m:
        rule=m.group(1); st['detection'].setdefault(rule, {'enabled':True}); st['detection'][rule].update({'threshold':int(m.group(2)), 'window':int(m.group(3))})
        if rule=='PORTSCAN': state.config.port_scan_threshold=int(m.group(2)); state.config.port_scan_window=int(m.group(3))
        return f'IEE600I DETECTION {rule} THRESHOLD={m.group(2)} WINDOW={m.group(3)}'
    m=re.match(r'SET DETECTION SUPPRESS_LOCALHOST_SCAN (ON|OFF)', u)
    if m:
        state.config.suppress_localhost_scan = (m.group(1) == 'ON')
        st['detection'].setdefault('SUPPRESS_LOCALHOST_SCAN', {})['enabled'] = state.config.suppress_localhost_scan
        return f'IEE600I DETECTION SUPPRESS_LOCALHOST_SCAN {m.group(1)}'
    m=re.match(r'SET DETECTION (\w+) (ON|OFF)', u)
    if m:
        st['detection'].setdefault(m.group(1), {})['enabled'] = (m.group(2)=='ON'); return f'IEE600I DETECTION {m.group(1)} {m.group(2)}'
    return None


def command_explain(cmd: str) -> str | None:
    u=cmd.upper().strip()
    if not u.startswith('EXPLAIN '): return None
    topic=u.split(None,1)[1]
    entries={
        'SETPROG APF':'SETPROG APF adds or deletes a simulated APF-authorized library. Use SETPROG APF,ADD,DSNAME=dsn,VOLUME=vol and D APF,RISK to review risk.',
        'SEARCH ALL WARNING NOMASK':'SEARCH ALL WARNING NOMASK lists RACF profiles in WARNING mode. WARNING permits the access path for training but records a warning/audit event.',
        'LISTDS STATUS HISTORY':'LISTDS dsn STATUS HISTORY displays simulated dataset metadata, catalog state, allocation, owner, and recent access/change history.',
        'NORACF':'NORACF disables simulated RACF authorization checks. It is intentionally dangerous and is logged as a security event.',
        'SMF TYPE 7':'SMF Type 7 is Gibson\'s simulated data-lost record. It is used to teach audit gaps and logging failure conditions.',
        'SDSF FILTER':'SDSF FILTER restricts panel rows, for example FILTER OWNER IBMUSER. RESET clears filters.',
        'WHYACCESS':'WHYACCESS explains a RACF access decision: WHYACCESS userid resource access [CLASS(class)].',
        'SPLITCON':'SPLITCON is not available in Gibson v26.1. Use the standard master console and dashboard monitoring.',
        'SEND NOW':'SEND \'text\' USER(userid) NOW immediately delivers a TSO message to an active session if connected.',
    }
    for k,v in entries.items():
        if topic.startswith(k): return f'GIBSON EXPLAIN: {k}\n{v}\nThis is a simulator/training representation.'
    return f'GIBSON EXPLAIN: NO ENTRY FOR {topic}\nTry EXPLAIN WHYACCESS, EXPLAIN ZSECURE, EXPLAIN SMP/E, or EXPLAIN SMF TYPE 7.'


def command_pf(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip(); st=_ensure_v26(state)
    if u=='PFSHOW ON': st['pfshow']=True; return 'ISPP100I PF KEY DISPLAY ENABLED'
    if u=='PFSHOW OFF': st['pfshow']=False; return 'ISPP101I PF KEY DISPLAY DISABLED'
    if u in {'KEYS','D PFKEYS','DISPLAY PFKEYS'}:
        return 'PF KEY DEFINITIONS\n' + '\n'.join(f'{k:<5} ==> {v}' for k,v in sorted(st['pfkeys'].items()))
    m=re.match(r'SET (PF\d+) (.+)$', u)
    if m: st['pfkeys'][m.group(1)] = m.group(2); return f'ISPP102I {m.group(1)} SET TO {m.group(2)}'
    return None


def command_scenario(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip(); st=_ensure_v26(state)
    names=['APF_ABUSE','NORACF_INCIDENT','FTP_EXFIL','JES_PERSISTENCE','PORT_SCAN','SMF_LOSS','UNKNOWN_HIGH_PORT']
    if u=='SCENARIO LIST': return 'AVAILABLE GIBSON SCENARIOS\n'+'\n'.join(f'  {n}' for n in names)
    m=re.match(r'SCENARIO LOAD ([A-Z0-9_]+)', u)
    if m:
        n=m.group(1); st['active_scenario']=n; security_event(state,'SCENARIO',f'SCENARIO {n} LOADED',userid=userid,severity='INFO',resource=n)
        return f'GIBSCN001I SCENARIO {n} LOADED\nOBJECTIVE: Investigate and document the simulated evidence chain.'
    if u=='SCENARIO STATUS': return f'ACTIVE SCENARIO: {st.get("active_scenario") or "NONE"}'
    if u=='SCENARIO RESET': st['active_scenario']=None; return 'GIBSCN002I SCENARIO STATE RESET'
    if u=='SCENARIO HINT': return 'HINT: Review D SECURITY, SMF SUMMARY, D APF,RISK, D NET,WARNINGS, and SDSF panels.'
    if u=='SCENARIO SOLUTION': return 'SOLUTION: Correlate console warnings, security events, SMF records, APF/JES/network state, and dataset history.'
    return None


def _hist_key(ds: str) -> str: return ds.upper().strip("'")

def track_dataset_change(state, userid: str, ds: str, action: str, text: str='') -> None:
    st=_ensure_v26(state); key=_hist_key(ds)
    versions=st['dataset_history'].setdefault(key, [])
    versions.append({'version':len(versions)+1,'time':_now(),'userid':userid.upper(),'action':action.upper(),'size':len(text or ''),'text':text or ''})
    versions[:] = versions[-50:]


def command_dataset_history(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip(); st=_ensure_v26(state)
    if u.startswith('D DATASET,HISTORY='):
        ds=cmd.split('=',1)[1].strip(); u='HISTORY '+ds
    if u.startswith('HISTORY '):
        ds=cmd.split(None,1)[1].strip().strip("'").upper(); versions=st['dataset_history'].get(ds, [])
        lines=[f'DATASET CHANGE HISTORY {ds}','VER TIME                 USERID    ACTION     SIZE']
        for v in versions: lines.append(f"{v['version']:<3} {v['time']:<19} {v['userid']:<8} {v['action']:<10} {v['size']:>6}")
        return '\n'.join(lines) if len(lines)>2 else f'NO CHANGE HISTORY FOR {ds}'
    m=re.match(r'DIFF\s+([^ ]+)\s+VERSION\((\d+)\)\s+VERSION\((\d+)\)', cmd, re.I)
    if m:
        ds=m.group(1).strip("'").upper(); a=int(m.group(2)); b=int(m.group(3)); versions=st['dataset_history'].get(ds, [])
        if a<1 or b<1 or a>len(versions) or b>len(versions): return 'ISPDX001I VERSION NOT FOUND'
        old=versions[a-1].get('text','').splitlines(); new=versions[b-1].get('text','').splitlines()
        lines=[f'DIFF {ds} VERSION({a}) VERSION({b})']
        for line in old:
            if line not in new: lines.append('- '+line)
        for line in new:
            if line not in old: lines.append('+ '+line)
        return '\n'.join(lines)
    m=re.match(r'RESTORE\s+([^ ]+)\s+VERSION\((\d+)\)', cmd, re.I)
    if m:
        ds=m.group(1).strip("'").upper(); ver=int(m.group(2)); versions=st['dataset_history'].get(ds, [])
        if ver<1 or ver>len(versions): return 'ISRDR001I VERSION NOT FOUND'
        try:
            state.datasets.write(userid, ds, versions[ver-1].get('text',''))
            track_dataset_change(state, userid, ds, 'RESTORE', versions[ver-1].get('text',''))
            return f'ISRDR002I {ds} RESTORED TO VERSION {ver}'
        except Exception as e: return f'ISRDR003I RESTORE FAILED - {e}'
    return None


def command_export(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip()
    if not u.startswith('EXPORT EVIDENCE'): return None
    outdir=Path(state.config.sim_root)/'exports'/('evidence_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    outdir.mkdir(parents=True, exist_ok=True)
    _sync_security_from_audit(state); st=_ensure_v26(state)
    (outdir/'security_events.json').write_text(json.dumps(st['security_events'], indent=2), encoding='utf-8')
    smf=[{'time':e.ts.isoformat(),'userid':e.userid,'component':e.component,'command':e.command,'result':e.result,'extra':e.extra} for e in _audit_events(state) if e.component.startswith('SMF')]
    (outdir/'smf_records.json').write_text(json.dumps(smf, indent=2, default=str), encoding='utf-8')
    (outdir/'dataset_history.txt').write_text(json.dumps(st['dataset_history'], indent=2), encoding='utf-8')
    (outdir/'apf_history.txt').write_text(json.dumps(st['apf_history'], indent=2), encoding='utf-8')
    (outdir/'network_sessions.txt').write_text(command_net(state, userid, 'D NET,SESSIONS') or '', encoding='utf-8')
    (outdir/'scenario_status.txt').write_text(command_scenario(state, userid, 'SCENARIO STATUS') or '', encoding='utf-8')
    (outdir/'summary.md').write_text(f'# Gibson evidence bundle\n\nGenerated: {_now()}\nUser: {userid}\n', encoding='utf-8')
    zip_path=outdir.with_suffix('.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in outdir.iterdir(): z.write(p, p.name)
    return f'GIBEVD001I EVIDENCE BUNDLE EXPORTED TO {zip_path}'



def _smf_by_component(state, comps: set[str]) -> list[Any]:
    return [e for e in _audit_events(state) if e.component.upper() in comps]

def command_zsecure(state, userid: str, cmd: str) -> str | None:
    u = cmd.upper().strip().replace('DISPLAY ', 'D ')
    if u not in {'ZSECURE','ZSEC','CKR'} and not u.startswith('ZSEC ') and not u.startswith('D ZSEC'):
        return None
    _sync_security_from_audit(state); events=_ensure_v26(state)['security_events'][-200:]
    def menu():
        return '\n'.join(['ZSECURE MAIN MENU - zSecure / Mainframe Security Monitor - Gibson Simulation','1  RACF user review        2  Privileged users','3  UID(0) / OMVS review    4  Dataset exposure review','5  General resource review 6  CICS security review','7  DB2 security review     8  SERVAUTH / network review','9  PassTicket review       A  MFA review','B  ICSF / crypto review    C  RACDCERT / certificate review','D  Started task review     E  SURROGAT review','F  JES review              G  SMF event review','H  Compliance summary      I  Drift analysis','J  Findings export         X  Exit','Commands: ZSEC PRIVILEGE UID0 STARTED SURROGAT JES TSOAUTH SERVAUTH PASSTICKET CICS DB2 ICSF RACDCERT DRIFT COMPLIANCE REPORTS'])
    if u in {'ZSECURE','ZSEC','CKR'}: return menu()
    if 'SMF7' in u:
        rows=_smf_by_component(state, {'SMF7'}); lines=['ZSECURE SMF TYPE 7 - DATA LOST CONDITIONS','TIME                 USERID    RESULT']
        for e in rows[-50:]: lines.append(f'{e.ts:%Y-%m-%d %H:%M} {e.userid:<8} {e.result[:60]}')
        return '\n'.join(lines) if len(lines)>2 else 'ZSECURE: NO SMF7 RECORDS FOUND'
    if 'SMF80' in u or 'EVENT' in u or 'SMF' in u:
        rows=_smf_by_component(state, {'SMF80'}); lines=['ZSECURE EVENTS / SMF80 REVIEW','TIME                 USERID    COMMAND/ACTION                         RESULT']
        for e in rows[-50:]: lines.append(f'{e.ts:%Y-%m-%d %H:%M} {e.userid:<8} {e.command[:38]:<38} {e.result[:20]}')
        if len(lines)==2:
            for e in events[-30:]: lines.append(f"{e.get('time','')[:16]:<16} {e.get('userid',''):<8} {e.get('type',''):<16} {e.get('result','')}")
        return '\n'.join(lines) if len(lines)>2 else 'ZSECURE: NO SECURITY EVENTS FOUND'
    if 'ALERT' in u or 'COMPLIANCE' in u:
        rows=[e for e in events if e.get('severity') in {'ALERT','HIGH','CRITICAL','WARNING'} or e.get('type') in {'PORT_SCAN','UNKNOWN_HIGH_PORT','RACF_DENY','NORACF','SMF7'}]
        lines=['ZSECURE ALERTS AND COMPLIANCE EXCEPTIONS','ID TYPE              SEV      USERID    RESOURCE             MESSAGE']
        for e in rows[-50:]: lines.append(f"{e.get('id',0):<2} {e.get('type','')[:16]:<16} {e.get('severity','')[:8]:<8} {e.get('userid','')[:8]:<8} {e.get('resource','')[:20]:<20} {e.get('message','')[:55]}")
        return '\n'.join(lines) if len(lines)>2 else 'ZSECURE: NO ALERTS'
    if 'APF' in u: return command_apf(state, userid, 'D APF,HISTORY') or 'ZSECURE: NO APF HISTORY'
    if 'SETROPTS' in u or 'PASSWORD' in u:
        pol=getattr(state,'password_policy',None)
        return '\n'.join(['ZSECURE SETROPTS / PASSWORD POLICY'] + (pol.list_lines() if pol else ['NO POLICY STATE']))
    if 'MFA' in u:
        mgr=getattr(state,'mfa_manager',None)
        uads=getattr(state,'uads',None)
        lines=['ZSECURE MFA COVERAGE']
        if mgr: lines.append(mgr.status())
        if uads:
            for uid,e in sorted(uads.entries.items()): lines.append(f"{uid:<8} REQUIRED({'YES' if e.mfa_required else 'NO '}) TYPE({e.mfa_type or '-'}) SECRET(MASKED)")
        return '\n'.join(lines)
    if 'UADS' in u:
        uads=getattr(state,'uads',None)
        return '\n'.join(['ZSECURE SYS1.UADS REVIEW'] + (uads.list_lines() if uads else ['SYS1.UADS STATE NOT AVAILABLE']))
    if 'CICS' in u:
        try:
            from gibson.core.cics_region import get_cics_region
            reg=get_cics_region(state)
            return '\n'.join(['ZSECURE CICS SECURITY POSTURE'] + reg.security_status_lines())
        except Exception as e:
            return 'ZSECURE CICS SECURITY POSTURE\nUNAVAILABLE: '+str(e)
    if 'RACF' in u:
        lines=['ZSECURE RACF OVERVIEW','USERS: ' + ', '.join(sorted(getattr(state.racf, 'users', {}).keys())[:20]), 'DATASET PROFILES:']
        for name,prof in sorted(state.dynamic_racf.profiles.get('DATASET', {}).items())[:30]: lines.append(f'  {name:<28} UACC({prof.uacc}) WARNING({"YES" if prof.warning else "NO"})')
        return '\n'.join(lines)
    if 'ACCESS' in u: return 'ZSECURE ACCESS ANALYSIS\nUse WHYACCESS userid dataset access for detailed access decision analysis.'
    if 'REPORT' in u:
        counts={}
        for e in events: counts[e.get('type','UNKNOWN')]=counts.get(e.get('type','UNKNOWN'),0)+1
        return 'ZSECURE AUDIT REPORT\n'+'\n'.join(f'{k:<24} {v:>5}' for k,v in sorted(counts.items()))
    return menu()

def command_smpe(state, userid: str, cmd: str) -> str | None:
    u = cmd.upper().strip().replace('SMP/E','SMPE')
    if u != 'SMPE' and not u.startswith('SMPE '): return None
    st=_ensure_v26(state); smpe=st['smpe']
    def menu(): return '\n'.join(['SMP/E MAIN MENU - GIBSON TRAINING SIMULATION','1  CSI          - Consolidated software inventory','2  ZONES        - GLOBAL, TARGET, DLIB zones','3  SYSMODS      - FMIDs, PTFs, APARs, USERMODs','4  RECEIVE      - Simulate receiving maintenance','5  APPLY        - Simulate applying maintenance to target zone','6  ACCEPT       - Simulate accepting maintenance to DLIB zone','7  REPORTS      - Maintenance and exception reports','8  HOLDDATA     - Review simulated holds','X  Exit'])
    if u=='SMPE': return menu()
    if 'CSI' in u: return f"SMP/E CSI OVERVIEW\nGLOBAL CSI . . . : {smpe['CSI']}\nTARGET CSI . . . : TARGET.CSI\nDLIB CSI . . . . : DLIB.CSI"
    if 'ZONE' in u: return 'SMP/E ZONES\n'+'\n'.join(f'  {z}' for z in smpe['zones'])
    if 'LIST' in u or 'SYSMOD' in u: return 'SMP/E SYSMOD STATUS\nSYSMOD    STATUS\n'+'\n'.join(f'{k:<9} {v}' for k,v in sorted(smpe['sysmods'].items()))
    m=re.search(r'RECEIVE(?:\s+([A-Z0-9]+))?', u)
    if m:
        name=m.group(1) or 'UNEW261'; smpe['sysmods'][name]='RECEIVED'; security_event(state,'SMPE',f'SYSMOD {name} RECEIVED',userid=userid,resource=name); return f'GIMSMP001I SYSMOD {name} RECEIVED'
    m=re.search(r'APPLY(?:\s+CHECK)?(?:\s+([A-Z0-9]+))?', u)
    if m:
        check='CHECK' in u; name=m.group(1) or next((k for k,v in smpe['sysmods'].items() if v=='RECEIVED'),'UGIB261')
        if check: return f'GIMSMP002I APPLY CHECK SUCCESSFUL FOR {name}'
        smpe['sysmods'][name]='APPLIED'; security_event(state,'SMPE',f'SYSMOD {name} APPLIED',userid=userid,resource=name); return f'GIMSMP003I SYSMOD {name} APPLIED TO TARGET ZONE'
    m=re.search(r'ACCEPT(?:\s+CHECK)?(?:\s+([A-Z0-9]+))?', u)
    if m:
        check='CHECK' in u; name=m.group(1) or next((k for k,v in smpe['sysmods'].items() if v=='APPLIED'),'UGIB261')
        if check: return f'GIMSMP004I ACCEPT CHECK SUCCESSFUL FOR {name}'
        smpe['sysmods'][name]='ACCEPTED'; security_event(state,'SMPE',f'SYSMOD {name} ACCEPTED',userid=userid,resource=name); return f'GIMSMP005I SYSMOD {name} ACCEPTED INTO DLIB ZONE'
    if 'HOLD' in u: return 'SMP/E HOLDDATA\nUZSEC80  SYSTEM HOLD - REVIEW SMF80 REPORTING DEPENDENCY\nUGIB261  NO HOLDS'
    if 'REPORT' in u: return 'SMP/E EXCEPTION REPORT\nNO CRITICAL EXCEPTIONS. HELD SYSMODS REQUIRE REVIEW BEFORE APPLY.'
    return menu()

def command_split(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip()
    if u.startswith("SPLITCON") or u in {"D SPLITCON", "DISPLAY SPLITCON"}:
        return "IEE305I SPLITCON COMMAND NOT AVAILABLE IN THIS RELEASE"
    if u in {"REFRESH", "CLEAR", "CLS"}: return "IEE600I CONSOLE DISPLAY REFRESHED"
    return None

def dispatch_tso(state, userid: str, cmd: str) -> str | None:
    for fn in (command_split, command_zsecure, command_smpe, command_security, command_smf, explain_access, command_net, command_apf, command_detection, lambda s,u,c: command_explain(c), command_pf, command_scenario, command_dataset_history, command_export):
        try:
            out = fn(state, userid, cmd)
            if out is not None: return out
        except Exception as e:
            return f'GIBV26E COMMAND FAILED - {type(e).__name__}: {e}'
    return None


def split_monitor_lines(state) -> list[str]:
    st=_ensure_v26(state)
    try:
        vols = sorted({getattr(r,'volume','WORK01') for r in state.datasets.listcat('IBMUSER', prefix='')})[:6]
    except Exception: vols=['SBSYS1','WORK01']
    mgr=getattr(state,'service_manager',None); rows=[]
    if mgr:
        try: rows=mgr.status_rows()
        except Exception: rows=[]
    started=sum(1 for _n,s,_p,_d in rows if s=='STARTED'); total=len(rows)
    sess=list(getattr(state.sessions,'sessions',{}).values())
    alerts=list(getattr(state,'dashboard_alerts',[]))[-5:]
    jesq=len(getattr(getattr(state,'jes',None),'jobs',[]) or [])
    smfstate='ACTIVE' if getattr(state,'audit',None) else 'INACTIVE'
    racf=getattr(state.config,'security_mode','vuln').upper()
    processing='PROCESSING' if getattr(state,'console_events',None) else 'IDLE'
    lines=[
        'SYSTEM MONITOR',
        f'Time: {_hhmm()}   Date: {datetime.now().strftime("%Y-%m-%d")}',
        f'RACF: {racf}   CPU: {processing}',
        f'Volumes: {", ".join(vols)}',
        f'Services: {started}/{total} STARTED',
        'Ports:',
    ]
    for name,s,port,desc in rows[:6]: lines.append(f'  {name:<8} {s:<8} {port}')
    lines += ['Connections:']
    for ss in sess[:5]: lines.append(f'  {ss.addr:<15} {ss.userid:<8} {"ON" if ss.connected else "OFF"}')
    lines += [f'JES jobs: {jesq}   SMF: {smfstate}', 'Alerts:']
    for a in alerts: lines.append(f"  {a.get('event_type','')[:10]} {a.get('addr','') or a.get('port','')}")
    lines.append('Power: ON')
    return lines


def render_split_console(state, log_lines: Iterable[str] | None = None, width: int = 100, height: int = 30) -> str:
    logs=list(log_lines or [])[-(height-5):]
    mon=split_monitor_lines(state)
    half=max(40, width//2-1)
    rows=max(len(logs), len(mon), height-5)
    out=['\x1b[2J\x1b[H' + '┌'+'─'*half+'┬'+'─'*half+'┐']
    for i in range(rows):
        left=(logs[i] if i<len(logs) else '')[:half]
        right=(mon[i] if i<len(mon) else '')[:half]
        out.append('│'+left.ljust(half)+'│'+right.ljust(half)+'│')
    out.append('├'+'─'*half+'┴'+'─'*half+'┤')
    out.append('│COMMAND ===> '.ljust(half*2+1)+'│')
    out.append('└'+'─'*(half*2+1)+'┘')
    return '\n'.join(out)


def display_split_state(state) -> str:
    st=_ensure_v26(state)
    return f"IEE600I SPLITCON STATE={'ON' if st.get('split_console') else 'OFF'} REFRESH={st.get('split_refresh')} LAYOUT=AUTO ANSI=AUTO"


def set_split(state, enabled: bool) -> str:
    _ensure_v26(state)['split_console']=enabled
    return f"IEE600I SPLITCON {'ENABLED' if enabled else 'DISABLED'}"


def tsoe_logon_panel(userid='IBMUSER') -> str:
    return """\x1b[2J\x1b[H---------------------------------------- TSO/E LOGON ----------------------------------------

Enter LOGON parameters below:                              RACF LOGON parameters:

Userid     ===> {userid}

Password   ===>

Procedure  ===> DBSPROCC                         New Password ===>

Acct Nmbr  ===> ACCT#                            Group Ident  ===>

Size       ===> 2096128

Perform    ===>

Command    ===> ispf

Enter an 'S' before each option desired below:
        -Nomail              -Nonotice          S -Reconnect            -OIDCard

PF1/PF13 ==> Help    PF3/PF15 ==> Logoff    PA1 ==> Attention    PA2 ==> Reshow
You may request specific help information by entering a '?' in any entry field
""".format(userid=userid.upper())


def ispf_right_panel(userid: str, *, terminal: str = "3278", procedure: str = "DBSPROCC", prefix: str | None = None, account: str = "ACCT#", system_id: str = "S0W1", release: str = "ISPF 7.5") -> list[str]:
    u=(userid or "IBMUSER").upper(); p=(prefix or u).upper()
    rows=[("User ID .", u, "G"),("Time. . .", _hhmm(), "G"),("Terminal.", terminal, "G"),("Screen. .", "1", "G"),("Language.", "ENGLISH", "G"),("Appl ID .", "ISR", "G"),("TSO logon", procedure, "G"),("TSO prefix", p, "G"),("System ID", system_id, "C"),("MVS acct.", account, "C"),("Release .", release, "C")]
    try:
        from gibson.render import colors
        out=[]
        for label,value,tone in rows:
            lab_col = colors.GREEN if tone == "G" else colors.TURQUOISE
            out.append(f"{lab_col}{label:<10}: {colors.TURQUOISE}{value}{colors.RESET}")
        return out
    except Exception:
        return [f"{label:<10}: {value}" for label,value,_ in rows]

def operator_authorized(state, userid: str, resource: str, access: str = 'UPDATE') -> tuple[bool, str]:
    who=(userid or 'UNKNOWN').upper(); res=resource.upper()
    if getattr(state.config, 'security_mode', 'vuln') == 'noracf':
        security_event(state, 'OPERCMDS_BYPASS', f'NORACF bypass for {who} {res}', userid=who, severity='WARNING', resource=res, result='ALLOWED')
        return True, 'NORACF BYPASS'
    try:
        rec=state.racf.get(who)
        if rec and getattr(rec, 'special', False):
            return True, 'SPECIAL'
    except Exception:
        pass
    try:
        if state.dynamic_racf.has_access('OPERCMDS', res, who, access, state.racf):
            return True, 'PERMIT'
    except Exception:
        pass
    security_event(state, 'OPERCMDS_DENY', f'USER {who} NOT AUTHORIZED TO {res}', userid=who, severity='ALERT', resource=res, result='DENIED')
    return False, f'ICH408I USER({who}) NOT AUTHORIZED TO RESOURCE {res} IN CLASS OPERCMDS'


# --- FIBS CTI/RSS enhancements ---
def _rss_config_dsn(userid: str = 'IBMUSER') -> str:
    return FEEDS_DSN

def command_rss(state, userid: str, cmd: str) -> str | None:
    u=(cmd or '').upper().strip()
    if u!='RSS' and not u.startswith('RSS '):
        return None
    return rss_command(state, userid, cmd)

def _zsec_menu() -> str:
    return '\n'.join(['ZSECURE MAIN MENU - zSecure / Mainframe Security Monitor - Gibson Simulation','1  RACF user review        2  Privileged users','3  UID(0) / OMVS review    4  Dataset exposure review','5  General resource review 6  CICS security review','7  DB2 security review     8  SERVAUTH / network review','9  PassTicket review       A  MFA review','B  ICSF / crypto review    C  RACDCERT / certificate review','D  Started task review     E  SURROGAT review','F  JES review              G  SMF event review','H  Compliance summary      I  Drift analysis','J  Findings export         X  Exit','Commands: ZSEC PRIVILEGE UID0 STARTED SURROGAT JES TSOAUTH SERVAUTH PASSTICKET CICS DB2 ICSF RACDCERT DRIFT COMPLIANCE REPORTS'])

def command_zsecure(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip().replace('DISPLAY ', 'D ')
    if u not in {'ZSECURE','ZSEC','CKR'} and not u.startswith('ZSEC ') and not u.startswith('ZSECURE ') and not u.startswith('D ZSEC'): return None
    _sync_security_from_audit(state); events=_ensure_v26(state)['security_events'][-500:]
    if u in {'ZSECURE','ZSEC','CKR'}: return _zsec_menu()
    # numeric shortcuts from interactive menu
    last = u.split()[-1]
    if last=='1': u='ZSEC EVENTS'
    elif last=='2': u='ZSEC RACF'
    elif last=='3': u='ZSEC ACCESS'
    elif last=='4': u='ZSEC COMPLIANCE'
    elif last=='5': u='ZSEC ALERTS'
    elif last=='6': u='ZSEC SMF'
    elif last=='7': u='ZSEC REPORTS'
    elif last=='8': u='ZSEC APF'
    elif last=='9': u='ZSEC PASSTICKET'
    elif last=='A': u='ZSEC MFA'
    elif last=='B': u='ZSEC ICSF'
    elif last=='C': u='ZSEC RACDCERT'
    elif last=='D': u='ZSEC STARTED'
    elif last=='E': u='ZSEC SURROGAT'
    elif last=='F': u='ZSEC JES'
    elif last=='G': u='ZSEC SMF'
    elif last=='H': u='ZSEC COMPLIANCE'
    elif last=='I': u='ZSEC DRIFT'
    elif last=='J': u='ZSEC REPORTS'
    elif last=='2': u='ZSEC PRIVILEGE'
    elif last=='3': u='ZSEC UID0'
    def sec_rows(types=None, alerts=False):
        rows=events
        if types: rows=[e for e in rows if e.get('type') in types]
        if alerts: rows=[e for e in rows if e.get('severity') in {'ALERT','HIGH','CRITICAL','WARNING'} or e.get('type') in {'PORT_SCAN','UNKNOWN_HIGH_PORT','RACF_DENY','SYS1_EDIT_DENIED','APF','NORACF','SMF7'}]
        return rows
    if 'ALERT' in u or 'COMPLIANCE' in u:
        rows=sec_rows(alerts=True); title='ZSECURE ALERTS AND COMPLIANCE EXCEPTIONS'
        lines=[title,'ID TYPE              SEV      USERID    RESOURCE             MESSAGE']
        for e in rows[-80:]: lines.append(f"{e.get('id',0):<2} {e.get('type','')[:16]:<16} {e.get('severity','')[:8]:<8} {e.get('userid','')[:8]:<8} {e.get('resource','')[:20]:<20} {e.get('message','')[:60]}")
        return '\n'.join(lines) if len(lines)>2 else 'ZSECURE: NO ALERTS'
    if 'SMF7' in u or ('SMF' in u and '80' not in u):
        rows=_smf_by_component(state, {'SMF7'}); lines=['ZSECURE SMF TYPE 7 - DATA LOST CONDITIONS','TIME              USERID    RESULT']
        for e in rows[-80:]: lines.append(f'{e.ts:%Y-%m-%d %H:%M} {e.userid:<8} {e.result[:60]}')
        # include security events if no audit rows
        if len(lines)==2:
            for e in [r for r in events if r.get('type') in {'SMF7','SMF_TYPE7_LOSS'}][-80:]: lines.append(f"{e.get('time','')[:16]} {e.get('userid',''):<8} {e.get('message','')[:60]}")
        return '\n'.join(lines) if len(lines)>2 else 'ZSECURE: NO SMF7 RECORDS FOUND'
    if 'EVENT' in u or 'SMF80' in u:
        rows=_smf_by_component(state, {'SMF80'}); lines=['ZSECURE EVENTS / SMF80 REVIEW','TIME              USERID    ACTION                               RESULT']
        for e in rows[-80:]: lines.append(f'{e.ts:%Y-%m-%d %H:%M} {e.userid:<8} {e.command[:36]:<36} {e.result[:20]}')
        if len(lines)==2:
            for e in events[-80:]: lines.append(f"{e.get('time','')[:16]:<16} {e.get('userid',''):<8} {e.get('type',''):<20} {e.get('result','')}")
        return '\n'.join(lines) if len(lines)>2 else 'ZSECURE: NO SECURITY EVENTS FOUND'
    if 'SETROPTS' in u or 'PASSWORD' in u:
        pol=getattr(state,'password_policy',None)
        return '\n'.join(['ZSECURE SETROPTS / PASSWORD POLICY'] + (pol.list_lines() if pol else ['NO POLICY STATE']))
    if 'MFA' in u:
        mgr=getattr(state,'mfa_manager',None)
        uads=getattr(state,'uads',None)
        lines=['ZSECURE MFA COVERAGE']
        if mgr: lines.append(mgr.status())
        if uads:
            for uid,e in sorted(uads.entries.items()): lines.append(f"{uid:<8} REQUIRED({'YES' if e.mfa_required else 'NO '}) TYPE({e.mfa_type or '-'}) SECRET(MASKED)")
        return '\n'.join(lines)
    if 'UADS' in u:
        uads=getattr(state,'uads',None)
        return '\n'.join(['ZSECURE SYS1.UADS REVIEW'] + (uads.list_lines() if uads else ['SYS1.UADS STATE NOT AVAILABLE']))
    if 'CICS' in u:
        try:
            from gibson.core.cics_region import get_cics_region
            reg=get_cics_region(state)
            return '\n'.join(['ZSECURE CICS SECURITY POSTURE'] + reg.security_status_lines())
        except Exception as e:
            return 'ZSECURE CICS SECURITY POSTURE\nUNAVAILABLE: '+str(e)
    if 'RACF' in u:
        lines=['ZSECURE RACF OVERVIEW','USERS: ' + ', '.join(sorted(getattr(state.racf,'users',{}).keys())[:30]), 'DATASET PROFILES:']
        try:
            for name,prof in sorted(state.dynamic_racf.profiles.get('DATASET',{}).items())[:60]: lines.append(f'  {name:<28} UACC({prof.uacc}) WARNING({"YES" if prof.warning else "NO"})')
        except Exception: pass
        lines.append('GUEST SYS1.** ACCESS(NONE) EXPECTED IN SECURE MODE')
        return '\n'.join(lines)
    if 'ACCESS' in u:
        m=re.search(r'USER=([A-Z0-9#$@]+).*RESOURCE=([^\s]+).*ACCESS=([A-Z]+)', u)
        if m: return explain_access(state, userid, f'WHYACCESS {m.group(1)} {m.group(2)} {m.group(3)}') or ''
        return 'ZSECURE ACCESS ANALYSIS\nUse: USER=GUEST RESOURCE=SYS1.PARMLIB ACCESS=UPDATE\nOr run WHYACCESS userid resource access.'
    if 'APF' in u: return command_apf(state, userid, 'D APF,HISTORY') or 'ZSECURE: NO APF HISTORY'
    if 'REPORT' in u:
        counts={}
        for e in events: counts[e.get('type','UNKNOWN')]=counts.get(e.get('type','UNKNOWN'),0)+1
        lines=['ZSECURE AUDIT REPORT','REPORT                    COUNT']
        lines += [f'{k:<25} {v:>5}' for k,v in sorted(counts.items())]
        return '\n'.join(lines) if len(lines)>2 else 'ZSECURE: NO REPORT DATA'
    if 'SETTING' in u: return 'ZSECURE SETTINGS\nSMF80 SOURCE: AUDIT LOG\nSMF7 SOURCE : AUDIT LOG\nMODE        : SIMULATED TRAINING REPRESENTATION'
    return _zsec_menu()

def _smpe_menu() -> str:
    return '\n'.join(['SMP/E MAIN MENU - GIBSON TRAINING SIMULATION','1  CSI          - Consolidated software inventory','2  ZONES        - GLOBAL, TARGET, DLIB zones','3  SYSMODS      - FMIDs, PTFs, APARs, USERMODs','4  RECEIVE      - Simulate receiving maintenance','5  APPLY        - Simulate applying maintenance to target zone','6  ACCEPT       - Simulate accepting maintenance to DLIB zone','7  REPORTS      - Maintenance and exception reports','8  HOLDDATA     - Review simulated holds','9  SETTINGS     - SMP/E simulation settings','X  Exit'])

def command_smpe(state, userid: str, cmd: str) -> str | None:
    u=cmd.upper().strip().replace('SMP/E','SMPE')
    if u!='SMPE' and not u.startswith('SMPE '): return None
    st=_ensure_v26(state); smpe=st['smpe']
    if u=='SMPE': return _smpe_menu()
    last=u.split()[-1]
    mapn={'1':'CSI','2':'ZONES','3':'LIST SYSMODS','4':'RECEIVE','5':'APPLY CHECK','6':'ACCEPT CHECK','7':'REPORT','8':'HOLDDATA','9':'SETTINGS'}
    if last in mapn: u='SMPE '+mapn[last]
    if 'CSI' in u: return f"SMP/E CSI OVERVIEW\nGLOBAL CSI . . . : {smpe['CSI']}\nTARGET CSI . . . : TARGET.CSI\nDLIB CSI . . . . : DLIB.CSI\nLAST UPDATE . . : {_now()}"
    if 'ZONE' in u: return 'SMP/E ZONES\nZONE       TYPE      STATUS\nGLOBAL     GLOBAL    ACTIVE\nMVST100    TARGET    ACTIVE\nDLIB100    DLIB      ACTIVE'
    if 'LIST' in u or 'SYSMOD' in u: return 'SMP/E SYSMOD STATUS\nSYSMOD    STATUS\n'+'\n'.join(f'{k:<9} {v}' for k,v in sorted(smpe['sysmods'].items()))
    m=re.search(r'RECEIVE(?:\s+([A-Z0-9]+))?', u)
    if m:
        name=m.group(1) or 'U30283'; smpe['sysmods'][name]='RECEIVED'; security_event(state,'SMPE',f'SYSMOD {name} RECEIVED',userid=userid,resource=name); return f'GIMSMP001I SYSMOD {name} RECEIVED'
    m=re.search(r'APPLY(?:\s+CHECK)?(?:\s+([A-Z0-9]+))?', u)
    if m:
        check='CHECK' in u; name=m.group(1) or next((k for k,v in smpe['sysmods'].items() if v=='RECEIVED'),'U30283')
        if check: return f'GIMSMP002I APPLY CHECK SUCCESSFUL FOR {name}\nNO UNRESOLVED HOLDS BLOCK APPLY'
        smpe['sysmods'][name]='APPLIED'; security_event(state,'SMPE',f'SYSMOD {name} APPLIED',userid=userid,resource=name); return f'GIMSMP003I SYSMOD {name} APPLIED TO TARGET ZONE'
    m=re.search(r'ACCEPT(?:\s+CHECK)?(?:\s+([A-Z0-9]+))?', u)
    if m:
        check='CHECK' in u; name=m.group(1) or next((k for k,v in smpe['sysmods'].items() if v=='APPLIED'),'U30283')
        if check: return f'GIMSMP004I ACCEPT CHECK SUCCESSFUL FOR {name}\nDLIB TARGET READY'
        smpe['sysmods'][name]='ACCEPTED'; security_event(state,'SMPE',f'SYSMOD {name} ACCEPTED',userid=userid,resource=name); return f'GIMSMP005I SYSMOD {name} ACCEPTED INTO DLIB ZONE'
    if 'HOLD' in u: return 'SMP/E HOLDDATA\nUZSEC80  SYSTEM HOLD - REVIEW SMF80 REPORTING DEPENDENCY\nUGIB261  NO HOLDS'
    if 'REPORT' in u: return 'SMP/E REPORTS\nMAINTENANCE STATUS: NORMAL\nEXCEPTIONS: HELD SYSMODS REQUIRE REVIEW BEFORE APPLY'
    if 'SETTING' in u: return 'SMP/E SETTINGS\nCSI=GLOBAL.CSI\nTARGET=MVST100\nDLIB=DLIB100\nMODE=SIMULATED'
    return _smpe_menu()

def dispatch_tso(state, userid: str, cmd: str) -> str | None:
    for fn in (command_split, command_zsecure, command_smpe, command_rss, sysview_command, command_security, command_smf, explain_access, command_net, command_apf, command_detection, lambda s,u,c: command_explain(c), command_pf, command_scenario, command_dataset_history, command_export):
        try:
            out=fn(state, userid, cmd)
            if out is not None: return out
        except Exception as e:
            return f'GIBV30283E COMMAND FAILED - {type(e).__name__}: {e}'
    return None

# v30.283 aligned ISPF side panel override
def ispf_right_panel(userid: str, *, terminal: str = "3278", procedure: str = "DBSPROCC", prefix: str | None = None, account: str = "ACCT#", system_id: str = "S0W1", release: str = "ISPF 7.5") -> list[str]:
    u=(userid or "IBMUSER").upper(); p=(prefix or u).upper()
    rows=[("User ID .",u,"G"),("Time. . .",_hhmm(),"G"),("Terminal.",terminal,"G"),("Screen. .","1","G"),("Language.","ENGLISH","G"),("Appl ID .","ISR","G"),("TSO logon",procedure,"G"),("TSO prefix",p,"G"),("System ID",system_id,"C"),("MVS acct.",account,"C"),("Release .",release,"C")]
    try:
        from gibson.render import colors
        out=[]
        for label,value,tone in rows:
            lab_col = colors.GREEN if tone == "G" else colors.TURQUOISE
            # align colon/value exactly: 10-char label, colon, blank, value
            out.append(f"{lab_col}{label:<10}: {colors.TURQUOISE}{value:<12}{colors.RESET}")
        return out
    except Exception:
        return [f"{label:<10}: {value}" for label,value,_ in rows]


def ensure_operations_datasets(state, userid: str = 'IBMUSER') -> None:
    """Create/update operational datasets used by RSS, zSecure and SYSVIEW."""
    datasets = {
        FEEDS_DSN: '', CACHE_DSN: '{}\n', LASTRUN_DSN: 'NEVER\n',
        'FIBS.ZSEC.FINDINGS': 'FINDING_ID|SEVERITY|RESOURCE|REMEDIATION\n',
        'FIBS.ZSEC.COMPLIANCE': 'CONTROL|STATUS|NOTES\n',
        'FIBS.ZSEC.EVENTS': 'TIME|USERID|EVENT|RESULT\n',
        'FIBS.SYSVIEW.LOG': 'TIME|RESOURCE|ACTION|RESULT\n',
        'FIBS.SYSVIEW.ALERTS': 'TIME|SEVERITY|RESOURCE|MESSAGE\n',
        'FIBS.SYSVIEW.THRESHOLDS': 'RESOURCE|METRIC|WARN|CRIT\n',
        'FIBS.SYSVIEW.REPORTS': 'REPORT|CREATED|STATUS\n',
        'FIBS.RACF.CHANGES': 'TIME|USERID|ACTION|RESOURCE|RESULT\n',
    }
    from gibson.apps.cti_rss import _ensure_dataset
    _ensure_dataset(state, userid)
    for dsn, default in datasets.items():
        try:
            state.datasets.read(userid, dsn)
            continue
        except Exception:
            pass
        try:
            state.datasets.allocate(userid, dsn, org='PS', recfm='VB', lrecl=1024)
        except Exception:
            pass
        if default:
            try: state.datasets.write(userid, dsn, default)
            except Exception: pass

# Production-grade panel engines override thin placeholders while preserving
# legacy commands as fallback.
try:
    from gibson.apps.racf_admin import racf_admin_command
    from gibson.apps.zsecure_engine import zsecure_command as _prod_zsecure_command
    from gibson.apps.sysview_engine import sysview_command as _prod_sysview_command
except Exception:  # pragma: no cover
    racf_admin_command = None  # type: ignore
    _prod_zsecure_command = None  # type: ignore
    _prod_sysview_command = None  # type: ignore

_V26_OLD_DISPATCH_TSO_PROD = dispatch_tso

def dispatch_tso(state, userid: str, cmd: str) -> str | None:  # type: ignore[override]
    try:
        ensure_operations_datasets(state, userid)
    except Exception:
        pass
    for fn in (racf_admin_command, _prod_zsecure_command, _prod_sysview_command, command_rss):
        if fn is None:
            continue
        try:
            out = fn(state, userid, cmd)
            if out is not None:
                return out
        except Exception as e:
            return f'GIBPRODE COMMAND FAILED - {type(e).__name__}: {e}'
    return _V26_OLD_DISPATCH_TSO_PROD(state, userid, cmd)

# ---------------------------------------------------------------------------
# Gibson NMAP TSO/ISPF integration.  Uses the same safe nmap menu engine as
# OMVS nmap -M and never invokes Python input()/SystemExit menu paths.
# ---------------------------------------------------------------------------
def command_nmap(state, userid: str, cmd: str) -> str | None:
    u = (cmd or '').strip()
    if not u:
        return None
    parts = u.split()
    if parts[0].upper() not in {'NMAP','M.10'}:
        return None
    from gibson.tools.nmap_menu_engine import NmapMenuState, render_menu, run_action
    nstate = getattr(state, '_tso_nmap_menu_state', None)
    if nstate is None:
        nstate = NmapMenuState(); setattr(state, '_tso_nmap_menu_state', nstate)
    if len(parts) == 1 or parts[1].upper() in {'MENU','?','HELP'}:
        return 'M.10 NMAP - Gibson NSE-style Mainframe Enumeration\n\n' + render_menu()
    selection = parts[1]
    extra = parts[2:]
    return run_action(selection, extra, state=nstate)

_V26_DISPATCH_BEFORE_NMAP = dispatch_tso

def dispatch_tso(state, userid: str, cmd: str) -> str | None:  # type: ignore[override]
    out = command_nmap(state, userid, cmd)
    if out is not None:
        return out
    return _V26_DISPATCH_BEFORE_NMAP(state, userid, cmd)
