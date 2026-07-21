from __future__ import annotations

import json
from html import escape
from typing import Any
from .lab_catalog import LabDefinition, list_labs
from .lab_diagrams import render_diagram
from .cobol_bo_annotated import render_cobol_bo_annotation


def _chips(items: list[str]) -> str:
    return "".join(f"<span class='lab-chip'>{escape(x)}</span>" for x in items)


def render_lab_index() -> str:
    cards = []
    for lab in list_labs():
        comps = ["API", "CICS", "Db2", "SMF"]
        if lab.slug in {"jwt", "oauth", "weak-auth"}:
            comps = ["Identity", "GACF", "SMF80", "API"]
        cards.append(f"""
<article class='academy-card' data-category='{escape(lab.category)}'>
  <div class='lab-meta'><span>{escape(lab.category)}</span><span>{escape(lab.estimated_time)}</span><span>{escape(lab.learner_level)}</span></div>
  <h2>{escape(lab.title)}</h2>
  <p>{escape(lab.summary)}</p>
  <div class='lab-chip-row'>{_chips(comps)}</div>
  <p class='evidence-line'><strong>Evidence:</strong> {escape(', '.join(lab.evidence_targets[:3]))}</p>
  <a class='button secondary' href='/labs/{escape(lab.slug)}'>Open lab</a>
</article>
""")
    filters = "".join(f"<button class='filter-chip' data-filter='{f}'>{f}</button>" for f in ["All","API","CICS","Db2","Identity","Authorization","Detection"])
    return f"""
<section class='academy-hero'>
  <p class='eyebrow'>FIBS BANK training environment</p>
  <h1>FIBS Mainframe API Security Academy</h1>
  <p>Explore API attacks against a simulated mainframe-backed bank. Each lab shows the web/API request, z/OS Connect-style and native CICS API paths, CICS transactions, Db2 SQL, and simulated SMF/Master Console evidence.</p>
  <div class='academy-architecture-summary'>
    <span>Browser / curl</span><strong>→</strong><span>FIBS WEB9080</span><strong>→</strong><span>z/OS Connect-style API</span><strong>→</strong><span>CICS / COBOL</span><strong>→</strong><span>Db2</span><strong>→</strong><span>SMF / Console</span>
  </div>
</section>
<section class='academy-filters'>{filters}</section>
<section class='academy-grid'>{''.join(cards)}</section>
"""


def _json_block(value: Any) -> str:
    try:
        return escape(json.dumps(value, indent=2, sort_keys=True, default=str))
    except Exception:
        return escape(str(value))


def _render_result(result: dict[str, Any] | None) -> tuple[str, str, str, str]:
    if not result:
        return (
            "Run the lab to see HTTP method, endpoint, response, correlation ID and evidence ID.",
            "<li>WEB9080 awaits lab execution.</li><li>CICS, Db2, SMF and Master Console steps appear after running the lab.</li>",
            "",
            "Ready. Choose a payload and run the lab.",
        )
    summary = {
        "request": result.get("request", {}),
        "response": result.get("response", {}),
        "trace_id": result.get("trace_id", ""),
        "correlation_id": result.get("correlation_id", ""),
        "evidence_id": result.get("evidence_id", ""),
        "secure_comparison": result.get("secure_comparison", ""),
    }
    events = result.get("trace_events") or result.get("events") or []
    timeline = "".join(
        f"<li>{escape(str(e.get('timestamp','')))} {escape(str(e.get('component','')))} {escape(str(e.get('action','')))} {escape(str(e.get('result','')))} {escape(str(e.get('message','')))}</li>"
        for e in events
    ) or "<li>No trace events returned. Check the selected trace session.</li>"
    smf = "".join(
        f"<li>SMF{escape(str(e.get('smf_type','')))} {escape(str(e.get('action','')))} {escape(str(e.get('result','')))} {escape(str(e.get('resource') or e.get('table') or ''))}</li>"
        for e in result.get("smf_events", [])
    )
    alerts = "".join(f"<li>{escape(str(a))}</li>" for a in result.get("console_alerts", []))
    evidence = f"""
<div class='lab-result-summary'>
  <h3>Latest evidence</h3>
  <p><strong>Trace:</strong> {escape(str(result.get('trace_id','')))} · <strong>Evidence:</strong> {escape(str(result.get('evidence_id','')))}</p>
  <ul>{smf or '<li>No SMF evidence returned.</li>'}{alerts}</ul>
</div>
"""
    status = f"{result.get('lab','Lab')} {result.get('mode','run')} complete. Trace {result.get('trace_id','')}."
    return _json_block(summary), timeline, evidence, escape(status)


