from __future__ import annotations

import csv
import datetime as dt
import ipaddress
import json
import os
import re
import shlex
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Iterable

from gibson.tools.host_aliases import resolve_host
from gibson.tools.security_events import emit_omvs_tool_event

SIGHBER_SUBS = {
    "www.sighberbank.com": "217.160.0.21",
    "investments.sighberbank.com": "217.160.0.21",
    "test.sighberbank.com": "217.160.0.59",
    "techforum.sighberbank.com": "217.160.0.59",
    "intranet.sighberbank.com": "217.160.0.59",
    "contacts.sighberbank.com": "217.160.0.59",
    "atm.sighberbank.com": "217.160.0.59",
    "mainframe.sighberbank.com": "82.31.22.123",
}
DNS_FIXTURES = {
    "sighberbank.com": {
        "A": ["217.160.0.21"],
        "NS": ["ns1104.ui-dns.de.", "ns1019.ui-dns.org.", "ns1083.ui-dns.com.", "ns1045.ui-dns.biz."],
        "MX": ["10 mx01.ionos.co.uk.", "10 mx00.ionos.co.uk."],
        "TXT": ['"v=spf1 include:_spf-eu.ionos.com ~all"'],
        "SOA": ["ns1104.ui-dns.de. hostmaster.ionos.com. 2026053001 28800 7200 604800 600"],
    },
    **{name: {"A": [ip]} for name, ip in SIGHBER_SUBS.items()},
    "mainframe": {"A": ["127.0.0.1"]},
    "localhost": {"A": ["127.0.0.1"]},
}
SHODAN_FIXTURES = {
    "ikj56700a port:23": [
        ("82.31.240.44", 23, "mainframe.sighberbank.com", "\\r\\nIKJ56700A ENTER USERID -\\r\\n"),
        ("71.44.82.19", 23, "zos-test.example", "\\r\\nIKJ56700A ENTER USERID -\\r\\n"),
    ],
    "ftp v1r* port:21": [
        ("82.31.240.44", 21, "mainframe.sighberbank.com", "220-FTPD IBM FTP CS V2R2"),
        ("192.168.0.97", 21, "mainframe", "220-FTPD1 IBM FTP CS V2R5 at GIBSON"),
    ],
}
GEO_FIXTURES = {
    "4.180.9.35": {"ip":"4.180.9.35","city":"Des Moines","region":"Iowa","country":"United States","country_code":"US","continent":"North America","latitude":41.5868,"longitude":-93.625,"asn":"AS8075","org":"Microsoft Corporation","source":"offline_fixture","confidence":"medium","classification":"public"},
    "192.168.0.97": {"ip":"192.168.0.97","city":"Livingston","region":"West Lothian","country":"Scotland / United Kingdom","country_code":"GB","continent":"Europe","latitude":55.8864,"longitude":-3.5226,"asn":"LOCAL","org":"Gibson home network override","source":"local_override","confidence":"configured","classification":"private_home_network"},
}


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write(env, cwd: str, path: str, text: str) -> str:
    vp = env.resolve(cwd, path)
    if not vp.startswith(cwd.rstrip('/') + '/') and vp != cwd:
        raise ValueError("output path escapes OMVS workspace")
    env.write_text(vp, text)
    return vp


def _authorised(env, cwd: str, target: str) -> tuple[bool, str, str]:
    r = resolve_host(target, env, cwd)
    if not r.allowed:
        return False, target, r.reason or "target not authorised"
    return True, r.address, r.display


def _record(env, event: str, detail: dict[str, Any]) -> None:
    try:
        detail = dict(detail or {})
        detail.setdefault("timestamp", _now())
        detail.setdefault("event", event)
        tool = str(event).split("_", 1)[0]
        script = detail.get("script") or detail.get("type") or event
        target = detail.get("target") or detail.get("domain") or detail.get("query") or detail.get("name") or ""
        emit_omvs_tool_event(env, tool=tool, script=str(script), target=str(target), result=str(detail.get("result", "OK")), severity=str(detail.get("severity", "INFO")), details=detail, service="OMVS", evidence_type="OMVS_TOOL")
    except Exception:
        pass


