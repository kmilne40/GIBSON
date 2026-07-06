from pathlib import Path
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]


def test_final_guacamole_compose_uses_single_wrapper_webroot():
    text = (ROOT / "web-terminal/docker-compose.yml").read_text()
    assert "./generated/wrapper-root:/usr/share/nginx/html:ro" in text
    assert "./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" in text
    assert "wrapper-config" not in text
    assert "/usr/share/nginx/html/generated" not in text
    assert "gibson-autologin-config.js:/usr/share/nginx/html" not in text


def test_final_nginx_config_is_file_and_has_guacamole_tunnels():
    conf = ROOT / "web-terminal/nginx/default.conf"
    assert conf.exists() and conf.is_file()
    text = conf.read_text()
    assert "proxy_pass http://guacamole:8080/guacamole/" in text
    assert "/guacamole/websocket-tunnel" in text
    assert "/guacamole/tunnel" in text
    assert "proxy_buffering off" in text


def test_final_generated_wrapper_is_self_contained_and_autoconnects():
    subprocess.run([str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "generate"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE)
    html = (ROOT / "web-terminal/generated/wrapper-root/index.html").read_text()
    assert "Gibson Browser Terminal" in html
    assert "Use Gibson/RACF credentials inside the terminal" in html
    assert "/guacamole/api/tokens" in html
    assert "Gibson VTAM Console" in html
    assert "btoa(identifier + \"\\0c\\0\" + ds)" in html
    assert "Guacamole fallback" in html


def test_final_user_mapping_plain_credentials_and_telnet_connection():
    subprocess.run([str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "generate"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE)
    xml = (ROOT / "web-terminal/generated/guacamole-home/user-mapping.xml").read_text()
    assert 'encoding="plain"' in xml
    assert '<connection name="Gibson VTAM Console">' in xml
    assert '<protocol>telnet</protocol>' in xml
    assert '<param name="hostname">host.docker.internal</param>' in xml
    assert '<param name="port">2023</param>' in xml


def test_final_web_terminal_helper_reports_specific_docker_failures_and_supports_status_commands():
    script = (ROOT / "web-terminal/bin/gibson-web-terminal.sh").read_text()
    assert "permission-denied-or-daemon" in script
    assert "Docker is installed but your current user cannot access" in script
    assert "Selected Guacamole image does not advertise host architecture" in script
    assert "--show-credentials" in script
    assert "image architecture validation" in script


def test_final_keypad_buttons_present_in_source_wrapper():
    html = (ROOT / "web-terminal/wrapper/index.html").read_text()
    for key in ["PF1","PF2","PF3","PF4","PF5","PF6","PF7","PF8","PF9","PF10","PF11","PF12","PA1","PA2","PA3","CLEAR","RESET","ERASEEOF","ERASEINPUT","DUP","FIELDMARK","SYSREQ","CURSORSELECT","ATTN","COMPOSE","ENTER","TAB","BACKTAB","UP","DOWN","LEFT","RIGHT"]:
        assert f'data-key="{key}"' in html or f"data-key='{key}'" in html
