from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_guacamole_sidecar_files_exist():
    for rel in [
        "web-terminal/docker-compose.yml",
        "web-terminal/bin/gibson-web-terminal.sh",
        "web-terminal/wrapper/index.html",
        "web-terminal/wrapper/keypad.js",
        "web-terminal/guacamole/templates/user-mapping.xml.tmpl",
        "web-terminal/guacamole/templates/guacamole.properties.tmpl",
        "web-terminal/guacamole/templates/nginx-default.conf.tmpl",
    ]:
        assert (ROOT / rel).exists(), rel


def test_compose_uses_official_guacamole_images_and_known_ports():
    text = (ROOT / "web-terminal/docker-compose.yml").read_text()
    assert "guacamole/guacd:1.6.0" in text
    assert "guacamole/guacamole:1.6.0" in text
    assert "${GIBSON_WEB_TERMINAL_PORT:-8023}:80" in text
    assert "gibson-guacd" in text
    assert "gibson-guacamole" in text
    assert "gibson-web-terminal" in text
    assert "host.docker.internal:host-gateway" in text


def test_guacamole_config_template_targets_telnet_backend():
    text = (ROOT / "web-terminal/guacamole/templates/user-mapping.xml.tmpl").read_text()
    assert "<protocol>telnet</protocol>" in text
    assert "${GIBSON_GUAC_BACKEND_HOST}" in text
    assert "${GIBSON_TELNET_PORT}" in text
    assert "Gibson VTAM Console" in text


def test_wrapper_contains_full_x3270_keypad():
    html = (ROOT / "web-terminal/wrapper/index.html").read_text()
    required = [
        "PF1","PF2","PF3","PF4","PF5","PF6","PF7","PF8","PF9","PF10","PF11","PF12",
        "PA1","PA2","PA3","CLEAR","RESET","ERASEEOF","ERASEINPUT","DUP","FIELDMARK",
        "SYSREQ","CURSORSELECT","ATTN","COMPOSE","ENTER","TAB","BACKTAB","UP","DOWN","LEFT","RIGHT",
    ]
    for key in required:
        assert f'data-key="{key}"' in html or f"data-key='{key}'" in html, key
    assert "Guacamole.Client" in html
    assert "guacamole-common-js" in html
    assert "<iframe" not in html
    assert "alert(" not in html
    assert "Use Gibson/RACF credentials inside the terminal" in html


def test_keypad_js_maps_core_buttons():
    js = (ROOT / "web-terminal/wrapper/keypad.js").read_text()
    for key in ["PF3", "PF7", "PF8", "PA1", "PA2", "CLEAR", "ENTER", "TAB"]:
        assert key in js
    assert "sendKeyEvent" in js
    assert "sendText" in js
    assert "guacamole-common-js-direct-client" in js


def test_gibsonctl_integrates_guacamole_sidecar_without_cli_web_terminal():
    text = (ROOT / "gibsonctl.sh").read_text()
    assert "WEB_HELPER" in text
    assert "web-status" in text
    assert "web-logs" in text
    assert "preflight" in text
    assert "install-deps" in text
    assert "Guacamole" in text
    # The retired Python browser terminal must not be passed to gibson.cli from gibsonctl.
    assert 'START_ARGS+=("--with-web-terminal"' not in text
    assert "--no-web-terminal" in text
    assert "--web-terminal-port" in text


def test_shell_scripts_parse():
    subprocess.run(["bash", "-n", str(ROOT / "gibsonctl.sh")], check=True)
    subprocess.run(["bash", "-n", str(ROOT / "web-terminal/bin/gibson-web-terminal.sh")], check=True)


def test_no_web_terminal_dry_run_does_not_start_sidecar():
    proc = subprocess.run(
        [str(ROOT / "gibsonctl.sh"), "start", "--dry-run", "--no-web-terminal"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "Starting Gibson" in proc.stdout
    assert "Guacamole browser terminal" not in proc.stdout


def test_web_terminal_helper_generate_creates_config():
    proc = subprocess.run(
        [str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "generate"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    assert proc.returncode == 0
    generated = ROOT / "web-terminal/generated/guacamole-home/user-mapping.xml"
    assert generated.exists()
    data = generated.read_text()
    assert "Gibson VTAM Console" in data
    assert "<protocol>telnet</protocol>" in data
    assert "2023" in data


def test_helper_selects_architecture_aware_images_and_generates_autologin_config():
    proc = subprocess.run(
        [str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "generate"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10,
    )
    assert proc.returncode == 0
    env = (ROOT / "web-terminal/generated/.env").read_text()
    assert "GIBSON_GUACAMOLE_IMAGE=guacamole/guacamole:1.6.0" in env
    assert "GIBSON_GUACD_IMAGE=guacamole/guacd:1.6.0" in env
    cfg = (ROOT / "web-terminal/generated/wrapper-config/gibson-autologin-config.js").read_text()
    assert "GIBSON_GUAC_CONFIG" in cfg
    assert "Gibson VTAM Console" in cfg


def test_preflight_and_install_deps_actions_are_available():
    proc = subprocess.run(
        [str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "preflight"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10,
    )
    assert proc.returncode == 0
    assert "Gibson web-terminal preflight" in proc.stdout
    proc2 = subprocess.run(
        [str(ROOT / "web-terminal/bin/gibson-web-terminal.sh"), "install-deps"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10,
    )
    assert proc2.returncode == 0
    assert "docker.io" in proc2.stdout