def subfinder_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or any(a in {"-h", "--help", "help"} for a in argv):
        return "subfinder -d DOMAIN [-resolve] [-json] [-o file]  # Gibson passive fixture mode"
    domain = ""; resolve = False; json_out = False; outfile = ""
    i=0
    while i < len(argv):
        a=argv[i]
        if a == "-d" and i+1 < len(argv): domain = argv[i+1].lower(); i+=2; continue
        if a.startswith("-d="): domain = a.split("=",1)[1].lower(); i+=1; continue
        if a in {"-resolve", "--resolve"}: resolve=True
        elif a in {"-json", "--json"}: json_out=True
        elif a == "-o" and i+1 < len(argv): outfile=argv[i+1]; i+=2; continue
        elif not a.startswith("-") and not domain: domain=a.lower()
        i+=1
    if not domain: return "subfinder: missing -d DOMAIN"
    if domain != "sighberbank.com":
        rows = [f"[INF] Gibson offline passive mode has no fixture data for {domain}"]
    else:
        rows=[]
        for h, ip in sorted(SIGHBER_SUBS.items()):
            if json_out:
                rows.append(json.dumps({"host":h,"ip":ip if resolve else None,"source":"gibson-fixture"}))
            elif resolve:
                rows.append(f"{h} -> {ip}")
            else:
                rows.append(h)
    text = "\n".join(rows)
    if outfile:
        vp=_write(env,cwd,outfile,text+"\n")
        text += f"\n[INF] Results written to {vp}"
    _record(env,"SUBFINDER_RUN",{"domain":domain,"count":len(rows)})
    return text


def dig_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or argv[0] in {"-h","--help","help"}:
        return "dig [TYPE] NAME | dig NAME TYPE | dig any sighberbank.com"
    qtype="A"; name=""
    toks=[a for a in argv if not a.startswith("+")]
    if len(toks)==1: name=toks[0].lower()
    elif toks[0].upper() in {"A","AAAA","MX","NS","TXT","SOA","ANY"}: qtype=toks[0].upper(); name=toks[1].lower()
    else: name=toks[0].lower(); qtype=toks[1].upper()
    if qtype == "ANY": qtype = "ANY"
    recs=DNS_FIXTURES.get(name)
    lines=[f"; <<>> DiG 9.18.30-Gibson <<>> {qtype.lower()} {name}", ";; global options: +cmd"]
    if not recs:
        lines += [";; status: NXDOMAIN", "", ";; ANSWER: 0"]
        return "\n".join(lines)
    lines += [";; Got answer:", ";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 19337", "", ";; ANSWER SECTION:"]
    types = ["A","NS","MX","TXT","SOA"] if qtype == "ANY" else [qtype]
    for typ in types:
        for val in recs.get(typ,[]):
            lines.append(f"{name}.\t\t1800\tIN\t{typ}\t{val}")
    lines += ["", ";; Query time: 2 msec", ";; SERVER: Gibson fixture resolver", f";; WHEN: {_now()}"]
    _record(env,"DIG_LOOKUP",{"name":name,"type":qtype})
    return "\n".join(lines)


def whois_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or argv[0] in {"-h","--help","help"}: return "whois DOMAIN|IP  # Gibson fixture mode"
    q=argv[-1].lower()
    _record(env,"WHOIS_LOOKUP",{"query":q})
    if q == "sighberbank.com":
        return "\n".join(["Domain Name: SIGHBERBANK.COM","Registrar WHOIS Server: whois.ionos.com","Creation Date: 2024-12-10T18:33:20Z","Domain Status: clientTransferProhibited","Name Server: NS1104.UI-DNS.DE","Name Server: NS1019.UI-DNS.ORG","DNSSEC: unsigned","Registrant Organization: SighberBank Training Fixture"])
    if q in {"4.180.9.35", "82.31.22.123"}:
        return "\n".join([f"NetRange: {q}","OrgName: Microsoft Corporation" if q.startswith("4.") else "OrgName: SighberBank Training Fixture","Country: US" if q.startswith("4.") else "Country: GB","Comment: Gibson fixture whois data; not an authoritative live lookup."])
    return f"No whois fixture for {q}. Real whois disabled in Gibson safe mode."


