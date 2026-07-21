from __future__ import annotations

from datetime import datetime
from typing import Any


def _safe_read(state: Any, userid: str, dsn: str, default: str = '') -> str:
    try: return state.datasets.read(userid, dsn).strip()
    except Exception: return default


def _service_rows(state: Any) -> list[str]:
    svc = getattr(state, 'service_manager', None)
    rows = []
    try:
        for r in svc.status_rows():
            if isinstance(r, dict): rows.append(f"{str(r.get('name','')):<12} {str(r.get('state','')):<8} {str(r.get('port','-')):<6} {str(r.get('description',''))[:32]}")
            elif isinstance(r, (list, tuple)): rows.append(f"{str(r[0] if len(r)>0 else ''):<12} {str(r[1] if len(r)>1 else ''):<8} {str(r[2] if len(r)>2 else '-'):<6}")
    except Exception: pass
    return rows


def sysview_command(state: Any, userid: str, cmd: str) -> str | None:
    u = (cmd or '').strip().upper()
    if not (u == 'SYSVIEW' or u.startswith('SYSVIEW ') or u.startswith('SYSV ')):
        return None
    topic = 'MENU' if u in {'SYSVIEW','SYSV'} else u.split(None,1)[1].strip().upper()
    try:
        fibs = __import__('gibson.apps.fibs_service', fromlist=['get_fibs_service']).get_fibs_service(state)
        cust, acct, batch, swift = len(fibs.customers), len(fibs.accounts), len(fibs.batches), len(fibs.swift)
        tx = len(fibs.transactions); audit = len(fibs.audit)
    except Exception:
        cust = acct = batch = swift = tx = audit = 0
    if topic in {'HELP','MENU'}:
        return '\n'.join(['SYSVIEW PERFORMANCE AND OPERATIONS MONITOR','1 System Overview','2 Active Jobs / Address Spaces','3 CICS Region Monitor','4 DB2 Subsystem Monitor','5 TCP/IP Summary','6 USS Sessions','7 Storage and CPU','8 Alerts and Thresholds','9 RSS Task','A Dataset / Spool Activity','B RSS Task','C Dataset / Spool Activity','D Automation Actions','Commands: SYSVIEW STATUS SYSTEM JOBS CICS DB2 TCPIP USS STORAGE CPU ALERTS THRESHOLDS RSS DATASETS SPOOL LOG REFRESH'])
    if topic in {'STATUS','SYSTEM','1'}:
        return f'SYSVIEW SYSTEM OVERVIEW\nSYSTEM GIBSON LPAR SIM1 TIME {datetime.now():%Y-%m-%d %H:%M:%S}\nCPU 07.4% STORAGE 41% CICS RESP 0.03S DB2 THREADS 0003\nRSS TASK READY'
    if topic in {'JOBS','ASID','2'}:
        return 'SYSVIEW ACTIVE ADDRESS SPACES\nJOBNAME   ASID  CPU% STORAGE STATUS\nGIBSON    0031  07.4 128M    ACTIVE\nGIBCICS  0042  01.1 064M    ACTIVE\nDB2A      0052  00.8 096M    ACTIVE\nRSSCTI    0061  00.0 008M    IDLE'
    if topic in {'CICS','3'}:
        sessions = getattr(state, 'fibs_sessions', {})
        return f'SYSVIEW CICS REGION MONITOR\nREGION   STATUS  SESSIONS TRANSACTIONS AVG RESP\nGIBCICS ACTIVE  {len(sessions):04d}     {max(1, tx):06d}       0.03'
    if topic in {'DB2','4'}:
        return f'SYSVIEW DB2 SUBSYSTEM MONITOR\nSSID STATUS THREADS SQLCOUNT BUFFERPOOL\nDB2A ACTIVE 00003 {max(482, tx+cust+acct):06d} BP0 42%'
    if topic in {'TCPIP','5'}:
        rows = _service_rows(state)
        return '\n'.join(['SYSVIEW TCP/IP SERVICE SUMMARY','SERVICE      STATUS   PORT   DESCRIPTION'] + rows) if rows else 'SYSVIEW TCP/IP SERVICE SUMMARY\nNO SERVICE MANAGER ROWS AVAILABLE'
    if topic in {'USS','6'}:
        subs = getattr(state, '_omvs_network_subsessions', {})
        lines = ['SYSVIEW USS SESSIONS','TYPE     USER     STATUS                 HOST']
        lines.append('OMVS     IBMUSER  ACTIVE                 LOCAL')
        for (user, mode), sub in subs.items():
            typ = 'FTP' if sub.__class__.__name__.upper().startswith('FTP') else 'TELNET'
            status = 'CONNECTED' if getattr(sub, 'ftp', None) or getattr(sub, 'sock', None) else 'OPEN'
            host = getattr(sub, 'host', '')
            lines.append(f'{typ:<8} {user:<8} {status:<22} {host}')
        return '\n'.join(lines)
    if topic in {'STORAGE','CPU','7'}:
        return 'SYSVIEW STORAGE AND CPU\nCPU TOTAL 07.4% MVS 04.0% USS 01.2% CICS 01.1% DB2 00.8%\nCSA 18% ECSA 21% PRIVATE 37% AUX 04%'
    if topic in {'ALERTS','THRESHOLDS','8'}:
        return f'SYSVIEW ALERTS AND THRESHOLDS\nID SEV RESOURCE MESSAGE\nSV001 INFO RSS Task ready\nSV002 INFO RACF Findings={len(getattr(state,"fibs_racf_store",{}).__dict__.get("users",{})) if hasattr(getattr(state,"fibs_racf_store",None),"__dict__") else 0}'
    if topic in {'RSS','9'}:
        return 'SYSVIEW RSS TASK STATUS\nUSE OMVS RSS OR CTI-RSS TO FETCH CONFIGURED FEEDS'
    if topic in {'RSS','9'}:
        last = _safe_read(state, userid, 'CTI.RSS.LASTRUN', 'NEVER')
        return f'SYSVIEW RSS TASK STATUS\nLAST RUN {last}\nDATASET CTI.RSS.FEEDS\nCACHE CTI.RSS.CACHE'
    if topic in {'DATASETS','SPOOL','A'}:
        ds = ['CTI.RSS.FEEDS','CTI.RSS.CACHE','ZSEC.FINDINGS','SYSVIEW.LOG']
        lines = ['SYSVIEW DATASET AND SPOOL ACTIVITY','DATASET                 STATUS  RECORDS']
        for d in ds:
            text = _safe_read(state, userid, d, '')
            lines.append(f'{d:<24} AVAILABLE {len(text.splitlines()):07d}')
        lines.append('JES SPOOL SIMULATED ACTIVE 0003 JOBS')
        return '\n'.join(lines)
    if topic in {'LOG'}:
        return 'SYSVIEW LOG\n' + _safe_read(state, userid, 'SYSVIEW.LOG', 'NO SYSVIEW LOG ENTRIES')
    if topic.startswith(('START','STOP','RESET')):
        return 'SYSVIEW ACTION REJECTED - NO REAL HOST PROCESS CONTROL - SIMULATED RESOURCES ONLY'
    if topic == 'REFRESH':
        try: state.datasets.write(userid, 'SYSVIEW.LOG', f'{datetime.now():%Y-%m-%d %H:%M:%S} REFRESH BY {userid}\n')
        except Exception: pass
        return 'SYSVIEW REFRESH COMPLETE - SIMULATED RESOURCE SNAPSHOT UPDATED'
    return 'SYSVIEW: UNKNOWN OPTION ' + topic


