from __future__ import annotations

import re
from typing import Any
from gibson.core.racf_legacy_des import verify_legacy_racf_des_hash, format_john_racf_hash
from gibson.core.racf_database import materialise_racfds
from gibson.core.smf.records.type80 import racf_event
from gibson.core.smf.records.type30 import job_step
from gibson.core.smf.records.type92 import uss_file


def _reject_host_path(name: str) -> bool:
    n = (name or '').strip()
    return any(x in n for x in ['..','/','\\',':']) or n.lower().startswith(('file:','http:','https:','ftp:','gopher:','data:'))


def _corr(state: Any) -> str:
    return f"RACFDS-{len(getattr(state, 'smf_records', []))+1:06d}"


def _emit_console_cti(state: Any, msg: str, *, event_type: str, corr: str) -> None:
    try: state.notify_console(msg, severity='ALERT')
    except Exception: pass
    try: state.raise_dashboard_alert(msg, severity='ALERT', event_type=event_type)
    except Exception: pass


def extract_hashes(state: Any, userid: str, input_dsn: str, output_dsn: str | None = None) -> str:
    if _reject_host_path(input_dsn) or (output_dsn and _reject_host_path(output_dsn)):
        return 'RACF2JOHN009E HOST FILE PATHS ARE NOT ALLOWED - USE GIBSON DATA SET NAMES'
    materialise_racfds(state)
    corr = _corr(state)
    try:
        text = state.datasets.read(userid, "SYS1.RACFDS(DATABASE)" if input_dsn.upper()=="SYS1.RACFDS" else input_dsn)
        result = 'SUCCESS'
    except Exception as e:
        racf_event(state, userid=userid, event_name='RACF_DATABASE_READ', result='FAILURE', class_name='DATASET', resource_name=input_dsn.upper(), profile_name='SYS1.RACFDS', access_requested='READ', access_allowed='NONE', reason_code='DENIED', correlation_id=corr, detail=str(e))
        return f'RACF2JOHN010E INPUT DATASET {input_dsn.upper()} NOT READABLE: {e}'
    legacy = []
    skipped = 0
    for line in text.splitlines():
        if not line.startswith('USER '):
            continue
        uidm = re.search(r'USERID=([^\s]+)', line)
        algm = re.search(r'ALG=([^\s]+)', line)
        hm = re.search(r'HASH=([^\s]+)', line)
        if not uidm:
            continue
        if algm and algm.group(1).upper() in {'LEGACY-DES','LEGACY-DES-SIM'} and hm and not hm.group(1).startswith('*'):
            legacy.append(format_john_racf_hash(uidm.group(1), hm.group(1)))
        else:
            skipped += 1
    outtext = '\n'.join(legacy) + ('\n' if legacy else '')
    if output_dsn:
        try:
            state.datasets.write(userid, output_dsn, outtext)
        except Exception as e:
            return f'RACF2JOHN011E OUTPUT DATASET {output_dsn.upper()} WRITE FAILED: {e}'
    racf_event(state, userid=userid, event_name='RACF_HASH_EXTRACT', result=result, class_name='DATASET', resource_name=input_dsn.upper(), profile_name='SYS1.RACFDS', access_requested='READ', access_allowed='READ', reason_code='OK', correlation_id=corr, detail=f'LEGACY_DES={len(legacy)} SKIPPED={skipped}')
    job_step(state, userid=userid, jobname='OMVS', program='RACF2JOHN', result='SUCCESS', correlation_id=corr, detail=f'INPUT={input_dsn.upper()} OUTPUT={output_dsn or "STDOUT"}')
    uss_file(state, userid=userid, path=input_dsn.upper(), operation='READ', program='racf2john', result='SUCCESS', bytes_count=len(text), correlation_id=corr, detail='RACF HASH EXTRACTION')
    if output_dsn:
        uss_file(state, userid=userid, path=output_dsn.upper(), operation='WRITE', program='racf2john', result='SUCCESS', bytes_count=len(outtext), correlation_id=corr, detail='JOHN HASH DATASET WRITE')
    _emit_console_cti(state, f'SMF080I SECURITY EVENT USER({userid.upper()}) EVENT(RACFDS-READ) RESULT(SUCCESS) DETAIL(DATASET={input_dsn.upper()} ACCESS=READ CORR={corr})', event_type='RACF_DATABASE_READ', corr=corr)
    _emit_console_cti(state, f'SMF030I PROGRAM EXECUTION USER({userid.upper()}) PROGRAM(RACF2JOHN) RESULT(SUCCESS) DETAIL(OMVS HASH EXTRACTION CORR={corr})', event_type='RACF_HASH_EXTRACT', corr=corr)
    _emit_console_cti(state, f'GIBSSEC2A RACF HASH EXTRACTION DETECTED USER({userid.upper()}) DATASET({input_dsn.upper()}) M4M=MF-TTP08 MITRE=T1110.002 CORR={corr}', event_type='RACF_HASH_EXTRACT', corr=corr)
    try:
        state.record_security_event(userid, 'RACF_HASH_EXTRACT', f'DATASET={input_dsn.upper()} LEGACY_DES={len(legacy)} CORR={corr}', service='OMVS', result='SUCCESS')
    except Exception: pass
    lines = [
        f'RACF2JOHN001I INPUT DATASET {input_dsn.upper()}',
        f'RACF2JOHN002I LEGACY DES HASHES EXTRACTED: {len(legacy)}',
        f'RACF2JOHN003I KDFAES RECORDS SKIPPED: {skipped}',
    ]
    if output_dsn:
        lines.append(f'RACF2JOHN004I OUTPUT WRITTEN TO {output_dsn.upper()}')
    else:
        lines.extend(legacy)
    lines.append(f'RACF2JOHN005I CORRELATION {corr}')
    return '\n'.join(lines)