def shodan_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or argv[0] in {"-h","--help","help"}:
        return "shodan info | shodan search QUERY | shodan host HOST | shodan init <api-key> (stores configured flag only)"
    sub=argv[0].lower()
    if sub == "init":
        # Do not store the key value; only record configured flag.
        env.write_text(env.resolve(cwd,".shodan_config"), json.dumps({"configured":True,"provider":"fixture-default"}))
        return "Shodan API key configured flag saved. Secret value is not displayed or stored by Gibson. Offline fixture mode remains default."
    if sub == "info":
        return "Query credits: fixture\nScan credits: fixture\nPlan: Gibson offline training mode\nAPI key configured: " + ("yes" if env.exists(env.resolve(cwd,".shodan_config")) else "no")
    if sub == "search":
        q=" ".join(argv[1:]).strip().strip('"\'').lower()
        rows=SHODAN_FIXTURES.get(q, [])
        if not rows: return f"No Shodan fixture results for: {q}\nTry: shodan search 'IKJ56700A port:23'"
        return "\n".join(f"{ip:<15} {port:<5} {host:<32} {banner}" for ip,port,host,banner in rows)
    if sub == "host" and len(argv)>=2:
        h=argv[1]
        ok,addr,disp=_authorised(env,cwd,h)
        if not ok and h not in {"82.31.240.44","82.31.22.123"}:
            return f"shodan: host {h} has no fixture data or is not in authorised HOSTS.TXT"
        return "\n".join([f"IP: {addr if ok else h}","Hostnames: mainframe.sighberbank.com", "Ports: 21,23,443,50000", "Data:", "  21/tcp 220-FTPD IBM FTP CS V2R5", "  23/tcp IKJ56700A ENTER USERID -", "  50000/tcp DB2 DRDA DSN12015"])
    return "Usage: shodan info | shodan search QUERY | shodan host HOST | shodan init <api-key>"


def geoloc_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or argv[0] in {"-h","--help","help"}: return "geoloc IP | geoloc -f ips.txt [--json|--csv -o file]"
    json_mode="--json" in argv; csv_mode="--csv" in argv; outfile=""; ips=[]
    i=0
    while i < len(argv):
        a=argv[i]
        if a == "-f" and i+1 < len(argv):
            for line in env.read_text(env.resolve(cwd,argv[i+1])).splitlines():
                line=line.strip()
                if line: ips.append(line)
            i+=2; continue
        if a == "-o" and i+1 < len(argv): outfile=argv[i+1]; i+=2; continue
        if not a.startswith("-"): ips.append(a)
        i+=1
    results=[]
    for ip in ips:
        try:
            obj=ipaddress.ip_address(ip)
        except ValueError:
            results.append({"ip":ip,"error":"invalid IP address"}); continue
        if ip in GEO_FIXTURES: results.append(dict(GEO_FIXTURES[ip])); continue
        if obj.is_private:
            results.append({"ip":ip,"classification":"private","city":"UNKNOWN","country":"UNKNOWN","source":"local-classifier","confidence":"high"}); continue
        # Use Gibson core provider if online is enabled; otherwise honest unknown.
        geo=None
        try:
            geo = env.state.geolocator.lookup(ip) if getattr(env.state,"geolocator",None) else None
        except Exception:
            geo=None
        if geo and getattr(geo,"latitude",None) is not None:
            d = geo.to_marker() if hasattr(geo,"to_marker") else geo.__dict__
            results.append(dict(d))
        else:
            results.append({"ip":ip,"classification":"public","city":"UNKNOWN","country":"UNKNOWN","source":"unknown-or-provider-unavailable","confidence":"none"})
    if json_mode:
        text=json.dumps(results,indent=2,sort_keys=True)
    elif csv_mode:
        import io
        buf=io.StringIO(); keys=sorted({k for r in results for k in r})
        w=csv.DictWriter(buf,fieldnames=keys); w.writeheader(); w.writerows(results); text=buf.getvalue().rstrip()
    else:
        lines=[]
        for r in results:
            if "error" in r: lines.append(f"{r['ip']}: {r['error']}")
            else: lines.append(f"{r.get('ip')}: {r.get('city','UNKNOWN')}, {r.get('region','')}, {r.get('country','UNKNOWN')} [{r.get('classification')}] {r.get('latitude','')},{r.get('longitude','')} ASN={r.get('asn','UNKNOWN')} source={r.get('source')}")
        text="\n".join(lines)
    if outfile:
        vp=_write(env,cwd,outfile,text+"\n"); text += f"\nSaved to {vp}"
    _record(env,"GEOLOC_LOOKUP",{"count":len(results)})
    return text


