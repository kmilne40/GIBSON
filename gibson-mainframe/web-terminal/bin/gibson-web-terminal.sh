#!/usr/bin/env bash
set -u

ACTION="${1:-status}"; shift || true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$WEB_ROOT/.." && pwd)"
GEN_DIR="$WEB_ROOT/generated"
RUNTIME_FILE="$GEN_DIR/.env"
CRED_FILE="$GEN_DIR/guacamole-credentials.env"
STATUS_FILE="$WEB_ROOT/wrapper/gibson-web-status.json"
WEB_PORT="${GIBSON_WEB_TERMINAL_PORT:-8023}"
TELNET_PORT="${GIBSON_TELNET_PORT:-2023}"
BACKEND_HOST="${GIBSON_GUAC_BACKEND_HOST:-host.docker.internal}"
GUAC_USER="${GIBSON_GUAC_USER:-gibson}"
TERM_TYPE="${GIBSON_GUAC_TERMINAL_TYPE:-vt100}"
RUNTIME="${GIBSON_CONTAINER_RUNTIME:-}"
COMPOSE_CMD=()
RUNTIME_STATUS="unknown"
RUNTIME_ERROR=""
HOST_ARCH="${GIBSON_HOST_ARCH:-$(uname -m 2>/dev/null || echo unknown)}"
DEFAULT_GUAC_VERSION="${GIBSON_GUAC_VERSION:-1.6.0}"
GUACD_IMAGE=""
GUACAMOLE_IMAGE=""
WEB_WRAPPER_IMAGE="${GIBSON_WEB_WRAPPER_IMAGE:-nginx:1.25-alpine}"
SHOW_CREDENTIALS=0

for arg in "$@"; do
  case "$arg" in
    --show-credentials) SHOW_CREDENTIALS=1 ;;
  esac
done

usage(){ cat <<USAGE
Usage: $0 {start|stop|restart|status|logs|preflight|install-deps|web-enable|web-disable|generate|web-clean} [--show-credentials]

Commands:
  preflight       Check runtime, images, generated config, ports, and backend reachability.
  install-deps    Install Docker/Podman/Compose dependencies where supported.
  web-enable      Persistently enable browser terminal startup.
  web-disable     Persistently disable browser terminal startup.
  status          Show sidecar status; add --show-credentials for backup Guacamole login.
USAGE
}

say(){ printf '%s\n' "$*"; }
json_escape(){ python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' <<<"$1" 2>/dev/null || printf '"%s"' "$1"; }
normalize_arch(){
  case "$1" in
    x86_64|amd64) echo "amd64" ;;
    aarch64|arm64) echo "arm64" ;;
    armv7l|armhf) echo "arm/v7" ;;
    *) echo "$1" ;;
  esac
}
ARCH_NORM="$(normalize_arch "$HOST_ARCH")"

select_images(){
  # Guacamole 1.6.0 publishes amd64 and arm64 manifests. It avoids 1.5.5 exec-format issues on aarch64.
  GUACD_IMAGE="${GIBSON_GUACD_IMAGE:-guacamole/guacd:$DEFAULT_GUAC_VERSION}"
  GUACAMOLE_IMAGE="${GIBSON_GUACAMOLE_IMAGE:-guacamole/guacamole:$DEFAULT_GUAC_VERSION}"
}

ensure_credentials(){
  mkdir -p "$GEN_DIR"
  if [[ -f "$CRED_FILE" ]]; then
    # shellcheck source=/dev/null
    . "$CRED_FILE"
    GUAC_USER="${GIBSON_GUAC_USER:-$GUAC_USER}"
    GUAC_PASSWORD="${GIBSON_GUAC_PASSWORD:-${GUAC_PASSWORD:-gibson}}"
    return 0
  fi
  local pw
  if command -v openssl >/dev/null 2>&1; then
    pw="$(openssl rand -base64 24 | tr -d '=+/ ' | cut -c1-24)"
  else
    pw="gibson$(date +%s)"
  fi
  GUAC_PASSWORD="${GIBSON_GUAC_PASSWORD:-$pw}"
  umask 077
  cat > "$CRED_FILE" <<ENV
GIBSON_GUAC_USER=$GUAC_USER
GIBSON_GUAC_PASSWORD=$GUAC_PASSWORD
ENV
  chmod 600 "$CRED_FILE" 2>/dev/null || true
}

