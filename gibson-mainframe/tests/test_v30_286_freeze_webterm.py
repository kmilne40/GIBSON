from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_generated_wrapper_uses_guacamole_common_js_direct_client():
    subprocess.run([str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "generate"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE)
    html = (ROOT / "web-terminal/generated/wrapper-root/index.html").read_text()
    assert "/guacamole/guacamole-common-js/all.min.js" in html
    assert "new Guacamole.Client" in html
    assert "new Guacamole.WebSocketTunnel" in html or "new Guacamole.HTTPTunnel" in html
    assert "client.sendKeyEvent" in html
    assert "<iframe" not in html
    assert "alert(" not in html


def test_freeze_wrapper_has_required_key_mappings():
    subprocess.run([str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "generate"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE)
    html = (ROOT / "web-terminal/generated/wrapper-root/index.html").read_text()
    for key in ["PF1","PF2","PF3","PF7","PF8","PF12","PA1","PA2","PA3","CLEAR","RESET","ENTER","TAB","BACKTAB","ERASEEOF","ERASEINPUT"]:
        assert f'data-key="{key}"' in html
    for keysym in ["PF3:0xffc0", "PF7:0xffc4", "PF8:0xffc5", "ENTER:0xff0d", "TAB:0xff09"]:
        assert keysym in html.replace(" ", "")
    assert "PA1:'PA1\\r'" in html or 'PA1:"PA1\\r"' in html


def test_freeze_helper_exposes_web_clean_and_status_credentials():
    helper = (ROOT / "web-terminal/bin/gibson-web-terminal.sh").read_text()
    ctl = (ROOT / "gibsonctl.sh").read_text()
    assert "web_clean" in helper
    assert "--show-credentials" in helper
    assert "guacamole-common-js direct client" in helper
    assert "web-clean" in ctl


def test_freeze_compose_single_webroot_mount_only():
    subprocess.run([str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "generate"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE)
    compose = (ROOT / "web-terminal/docker-compose.yml").read_text()
    assert "./generated/wrapper-root:/usr/share/nginx/html:ro" in compose
    assert "wrapper-config:/usr/share/nginx/html" not in compose
    assert "gibson-autologin-config.js:/usr/share/nginx/html" not in compose
    assert not (ROOT / "web-terminal/nginx/default.conf").is_dir()
