from __future__ import annotations
import html
from typing import Any


def landing() -> str:
    return """<!doctype html><html><head><title>Apache Tomcat/9.0.x</title></head><body>
<h1>Apache Tomcat/9.0.x - Gibson Training Simulator</h1>
<p>If you're seeing this, you've successfully reached the simulated Tomcat web tier.</p>
<ul><li><a href='/manager/html'>Manager App</a></li><li><a href='/docs'>Documentation</a></li><li><a href='/examples'>Examples</a></li></ul>
</body></html>"""


def docs() -> str:
    return """<!doctype html><html><head><title>Apache Tomcat Documentation</title></head><body><h1>Apache Tomcat Documentation</h1><p>Gibson provides a safe Tomcat-like target for Chapter 8 training.</p></body></html>"""


def examples() -> str:
    return """<!doctype html><html><head><title>Apache Tomcat Examples</title></head><body><h1>Servlet and JSP Examples</h1><p>Example applications are present for enumeration realism only.</p></body></html>"""


def manager_html(state: Any, user: str, message: str = "") -> str:
    from .state import get_state
    sim = get_state(state)
    rows = []
    for ctx, dep in sorted(sim.deployments.items()):
        rows.append(f"<tr><td>{html.escape(ctx)}</td><td>{html.escape(dep.status)}</td><td>{html.escape(dep.display_name or dep.filename)}</td><td>{html.escape(str(dep.size))}</td><td>{html.escape(dep.sha256[:16])}</td></tr>")
    msg = f"<p class='msg'>{html.escape(message)}</p>" if message else ""
    return f"""<!doctype html><html><head><title>Apache Tomcat/9.0.x - Manager App</title>
<style>body{{font-family:Arial,sans-serif;background:#fff;color:#111}}h1{{background:#003b66;color:white;padding:10px}}h2{{background:#e5eef8;padding:6px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #999;padding:5px}}.msg{{background:#efe;border:1px solid #090;padding:8px}}.warn{{background:#fff4d6;border:1px solid #d90;padding:8px}}</style></head>
<body><h1>Apache Tomcat/9.0.x - Manager App</h1><p>Logged in as <b>{html.escape(user)}</b></p>{msg}
<div class='warn'>Training note: this is a Gibson safe simulator. WAR files are stored as metadata and are never executed.</div>
<h2>Applications</h2><table><thead><tr><th>Path</th><th>Status</th><th>Display Name</th><th>Size</th><th>SHA-256</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>WAR file to deploy</h2><form method='post' action='/manager/html/upload' enctype='multipart/form-data'>
<label>Context path: <input name='path' value='/shell_exploit'></label><br>
<label>WAR file: <input type='file' name='war'></label><br><button type='submit'>Deploy</button></form>
<h2>Manager</h2><ul><li><a href='/manager/text/list'>Text list</a></li><li><a href='/manager/text/serverinfo'>Server info</a></li><li><a href='/manager/status'>Server status</a></li></ul>
</body></html>"""


def status(state: Any, user: str) -> str:
    from .state import get_state, active_sessions
    sim = get_state(state)
    return f"""<!doctype html><html><head><title>Apache Tomcat Status</title></head><body><h1>Server Status</h1><pre>
Server Version: Apache Tomcat/9.0.x (Gibson safe simulator)
Server Built:   training build
JVM Version:    17.0.x simulated
OS Name:        z/OS UNIX Gibson USS
User Name:      {html.escape(user)}
Connector:      HTTP/1.1 8080
Applications:   {len(sim.deployments)}
Active Sessions:{len(active_sessions(state))}
</pre></body></html>"""