def nikto_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or argv[0] in {"--help","help"}: return "nikto -h http://mainframe:8080/manager/html [-id user:pass] [-C all]"
    host=""; creds=""; i=0
    while i < len(argv):
        if argv[i] == "-h" and i+1 < len(argv): host=argv[i+1]; i+=2; continue
        if argv[i] == "-id" and i+1 < len(argv): creds=argv[i+1]; i+=2; continue
        if not argv[i].startswith("-") and not host: host=argv[i]
        i+=1
    m=re.search(r"https?://([^/:]+)(?::(\d+))?", host)
    target = m.group(1) if m else (host.split('/')[0] if host else "mainframe")
    ok,addr,disp=_authorised(env,cwd,target)
    if not ok: return f"nikto: target denied - {disp}"
    port = int(m.group(2) or (8080 if "8080" in host else 80)) if m else 80
    vuln = bool(getattr(env.state.config,"security_mode","vuln") == "vuln" or os.getenv("GIBSON_VULN_MODE","0") == "1")
    accepted = creds in {"tomcat:tomcat","tomcat:manager"}
    findings=["- Nikto v2.5.0-Gibson","--------------------------------------------------------------------------",f"+ Target IP:          {addr}",f"+ Target Hostname:    {target}",f"+ Target Port:        {port}",f"+ Start Time:         {_now()}","--------------------------------------------------------------------------"]
    if port == 8080:
        findings.append("+ Server: Apache-Coyote/1.1 (Apache Tomcat Gibson simulator)")
        findings.append('+ HTTP Authentication: Basic realm="Tomcat Manager Application"')
        if accepted and vuln:
            findings.append(f"+ Supplied credentials accepted (user: {creds.split(':',1)[0]}).")
            findings.append("+ /manager/html: Accessible with provided credentials; deployment functions exposed.")
            findings.append("+ /manager/text/list: Script/CLI Manager endpoint available to authenticated user.")
            findings.append("+ The X-Frame-Options header is not present.")
        else:
            findings.append("+ /manager/html: Authentication required; supplied credentials rejected or secure mode enabled.")
    else:
        findings.append("+ Server: Gibson Welcome HTTP")
        findings.append("+ No CGI directories found in fixture profile.")
    findings += ["--------------------------------------------------------------------------", "+ 1 hosts tested."]
    _record(env,"NIKTO_SCAN",{"target":target,"port":port,"creds_tested":bool(creds),"vuln":vuln})
    return "\n".join(findings)


def db2connect_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or argv[0] in {"-h","--help","help"}: return "db2connect mainframe USER PASSWORD | db2 connect to GIBSONDB user IBMUSER using SYS1"
    line=" ".join(argv)
    if argv[0].lower()=="connect" or line.lower().startswith("connect "):
        m=re.search(r"user\s+(\S+)\s+using\s+(\S+)", line, re.I)
        user=m.group(1).upper() if m else "IBMUSER"; pw=m.group(2) if m else ""
        target="mainframe"
    else:
        target=argv[0]; user=(argv[1].upper() if len(argv)>1 else "IBMUSER"); pw=(argv[2] if len(argv)>2 else "")
    ok,addr,disp=_authorised(env,cwd,target)
    if not ok: return f"db2connect: target denied - {disp}"
    if (user,pw) not in {("IBMUSER","SYS1"),("SYSADM","PASSWORD"),("RUARIV","SPRING26")}:
        return "SQL30082N Security processing failed with reason \"24\" (USERNAME AND/OR PASSWORD INVALID). SQLSTATE=08001"
    _record(env,"DB2CONNECT_LOGIN",{"target":target,"user":user})
    return "\n".join(["IBM DB2 Command Line Processor for z/OS - Gibson",f"Database Connection Information",f" Database server        = DB2 z/OS DSN12015",f" SQL authorization ID   = {user}"," Local database alias   = GIBSONDB"," DB2 subsystem          = ZDB2A","", "db2 => select current server from sysibm.sysdummy1;", "1", "--------", "ZDB2A", "  1 record(s) selected.", "", "db2 => list tables", "Table/View                      Schema", "------------------------------  --------", "CUSTOMER                        FIBS", "ACCOUNTS                        FIBS", "SYSUSERAUTH                     SYSIBM"])