def _action_form(lab: LabDefinition, action: str, label: str, css: str, payload: str, trace_id: str = "") -> str:
    return f"""
<form method='post' action='/labs/{escape(lab.slug)}/{escape(action)}' class='lab-action-form' data-lab='{escape(lab.slug)}' data-action='{escape(action)}' data-api='/webapi/labs/{escape(lab.slug)}/{escape(action)}'>
  <input type='hidden' class='action-payload' name='payload' value='{escape(payload, quote=True)}'>
  <input type='hidden' name='trace_id' value='{escape(trace_id, quote=True)}'>
  <button class='{css}' type='submit'>{escape(label)}</button>
</form>
"""


def render_lab_detail(lab: LabDefinition, mode: str, result: dict[str, Any] | None = None, message: str = "") -> str:
    payload_default = result.get("payload") if result else (lab.payloads[0].value if lab.payloads else "")
    trace_id = result.get("trace_id", "") if result else ""
    payload_options = "".join(
        f"<option value='{escape(p.value, quote=True)}'>{escape(p.name)} — {escape(p.description)}</option>"
        for p in lab.payloads
    )
    objectives = "".join(f"<li>{escape(x)}</li>" for x in lab.learning_objectives)
    prereq = "".join(f"<li>{escape(x)}</li>" for x in lab.prerequisites)
    backend_rows = "".join(f"<tr><th>{escape(k)}</th><td>{escape(v)}</td></tr>" for k, v in lab.backend_mapping.items())
    evidence = "".join(f"<li>{escape(x)}</li>" for x in lab.evidence_targets)
    hints = "".join(f"<li class='hint-item hidden' data-hint-index='{i}'>{escape(h)}</li>" for i, h in enumerate(lab.hints, 1))
    solution_rows = "".join(f"<tr><th>{escape(k.replace('_',' ').title())}</th><td>{escape(v)}</td></tr>" for k, v in lab.solution.items())
    remediation = "".join(f"<li>{escape(x)}</li>" for x in lab.remediation)
    questions = "".join(
        f"<div class='knowledge-question'><p><strong>{escape(q['question'])}</strong></p><button class='button tiny secondary knowledge-toggle' type='button'>Show answer</button><p class='hidden'>{escape(q['answer'])}</p></div>"
        for q in lab.knowledge_checks
    )
    glossary = "".join(f"<tr><th>{escape(k)}</th><td>{escape(v)}</td></tr>" for k, v in (lab.glossary or {}).items())
    instructor_notes = "".join(f"<li>{escape(x)}</li>" for x in (lab.instructor_notes or []))
    api_paths = "".join(f"<code>{escape(x)}</code>" for x in lab.api_paths)
    rr_text, timeline, dynamic_evidence, status_msg = _render_result(result)
    if message:
        status_msg = escape(message)
    return f"""
<article class='lab-page' data-lab='{escape(lab.slug)}' data-trace-id='{escape(trace_id, quote=True)}'>
  <header class='lab-header'>
    <div><p class='eyebrow'>FIBS Mainframe API Security Academy</p><h1>{escape(lab.title)}</h1><p>{escape(lab.summary)}</p></div>
    <aside><span class='status-chip'>{escape(lab.severity)}</span><span class='status-chip'>{escape(lab.estimated_time)}</span><span class='status-chip'>MODE: {escape(mode)}</span></aside>
  </header>

  <section class='lab-two-col'>
    <div class='panel'><h2>Overview</h2><h3>What is this vulnerability?</h3><p>{escape(lab.beginner_explanation or lab.summary)}</p><h3>Why it matters</h3><p>{escape(lab.why_it_matters or lab.summary)}</p><h3>What an attacker tries</h3><p>{escape(lab.attacker_goal or 'The attacker changes request data to reach an unintended backend effect.')}</p><h3>Defender view</h3><p>{escape(lab.defender_view or 'Defenders validate input, authorize every object, monitor evidence and compare secure behaviour.')}</p><h3>Mainframe context</h3><p>{escape(lab.mainframe_context)}</p><h3>Learning objectives</h3><ul>{objectives}</ul><h3>Prerequisites</h3><ul>{prereq}</ul><h3>API paths</h3><div class='api-paths'>{api_paths}</div></div>
    <div class='panel'><h2>Mainframe architecture</h2>{render_diagram(lab)}</div>
  </section>

  <section class='panel lab-workbench'>
    <h2>Attack workbench</h2>
    <p>Run the payload, compare secure behaviour, then review the CICS/Db2/SMF evidence generated by the simulator.</p>
    <div id='labStatus' class='notice'>{status_msg}</div>
    <div class='form-row'>
      <label>Payload<select id='labPayload'>{payload_options}</select></label>
      <label>Editable payload<input id='labPayloadText' value='{escape(str(payload_default or ""), quote=True)}'></label>
      {_action_form(lab, 'run', 'Run vulnerable', 'button', str(payload_default or ''), trace_id)}
    </div>
    <div class='quick'>
      {_action_form(lab, 'secure-compare', 'Run secure comparison', 'button secondary', str(payload_default or ''), trace_id)}
      {_action_form(lab, 'reset', 'Reset lab', 'button ghost', '', trace_id)}
      <button class='button secondary' id='copyCurlButton' type='button'>Copy curl</button>
      <a class='button secondary' id='exportEvidenceLink' href='/labs/{escape(lab.slug)}/export?trace_id={escape(trace_id, quote=True)}'>Export evidence</a>
      <button class='button secondary' id='exportEvidenceButton' type='button'>Export evidence to panel</button>
    </div>
    <pre id='curlBox' class='sql-trace'>curl -X POST http://127.0.0.1:9080/webapi/labs/{escape(lab.slug)}/run -d payload=...</pre>
  </section>

  <section class='lab-two-col'>
    <div class='panel'><h2>Request / response</h2><pre id='labRequestResponse' class='sql-trace'>{rr_text}</pre></div>
    <div class='panel'><h2>CICS / Db2 / backend evidence</h2><table class='backend-table'>{backend_rows}</table><h3>Evidence targets</h3><ul>{evidence}</ul><div id='labEvidenceDynamic'>{dynamic_evidence}</div></div>
  </section>

  <section class='panel'><h2>Live mainframe timeline</h2><ol id='labTimeline' class='timeline'>{timeline}</ol></section>

  <section class='lab-two-col'>
    <div class='panel'><h2>Progressive hints</h2><button class='button secondary' id='showNextHint' type='button'>Show next hint</button><ol id='hintList'>{hints}</ol></div>
    <div class='panel'><h2>Hidden solution</h2><details class='solution-panel'><summary>Show solution</summary><table>{solution_rows}</table><h3>Remediation</h3><ul>{remediation}</ul></details></div>
  </section>

  {render_cobol_bo_annotation() if lab.slug == 'cobol-buffer-overflow' else ''}
  <section class='lab-two-col'><div class='panel'><h2>Beginner glossary</h2><table class='backend-table'>{glossary}</table></div><div class='panel'><h2>Instructor notes</h2><ul>{instructor_notes}</ul></div></section><section class='panel'><h2>Knowledge check</h2>{questions}</section>
</article>
"""