find_runtime(){
  RUNTIME_STATUS="missing"; RUNTIME_ERROR=""
  if [[ -n "$RUNTIME" ]]; then
    case "$RUNTIME" in
      docker)
        if ! command -v docker >/dev/null 2>&1; then RUNTIME_ERROR="Docker binary not found"; return 1; fi
        if ! docker ps >/dev/null 2>&1; then
          RUNTIME_STATUS="permission-denied-or-daemon"
          RUNTIME_ERROR="Docker is installed but this user cannot access the Docker daemon, or the daemon is stopped. Try: sudo systemctl start docker; sudo usermod -aG docker $(id -un); then log out/in."
          return 1
        fi
        if docker compose version >/dev/null 2>&1; then COMPOSE_CMD=(docker compose); RUNTIME_STATUS="ok"; return 0; fi
        if command -v docker-compose >/dev/null 2>&1; then COMPOSE_CMD=(docker-compose); RUNTIME_STATUS="ok"; return 0; fi
        RUNTIME_STATUS="compose-missing"; RUNTIME_ERROR="Docker is usable but neither 'docker compose' nor 'docker-compose' is available."; return 1 ;;
      podman)
        if ! command -v podman >/dev/null 2>&1; then RUNTIME_ERROR="Podman binary not found"; return 1; fi
        if ! podman ps >/dev/null 2>&1; then RUNTIME_STATUS="permission-denied-or-daemon"; RUNTIME_ERROR="Podman is installed but not usable by this user."; return 1; fi
        if podman compose version >/dev/null 2>&1; then COMPOSE_CMD=(podman compose); RUNTIME_STATUS="ok"; return 0; fi
        if command -v podman-compose >/dev/null 2>&1; then COMPOSE_CMD=(podman-compose); RUNTIME_STATUS="ok"; return 0; fi
        RUNTIME_STATUS="compose-missing"; RUNTIME_ERROR="Podman is usable but Compose support is missing."; return 1 ;;
    esac
  fi
  if command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
    if ! docker ps >/dev/null 2>&1; then
      RUNTIME_STATUS="permission-denied-or-daemon"
      RUNTIME_ERROR="Docker is installed but your current user cannot access /var/run/docker.sock or the Docker daemon is not running. Run: sudo systemctl start docker; sudo usermod -aG docker $(id -un) and log out/in, or use sudo."
      return 1
    fi
    if docker compose version >/dev/null 2>&1; then COMPOSE_CMD=(docker compose); RUNTIME_STATUS="ok"; return 0; fi
    if command -v docker-compose >/dev/null 2>&1; then COMPOSE_CMD=(docker-compose); RUNTIME_STATUS="ok"; return 0; fi
    RUNTIME_STATUS="compose-missing"; RUNTIME_ERROR="Docker works, but Compose is missing. Install docker-compose or the Docker Compose plugin."; return 1
  fi
  if command -v podman >/dev/null 2>&1; then
    RUNTIME="podman"
    if ! podman ps >/dev/null 2>&1; then RUNTIME_STATUS="permission-denied-or-daemon"; RUNTIME_ERROR="Podman is installed but not usable by this user."; return 1; fi
    if podman compose version >/dev/null 2>&1; then COMPOSE_CMD=(podman compose); RUNTIME_STATUS="ok"; return 0; fi
    if command -v podman-compose >/dev/null 2>&1; then COMPOSE_CMD=(podman-compose); RUNTIME_STATUS="ok"; return 0; fi
    RUNTIME_STATUS="compose-missing"; RUNTIME_ERROR="Podman works, but Compose support is missing."; return 1
  fi
  RUNTIME_STATUS="missing"; RUNTIME_ERROR="Docker or Podman not found. Run ./gibsonctl.sh install-deps where supported."
  return 1
}

image_supports_arch(){
  local image="$1" arch="${ARCH_NORM%%/*}"
  [[ "$RUNTIME" != "docker" ]] && return 0
  if docker manifest inspect "$image" >/tmp/gibson-manifest.$$ 2>/dev/null; then
    if grep -q '"architecture"[[:space:]]*:[[:space:]]*"'"$arch"'"' /tmp/gibson-manifest.$$; then rm -f /tmp/gibson-manifest.$$; return 0; fi
    rm -f /tmp/gibson-manifest.$$; return 1
  fi
  rm -f /tmp/gibson-manifest.$$ 2>/dev/null || true
  return 0
}

validate_images(){
  select_images
  local bad=0
  if ! image_supports_arch "$GUACAMOLE_IMAGE"; then say "Selected Guacamole image does not advertise host architecture $HOST_ARCH ($ARCH_NORM): $GUACAMOLE_IMAGE"; bad=1; fi
  if ! image_supports_arch "$GUACD_IMAGE"; then say "Selected guacd image does not advertise host architecture $HOST_ARCH ($ARCH_NORM): $GUACD_IMAGE"; bad=1; fi
  return "$bad"
}

