from __future__ import annotations

from html import escape
from .lab_catalog import LabDefinition

_COMPONENT_MAP = {
    "Browser / curl": "BROWSER",
    "FIBS WEB9080": "WEB9080",
    "z/OS Connect-style API provider": "API",
    "Native CICS JSON web service": "CICS",
    "CICS transaction": "CICS",
    "COBOL/service program": "CBSA",
    "Db2 SQL": "SQL",
    "Db2 tables": "DB2",
    "Audit/Event Bus": "AUDIT",
    "SMF": "SMF",
    "Master Console": "CONSOLE",
    "zSecure/SYSVIEW": "CONSOLE",
    "JWT validator": "IDENTITY",
    "OAuth authorization server": "IDENTITY",
    "GACF.DB / WEB_USERS": "IDENTITY",
    "Response filter": "API",
    "API method router": "API",
}


def render_diagram(lab: LabDefinition) -> str:
    nodes = []
    for node in lab.architecture_nodes:
        comp = _COMPONENT_MAP.get(node, node.upper().replace(" ", "_"))
        nodes.append(f"<div class='lab-diagram-node' data-component='{escape(comp)}'><span>{escape(node)}</span></div>")
    edge_rows = "".join(f"<li>{escape(a)} <strong>→</strong> {escape(b)}</li>" for a, b in lab.architecture_edges[:12])
    return f"""
<div class='lab-diagram' data-lab='{escape(lab.slug)}'>
  <div class='lab-diagram-nodes'>{''.join(nodes)}</div>
  <details class='lab-edges'><summary>Show architecture path</summary><ol>{edge_rows}</ol></details>
</div>
"""
