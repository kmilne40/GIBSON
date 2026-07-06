from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any

RARE_TERMS = ("RACFDS","RACF_HASH","HASH","JOHN","RACF2JOHN","IND$FILE","INDFILE","SENSITIVE","PASSTICKET","PTKT","REPLAY","MFA","ICSF","MASTERKEY","SYS1.MAN","APF","SURROGAT","SETROPTS","UID(0)","SPECIAL","OPERATIONS")


def _smf_rows(state: Any):
    try:
        from gibson.core.smf.writer import get_smf_writer
        for r in get_smf_writer(state).records:
            f={str(k).upper(): str(v) for k,v in r.to_flat_fields().items()}
            yield f.get('TIMESTAMP',''), f.get('USERID',''), f.get('EVENT_NAME') or f.get('EVENT') or 'SMF', f.get('RESULT',''), f.get('RESOURCE_NAME') or f.get('DETAIL') or f.get('SUMMARY') or ''
    except Exception:
        return


def _audit_rows(state: Any):
    try:
        events=list(getattr(getattr(state,'audit',None),'events',[]) or [])
    except Exception:
        events=[]
    for e in events:
        try: ts=e.ts.strftime('%Y-%m-%d %H:%M:%S')
        except Exception: ts=''
        yield ts, str(getattr(e,'userid','')), str(getattr(e,'command','')), str(getattr(e,'result','')), str(getattr(e,'extra',{}))


def security_event_rows(state: Any, *, period: str='RARE', limit:int=40):
    p=(period or 'RARE').upper()
    rows=[]
    for r in list(_smf_rows(state))+list(_audit_rows(state)):
        blob=' '.join(str(x) for x in r).upper()
        if p=='RARE' and not any(t in blob for t in RARE_TERMS):
            continue
        rows.append(r)
    # best-effort period filtering where timestamps are parseable
    days={'DAILY':1,'WEEKLY':7,'MONTHLY':30}.get(p)
    if days:
        cutoff=datetime.now()-timedelta(days=days)
        filt=[]
        for r in rows:
            try:
                dt=datetime.fromisoformat(str(r[0])[:19].replace('Z',''))
                if dt < cutoff: continue
            except Exception:
                pass
            filt.append(r)
        rows=filt
    seen=set(); out=[]
    for r in rows:
        key=(r[1],r[2],r[3],r[4])
        if key in seen: continue
        seen.add(key); out.append(r)
    return out[-limit:]


def format_security_period(state: Any, period: str='RARE') -> str:
    p=(period or 'RARE').upper()
    rows=security_event_rows(state, period=p, limit=80)
    if p=='RARE': title='IEE174I SECURITY RARE EVENT SUMMARY'
    else: title=f'IEE174I SECURITY {p} REVIEW SUMMARY'
    sev_counts={'SUCCESS':0,'FAILURE':0,'WARNING':0,'OTHER':0}
    for _t,_u,_e,r,_d in rows:
        ru=str(r).upper()
        if 'FAIL' in ru: sev_counts['FAILURE']+=1
        elif 'WARN' in ru: sev_counts['WARNING']+=1
        elif 'SUCCESS' in ru: sev_counts['SUCCESS']+=1
        else: sev_counts['OTHER']+=1
    lines=[title, f'PERIOD={p} EVENTS={len(rows)} SUCCESS={sev_counts["SUCCESS"]} FAILURE={sev_counts["FAILURE"]} WARNING={sev_counts["WARNING"]}', 'TIME                USER     EVENT                    RESULT   DETAIL']
    if not rows: lines.append('NO SECURITY EVENTS RECORDED')
    for t,u,e,r,d in rows[-25:]:
        lines.append(f'{str(t)[:19]:<19} {str(u)[:8]:<8} {str(e)[:24]:<24} {str(r)[:8]:<8} {str(d)[:52]}')
    return '\n'.join(lines)