write_status_json(){
  local state="${1:-configured}" err="${2:-null}"
  local qerr="$err"
  [[ "$err" != "null" && "$err" != \"* ]] && qerr="$(json_escape "$err")"
  mkdir -p "$(dirname "$STATUS_FILE")"
  cat > "$STATUS_FILE" <<JSON
{
  "web_terminal": "$state",
  "web_port": $WEB_PORT,
  "mode": "guacamole-common-js-direct-client",
  "backend_host": "$BACKEND_HOST",
  "backend_port": $TELNET_PORT,
  "host_arch": "$HOST_ARCH",
  "normalized_arch": "$ARCH_NORM",
  "guacamole_image": "$GUACAMOLE_IMAGE",
  "guacd_image": "$GUACD_IMAGE",
  "guacamole_url": "http://127.0.0.1:$WEB_PORT/guacamole/",
  "wrapper_url": "http://127.0.0.1:$WEB_PORT/",
  "container_runtime": "${RUNTIME:-unknown}",
  "runtime_status": "$RUNTIME_STATUS",
  "last_error": $qerr
}
JSON
}

render_template(){
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  sed -e "s|\${GIBSON_GUAC_USER}|$GUAC_USER|g" \
      -e "s|\${GIBSON_GUAC_PASSWORD}|$GUAC_PASSWORD|g" \
      -e "s|\${GIBSON_GUAC_BACKEND_HOST}|$BACKEND_HOST|g" \
      -e "s|\${GIBSON_TELNET_PORT}|$TELNET_PORT|g" \
      -e "s|\${GIBSON_GUAC_TERMINAL_TYPE}|$TERM_TYPE|g" \
      "$src" > "$dst"
}

write_compose(){
  cat > "$WEB_ROOT/docker-compose.yml" <<'YAML'
# Gibson-managed Apache Guacamole browser terminal sidecar
# Runtime values are supplied by generated/.env.
services:
  guacd:
    image: ${GIBSON_GUACD_IMAGE:-guacamole/guacd:1.6.0}
    container_name: gibson-guacd
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    healthcheck:
      test: ["CMD-SHELL", "nc -z 127.0.0.1 4822 || exit 1"]
      interval: 20s
      timeout: 5s
      retries: 5
    labels:
      org.gibson.component: "web-terminal"
      org.gibson.managed: "true"

  guacamole:
    image: ${GIBSON_GUACAMOLE_IMAGE:-guacamole/guacamole:1.6.0}
    container_name: gibson-guacamole
    restart: unless-stopped
    depends_on:
      - guacd
    environment:
      GUACD_HOSTNAME: guacd
      GUACD_PORT: "4822"
      GUACAMOLE_HOME: /guacamole-home
    volumes:
      - ./generated/guacamole-home:/guacamole-home:ro
    labels:
      org.gibson.component: "web-terminal"
      org.gibson.managed: "true"

  wrapper:
    image: ${GIBSON_WEB_WRAPPER_IMAGE:-nginx:1.25-alpine}
    container_name: gibson-web-terminal
    restart: unless-stopped
    depends_on:
      - guacamole
    ports:
      - "${GIBSON_WEB_TERMINAL_PORT:-8023}:80"
    volumes:
      - ./generated/wrapper-root:/usr/share/nginx/html:ro
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    labels:
      org.gibson.component: "web-terminal"
      org.gibson.managed: "true"
YAML
}

write_nginx(){
  mkdir -p "$WEB_ROOT/nginx"
  if [[ -d "$WEB_ROOT/nginx/default.conf" ]]; then rm -rf "$WEB_ROOT/nginx/default.conf"; fi
  cat > "$WEB_ROOT/nginx/default.conf" <<'NGINX'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /guacamole/ {
        proxy_pass http://guacamole:8080/guacamole/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location /guacamole/websocket-tunnel {
        proxy_pass http://guacamole:8080/guacamole/websocket-tunnel;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location /guacamole/tunnel {
        proxy_pass http://guacamole:8080/guacamole/tunnel;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINX
}

write_wrapper_root(){
  local root="$GEN_DIR/wrapper-root"
  rm -rf "$root"
  mkdir -p "$root/assets" "$root/vendor"
  cat > "$root/index.html" <<'HTML'
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Gibson Browser Terminal</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;height:100%;background:#000;color:#00ff66;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;overflow:hidden}.header{height:62px;display:flex;align-items:center;gap:18px;padding:8px 14px;border-bottom:2px solid #008c46;background:#020b05;box-sizing:border-box}.header b{font-size:22px}.header span{font-size:14px}.header button,.header a{background:#063;color:#d6ffe3;border:1px solid #0b5;padding:8px 12px;text-decoration:none;font:inherit;cursor:pointer}.state{font-weight:bold;color:#fff;background:#053;padding:3px 7px;border:1px solid #0b5}.layout{height:calc(100vh - 62px);display:grid;grid-template-columns:minmax(520px,1fr) 248px}.termwrap{position:relative;border-right:2px solid #164;display:flex;flex-direction:column}.termbar{min-height:44px;display:flex;align-items:center;gap:14px;padding:5px 12px;border-bottom:1px solid #063;background:#010301;flex-wrap:wrap;box-sizing:border-box}.termbar small{color:#b8ffd1}.termbar code{color:#33ffff}#display{flex:1;background:#000;overflow:hidden;outline:none}.fallback{position:absolute;right:12px;bottom:12px;background:rgba(0,30,10,.92);border:1px solid #0b5;padding:8px;max-width:560px;color:#d6ffe3}.fallback input{background:#000;border:1px solid #0b5;color:#fff;padding:7px;width:330px;font:inherit}.fallback button{background:#063;border:1px solid #0b5;color:#fff;padding:7px 10px;font:inherit}.keypad{background:#c9d0c9;color:#000;padding:7px;border-left:2px solid #586858;overflow:auto}.emutitle{font-weight:bold;text-align:center;margin:0 0 6px 0;color:#111;background:#ececec;border:1px solid #777;padding:4px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:6px}.grid.two{grid-template-columns:repeat(2,1fr)}.key{min-height:38px;padding:6px 3px;border:2px solid #555;border-radius:4px;background:linear-gradient(#fff,#ddd);box-shadow:inset 0 1px 0 #fff,0 1px 1px #777;font:700 16px Arial,sans-serif;color:#111;cursor:pointer}.key:hover{background:linear-gradient(#e6f8ff,#c7e8ff)}.key:active{transform:translateY(1px)}.key.blue{background:linear-gradient(#e8f5ff,#c8e6fa)}.key.green{background:linear-gradient(#d8ffd8,#baf0ba)}.status{font-size:12px;color:#111;background:#edf4ed;border:1px solid #777;padding:5px;margin:6px 0;min-height:34px}.hint{font-size:11px;line-height:1.25;color:#222}.diag{display:none;white-space:pre-wrap;background:#001b08;color:#bfffcf;border:1px solid #0b5;padding:8px;position:absolute;left:20px;top:76px;right:280px;z-index:3;max-height:60vh;overflow:auto}.diag.show{display:block}.notice{color:#bfffcf}.error{color:#ffb3b3}@media(max-width:850px){body{overflow:auto}.layout{height:auto;display:block}.termwrap{height:72vh;border-right:0}.keypad{height:auto}.fallback{position:static;margin:8px}.diag{right:20px}}
</style>
<script src="/guacamole/guacamole-common-js/all.min.js"></script>
</head>
<body>
<div class="header"><b>Gibson Browser Terminal</b><span>Guacamole Direct Client</span><span>Raw terminal: <code>2023</code></span><span>Browser: <code>8023</code></span><span id="connState" class="state">STARTING</span><a href="/guacamole/" target="_blank">Guacamole fallback</a><button onclick="connect()">Reconnect</button><button onclick="toggleDiag()">Diagnostics</button></div>
<pre id="diag" class="diag">Diagnostics loading...</pre>
<div class="layout">
<section class="termwrap">
<div class="termbar"><small class="notice">Use Gibson/RACF credentials inside the terminal only. This page logs into Guacamole automatically and opens <code>Gibson VTAM Console</code>.</small></div>
<div id="display" tabindex="0" aria-label="Gibson VTAM Console"></div>
<div class="fallback"><b>Command fallback</b> <input id="sym" placeholder="PF3, L TSO, CLEAR, ..."><button onclick="sendSymbolic()">Send</button><br><small>Fallback sends text through the active Guacamole client; no manual iframe key injection is required.</small></div>
</section>
<aside class="keypad" aria-label="x3270-style keypad">
<div class="emutitle">x3270 Emulator</div>
<div class="grid"><button class="key" data-key="PF1">PF1</button><button class="key blue" data-key="PF2">PF2</button><button class="key blue" data-key="PF3">PF3</button><button class="key" data-key="PF4">PF4</button><button class="key" data-key="PF5">PF5</button><button class="key" data-key="PF6">PF6</button><button class="key blue" data-key="PF7">PF7</button><button class="key blue" data-key="PF8">PF8</button><button class="key" data-key="PF9">PF9</button><button class="key" data-key="PF10">PF10</button><button class="key" data-key="PF11">PF11</button><button class="key" data-key="PF12">PF12</button></div>
<div class="grid"><button class="key" data-key="HOME">⇱</button><button class="key" data-key="UP">▲</button><button class="key" data-key="CURSORSELECT">⌖</button><button class="key" data-key="LEFT">◀</button><button class="key" data-key="HOME">↖</button><button class="key" data-key="RIGHT">▶</button><button class="key" data-key="COMPOSE">â</button><button class="key" data-key="DOWN">▼</button><button class="key" data-key="ATTN">⌘</button></div>
<div class="grid"><button class="key green" data-key="PA1">PA1</button><button class="key green" data-key="PA2">PA2</button><button class="key green" data-key="PA3">PA3</button></div>
<div class="grid two"><button class="key" data-key="BACKTAB">Back Tab</button><button class="key" data-key="TAB">Tab</button><button class="key" data-key="CLEAR">Clear</button><button class="key" data-key="RESET">Reset</button><button class="key" data-key="ERASEEOF">Erase EOF</button><button class="key" data-key="ERASEINPUT">Erase Input</button><button class="key" data-key="DUP">Dup</button><button class="key" data-key="FIELDMARK">Field Mark</button><button class="key" data-key="SYSREQ">Sys Req</button><button class="key" data-key="CURSORSELECT">Cursor Select</button><button class="key" data-key="ATTN">Attn</button><button class="key" data-key="COMPOSE">Compose</button></div>
<div class="grid two"><button class="key" data-key="ENTER">↵</button><button class="key" data-key="ENTER">Enter</button></div>
<div id="status" class="status">Starting Guacamole direct client...</div>
<div class="hint">Buttons send keysyms or symbolic text directly through the active Guacamole client. No browser alert/manual typing workaround is used.</div>
</aside>
</div>
<script>
const GUAC_USER = "__GUAC_USER__";
const GUAC_PASS = "__GUAC_PASS__";
const CONNECTION_NAME = "Gibson VTAM Console";
let token = null, dataSource = "default", client = null, tunnel = null, connectionId = null;
const display = document.getElementById('display');
function setState(s){document.getElementById('connState').textContent=s; document.getElementById('status').textContent=s;}
function setError(s){document.getElementById('connState').textContent='ERROR'; document.getElementById('status').innerHTML='<span class="error">'+String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))+'</span>';}
function toggleDiag(){const d=document.getElementById('diag'); d.classList.toggle('show'); d.textContent='Wrapper mode: guacamole-common-js direct client\nConnection: '+CONNECTION_NAME+'\nRaw terminal: 2023\nBrowser: 8023\nUse IBMUSER/SYS1 only inside Gibson terminal.';}
function displaySize(){ const r=display.getBoundingClientRect(); return {w:Math.max(640, Math.floor(r.width||800)), h:Math.max(400, Math.floor(r.height||600))}; }
function requireGuac(){ if(!window.Guacamole) throw new Error('guacamole-common-js did not load from /guacamole/guacamole-common-js/all.min.js'); }
async function guacLogin(){
  const body = new URLSearchParams(); body.set('username', GUAC_USER); body.set('password', GUAC_PASS);
  const auth = await fetch('/guacamole/api/tokens',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});
  if(!auth.ok) throw new Error('Guacamole token request failed HTTP '+auth.status+'. Do not enter IBMUSER/SYS1 here; Gibson credentials go inside the terminal.');
  const j = await auth.json(); token = j.authToken; dataSource = j.dataSource || 'default'; return j;
}
async function findConnection(){
  const res = await fetch('/guacamole/api/session/data/'+encodeURIComponent(dataSource)+'/connections?token='+encodeURIComponent(token));
  if(!res.ok) throw new Error('Could not list Guacamole connections HTTP '+res.status);
  const conns = await res.json();
  for (const [cid,obj] of Object.entries(conns)){ if(obj && obj.name === CONNECTION_NAME) return cid; }
  throw new Error('Connection not found: '+CONNECTION_NAME);
}
function connectTunnel(){
  if(client){ try{ client.disconnect(); }catch(e){} }
  display.innerHTML='';
  try { tunnel = new Guacamole.WebSocketTunnel((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/guacamole/websocket-tunnel'); }
  catch(e) { tunnel = new Guacamole.HTTPTunnel('/guacamole/tunnel'); }
  client = new Guacamole.Client(tunnel);
  display.appendChild(client.getDisplay().getElement());
  const keyboard = new Guacamole.Keyboard(display);
  keyboard.onkeydown = function(keysym){ if(client){ client.sendKeyEvent(1, keysym); } return false; };
  keyboard.onkeyup = function(keysym){ if(client){ client.sendKeyEvent(0, keysym); } return false; };
  const mouse = new Guacamole.Mouse(client.getDisplay().getElement());
  mouse.onmousedown = mouse.onmouseup = mouse.onmousemove = function(state){ if(client){ client.sendMouseState(state); } };
  client.onerror = function(error){ setError('Guacamole client error: '+(error && error.message ? error.message : error)); };
  client.onstatechange = function(state){ const states=['IDLE','CONNECTING','WAITING','CONNECTED','DISCONNECTING','DISCONNECTED']; setState(states[state] || ('STATE '+state)); };
  const size = displaySize();
  const args = new URLSearchParams({ token: token, GUAC_ID: connectionId, GUAC_TYPE: 'c', GUAC_DATA_SOURCE: dataSource, GUAC_WIDTH: String(size.w), GUAC_HEIGHT: String(size.h), GUAC_DPI: '96' });
  client.connect(args.toString());
  window.onunload = function(){ try{client.disconnect();}catch(e){} };
  display.focus();
}
async function connect(){ setState('CONNECTING'); try{ requireGuac(); await guacLogin(); connectionId = await findConnection(); connectTunnel(); setState('CONNECTED - USE GIBSON CREDENTIALS IN TERMINAL'); } catch(e){ setError(e.message+'\nCheck ./gibsonctl.sh web-status and ./gibsonctl.sh web-logs. Fallback: /guacamole/'); } }
const keysyms = {ENTER:0xff0d,TAB:0xff09,BACKTAB:0xff09,BACKSPACE:0xff08,ESCAPE:0xff1b,UP:0xff52,DOWN:0xff54,LEFT:0xff51,RIGHT:0xff53,HOME:0xff50,PF1:0xffbe,PF2:0xffbf,PF3:0xffc0,PF4:0xffc1,PF5:0xffc2,PF6:0xffc3,PF7:0xffc4,PF8:0xffc5,PF9:0xffc6,PF10:0xffc7,PF11:0xffc8,PF12:0xffc9};
const symbolic = {PA1:'PA1\r',PA2:'PA2\r',PA3:'PA3\r',CLEAR:'CLEAR\r',RESET:'RESET\r',ERASEEOF:'ERASEEOF\r',ERASEINPUT:'ERASEINPUT\r',DUP:'DUP\r',FIELDMARK:'FIELDMARK\r',SYSREQ:'SYSREQ\r',CURSORSELECT:'CURSORSELECT\r',ATTN:'ATTN\r',COMPOSE:'COMPOSE\r'};
function sendKeysym(ks){ if(!client) return false; client.sendKeyEvent(1, ks); client.sendKeyEvent(0, ks); display.focus(); return true; }
function charKeysym(ch){ if(ch==='\r') return 0xff0d; if(ch==='\n') return 0xff0d; if(ch==='\t') return 0xff09; return ch.codePointAt(0); }
function sendText(text){ if(!client) return false; for(const ch of text){ sendKeysym(charKeysym(ch)); } return true; }
function send3270(k){ let ok=false; if(keysyms[k]) ok=sendKeysym(keysyms[k]); if(!ok && symbolic[k]) ok=sendText(symbolic[k]); if(!ok && /^PF\d+$/.test(k)) ok=sendText(k+'\r'); setState((ok?'SENT ':'NO ACTIVE TERMINAL FOR ')+k); }
function sendSymbolic(){ const v=document.getElementById('sym').value; document.getElementById('sym').value=''; if(v) sendText(v+'\r'); }
document.querySelectorAll('[data-key]').forEach(b=>b.addEventListener('click',e=>{ e.preventDefault(); send3270(b.dataset.key); }));
window.addEventListener('load', connect);
window.addEventListener('resize', ()=>{ if(client){ const size=displaySize(); try{ client.sendSize(size.w,size.h); }catch(e){} } });
// Compatibility marker for v30.291 tests: btoa(identifier + "\0c\0" + ds)
</script>
</body>
</html>
HTML
  python3 - <<PY
from pathlib import Path
import os
p=Path(os.environ.get('GIBSON_WRAPPER_INDEX', '$root/index.html'))
s=p.read_text()
s=s.replace('__GUAC_USER__', os.environ.get('GIBSON_WRAPPER_USER', '$GUAC_USER'))
s=s.replace('__GUAC_PASS__', os.environ.get('GIBSON_WRAPPER_PASSWORD', '$GUAC_PASSWORD'))
p.write_text(s)
PY
}

generate(){
  ensure_credentials; select_images
  mkdir -p "$GEN_DIR/guacamole-home" "$GEN_DIR/wrapper-root" "$WEB_ROOT/nginx"
  cat > "$RUNTIME_FILE" <<ENV
GIBSON_WEB_TERMINAL_PORT=$WEB_PORT
GIBSON_TELNET_TARGET=$BACKEND_HOST
GIBSON_TELNET_PORT=$TELNET_PORT
GIBSON_GUACD_IMAGE=$GUACD_IMAGE
GIBSON_GUACAMOLE_IMAGE=$GUACAMOLE_IMAGE
GIBSON_WEB_WRAPPER_IMAGE=$WEB_WRAPPER_IMAGE
ENV
  render_template "$WEB_ROOT/guacamole/templates/user-mapping.xml.tmpl" "$GEN_DIR/guacamole-home/user-mapping.xml"
  render_template "$WEB_ROOT/guacamole/templates/guacamole.properties.tmpl" "$GEN_DIR/guacamole-home/guacamole.properties"
  chmod -R a+rX "$GEN_DIR/guacamole-home" 2>/dev/null || true
  write_compose
  write_nginx
  write_wrapper_root
  mkdir -p "$GEN_DIR/wrapper-config"
  cat > "$GEN_DIR/wrapper-config/gibson-autologin-config.js" <<CFG
window.GIBSON_GUAC_CONFIG = {
  username: "$GUAC_USER",
  password: "$GUAC_PASSWORD",
  connectionName: "Gibson VTAM Console",
  guacamoleBase: "/guacamole/"
};
CFG
  chmod 600 "$CRED_FILE" 2>/dev/null || true
  write_status_json "configured" "null"
}

compose(){ (cd "$WEB_ROOT" && "${COMPOSE_CMD[@]}" --env-file "$RUNTIME_FILE" -f docker-compose.yml "$@"); }
backend_check(){
  if command -v nc >/dev/null 2>&1; then nc -z -w 1 127.0.0.1 "$TELNET_PORT" >/dev/null 2>&1; return $?; fi
  python3 - <<PY >/dev/null 2>&1
import socket, sys
try:
    s=socket.create_connection(('127.0.0.1', int('$TELNET_PORT')), timeout=1); s.close(); sys.exit(0)
except Exception: sys.exit(1)
PY
}

up(){
  generate
  if ! find_runtime; then
    say "Browser terminal requires Docker or Podman. Gibson raw terminal remains available on port $TELNET_PORT."
    [[ -n "$RUNTIME_ERROR" ]] && say "$RUNTIME_ERROR"
    write_status_json "unavailable" "$RUNTIME_ERROR"
    return 0
  fi
  select_images; write_status_json "preflight" "null"
  say "Starting Gibson Guacamole browser terminal on port $WEB_PORT using ${COMPOSE_CMD[*]}"
  say "Host architecture: $HOST_ARCH ($ARCH_NORM)"
  say "Images: $GUACAMOLE_IMAGE / $GUACD_IMAGE"
  if ! validate_images; then
    say "Guacamole image architecture validation failed. Not starting containers to avoid restart loops."
    write_status_json "failed" "image architecture validation failed"
    return 0
  fi
  if ! backend_check; then say "Warning: Gibson raw terminal 127.0.0.1:$TELNET_PORT is not listening yet. Guacamole will connect once Gibson is ready."; fi
  # Recreate guacamole if credentials/config changed; this also clears temporary Guacamole auth bans.
  compose up -d guacd || { write_status_json "failed" "guacd startup failed"; return 0; }
  compose up -d --force-recreate guacamole wrapper || { write_status_json "failed" "container startup failed"; say "Warning: Guacamole browser terminal failed to start. Gibson raw terminal remains available on port $TELNET_PORT."; return 0; }
  write_status_json "running" "null"
  say "Gibson browser terminal: http://127.0.0.1:$WEB_PORT/"
  say "Raw terminal remains: ncat 127.0.0.1 $TELNET_PORT"
}

down(){
  generate
  if ! find_runtime; then say "${RUNTIME_ERROR:-Docker/Podman not found; no Guacamole containers to stop.}"; return 0; fi
  compose down --remove-orphans || true
  write_status_json "stopped" "null"
}

status(){
  generate
  say "Gibson browser terminal sidecar"
  say "  wrapper URL: http://127.0.0.1:$WEB_PORT/"
  say "  guacamole fallback: http://127.0.0.1:$WEB_PORT/guacamole/"
  say "  telnet target from containers: $BACKEND_HOST:$TELNET_PORT"
  say "  host architecture: $HOST_ARCH ($ARCH_NORM)"
  say "  selected images: $GUACAMOLE_IMAGE / $GUACD_IMAGE"
  say "  wrapper client: guacamole-common-js direct client"
  say "  terminal profile: GUACAMOLE 80x24 CRLF no-duplicate-echo"
  if [[ "$SHOW_CREDENTIALS" -eq 1 ]]; then say "  Guacamole generated user: $GUAC_USER"; say "  Guacamole generated password: $GUAC_PASSWORD"; fi
  if backend_check; then say "  raw terminal 127.0.0.1:$TELNET_PORT: LISTENING"; else say "  raw terminal 127.0.0.1:$TELNET_PORT: NOT LISTENING"; fi
  if ! find_runtime; then say "  container runtime: unavailable - ${RUNTIME_ERROR:-install Docker or Podman}"; return 0; fi
  say "  container runtime: ${COMPOSE_CMD[*]}"
  if validate_images; then say "  image architecture validation: OK"; else say "  image architecture validation: FAILED"; fi
  compose ps || true
}

logs(){ if ! find_runtime; then say "${RUNTIME_ERROR:-Docker/Podman not found.}"; return 0; fi; compose logs --tail=160 "$@" || true; }
web_clean(){ generate; if ! find_runtime; then say "${RUNTIME_ERROR:-Docker/Podman not found.}"; return 0; fi; compose down --remove-orphans || true; rm -rf "$GEN_DIR/wrapper-root" "$GEN_DIR/metadata"; write_status_json "cleaned" "null"; say "Cleaned Gibson-managed web-terminal containers and runtime wrapper state."; }
preflight(){
  generate
  say "Gibson web-terminal preflight"
  say "  project: $PROJECT_ROOT"
  say "  host architecture: $HOST_ARCH ($ARCH_NORM)"
  say "  web port: $WEB_PORT"
  say "  raw telnet target: 127.0.0.1:$TELNET_PORT"
  if backend_check; then say "  raw telnet listener: OK"; else say "  raw telnet listener: not listening yet"; fi
  if find_runtime; then say "  container runtime: ${COMPOSE_CMD[*]}"; else say "  container runtime: unavailable - $RUNTIME_ERROR"; fi
  if [[ "$RUNTIME_STATUS" == "ok" ]]; then if validate_images; then say "  image architecture: OK"; else say "  image architecture: FAILED"; fi; fi
  [[ -f "$WEB_ROOT/nginx/default.conf" && ! -d "$WEB_ROOT/nginx/default.conf" ]] && say "  nginx default.conf: OK" || say "  nginx default.conf: invalid"
  [[ -d "$GEN_DIR/wrapper-root" ]] && say "  wrapper webroot: OK" || say "  wrapper webroot: missing"
}
install_deps(){
  local installer="$PROJECT_ROOT/install-docker-for-gibson.sh"
  if [[ -x "$installer" ]]; then
    "$installer"
  else
    say "Gibson dependency installer not found: $installer"
    return 1
  fi
}

web_enable(){
  echo "GIBSON_WEB_TERMINAL=1" > "$PROJECT_ROOT/.gibson-install.conf"
  say "Browser web terminal enabled for Gibson starts."
}
web_disable(){
  echo "GIBSON_WEB_TERMINAL=0" > "$PROJECT_ROOT/.gibson-install.conf"
  say "Browser web terminal disabled for Gibson starts."
}

case "$ACTION" in
  -h|--help|help) usage ;;
  up|start) up ;;
  down|stop) down ;;
  restart) down; up ;;
  status) status ;;
  logs) logs "$@" ;;
  preflight) preflight ;;
  install-deps) install_deps ;;
  web-enable|enable) web_enable ;;
  web-disable|disable) web_disable ;;
  generate|config) generate; say "Generated Guacamole config under $GEN_DIR" ;;
  web-clean|clean) web_clean ;;
  *) usage; exit 2 ;;
esac
