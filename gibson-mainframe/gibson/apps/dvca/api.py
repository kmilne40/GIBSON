from __future__ import annotations
import json
from urllib.parse import urlparse
from gibson.apps.dvca import hack3270_bridge as h
from gibson.apps.dvca.store import get_dvca_store
from gibson.apps.dvca.render_html import field_table_rows
from gibson.apps.dvca.screen_model import screen_for


def _body(handler):
    n = int(handler.headers.get('Content-Length','0') or 0)
    raw = handler.rfile.read(n) if n else b''
    try:
        return json.loads(raw.decode('utf-8')) if raw else {}
    except Exception:
        return {}


def _json(handler, code, payload):
    b = json.dumps(payload, indent=2, sort_keys=True).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type','application/json; charset=utf-8')
    handler.send_header('Cache-Control','no-store')
    handler.send_header('Content-Length',str(len(b)))
    handler.end_headers()
    handler.wfile.write(b)


def _html(handler, body):
    b = body.encode('utf-8')
    handler.send_response(200)
    handler.send_header('Content-Type','text/html; charset=utf-8')
    handler.send_header('Content-Length',str(len(b)))
    handler.end_headers()
    handler.wfile.write(b)


def render_page(hack=False):
    return """<!doctype html><html><head><meta charset='utf-8'><title>hack3270-gibson professional</title>
<style>
:root{--term:#050505;--green:#00ff7f;--panel:#d8d8d8;--ink:#111;--yellow:#ffeb3b;--blue:#5db7ff;--red:#ff5252;--gold:#caa64b}
body{margin:0;background:#0b0b0b;color:var(--green);font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.bar{background:var(--panel);color:var(--ink);padding:10px;border-bottom:4px solid #888}.title{display:flex;justify-content:space-between;align-items:center}.state{font-weight:900}.hack-off{color:#772222}.hack-on{color:#a40000;background:#fff0f0;border:1px solid #a40000;padding:3px 6px;border-radius:4px}.tabs{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap}.tabs button,.toolbar button,.primary{padding:7px 10px;border:1px solid #777;border-radius:4px;background:#f4f4f4;cursor:pointer}.primary{font-weight:900}.primary.on{background:#a40000;color:white}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:8px}.toolbar label{display:inline-flex;gap:5px;align-items:center}.wrap{display:grid;grid-template-columns:minmax(680px,2fr) minmax(360px,1fr);gap:12px;padding:14px}.terminal{background:#000;border:2px solid #555;min-height:560px;padding:16px;color:var(--green);white-space:pre;font-size:16px;line-height:1.2;overflow:auto}.side{background:#101010;border:1px solid #444;padding:12px;min-height:560px;overflow:auto}.panel{display:none}.panel.active{display:block}.field-hidden-revealed{color:#000;background:var(--yellow);font-weight:bold}.field-hidden{visibility:hidden}.field-protected{outline:1px dotted var(--blue)}.field-numeric{border-bottom:2px solid #a66cff}.field-mdt,.field-fset{box-shadow:inset 0 -2px 0 var(--gold)}.field-modified{outline:2px solid var(--red)}table{width:100%;border-collapse:collapse;color:#e8ffe8}th,td{border-bottom:1px solid #333;padding:5px;text-align:left}.badge{display:inline-block;background:#223b5a;color:#fff;border-radius:4px;padding:1px 4px;margin:1px;font-size:11px}input,select{padding:7px;margin:3px;background:#fff;color:#111}.mutate{background:#ddd;color:#111;padding:7px;border-top:4px solid #777}.log{background:#000;color:#7cff7c;white-space:pre-wrap;max-height:320px;overflow:auto;padding:8px;border:1px solid #333}.warning{color:#ffb000}.json{color:#b7ffb7;white-space:pre-wrap}.statusbar{background:#002b00;color:#9cff9c;padding:7px;border-top:2px solid #295}
</style></head><body>
<div class='bar'><div class='title'><b>hack3270-gibson v1.1 professional</b><span id='state' class='state hack-off'>MODE: ? | HACK: OFF | SCREEN: ?</span></div>
<div class='tabs'><button onclick="tab('terminal')">Terminal</button><button onclick="tab('attrs')">Hack Field Attributes</button><button onclick="tab('inject')">Inject Info Fields</button><button onclick="tab('keys')">Inject Key Presses</button><button onclick="tab('pin')">BATCH PIN</button><button onclick="tab('api')">API Leakage</button><button onclick="tab('logs')">Logs</button><button onclick="tab('stats')">Statistics</button><button onclick="tab('help')">Help</button></div>
<div class='toolbar'><button id='hackbtn' class='primary' onclick='hackToggle()'>HACK OFF</button><label><input id='dp' type='checkbox'> Disable Field Protection</label><label><input id='eh' type='checkbox'> Enable Hidden Fields</label><label><input id='rn' type='checkbox'> Remove Numeric Only Restrictions</label><label><input id='sf' type='checkbox'> Start Field</label><label><input id='sfe' type='checkbox'> Start Field Extended</label>
<button onclick="aid('PF5')">PF5 Main Menu</button><button onclick="aid('PF1')">PF1 Help</button><button onclick="aid('PF7')">PF7</button><button onclick="aid('PF8')">PF8</button><button onclick="aid('PA3')">PA3 Secret</button></div></div>
<div class='wrap'><pre id='terminalScreen' class='terminal'>Connecting to DVCA...</pre><aside class='side'>
<div id='terminal' class='panel active'><h3>Session</h3><p>Use the terminal and controls to inspect DVCA fields. Mutation requires HACK ON.</p><div id='message' class='warning'></div></div>
<div id='attrs' class='panel'><h3>Field Inspector</h3><table><thead><tr><th>Name</th><th>R</th><th>C</th><th>Len</th><th>Value</th><th>Attr</th><th>Map</th></tr></thead><tbody id='fieldRows'></tbody></table></div>
<div id='inject' class='panel'><h3>Modify Field</h3><p>Field mutation is checked against HACK ON/OFF and field attributes.</p><select id='fieldSel'></select><input id='value' placeholder='VALUE'><button onclick='setf()'>Modify Field</button><div id='mutateResult'></div></div>
<div id='keys' class='panel'><h3>AID Keys</h3><button onclick="aid('ENTER')">ENTER</button><button onclick="aid('PF1')">PF1 Help</button><button onclick="aid('PF3')">PF3 Back</button><button onclick="aid('PF5')">PF5 Menu</button><button onclick="aid('PF7')">PF7</button><button onclick="aid('PF8')">PF8</button><button onclick="aid('PA3')">PA3 Secret</button><input id='cmd' placeholder='command or menu option'><button onclick='inputCmd()'>Enter command</button></div>
<div id='pin' class='panel'><h3>Batch PIN</h3><p>PIN is masked until discovered or injected. Batch PIN is bounded and requires HACK ON.</p><label>Start <input id='pinStart' value='0000'></label><label>End <input id='pinEnd' value='9999'></label><label>Max attempts <input id='pinMax' value='1500'></label><button onclick='pin()'>Run Batch PIN</button><div id='pinResult'></div></div>
<div id='api' class='panel'><h3>API Leakage</h3><p>Training-only structured session and field metadata.</p><pre id='apiJson' class='json'></pre></div>
<div id='logs' class='panel'><h3>Logs</h3><pre id='logText' class='log'></pre></div>
<div id='stats' class='panel'><h3>Statistics</h3><pre id='statsText' class='json'></pre></div>
<div id='help' class='panel'><h3>Help</h3><p>TN3270/BMS screens use field attributes. Protected fields, hidden/nondisplay fields, numeric-only fields, MDT and FSET are client/session controls, not server-side authorization. DVCA teaches what happens when CICS application code trusts those values.</p><ul><li>Enable Hidden Fields reveals DRK/nondisplay fields in yellow.</li><li>Disable Field Protection permits protected-field mutation in vulnerable mode.</li><li>Start Field Extended shows PROT/HIDDEN/NUM/MDT/FSET badges.</li><li>Batch PIN demonstrates the hardcoded supervisor PIN lab.</li></ul></div>
</aside></div><div class='mutate'><b>Command/Input ===&gt;</b> <input id='cmdMain' placeholder='1, 2, 3, H, 99, HACK ON, BRUTE FORCE PIN' style='min-width:360px'> <button onclick='inputCmdMain()'>ENTER</button> &nbsp; <b>Hack Modify Field</b> FIELD <input id='field' placeholder='FIELD'> VALUE <input id='val2' placeholder='VALUE'> <button onclick='setf2()'>Modify Field</button></div><div class='statusbar'>TRANS: DVCA &nbsp; OPER: DVCA &nbsp; CANONICAL PORT: 8080 &nbsp; FIBS BANK remains on 9080</div>
<script>
let sid=null,last=null;let ui={};
function initUi(){ui={terminal:document.getElementById('terminalScreen'),message:document.getElementById('message'),state:document.getElementById('state'),apiJson:document.getElementById('apiJson'),fieldRows:document.getElementById('fieldRows'),fieldSel:document.getElementById('fieldSel'),hackbtn:document.getElementById('hackbtn'),dp:document.getElementById('dp'),eh:document.getElementById('eh'),rn:document.getElementById('rn'),sf:document.getElementById('sf'),sfe:document.getElementById('sfe'),logText:document.getElementById('logText'),statsText:document.getElementById('statsText'),mutateResult:document.getElementById('mutateResult')}}
function escapeText(v){return String(v||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function tab(n){document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));document.getElementById(n).classList.add('active')}
async function j(u,o){try{let r=await fetch(u,o);let t=await r.text();try{return JSON.parse(t)}catch(e){return {error:t,status:r.status}}}catch(e){return {error:'connection failed: '+e.message}}}
function showError(msg){if(ui.terminal)ui.terminal.textContent='Connection failed. '+msg+'\\nUse Retry to reconnect.';if(ui.message)ui.message.innerHTML='<button onclick="load()">Retry</button> '+escapeText(msg)}
async function load(){if(ui.terminal)ui.terminal.textContent='Connecting to DVCA...';let d=await j('/api/v1/hack3270/session/start',{method:'POST'});if(d.error&&!d.session_id){showError(d.error);return}sid=d.session_id;show(d)}
function syncBoxes(h){ui.dp.checked=!!h.disable_protection;ui.eh.checked=!!h.reveal_hidden;ui.rn.checked=!!h.remove_numeric;ui.sf.checked=!!h.show_start_field;ui.sfe.checked=!!h.show_sfe;ui.hackbtn.textContent=h.enabled?'HACK ON':'HACK OFF';ui.hackbtn.className='primary '+(h.enabled?'on':'');ui.state.textContent='MODE: '+(last?.mode||'?')+' | HACK: '+(h.enabled?'ON':'OFF')+' | SCREEN: '+(last?.screen_id||'?');ui.state.className='state '+(h.enabled?'hack-on':'hack-off')}
function show(d){last=d;if(ui.terminal)ui.terminal.innerHTML=d.rendered_html||escapeText(d.rendered||'');ui.message.textContent=d.message||d.error||'';ui.apiJson.textContent=JSON.stringify({mode:d.mode,hack:d.hack,fields:d.fields,message:d.message},null,2);syncBoxes(d.hack||{});let opts='';let rows='';(d.fields||[]).forEach(f=>{opts+=`<option>${escapeText(f.name)}</option>`;let attrs=[f.protected?'PROT':'',f.hidden?'HIDDEN':'',f.numeric?'NUM':'',f.mdt?'MDT':'',f.fset?'FSET':''].filter(Boolean).map(x=>`<span class="badge">${x}</span>`).join(' ');rows+=`<tr><td>${escapeText(f.name)}</td><td>${f.row}</td><td>${f.col}</td><td>${f.length}</td><td><code>${escapeText(f.value)}</code></td><td>${attrs}</td><td>${escapeText(f.source||'')}</td></tr>`});ui.fieldSel.innerHTML=opts;ui.fieldRows.innerHTML=rows;refreshLogs();refreshStats()}
async function toggle(){show(await j('/api/v1/hack3270/session/'+sid+'/toggle',{method:'POST',body:JSON.stringify({disable_field_protection:ui.dp.checked,enable_hidden_fields:ui.eh.checked,remove_numeric_only:ui.rn.checked,start_field:ui.sf.checked,start_field_extended:ui.sfe.checked}),headers:{'Content-Type':'application/json'}}))}
async function hackToggle(){let on=!(last&&last.hack&&last.hack.enabled);show(await j('/api/v1/hack3270/session/'+sid+(on?'/hack-on':'/hack-off'),{method:'POST'}))}
async function aid(a){show(await j('/api/v1/hack3270/session/'+sid+'/send-aid',{method:'POST',body:JSON.stringify({aid:a}),headers:{'Content-Type':'application/json'}}))}
async function setf(){let valueEl=document.getElementById('value');let d=await j('/api/v1/hack3270/session/'+sid+'/send-field',{method:'POST',body:JSON.stringify({field:ui.fieldSel.value,value:valueEl.value}),headers:{'Content-Type':'application/json'}});ui.mutateResult.textContent=d.error||d.message||'OK';show(d)}
async function setf2(){let f=document.getElementById('field'),v=document.getElementById('val2');show(await j('/api/v1/hack3270/session/'+sid+'/send-field',{method:'POST',body:JSON.stringify({field:f.value,value:v.value}),headers:{'Content-Type':'application/json'}}))}
async function inputCmd(){let cmd=document.getElementById('cmd');show(await j('/api/v1/dvca/session/'+sid+'/input',{method:'POST',body:JSON.stringify({command:cmd.value}),headers:{'Content-Type':'application/json'}}))}
async function inputCmdMain(){let cmd=document.getElementById('cmdMain');show(await j('/api/v1/dvca/session/'+sid+'/input',{method:'POST',body:JSON.stringify({command:cmd.value}),headers:{'Content-Type':'application/json'}})); if(cmd)cmd.value='';}
async function pin(){let pinStart=document.getElementById('pinStart'),pinEnd=document.getElementById('pinEnd'),pinMax=document.getElementById('pinMax'),pinResult=document.getElementById('pinResult');let d=await j('/api/v1/hack3270/session/'+sid+'/batch-pin/start',{method:'POST',body:JSON.stringify({start_pin:pinStart.value,end_pin:pinEnd.value,max_attempts:pinMax.value}),headers:{'Content-Type':'application/json'}});pinResult.textContent=d.error||('found='+(d.found||'')+' attempts='+(d.attempts||0)+' injected='+(d.injected||false));show(d)}
async function refreshLogs(){if(!sid)return;let d=await j('/api/v1/hack3270/session/'+sid+'/logs');ui.logText.textContent=JSON.stringify(d.events||[],null,2)}
async function refreshStats(){if(!sid)return;let d=await j('/api/v1/hack3270/session/'+sid+'/statistics');ui.statsText.textContent=JSON.stringify(d,null,2)}
document.addEventListener('DOMContentLoaded',()=>{initUi();['dp','eh','rn','sf','sfe'].forEach(e=>document.getElementById(e).onchange=toggle);load()});
</script></body></html>"""


