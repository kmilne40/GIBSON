'use strict';

let traceSessionId = '';
let tracePaused = false;
let traceEvents = [];
let lastTraceEventId = '';
let lastEvidence = '';

function qs(sel, root=document){ return root.querySelector(sel); }
function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
function esc(value){ return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function traceLine(ev){ return `${ev.timestamp || ''} ${ev.component || ''} ${ev.action || ''} ${ev.result || ''} ${ev.message || ''} ${ev.correlation_id || ''}`.trim(); }
function setText(id, value){ const el = document.getElementById(id); if(el) el.textContent = value; }
function setHtml(id, value){ const el = document.getElementById(id); if(el) el.innerHTML = value; }
function labPage(){ return qs('.lab-page'); }
function labSlug(){ const p = labPage(); return p ? p.dataset.lab : ''; }
function currentPayload(){ const txt = qs('#labPayloadText'); const sel = qs('#labPayload'); return (txt && txt.value) || (sel && sel.value) || ''; }
function setLabStatus(msg, kind='info'){ const el = qs('#labStatus'); if(el){ el.textContent = msg; el.dataset.kind = kind; } }
function ensureTraceInputs(){ qsa('input[name="trace_id"]').forEach(i => { if(!i.value) i.value = traceSessionId || ''; }); }
function syncPayloadFields(){ const payload = currentPayload(); qsa('input.action-payload').forEach(i => { i.value = payload; }); updateCurl(); }

function renderTrace(){
  const stream = qs('#traceStream');
  if(!stream) return;
  const filter = (qs('#traceFilter')?.value || 'ALL').toUpperCase();
  const rows = traceEvents.filter(e => filter === 'ALL' || String(e.component || '').toUpperCase() === filter);
  stream.textContent = rows.length ? rows.map(traceLine).join('\n') : 'Waiting for teller activity...';
}
function addTrace(ev){
  if(!ev || !ev.event_id) return;
  if(traceEvents.some(x => x.event_id === ev.event_id)) return;
  traceEvents.push(ev);
  if(traceEvents.length > 100) traceEvents.shift();
  lastTraceEventId = ev.event_id || lastTraceEventId;
  const status = qs('#traceStatus');
  if(status) status.textContent = 'Trace active';
  renderTrace();
}
function highlightArchitectureNode(component){
  if(!component) return;
  qsa('.arch-node').forEach(n => n.classList.remove('active'));
  const node = qs(`.arch-node[data-node="${String(component).toUpperCase()}"]`);
  if(node) node.classList.add('active');
}
async function createTraceSession(){
  const page = labPage();
  const slug = labSlug();
  if(!page) return;
  if(page.dataset.traceId){ traceSessionId = page.dataset.traceId; ensureTraceInputs(); return; }
  if(!window.fetch) return;
  try{
    const body = new URLSearchParams({page: location.pathname, lab_slug: slug});
    const r = await fetch('/webapi/trace/session', {method:'POST', headers:{'Accept':'application/json'}, body});
    const j = await r.json();
    traceSessionId = j.trace_id || '';
    page.dataset.traceId = traceSessionId;
    ensureTraceInputs();
    if(j.event_id) addTrace({event_id:j.event_id, timestamp:j.created_at, trace_id:traceSessionId, correlation_id:traceSessionId, component:'WEB9080', action:'TRACE_SESSION_CREATED', result:'OK', message:'Trace session created'});
  }catch(e){ setLabStatus('Trace session could not start: ' + (e.message || e), 'error'); }
}
async function pollTraceEvents(){
  if(tracePaused || !window.fetch) return;
  const id = traceSessionId || labPage()?.dataset.traceId || '';
  const url = id ? `/webapi/trace/${encodeURIComponent(id)}/events${lastTraceEventId ? '?since=' + encodeURIComponent(lastTraceEventId) : ''}` : `/webapi/teller/events${lastTraceEventId ? '?since=' + encodeURIComponent(lastTraceEventId) : ''}`;
  try{
    const r = await fetch(url, {headers:{'Accept':'application/json'}});
    if(!r.ok) return;
    const j = await r.json();
    (j.events || []).forEach(ev => { addTrace(ev); highlightArchitectureNode(ev.component); });
  }catch(e){ /* keep UI usable */ }
}
function pauseTrace(){ tracePaused = true; const s=qs('#traceStatus'); if(s) s.textContent='Trace paused'; }
function resumeTrace(){ tracePaused = false; const s=qs('#traceStatus'); if(s) s.textContent='Trace active'; pollTraceEvents(); }
async function clearTrace(){
  traceEvents = []; lastTraceEventId = ''; renderTrace();
  if(!window.fetch) return;
  try{
    const id = traceSessionId || labPage()?.dataset.traceId || '';
    const endpoint = id ? `/webapi/trace/${encodeURIComponent(id)}/clear` : '/webapi/teller/trace/clear';
    await fetch(endpoint, {method:'POST', headers:{'Accept':'application/json'}});
  }catch(e){ setLabStatus('Trace clear failed: ' + (e.message || e), 'error'); }
}
window.pauseTrace = pauseTrace; window.resumeTrace = resumeTrace; window.clearTrace = clearTrace; window.renderTrace = renderTrace;

function updateCurl(){
  const curl = qs('#curlBox'); const slug = labSlug(); if(!curl || !slug) return;
  curl.textContent = `curl -X POST http://127.0.0.1:9080/webapi/labs/${slug}/run -d payload=${JSON.stringify(currentPayload())} -d trace_id=${JSON.stringify(traceSessionId || '')}`;
}
function renderLabResult(j, action){
  lastEvidence = j.evidence_id || lastEvidence;
  if(j.trace_id){ traceSessionId = j.trace_id; const p=labPage(); if(p) p.dataset.traceId=traceSessionId; ensureTraceInputs(); }
  setText('labRequestResponse', JSON.stringify({request:j.request, response:j.response, trace_id:j.trace_id, correlation_id:j.correlation_id, evidence_id:j.evidence_id, secure_comparison:j.secure_comparison}, null, 2));
  const events = j.trace_events || j.events || [];
  setHtml('labTimeline', events.length ? events.map(e => `<li>${esc(traceLine(e))}</li>`).join('') : '<li>No trace events returned. Check the selected trace session.</li>');
  const evBox = qs('#labEvidenceDynamic');
  if(evBox){
    const smf = (j.smf_events || []).map(e => `<li>SMF${esc(e.smf_type || '')} ${esc(e.action || '')} ${esc(e.result || '')} ${esc(e.resource || e.table || '')}</li>`).join('');
    const alerts = (j.console_alerts || []).map(a => `<li>${esc(a)}</li>`).join('');
    evBox.innerHTML = `<h3>Latest evidence</h3><p><strong>Trace:</strong> ${esc(j.trace_id || '')} <strong>Evidence:</strong> ${esc(j.evidence_id || '')}</p><ul>${smf || '<li>No SMF evidence returned.</li>'}${alerts}</ul>`;
  }
  events.forEach(ev => { addTrace(ev); highlightArchitectureNode(ev.component); });
  setLabStatus(action === 'secure-compare' ? 'Secure comparison complete.' : action === 'reset' ? 'Lab reset complete.' : 'Lab action complete.', 'ok');
  updateCurl();
}
async function enhanceLabForm(form){
  if(!window.fetch) return false;
  syncPayloadFields(); ensureTraceInputs();
  const action = form.dataset.action || 'run'; const slug = form.dataset.lab || labSlug();
  const endpoint = form.dataset.api || `/webapi/labs/${encodeURIComponent(slug)}/${encodeURIComponent(action)}`;
  try{
    setLabStatus(action === 'reset' ? 'Resetting lab...' : 'Collecting backend evidence...');
    const fd = new FormData(form);
    fd.set('payload', action === 'reset' ? '' : currentPayload());
    fd.set('trace_id', traceSessionId || '');
    const r = await fetch(endpoint, {method:'POST', headers:{'Accept':'application/json'}, body: new URLSearchParams(fd)});
    const txt = await r.text(); let j = {};
    try{ j = JSON.parse(txt || '{}'); }catch(e){ throw new Error('Invalid JSON response: ' + txt.slice(0, 160)); }
    if(!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
    renderLabResult(j, action);
    await pollTraceEvents();
    return true;
  }catch(e){ setLabStatus('Error: ' + (e.message || e), 'error'); return true; }
}
function revealNextHint(){ const h = qsa('.hint-item.hidden')[0]; const btn = qs('#showNextHint'); if(h){ h.classList.remove('hidden'); if(!qs('.hint-item.hidden') && btn){ btn.textContent='All hints shown'; btn.disabled=true; } } }
function copyCurl(){ const c=qs('#curlBox'); if(c && navigator.clipboard){ navigator.clipboard.writeText(c.textContent); setLabStatus('Curl copied to clipboard.','ok'); } }
async function exportEvidence(){
  const slug = labSlug(); if(!slug || !window.fetch) return;
  try{
    const id = lastEvidence || '';
    const url = `/webapi/labs/${encodeURIComponent(slug)}/export/${encodeURIComponent(id)}?trace_id=${encodeURIComponent(traceSessionId || '')}`;
    const r = await fetch(url, {headers:{'Accept':'application/json'}}); const j = await r.json();
    setText('labRequestResponse', JSON.stringify(j, null, 2)); setLabStatus('Evidence exported to response panel.','ok');
  }catch(e){ setLabStatus('Export failed: ' + (e.message || e), 'error'); }
}

document.addEventListener('DOMContentLoaded', async () => {
  const sel = qs('#labPayload'); const txt = qs('#labPayloadText');
  if(sel && txt){ sel.addEventListener('change', () => { txt.value = sel.value; syncPayloadFields(); }); txt.addEventListener('input', syncPayloadFields); }
  await createTraceSession(); syncPayloadFields(); updateCurl(); pollTraceEvents(); setInterval(pollTraceEvents, 2500);
  qsa('form.lab-action-form').forEach(form => form.addEventListener('submit', async ev => { const handled = await enhanceLabForm(form); if(handled) ev.preventDefault(); }));
  qs('#showNextHint')?.addEventListener('click', ev => { ev.preventDefault(); revealNextHint(); });
  qs('#copyCurlButton')?.addEventListener('click', ev => { ev.preventDefault(); copyCurl(); });
  qs('#exportEvidenceButton')?.addEventListener('click', ev => { ev.preventDefault(); exportEvidence(); });
  qsa('.knowledge-toggle').forEach(btn => btn.addEventListener('click', () => btn.nextElementSibling?.classList.toggle('hidden')));
  qs('#traceFilter')?.addEventListener('change', renderTrace);
});
