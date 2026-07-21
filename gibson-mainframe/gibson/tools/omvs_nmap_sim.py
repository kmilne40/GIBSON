#!/usr/bin/env python3
"""Standalone Gibson Nmap-style mainframe NSE training simulator.
Safe, bounded, ASCII-only, and separate from Gibson server internals.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, random, re, socket, sys, time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION="2.0.0"
DEFAULT_HOST="127.0.0.1"; DEFAULT_PORT=2023; DEFAULT_TIMEOUT=3.0; DEFAULT_MAX_GUESSES=20; DEFAULT_DELAY=0.05
SERVICE="gibson-vtam"
STATUSES=("CONFIRMED","INFERRED","DENIED","DISABLED","UNAVAILABLE","ERROR")
DEFAULT_TSO_USERS=["IBMUSER","GRRR","NIALLA","RUARIV","SARCHER","ENLIMV","PHILIY","GUEST","KEVINM","KEV","SYSADM","TEST01","9BAD","TOOLONG1"]
DEFAULT_PASSWORDS=["SYS1","PASSWORD","CICS","TRAINING"]
DEFAULT_CICS_IDS=["CESN","CESL","CEMT","CEDA","CECI","CEBR","CSMT","CEDF","ABCD"]
VALID_TSO={"IBMUSER","SYSADM","TEST01","CICSUSR","NIALLA","SARCHER","ENLIMV","PHILIY","GUEST","KEVINM"}; DENIED_TSO={"RUARIV"}
VALID_CICS={"CICSUSR","IBMUSER","OPR001"}; DENIED_CICS={"GUEST"}
VALID_CREDS={("IBMUSER","SYS1"),("SYSADM","PASSWORD"),("TEST01","PASSWORD"),("CICSUSR","CICS")}
VALID_CICS_CREDS={("CICSUSR","CICS"),("IBMUSER","SYS1"),("OPR001","PASSWORD")}
CICS_STATES={"CESN":("CONFIRMED","LOGON_TRANSACTION"),"CESL":("CONFIRMED","LOGON_TRANSACTION"),"CEMT":("DENIED","SECURITY_PROTECTED"),"CEDA":("DENIED","SECURITY_PROTECTED"),"CECI":("DENIED","SECURITY_PROTECTED"),"CEBR":("DISABLED","TRANSACTION_DISABLED"),"CSMT":("CONFIRMED","SYSTEM_LOG_TRANSACTION"),"CEDF":("DENIED","SECURITY_PROTECTED")}

@dataclass
class Finding:
    key:str; status:str; detail:str=""; evidence:str=""
    def line(self,w:int=14)->str:
        d=f"  {self.detail}" if self.detail else ""
        return f"{self.key:<{w}} {self.status:<12}{d}".rstrip()

@dataclass
class ScriptResult:
    script:str; host:str; port:int; service:str=SERVICE; port_state:str="open"
    findings:List[Finding]=field(default_factory=list); sections:Dict[str,List[Finding]]=field(default_factory=dict)
    notes:List[str]=field(default_factory=list); warnings:List[str]=field(default_factory=list)
    correlation_id:str=""; result:str="OK"; transport_error:str=""
    started_at:str=field(default_factory=lambda: dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()+"Z")
    ended_at:str=""
    def finish(self):
        self.ended_at=dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()+"Z"
        if not self.correlation_id: self.correlation_id=correlation_id(self.script)
        return self
    def jsonable(self):
        d=asdict(self); d["findings"]=[asdict(x) for x in self.findings]; d["sections"]={k:[asdict(x) for x in v] for k,v in self.sections.items()}; return d

def correlation_id(prefix:str)->str:
    tok=''.join(random.choice('0123456789ABCDEF') for _ in range(4))
    clean=re.sub(r'[^A-Za-z0-9]+','-',prefix).strip('-').upper() or 'SIM'
    return f"{clean}-{dt.datetime.now(dt.UTC).strftime('%Y%m%d-%H%M%S')}-{tok}"

def trim(s:str,n:int=180)->str: return ' '.join((s or '').split())[:n]
def banner()->str: return "GIBSON VTAM FRONT DOOR\nAPPLID ===>\nAvailable training applications: TSO CICS DB2 SDSF\n"
def sim_response(cmd:str)->str:
    c=cmd.strip().upper()
    if c in {"L TSO","TSO","LOGON APPLID(TSO)"}: return "IKJ56700A ENTER USERID -\n"
    if c in {"L CICS","CICS","LOGON APPLID(CICS)"}: return "DFHAC2001 GIBCICS CICS Transaction Server\nENTER TRANSACTION ID\n"
    if c.startswith("USER ") or c.startswith("LOGON "):
        u=c.split()[-1]
        if u in VALID_TSO: return f"TSO/E LOGON PANEL\nUSERID ===> {u}\nPASSWORD ===>\n"
        if u in DENIED_TSO: return f"IKJ56421I USERID {u} ACCESS RESTRICTED\n"
        return f"IKJ56420I Userid {u} not authorized to use TSO\n"
    if c in CICS_STATES:
        st,de=CICS_STATES[c]
        if st=="CONFIRMED": return f"DFHAC2001 {c} READY {de}\n"
        if st=="DENIED": return f"DFHXS1111 {c} SECURITY CHECK FAILED\n"
        if st=="DISABLED": return f"DFHAC2206 Transaction {c} is disabled\n"
    if c.startswith(("CEMT","CEDA","CECI")): return "DFHXS1111 TRANSACTION SECURITY CHECK FAILED\n"
    return f"UNKNOWN COMMAND OR UNAVAILABLE RESOURCE: {c}\n"

def send_line(sock:socket.socket,line:str)->None: sock.sendall((line+"\r\n").encode("ascii","ignore"))

class Transport:
    def __init__(self,ctx): self.ctx=ctx; self.sock=None; self.error=""; self.initial=""
    def __enter__(self): self.connect(); return self
    def __exit__(self,*a):
        if self.sock:
            try: self.sock.close()
            except OSError: pass
    def connect(self)->bool:
        if getattr(self.ctx,'offline',False): self.initial=banner(); return True
        last=""
        for _ in range(max(1,int(self.ctx.max_retries))):
            try:
                self.sock=socket.create_connection((self.ctx.host,int(self.ctx.port)),timeout=float(self.ctx.host_timeout)); self.sock.settimeout(float(self.ctx.host_timeout)); self.initial=self.read(); return True
            except OSError as e: last=str(e); time.sleep(0.05)
        self.error=last or "connection failed"; return False
    def read(self,quiet:float=.25,limit:int=8192)->str:
        if getattr(self.ctx,'offline',False): return self.initial or banner()
        if not self.sock: return ""
        chunks=[]; end=time.time()+quiet
        while time.time()<end and sum(map(len,chunks))<limit:
            try:
                b=self.sock.recv(min(1024,limit-sum(map(len,chunks))))
                if not b: break
                chunks.append(b); end=time.time()+quiet
            except (socket.timeout,OSError): break
        return b''.join(chunks).decode('ascii','ignore')
    def send(self,line:str)->str:
        if getattr(self.ctx,'offline',False): return sim_response(line)
        if not self.sock: return ""
        try: send_line(self.sock,line); return self.read()
        except OSError as e: self.error=str(e); return ""

def split_args(text:str)->List[str]:
    out=[]; buf=[]; quote=None; esc=False; depth=0
    for ch in text or "":
        if esc: buf.append(ch); esc=False; continue
        if ch=='\\' and quote: esc=True; buf.append(ch); continue
        if ch in "'\"":
            if quote is None: quote=ch
            elif quote==ch: quote=None
            buf.append(ch); continue
        if quote is None:
            if ch=='{': depth+=1
            elif ch=='}' and depth: depth-=1
            elif ch in ',\n' and depth==0:
                p=''.join(buf).strip(); buf=[]
                if p: out.append(p)
                continue
        buf.append(ch)
    p=''.join(buf).strip()
    if p: out.append(p)
    return out

def unquote(v:str)->str:
    v=v.strip()
    if len(v)>=2 and v[0]==v[-1] and v[0] in "'\"": return v[1:-1].replace('\\'+v[0],v[0])
    return v

def parse_script_args_text(text:str)->Dict[str,str]:
    d={}
    for p in split_args(text):
        if '=' in p:
            k,v=p.split('=',1); k=k.strip()
            if k: d[k]=unquote(v)
        elif p.strip(): d[p.strip()]="true"
    return d

def parse_script_args(arg_text:str='',arg_file:str='')->Dict[str,str]:
    d={}
    if arg_file: d.update(parse_script_args_text(Path(arg_file).read_text(encoding='utf-8')))
    if arg_text: d.update(parse_script_args_text(arg_text))
    return d

def argget(args:Dict[str,str],script:str,key:str,default=None): return args.get(f"{script}.{key}",args.get(key,default))
def boolish(v,default=False): return default if v is None else str(v).lower() in {'1','true','yes','y','on'}
def words(path,defaults):
    if not path: return list(defaults)
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(path)
    return [x.strip() for x in p.read_text(encoding='utf-8',errors='ignore').splitlines() if x.strip() and not x.strip().startswith('#')]
def valid_tso_userid(u:str)->Tuple[bool,str]:
    if not u: return False,"EMPTY_USERID"
    if len(u)>7: return False,"TOO_LONG"
    if u[0].isdigit(): return False,"LEADING_NUMBER"
    if not re.fullmatch(r'[A-Za-z0-9@#$]+',u): return False,"INVALID_CHARACTER"
    return True,"VALID_FORMAT"
def classify_tso(u:str,r:str)->Finding:
    x=(r or '').upper()
    if 'PASSWORD' in x or 'LOGON PANEL' in x: return Finding(u,'CONFIRMED','PASSWORD_PROMPT',trim(r))
    if 'ACCESS RESTRICTED' in x or 'REVOK' in x or 'DENIED' in x: return Finding(u,'DENIED','ACCESS_RESTRICTED',trim(r))
    if 'IKJ56420I' in x or 'NOT AUTHORIZED' in x or 'NOT FOUND' in x: return Finding(u,'UNAVAILABLE','USER_NOT_FOUND',trim(r))
    return Finding(u,'INFERRED','AMBIGUOUS_PROMPT',trim(r))
def classify_cics(tid:str,r:str='')->Finding:
    tid=tid.strip().upper()[:4]; x=(r or '').upper()
    if 'SECURITY' in x or 'DENIED' in x or 'NOT AUTH' in x: return Finding(tid,'DENIED','SECURITY_PROTECTED',trim(r))
    if 'DISABLED' in x: return Finding(tid,'DISABLED','TRANSACTION_DISABLED',trim(r))
    if 'UNKNOWN' in x or 'UNAVAILABLE' in x or 'INVALID' in x: return Finding(tid,'UNAVAILABLE','TRANSACTION_NOT_FOUND',trim(r))
    if tid in CICS_STATES: st,de=CICS_STATES[tid]; return Finding(tid,st,de,trim(r))
    return Finding(tid,'INFERRED','AMBIGUOUS_RESPONSE',trim(r)) if r.strip() else Finding(tid,'UNAVAILABLE','TRANSACTION_NOT_FOUND')
def summary(fs:Iterable[Finding])->str:
    counts={s:0 for s in STATUSES}
    for f in fs: counts[f.status]=counts.get(f.status,0)+1
    return ', '.join(f'{k.lower()}={v}' for k,v in counts.items() if v) or 'no findings'
def base(script,ctx): return ScriptResult(script,ctx.host,int(ctx.port),correlation_id=correlation_id(script))

def run_tn3270_screen(ctx,args):
    r=base('tn3270-screen',ctx)
    with Transport(ctx) as t:
        if t.error: r.port_state='closed'; r.transport_error=t.error; r.result='ERROR'; r.findings.append(Finding('screen','ERROR','TRANSPORT_FAILURE',t.error)); return r.finish()
        screen=t.initial or banner()
        for cmd in [c.strip() for c in str(argget(args,'tn3270-screen','commands','')).split(';') if c.strip()]: screen=t.send(cmd) or screen
        r.findings.append(Finding('screen','CONFIRMED','ASCII_SCREEN_CAPTURE',screen.strip()))
        r.notes.append('ASCII-only screen capture; no real TN3270 field decoding performed.')
    return r.finish()

def run_tso_enum(ctx,args):
    r=base('tso-enum',ctx)
    try: us=words(ctx.userdb or argget(args,'tso-enum','userdb'),DEFAULT_TSO_USERS)
    except FileNotFoundError as e: r.result='ERROR'; r.findings.append(Finding('userdb','ERROR',str(e))); return r.finish()
    with Transport(ctx) as t:
        if t.error: r.transport_error=t.error; r.warnings.append(f'Transport failed: {t.error}; using simulator classification only.')
        elif argget(args,'tso-enum','commands','L TSO'):
            for c in str(argget(args,'tso-enum','commands','L TSO')).split(';'): t.send(c.strip())
        for raw in us:
            u=raw.upper(); ok,why=valid_tso_userid(u)
            if not ok: r.findings.append(Finding(u,'UNAVAILABLE',f'INVALID_TSO_USERID:{why}')); continue
            resp=sim_response('USER '+u) if t.error else (t.send('USER '+u) or sim_response('USER '+u))
            r.findings.append(classify_tso(u,resp))
    r.notes.append('Summary: '+summary(r.findings)); return r.finish()

def bounded_pairs(users,passes,maxg):
    n=0
    for u in users:
        for p in passes:
            if n>=maxg: return
            n+=1; yield u.upper(),p

def run_brute(ctx,args,script,valid,users_default):
    r=base(script,ctx); r.warnings.append('This is a bounded training simulation. Use only against Gibson or authorised lab systems.')
    try: us=words(ctx.userdb or argget(args,script,'userdb'),users_default); ps=words(ctx.passdb or argget(args,script,'passdb'),DEFAULT_PASSWORDS)
    except FileNotFoundError as e: r.result='ERROR'; r.findings.append(Finding('wordlist','ERROR',str(e))); return r.finish()
    maxg=max(1,min(int(ctx.max_guesses),int(argget(args,script,'guesses',args.get('brute.guesses',ctx.max_guesses)))))
    delay=max(0,min(float(argget(args,script,'delay',args.get('brute.delay',ctx.delay))),5.0)); first=boolish(argget(args,script,'firstonly',args.get('brute.firstonly',ctx.firstonly)))
    attempts=succ=0
    with Transport(ctx) as t:
        if t.error: r.transport_error=t.error; r.warnings.append(f'Transport failed: {t.error}; using simulator credential audit responses.')
        for u,pw in bounded_pairs(us,ps,maxg):
            attempts+=1
            if delay: time.sleep(delay)
            ok,why=valid_tso_userid(u)
            if not ok: r.findings.append(Finding(u,'UNAVAILABLE',f'INVALID_USERID:{why}')); continue
            if (u,pw) in valid: succ+=1; r.findings.append(Finding(u,'CONFIRMED','SIMULATED_CREDENTIAL_ACCEPTED','password redacted')); \
                (first and None)
            elif u in DENIED_TSO or u in DENIED_CICS: r.findings.append(Finding(u,'DENIED','ACCOUNT_RESTRICTED','password redacted'))
            else: r.findings.append(Finding(u,'UNAVAILABLE','SIMULATED_LOGIN_REJECTED','password redacted'))
            if first and succ: break
    r.notes.append(f'Statistics: Performed {attempts} guesses; successes={succ}; max_guesses={maxg}; firstonly={first}')
    r.notes.append('Passwords are never printed in output; review Gibson forensic logs with the correlation ID.')
    return r.finish()
def run_tso_brute(ctx,args): return run_brute(ctx,args,'tso-brute',VALID_CREDS,DEFAULT_TSO_USERS)
def run_cics_user_brute(ctx,args): return run_brute(ctx,args,'cics-user-brute',VALID_CICS_CREDS,["CICSUSR","IBMUSER","OPR001","GUEST","BOGUS"])

def run_cics_info(ctx,args):
    r=base('cics-info',ctx)
    with Transport(ctx) as t:
        if t.error: r.transport_error=t.error; r.warnings.append(f'Transport failed: {t.error}; using simulator region profile.')
        else:
            for c in str(argget(args,'cics-info','commands','L CICS')).split(';'): t.send(c.strip())
    r.sections['region']=[Finding('Region','CONFIRMED','GIBCICS'),Finding('Application ID','CONFIRMED','CICS'),Finding('Security','CONFIRMED','ENABLED'),Finding('CICS Version','INFERRED','TRAINING_SIMULATOR')]
    r.sections['datasets']=[Finding('GIBSON.CICS.DFHCSD','CONFIRMED','CATALOG_VISIBLE'),Finding('GIBSON.CICS.SDFHLOAD','CONFIRMED','LIBRARY_VISIBLE'),Finding('GIBSON.APP.CUSTOMER','DENIED','FILE_SECURITY_PROTECTED')]
    r.sections['transactions']=[classify_cics(x) for x in DEFAULT_CICS_IDS]
    r.sections['users']=[Finding('CICSUSR','CONFIRMED','ACTIVE_SESSION'),Finding('IBMUSER','INFERRED','RECENT_SESSION')]
    r.notes.append('CEMT inquiry capability is modelled as protected unless Gibson explicitly allows it.'); return r.finish()

def run_cics_enum(ctx,args):
    r=base('cics-enum',ctx)
    try: ids=words(argget(args,'cics-enum','idlist',args.get('idlist')),DEFAULT_CICS_IDS)
    except FileNotFoundError as e: r.result='ERROR'; r.findings.append(Finding('idlist','ERROR',str(e))); return r.finish()
    with Transport(ctx) as t:
        if t.error: r.transport_error=t.error; r.warnings.append(f'Transport failed: {t.error}; using simulator transaction states.')
        else:
            for c in str(argget(args,'cics-enum','commands','L CICS')).split(';'): t.send(c.strip())
        for raw in ids:
            tid=raw.upper()[:4]
            if len(tid)!=4: r.findings.append(Finding(raw.upper(),'UNAVAILABLE','INVALID_CICS_TRANSID_LENGTH')); continue
            resp=sim_response(tid) if t.error else (t.send(tid) or sim_response(tid)); r.findings.append(classify_cics(tid,resp))
    r.notes.append('Summary: '+summary(r.findings)); return r.finish()

def run_cics_user_enum(ctx,args):
    r=base('cics-user-enum',ctx); trans=str(argget(args,'cics-user-enum','transaction','CESL')).upper()[:4]; r.notes.append(f'Transaction: {trans}')
    try: us=words(ctx.userdb or argget(args,'cics-user-enum','userdb',args.get('userdb')), ["CICSUSR","IBMUSER","OPR001","GUEST","BOGUS"])
    except FileNotFoundError as e: r.result='ERROR'; r.findings.append(Finding('userdb','ERROR',str(e))); return r.finish()
    with Transport(ctx) as t:
        if t.error: r.transport_error=t.error; r.warnings.append(f'Transport failed: {t.error}; using simulator CICS user states.')
        for raw in us:
            u=raw.upper(); ok,why=valid_tso_userid(u)
            if not ok: r.findings.append(Finding(u,'UNAVAILABLE',f'INVALID_USERID:{why}'))
            elif u in VALID_CICS: r.findings.append(Finding(u,'CONFIRMED','CICS_USERID_PROMPT'))
            elif u in DENIED_CICS: r.findings.append(Finding(u,'DENIED','CICS_ACCESS_RESTRICTED'))
            else: r.findings.append(Finding(u,'UNAVAILABLE','CICS_USERID_NOT_FOUND'))
    r.notes.append('Summary: '+summary(r.findings)); return r.finish()

def run_cicspwn(ctx,args):
    r=base('cicspwn',ctx); r.warnings.append('This is a bounded training simulation. Use only against Gibson or authorised lab systems.')
    with Transport(ctx) as t:
        if t.error: r.transport_error=t.error; r.warnings.append(f'Transport failed: {t.error}; using simulator CICS response model.'); front=banner()
        else: front=t.initial or banner(); [t.send(c.strip()) for c in str(argget(args,'cicspwn','commands','L CICS')).split(';') if c.strip()]
        tx=[]
        for tid in ['CESN','CEMT','CEDA','CECI','CEBR']:
            resp=sim_response(tid) if t.error else (t.send(tid) or sim_response(tid)); tx.append(classify_cics(tid,resp))
    r.sections['discovery']=[Finding('Front-door prompt','CONFIRMED','ASCII_PROMPT_OBSERVED',trim(front)),Finding('APPLID CICS','CONFIRMED','TRAINING_APPLICATION_VISIBLE'),Finding('Mode','CONFIRMED',str(argget(args,'cicspwn','mode','forensic'))),Finding('Safe mode','CONFIRMED',str(boolish(argget(args,'cicspwn','safe','true'),True)).lower())]
    r.sections['transaction-access']=tx
    r.sections['region-info']=[Finding('Region','CONFIRMED','GIBCICS'),Finding('Security','CONFIRMED','ENABLED'),Finding('Visible files','INFERRED','GIBSON.CICS.DFHCSD,GIBSON.CICS.SDFHLOAD'),Finding('Visible queues','INFERRED','CSMT,CSSL')]
    states={f.key:f.status for f in tx}
    r.sections['capability-assessment']=[Finding('Administrative path','DENIED' if states.get('CEMT')!='CONFIRMED' else 'INFERRED','CEMT_PROTECTED' if states.get('CEMT')!='CONFIRMED' else 'CEMT_INQUIRY_ALLOWED'),Finding('Define/install path','DENIED' if states.get('CEDA')!='CONFIRMED' else 'INFERRED','CEDA_PROTECTED' if states.get('CEDA')!='CONFIRMED' else 'CEDA_AVAILABLE_SIMULATED_ONLY'),Finding('Command-level path','DENIED' if states.get('CECI')!='CONFIRMED' else 'INFERRED','CECI_PROTECTED' if states.get('CECI')!='CONFIRMED' else 'CECI_AVAILABLE_SIMULATED_ONLY')]
    r.sections['forensic-correlation']=[Finding('Correlation ID','CONFIRMED',r.correlation_id),Finding('SDSF','INFERRED','Review ST/O/H and SMF80 training views'),Finding('OPERLOG','INFERRED','Review CICS transaction denial events'),Finding('CICS events','INFERRED','Review security/forensic event stream')]
    r.result='BLOCKED - no simulated exploit path completed' if any(f.status=='CONFIRMED' for f in tx) else 'NO PATH - CICS entry not confirmed'
    r.notes.append('No real shell, listener, code execution, or JCL submission is implemented.'); return r.finish()

SCRIPT_REGISTRY={"tn3270-screen":run_tn3270_screen,"tso-enum":run_tso_enum,"tso-brute":run_tso_brute,"cics-info":run_cics_info,"cics-enum":run_cics_enum,"cics-user-enum":run_cics_user_enum,"cics-user-brute":run_cics_user_brute,"cicspwn":run_cicspwn}

def render_result(r:ScriptResult)->str:
    out=["PORT     STATE SERVICE",f"{r.port}/tcp {r.port_state:<5} {r.service}","",f"| {r.script}:"]
    for w in r.warnings: out.append(f"|   Warning: {w}")
    for f in r.findings:
        if f.key=='screen' and f.evidence:
            out.append('|   screen:'); out.extend('|     '+line for line in f.evidence.splitlines())
        if f.key!='screen': out.append('|   '+f.line())
    for sec,fs in r.sections.items():
        out.append(f"|   Stage: {sec}" if r.script=='cicspwn' else f"|   {sec}:")
        for f in fs: out.append('|     '+f.line(22))
    for n in r.notes: out.append('|   '+n)
    if r.transport_error: out.append('|   Transport: '+r.transport_error)
    out.append('|   Correlation ID: '+r.correlation_id); out.append('|_  Result: '+r.result)
    return '\n'.join(out)
def render_all_text(rs): return f"Starting nmap-sim {VERSION} at {dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()}Z\n\n"+'\n\n'.join(render_result(r) for r in rs)+f"\n\nNmap-sim done: {len(rs)} script(s) executed\n"
def render_all_json(rs,ctx): return json.dumps({"tool":"nmap-sim.py","version":VERSION,"host":ctx.host,"port":int(ctx.port),"generated_at":dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()+"Z","scripts":[r.jsonable() for r in rs]},indent=2,sort_keys=True)+"\n"
def norm_scripts(ctx):
    ss=[]
    if ctx.screen: ss.append('tn3270-screen')
    if ctx.cicspwn: ss.append('cicspwn')
    if ctx.tso_brute: ss.append('tso-brute')
    if ctx.script: ss += [p for p in re.split(r'[,\s]+',ctx.script) if p]
    if not ss: ss=['tn3270-screen']
    out=[]
    for s in ss:
        if s not in out: out.append(s)
    return out

def build_parser():
    p=argparse.ArgumentParser(description='Standalone Gibson Nmap-style mainframe NSE training simulator (ASCII-only).')
    p.add_argument('target',nargs='?'); p.add_argument('-H','--host'); p.add_argument('-p','--port',type=int,default=DEFAULT_PORT)
    p.add_argument('-s','--screen',action='store_true'); p.add_argument('--script'); p.add_argument('--script-args',default=''); p.add_argument('--script-args-file',default='')
    p.add_argument('-u','--userdb'); p.add_argument('-P','--passdb'); p.add_argument('--cicspwn',action='store_true'); p.add_argument('--tso-brute',action='store_true'); p.add_argument('-M','--menu',action='store_true')
    p.add_argument('-oN',dest='output_normal'); p.add_argument('-oJ',dest='output_json'); p.add_argument('-v','--verbose',action='count',default=0)
    p.add_argument('--max-retries',type=int,default=1); p.add_argument('--host-timeout',type=float,default=DEFAULT_TIMEOUT); p.add_argument('--delay',type=float,default=DEFAULT_DELAY); p.add_argument('--max-guesses',type=int,default=DEFAULT_MAX_GUESSES); p.add_argument('--firstonly',action='store_true')
    p.add_argument('--offline',action='store_true',help=argparse.SUPPRESS); p.add_argument('--version',action='version',version=f'nmap-sim.py {VERSION}')
    return p
def prep(a):
    a.host=a.host or a.target or DEFAULT_HOST; a.port=int(a.port or DEFAULT_PORT); a.max_retries=max(1,int(a.max_retries)); a.host_timeout=max(.2,float(a.host_timeout)); a.max_guesses=max(1,int(a.max_guesses)); a.delay=max(0,float(a.delay)); return a
def execute(ctx):
    args=parse_script_args(ctx.script_args,ctx.script_args_file); out=[]
    for s in norm_scripts(ctx):
        fn=SCRIPT_REGISTRY.get(s)
        if not fn:
            r=base(s,ctx); r.result='ERROR'; r.findings.append(Finding(s,'ERROR','UNKNOWN_SCRIPT')); out.append(r.finish())
        else: out.append(fn(ctx,args))
    return out
def write_outputs(rs,ctx):
    text=render_all_text(rs)
    if ctx.output_normal: Path(ctx.output_normal).write_text(text,encoding='utf-8')
    if ctx.output_json: Path(ctx.output_json).write_text(render_all_json(rs,ctx),encoding='utf-8')
    return text
def clone(ctx,**kw): d=vars(ctx).copy(); d.update(kw); return argparse.Namespace(**d)
def pd(prompt,default): v=input(f'{prompt} [{default}]: ').strip(); return v or default
def menu(ctx):
    print('Gibson nmap-sim.py guided menu\nThis standalone tool is for Gibson or authorised training labs only.\n'); last=[]
    items={'1':'tn3270-screen','2':'tso-enum','3':'cics-info','4':'cics-enum','5':'cicspwn','6':'tso-brute','7':'cics-user-brute','8':'tn3270-screen,tso-enum,cics-info,cics-enum,cicspwn'}
    while True:
        print('1) Quick screen grab\n2) TSO user enumeration\n3) Safe CICS information gathering\n4) CICS transaction enumeration\n5) CICSPWN simulation: safe forensic mode\n6) Bounded TSO credential audit\n7) Bounded CICS credential audit\n8) Full Gibson classroom smoke run\n9) Export last results\nX) Exit')
        c=input('Select option: ').strip().upper()
        if c=='X': return 0
        if c=='9':
            if not last: print('No results to export yet.\n'); continue
            e=clone(ctx,output_normal=pd('Normal output file','nmap-sim-last.txt'),output_json=pd('JSON output file','nmap-sim-last.json')); write_outputs(last,e); print('Exported.\n'); continue
        if c not in items: print('Unknown option.\n'); continue
        host=pd('Host',ctx.host); port=int(pd('Port',str(ctx.port))); userdb=ctx.userdb; passdb=ctx.passdb; maxg=ctx.max_guesses; sargs=ctx.script_args
        if c in {'2','6','7'}: userdb=pd('User wordlist or blank for defaults',userdb or '') or None
        if c in {'6','7'}: passdb=pd('Password wordlist or blank for defaults',passdb or '') or None; maxg=int(pd('Maximum guesses',str(maxg)))
        if c=='5': sargs='cicspwn.mode=forensic,cicspwn.safe=true'
        rctx=clone(ctx,host=host,port=port,script=items[c],screen=False,cicspwn=False,tso_brute=False,userdb=userdb,passdb=passdb,max_guesses=maxg,script_args=sargs); last=execute(rctx); print(write_outputs(last,rctx))
def main(argv=None):
    ctx=prep(build_parser().parse_args(argv))
    if ctx.menu: return menu(ctx)
    try: rs=execute(ctx)
    except FileNotFoundError as e: print('nmap-sim error:',e,file=sys.stderr); return 2
    sys.stdout.write(write_outputs(rs,ctx)); return 1 if any(r.result=='ERROR' for r in rs) else 0
if __name__=='__main__': raise SystemExit(main())