# ---------------------------------------------------------------------------
# Fully state-backed SYSVIEW command override.
# ---------------------------------------------------------------------------
_SYSVIEW_OLD_COMMAND = sysview_command

def sysview_command(state: Any, userid: str, cmd: str) -> str | None:  # type: ignore[override]
    u = (cmd or '').strip().upper()
    if not (u == 'SYSVIEW' or u.startswith('SYSVIEW ') or u.startswith('SYSV ')):
        return None
    topic = 'MENU' if u in {'SYSVIEW','SYSV'} else u.split(None,1)[1].strip().upper()
    if topic in {'HELP','MENU','?'}:
        return '\n'.join(['SYSVIEW PERFORMANCE AND OPERATIONS MONITOR','1  System Overview','2  Active Jobs / Address Spaces','3  CICS Region Monitor','4  DB2 Subsystem Monitor','5  TCP/IP Summary','6  USS Sessions','7  Storage and CPU','8  Alerts and Thresholds','9  RSS Task','A  Dataset / Spool Activity','B  RSS Task','C  Dataset / Spool Activity','D  Automation Actions','Commands: SYSVIEW STATUS SYSTEM JOBS CICS DB2 TCPIP USS FTP TELNET RSS DATASETS SPOOL ALERTS THRESHOLDS LOG REFRESH'])
    try:
        from gibson.apps.fibs_service import get_fibs_service
        fibs = get_fibs_service(state)
        cust, acct, tx = len(fibs.customers), len(fibs.accounts), len(fibs.transactions)
        batch, swift = len(fibs.batches), len(fibs.swift)
    except Exception:
        cust = acct = tx = batch = swift = 0
    subs = getattr(state, '_omvs_network_subsessions', {})
    if topic in {'USS','FTP','TELNET','6'}:
        lines=['SYSVIEW USS SESSIONS','TYPE     USER     MODE     STATUS       HOST             PORT']
        lines.append('OMVS     IBMUSER  SHELL    ACTIVE       LOCAL            -')
        for (user, mode), sub in sorted(subs.items(), key=lambda x: str(x[0])):
            typ='FTP' if sub.__class__.__name__.upper().startswith('FTP') else 'TELNET'
            connected = bool(getattr(sub,'ftp',None) or getattr(sub,'sock',None))
            host=getattr(sub,'host','') or '-'; port=getattr(sub,'port','-')
            lines.append(f'{typ:<8} {user:<8} {mode:<8} {"CONNECTED" if connected else "OPEN":<12} {str(host)[:15]:<15} {port}')
        if len(lines) == 2:
            lines.append('NO ACTIVE FTP/TELNET SUBSESSIONS')
        return '\n'.join(lines)
    if topic in {'RSS','9'}:
        import json
        last = _safe_read(state, userid, 'CTI.RSS.LASTRUN', 'NEVER')
        cache = _safe_read(state, userid, 'CTI.RSS.CACHE', '{}')
        try:
            obj=json.loads(cache or '{}'); items=len(obj.get('items') or []); statuses=obj.get('status') or []
        except Exception:
            items=0; statuses=[]
        lines=['SYSVIEW RSS TASK STATUS', f'LAST RUN {last}', f'ITEMS {items:05d}', 'FEED STATUS COUNT ' + str(len(statuses)), 'DATASET CTI.RSS.FEEDS', 'CACHE CTI.RSS.CACHE']
        for s in statuses[:8]: lines.append(f"{s.get('name','')[:24]:<24} {s.get('status',''):<8} ITEMS={s.get('items',0)}")
        return '\n'.join(lines)
    if topic in {'STATUS','SYSTEM','1'}:
        return f'SYSVIEW SYSTEM OVERVIEW\nSYSTEM GIBSON LPAR SIM1 TIME {datetime.now():%Y-%m-%d %H:%M:%S}\nCPU 07.4% STORAGE 41% CICS RESP 0.03S DB2 THREADS 0003\nRSS TASK READY\nACTIVE FTP/TELNET {len(subs):04d}'
    if topic in {'RSS','9'}:
        return 'SYSVIEW RSS TASK STATUS\nUSE OMVS RSS OR CTI-RSS TO FETCH CONFIGURED FEEDS'
    if topic == 'REFRESH':
        try: state.datasets.write(userid, 'SYSVIEW.LOG', f'{datetime.now():%Y-%m-%d %H:%M:%S} REFRESH BY {userid}\n')
        except Exception: pass
        return 'SYSVIEW REFRESH COMPLETE - GIBSON STATE SNAPSHOT UPDATED'
    return _SYSVIEW_OLD_COMMAND(state, userid, cmd)