def task_command(env, cwd: str, userid: str, argv: list[str]) -> str:
    path=env.resolve(cwd,".gibson_tasks.json")
    try: tasks=json.loads(env.read_text(path))
    except Exception: tasks=[]
    def save(): env.write_text(path,json.dumps(tasks,indent=2,sort_keys=True))
    if not argv or argv[0] in {"list","next"}:
        active=[t for t in tasks if t.get("status","pending") == "pending"]
        lines=["ID Project Pri Due        Tags        Description"]
        for t in active:
            lines.append(f"{t['id']:<2} {t.get('project',''):<7} {t.get('pri',''):<3} {t.get('due',''):<10} {','.join(t.get('tags',[])):<10} {t.get('description','')}")
        lines.append(f"{len(active)} task" + ("s" if len(active)!=1 else ""))
        return "\n".join(lines)
    if argv[0] == "add":
        desc=[]; project=""; pri=""; due=""; tags=[]
        for a in argv[1:]:
            if a.startswith("project:"): project=a.split(":",1)[1]
            elif a.startswith("pri:"): pri=a.split(":",1)[1].upper()[:1]
            elif a.startswith("due:"): due=a.split(":",1)[1]
            elif a.startswith("+"): tags.append(a[1:])
            else: desc.append(a)
        if not desc: return "task: add requires a description"
        nid=max([int(t.get("id",0)) for t in tasks] or [0])+1
        tasks.append({"id":nid,"description":" ".join(desc),"project":project,"pri":pri,"due":due,"tags":tags,"status":"pending","entry":_now()}); save()
        _record(env,"TASK_CREATED",{"id":nid,"user":userid})
        return f"Created task {nid}."
    if argv[0].isdigit() and len(argv)>=2:
        tid=int(argv[0]); task=next((t for t in tasks if int(t.get("id",0))==tid),None)
        if not task: return f"No task {tid}."
        action=argv[1]
        if action == "done": task["status"]="completed"; task["end"]=_now(); save(); _record(env,"TASK_COMPLETED",{"id":tid,"user":userid}); return f"Completed {tid} '{task.get('description')}'.\nMarked 1 task as done."
        if action == "delete": tasks.remove(task); save(); return f"Deleted task {tid}."
        if action == "modify":
            for a in argv[2:]:
                if a.startswith("project:"): task["project"]=a.split(":",1)[1]
                elif a.startswith("pri:"): task["pri"]=a.split(":",1)[1].upper()[:1]
                elif a.startswith("due:"): task["due"]=a.split(":",1)[1]
                elif a.startswith("+"): task.setdefault("tags",[]).append(a[1:])
            save(); return f"Modified task {tid}."
    if argv[0] == "projects":
        ps=sorted({t.get("project") for t in tasks if t.get("project")})
        return "Project\n" + "\n".join(ps) if ps else "No projects."
    if argv[0] == "tags":
        tags=sorted({tag for t in tasks for tag in t.get("tags",[])})
        return "Tags\n" + "\n".join("+"+x for x in tags) if tags else "No tags."
    if argv[0] == "export": return json.dumps(tasks,indent=2,sort_keys=True)
    return "Usage: task [list] | task add DESC [project:X] [pri:H] [due:tomorrow] [+tag] | task ID done|modify|delete | task projects|tags|export"