def racf2john_command(state: Any, userid: str, argv: list[str]) -> str:
    if not argv or argv[0].upper() in {'HELP','?','--HELP'}:
        return 'usage: racf2john [--summary|--json] SYS1.RACFDS [> OUTPUT.DATASET] - Gibson training-only RACF legacy-DES extractor'
    json_mode='--json' in [a.lower() for a in argv]
    summary='--summary' in [a.lower() for a in argv]
    args=[a for a in argv if a.lower() not in {'--json','--summary'}]
    inp = (args[0] if args else 'SYS1.RACFDS').strip().strip("'").upper()
    out = None
    if '>' in args:
        idx = args.index('>')
        if idx + 1 < len(args): out = args[idx+1].strip().strip("'").upper()
    if summary or json_mode:
        materialise_racfds(state)
        text=state.datasets.read(userid, 'SYS1.RACFDS(DATABASE)' if inp=='SYS1.RACFDS' else inp)
        legacy=sum(1 for l in text.splitlines() if l.startswith('USER ') and ('ALG=LEGACY-DES ' in l or 'ALG=LEGACY-DES-SIM' in l))
        protected=sum(1 for l in text.splitlines() if l.startswith('USER ') and 'ALG=LEGACY-DES' not in l)
        if json_mode:
            import json
            return json.dumps({'input': inp, 'legacy_des': legacy, 'protected': protected, 'john_compatible': bool(legacy)}, indent=2)
        return f'RACF2JOHN SUMMARY INPUT({inp}) LEGACY-DES({legacy}) KDFAES-SKIPPED({protected}) JOHN-COMPATIBLE({"YES" if legacy else "NO"})'
    return extract_hashes(state, userid, inp, out)


_cracked: dict[str, dict[str, str]] = {}