def handle(handler, state):
    path = urlparse(handler.path).path.rstrip('/') or '/'
    method = handler.command.upper()
    data = _body(handler) if method in {'POST','PUT'} else {}
    if path in {'/dvca','/dvca/hack3270'}:
        return _html(handler, render_page(path.endswith('hack3270')))
    if path == '/api/v1/dvca/health':
        return _json(handler, 200, {'status':'UP','service':'DVCA','vulnerable':h.is_vulnerable(state),'port':8080})
    if path == '/api/v1/hack3270/status':
        return _json(handler, 200, {'status':'UP','service':'hack3270-gibson','vulnerable':h.is_vulnerable(state)})
    if path in {'/api/v1/dvca/session/start','/api/v1/hack3270/session/start'} and method == 'POST':
        return _json(handler, 200, h.start(state))
    parts = path.strip('/').split('/')
    sid = ''
    if 'session' in parts:
        try:
            sid = parts[parts.index('session') + 1]
        except Exception:
            sid = ''
    if path.endswith('/hack-on') and method == 'POST': return _json(handler, 200, h.hack_on(state, sid))
    if path.endswith('/hack-off') and method == 'POST': return _json(handler, 200, h.hack_off(state, sid))
    if path.endswith('/state'): return _json(handler, 200, h.snapshot(state, sid))
    if path.endswith('/screen') or path.endswith('/rendered-html'): return _json(handler, 200, h.snapshot(state, sid))
    if path.endswith('/fields') or path.endswith('/field-inspector'): return _json(handler, 200, {'fields': h.snapshot(state, sid).get('fields', [])})
    if path.endswith('/logs'): return _json(handler, 200, h.logs(state, sid))
    if path.endswith('/statistics'): return _json(handler, 200, h.stats(state, sid))
    if path.endswith('/export'): return _json(handler, 200, {'snapshot': h.snapshot(state, sid), 'logs': h.logs(state, sid)})
    if path.endswith('/reset') and method == 'POST': get_dvca_store(state).reset(); return _json(handler, 200, h.start(state))
    if path.endswith('/input') and method == 'POST': return _json(handler, 200, h.send_input(state, sid, data.get('command',''), data.get('fields') or {}))
    if path.endswith('/aid') or path.endswith('/send-aid'): return _json(handler, 200, h.send_aid(state, sid, data.get('aid','ENTER')))
    if path.endswith('/toggle') or path.endswith('/action'): return _json(handler, 200, h.toggle(state, sid, data))
    if path.endswith('/send-field'): return _json(handler, 200, h.send_field(state, sid, data.get('field',''), data.get('value','')))
    if path.endswith('/batch-pin') or path.endswith('/batch-pin/start') or path.endswith('/batch-pin/step') or path.endswith('/batch-pin/inject'):
        return _json(handler, 200, h.batch_pin(state, sid, int(data.get('max_attempts', 1500)), data.get('start_pin', 0), data.get('end_pin'), True, True))
    if path.endswith('/batch-pin/stop'): return _json(handler, 200, {'status':'STOPPED', **h.snapshot(state, sid)})
    if path.endswith('/aid-scan'): return _json(handler, 200, h.aid_scan(state, sid))
    return False