def tshocker_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or any(a in {"-h","--help","help"} for a in argv):
        return "tshocker [-p 21] (-l --lport PORT | -r --rhost HOST --rport PORT) [--print] TARGET USER PASS"
    dotprint=False; listener=False; reverse=False; lport="4444"; rhost=""; rport=""; port="21"; pos=[]
    i=0
    while i < len(argv):
        a=argv[i]
        if a in {"--print","-P"}: dotprint=True
        elif a in {"-l","--listener"}: listener=True
        elif a in {"-r","--reverse"}: reverse=True
        elif a in {"-p","--port"} and i+1<len(argv): port=argv[i+1]; i+=1
        elif a == "--lport" and i+1<len(argv): lport=argv[i+1]; i+=1
        elif a == "--rhost" and i+1<len(argv): rhost=argv[i+1]; i+=1
        elif a == "--rport" and i+1<len(argv): rport=argv[i+1]; i+=1
        elif not a.startswith("-"): pos.append(a)
        i+=1
    if len(pos)<3: return "tshocker: target, username and password required"
    target,user,pw=pos[-3],pos[-2].upper(),pos[-1]
    ok,addr,disp=_authorised(env,cwd,target)
    if not ok: return f"tshocker: target denied - {disp}"
    mode="L" if listener or not reverse else "R"; parm=(lport if mode=="L" else f"{rhost} {rport}")
    jcl="\n".join([f"//{user}TSH JOB ({user}),'TSHOCKER',CLASS=A,MSGCLASS=0","//CREATOMG EXEC PGM=IEBGENER","//SYSUT1 DD DATA,DLM=##","/* CATSO Gibson safe training REXX */",f"SAY 'CATSO {mode} {parm}'","##","//EXECREXX EXEC PGM=IKJEFT01,PARM='%CATSO '","//SYSTSPRT DD SYSOUT=*","//* No real shell is created outside Gibson safe simulator"])
    if dotprint:
        return jcl
    vuln=bool(getattr(env.state.config,"security_mode","vuln") == "vuln" or os.getenv("GIBSON_VULN_MODE","0") == "1")
    if not vuln: return "TShOcker: FTP/JES execution path is disabled in secure mode. Use Gibson --vuln mode for the lab."
    _record(env,"TSHOCKER_JCL_GENERATED",{"target":target,"user":user,"mode":mode,"port":lport if mode=='L' else rport})
    if mode=="L":
        try: env.state.allowed_high_ports.add(int(lport))
        except Exception: pass
    return "\n".join(["[+] Connecting to: " + disp + ":" + port,"[+] FTP login accepted for Gibson training profile","[+] QUOTE SITE FILETYPE=JES accepted","[+] JCL/REXX uploaded to internal reader","[+] Job JOB19337 submitted","[+] CATSO safe training session prepared on port " + (lport if mode=='L' else rport),"No real shell or external job execution occurred."])


def ezrecon_command(env, cwd: str, argv: list[str]) -> str:
    if not argv or argv[0] in {"-h","--help","help"}: return "ezrecon dork|subdomains|email-scrape|report sighberbank.com"
    sub=argv[0].lower(); target=argv[1] if len(argv)>1 else "sighberbank.com"
    if sub == "subdomains": return subfinder_command(env,cwd,["-d",target,"-resolve"])
    if sub == "dork":
        return "\n".join(["Searching for: site:sighberbank.com", "1. Sighber Bank – The Humorous New Banking Experience", "2. SighberBank OSINT Forum - Mainframe Leakage Demonstration", "3. SighberBank Departments and Employees of Importance intext:\"@\"", "4. Welcome to the SighberBank Intranet – passwords.xlsx problem-code.txt", "Suggested next step: ezrecon report sighberbank.com"])
    if sub == "email-scrape": return "Emails found:\n  melin.tsay@sighberbank.com\n  Fraud@sighberbank.com\n  mainframe@sighberbank.com\n  admin@sighberbank.com"
    if sub == "report": return "SighberBank OSINT Reconnaissance Report\n- Exposed subdomains include mainframe, intranet and techforum.\n- Mainframe clues include IKJ56700A, CICS, DB2 DRDA and IBM FTP CS.\n- Treat all results as fixture/passive data until HOSTS.TXT authorisation is added."
    return "ezrecon dork|subdomains|email-scrape|report sighberbank.com"


def msfvenom_command(env, cwd: str, argv: list[str]) -> str:
    # Existing implementation may handle this; this helper is for caller fallback only.
    return "msfvenom simulation is provided by Gibson's existing Tomcat training module."