def john_command(state: Any, userid: str, argv: list[str]) -> str:
    if not argv or argv[0].upper() in {'HELP','?','--HELP'}:
        return 'usage: john [--wordlist=DATASET] HASH.DATASET | john --show HASH.DATASET - Gibson training-only dictionary simulator'
    show = '--show' in [a.lower() for a in argv]
    status_mode = '--status' in [a.lower() for a in argv]
    json_mode = '--json' in [a.lower() for a in argv]
    wordlist = 'GIBSON.WORDLIST'
    hashes = ''
    for a in argv:
        if a.lower().startswith('--wordlist='):
            wordlist = a.split('=',1)[1].strip().strip("'").upper()
        elif not a.startswith('-'):
            hashes = a.strip().strip("'").upper()
    if not hashes or _reject_host_path(hashes) or _reject_host_path(wordlist):
        return 'JOHN009E HOST FILE PATHS ARE NOT ALLOWED - USE GIBSON DATA SET NAMES'
    key = f'{userid.upper()}:{hashes}'
    if show:
        rows = _cracked.get(key, {})
        if not rows: return 'JOHN010I NO CRACKED HASHES TO SHOW'
        return '\n'.join([f'{u}:{p}' for u,p in sorted(rows.items())] + [f'JOHN011I {len(rows)} PASSWORD HASHES SHOWN'])
    if status_mode:
        rows = _cracked.get(key, {})
        return f'JOHN020I STATUS HASHSET({hashes}) CRACKED({len(rows)}) BOUNDED(YES)'
    corr = _corr(state)
    try:
        htxt = state.datasets.read(userid, hashes)
    except Exception as e:
        return f'JOHN012E HASH DATASET {hashes} NOT READABLE: {e}'
    try:
        wtxt = state.datasets.read(userid, wordlist)
    except Exception:
        # stable built-in training dictionary
        wtxt = 'VIPER1\nSWIM\nWELCOME1\nPASSWORD\nINTEGRA\nFINANCE$\nSUMMER25\nPASS123\n'
    entries = []
    for line in htxt.splitlines()[:100]:
        m = re.match(r'([^:]+):\$racf\$\*([^*]+)\*([0-9A-Fa-f]+)', line.strip())
        if m:
            entries.append((m.group(1).upper(), m.group(3).upper()))
    cracked = {}
    words = [w.strip() for w in wtxt.splitlines() if w.strip()][:10000]
    for uid, hx in entries:
        for word in words:
            if verify_legacy_racf_des_hash(uid, word, hx):
                cracked[uid] = word.upper()
                break
    _cracked[key] = cracked
    job_step(state, userid=userid, jobname='OMVS', program='JOHN', result='SUCCESS', correlation_id=corr, detail=f'HASHES={hashes} CRACKED={len(cracked)} TOTAL={len(entries)}')
    uss_file(state, userid=userid, path=hashes, operation='READ', program='john', result='SUCCESS', bytes_count=len(htxt), correlation_id=corr, detail='RACF HASH CRACK ATTEMPT')
    _emit_console_cti(state, f'SMF030I PROGRAM EXECUTION USER({userid.upper()}) PROGRAM(JOHN) RESULT(SUCCESS) DETAIL(CRACKED={len(cracked)} TOTAL={len(entries)} CORR={corr})', event_type='RACF_HASH_CRACK_ATTEMPT', corr=corr)
    _emit_console_cti(state, f'GIBSSEC3A OFFLINE RACF HASH CRACKING DETECTED USER({userid.upper()}) RESULT(CRACKED={len(cracked)}) M4M=MF-TTP08 MITRE=T1110.002 CORR={corr}', event_type='RACF_HASH_CRACK_SUCCESS' if cracked else 'RACF_HASH_CRACK_ATTEMPT', corr=corr)
    try:
        state.record_security_event(userid, 'RACF_HASH_CRACK_SUCCESS' if cracked else 'RACF_HASH_CRACK_ATTEMPT', f'HASHES={hashes} CRACKED={len(cracked)} TOTAL={len(entries)} CORR={corr}', service='OMVS', result='SUCCESS' if cracked else 'WARNING')
    except Exception: pass
    if json_mode:
        import json
        return json.dumps({'hash_dataset': hashes, 'format': 'RACF LEGACY DES', 'total': len(entries), 'cracked': len(cracked), 'users': cracked}, indent=2)
    lines=['JOHN001I GIBSON JOHN SIMULATOR - TRAINING ONLY','JOHN002I FORMAT RACF LEGACY DES']
    lines += [f'{u}:{p}' for u,p in sorted(cracked.items())]
    lines.append(f'JOHN003I {len(cracked)} OF {len(entries)} HASHES CRACKED')
    if len(cracked) < len(entries):
        lines.append('JOHN014I HASH ATTEMPTED BUT NOT MATCHED BY WORDLIST')
    lines.append(f'JOHN004I CORRELATION {corr}')
    return '\n'.join(lines)
