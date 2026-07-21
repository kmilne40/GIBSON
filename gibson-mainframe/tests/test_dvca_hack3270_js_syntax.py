from __future__ import annotations

import re
import subprocess
from gibson.apps.dvca.api import render_page


def test_hack3270_inline_js_parses_with_node_when_available():
    html = render_page(True)
    assert "terminalScreen" in html
    assert "screen.innerHTML" not in html
    script = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    assert "Connection failed." in script
    with open("/tmp/gibson_hack3270_syntax_test.js", "w", encoding="utf-8") as f:
        f.write(script)
    proc = subprocess.run(["node", "--check", "/tmp/gibson_hack3270_syntax_test.js"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
