from __future__ import annotations
from datetime import datetime

def _rows_services(state):
    rows=[]
    try:
        for name, st, port, desc in state.service_manager.status_rows(): rows.append((name, st, port, desc))
    except Exception:
        rows=[]
    if not rows:
        rows=[('CICS','ACTIVE','2023','CICS simulator'),('DB2','ACTIVE','-','DB2 simulator'),('OMVS','ACTIVE','2022','USS simulator')]
    return rows

def sysview_command(state, userid: str, command: str) -> str | None:
    u=(command or '').strip().upper()
    if u not in {'SYSVIEW','SYSV'} and not u.startswith('SYSVIEW ') and not u.startswith('SYSV '): return None
    topic='MENU' if u in {'SYSVIEW','SYSV'} else u.split(None,1)[1].strip()
    if topic in {'HELP','?','MENU'}:
        return '\n'.join(['SYSVIEW PERFORMANCE AND OPERATIONS MONITOR - GIBSON SIMULATION',
          '1 SYSTEM OVERVIEW     2 ACTIVE JOBS / ADDRESS SPACES',
          '3 CICS MONITOR        4 DB2 MONITOR',
          '5 TCP/IP SUMMARY      6 USS PROCESS SUMMARY',
          '7 STORAGE/CPU         8 ALERTS/THRESHOLDS',
          '9 COMMAND CONSOLE     A RSS TASK',
          'B DATASET/SPOOL ACTIVITY',
          'Commands: SYSVIEW STATUS|SYSTEM|JOBS|CICS|DB2|TCPIP|USS|STORAGE|CPU|ALERTS|THRESHOLDS|RSS|DATASETS|SPOOL|LOG|REFRESH'])
    if topic in {'STATUS','SYSTEM','1'}:
        return f"SYSVIEW SYSTEM OVERVIEW\nSYSTEM GIBSON  LPAR SIM1  TIME {datetime.now():%Y-%m-%d %H:%M:%S}\nCPU  07.4%   STORAGE  41%   CICS RESP 0.03S   DB2 THREADS 0003\nMODE SIMULATED - GIBSON OWNED RESOURCES ONLY"
    if topic in {'JOBS','ASID','2'}:
        return 'SYSVIEW ACTIVE ADDRESS SPACES\nJOBNAME   ASID  CPU%  STORAGE  STATUS\nGIBSON    0031  07.4  128M     ACTIVE\nCICSREGN  0042  01.1   64M     ACTIVE\nDB2A      0052  00.8   96M     ACTIVE\nRSSCTI    0061  00.0    8M     IDLE'
    if topic in {'CICS','3'}:
        return 'SYSVIEW CICS REGION MONITOR\nREGION   STATUS  TRANSACTIONS  AVG RESP  MESSAGE\nCICSFIBS ACTIVE  000128        0.03     FIBS AVAILABLE'
    if topic in {'DB2','4'}:
        return 'SYSVIEW DB2 SUBSYSTEM MONITOR\nSSID STATUS THREADS SQLCOUNT BUFFERPOOL\nDB2A ACTIVE 00003   000482   BP0 42%'
    if topic in {'TCPIP','5'}:
        rows=_rows_services(state); lines=['SYSVIEW TCP/IP SERVICE SUMMARY','SERVICE     STATUS   PORT   DESCRIPTION']
        for r in rows: lines.append(f'{r[0]:<11} {r[1]:<8} {str(r[2]):<6} {r[3]}')
        return '\n'.join(lines)
    if topic in {'USS','6'}:
        return 'SYSVIEW USS PROCESS SUMMARY\nPID   USER     CPU  COMMAND\n0001  OMVSKERN 0.0  BPXOINIT\n0100  IBMUSER  0.1  OMVS-SHELL\n0101  IBMUSER  0.0  RSS-CLIENT'
    if topic in {'STORAGE','CPU','7'}:
        return 'SYSVIEW STORAGE AND CPU\nCPU TOTAL 07.4%  MVS 04.0%  USS 01.2%  CICS 01.1%  DB2 00.8%\nCSA 18%  ECSA 21%  PRIVATE 37%  AUX 04%'
    if topic in {'ALERTS','THRESHOLDS','8'}:
        alerts=[]
        try: alerts=list(getattr(state,'dashboard_alerts',[]))[-20:]
        except Exception: pass
        lines=['SYSVIEW ALERTS AND THRESHOLDS','ID SEV      RESOURCE        MESSAGE']
        for i,a in enumerate(alerts,1): lines.append(f'{i:<2} WARNING  GIBSON          {a}')
        if len(lines)==2: lines.append('NO ACTIVE SYSVIEW ALERTS')
        return '\n'.join(lines)
    if topic in {'RSS','A'}:
        return 'SYSVIEW RSS TASK STATUS\nUSE OMVS RSS OR CTI-RSS TO FETCH CONFIGURED FEEDS'
    if topic in {'DATASETS','SPOOL','B'}:
        return 'SYSVIEW DATASET AND SPOOL ACTIVITY\nDATASET                 STATUS  RECORDS\nCTI.RSS.FEEDS           OPEN    VARIABLE\nZSEC.FINDINGS           CLOSED  SIMULATED\nSPOOL QUEUE             ACTIVE  0003 JOBS'
    if topic in {'DATASETS','SPOOL','C'}:
        return 'SYSVIEW DATASET AND SPOOL ACTIVITY\nDATASET                 STATUS  RECORDS\nCTI.RSS.FEEDS      OPEN    VARIABLE\nZSEC.FINDINGS      CLOSED  SIMULATED\nSPOOL QUEUE             ACTIVE  0003 JOBS'
    if topic.startswith('START ') or topic.startswith('STOP ') or topic.startswith('RESET '):
        return f'SYSVIEW ACTION ACCEPTED FOR SIMULATED RESOURCE {topic.split(None,1)[1]}\nNO REAL HOST PROCESS CONTROL PERFORMED'
    if topic in {'LOG','REFRESH'}:
        return f'SYSVIEW {topic} COMPLETE AT {datetime.now():%H:%M:%S}\nLOG DATA SET SYSVIEW.LOG UPDATED (SIMULATED)'
    return sysview_command(state, userid, 'SYSVIEW HELP')
