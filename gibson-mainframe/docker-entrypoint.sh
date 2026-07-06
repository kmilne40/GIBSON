#!/usr/bin/env bash
set -euo pipefail

SIM_ROOT="${GIBSON_SIM_ROOT:-/mfsim}"
ASSETS_DIR="/app/gibson/assets"

# Seed simulator root on first start
if [[ ! -f "$SIM_ROOT/GACF.DB" ]]; then
    mkdir -p "$SIM_ROOT/f/commands" "$SIM_ROOT/logs" "$SIM_ROOT/transfers"
    if [[ -d "$ASSETS_DIR" ]]; then
        for f in "$ASSETS_DIR"/*; do
            [[ -f "$f" ]] || continue
            b="$(basename "$f")"
            cp -n "$f" "$SIM_ROOT/$b" 2>/dev/null || true
            cp -n "$f" "$SIM_ROOT/f/commands/$b" 2>/dev/null || true
        done
    fi
fi

# Resolve configured ports (mirror config.py defaults)
TSO_PORT="${GIBSON_PORT:-2023}"
TN3270_PORT="${GIBSON_TN3270_PORT:-3270}"
USS_PORT="${GIBSON_USS_PORT:-2022}"
FTP_PORT="${GIBSON_FTP_PORT:-2111}"
DASH_PORT="${GIBSON_DASHBOARD_PORT:-8443}"
WEBTERM_PORT="${GIBSON_WEB_TERMINAL_PORT:-8023}"
APP_PORT="${GIBSON_CBSA_API_PORT:-8080}"
FIBS_PORT="${GIBSON_FIBS_WEB_PORT:-9080}"
WELCOME_PORT="${GIBSON_WELCOME_PORT:-80}"
DB2_TCP_PORT="${GIBSON_DB2_TCP_PORT:-50000}"
DB2_WS_PORT="${GIBSON_DB2_WS_PORT:-50001}"

W=62  # table width (inner)

line() { printf '+%s+\n' "$(printf '%*s' "$W" '' | tr ' ' '-')"; }
row()  { printf '| %-20s  %-14s  %-21s |\n' "$1" "$2" "$3"; }

echo ""
line
printf '|%s|\n' "$(printf '%*s' $(( (W + 30) / 2 )) 'GIBSON MAINFRAME SIMULATOR' | \
    awk -v w=$W '{printf "%*s%-*s", (w-length($0))/2, "", w-(w-length($0))/2, $0}')"
line
row "SERVICE" "PORT" "URL / CONNECT"
line
row "Welcome Site"        "$WELCOME_PORT/tcp"  "http://localhost:${WELCOME_PORT}"
row "TSO / VTAM"          "$TSO_PORT/tcp"      "telnet localhost ${TSO_PORT}"
row "TN3270 (z/VM)"       "$TN3270_PORT/tcp"   "tn3270 localhost ${TN3270_PORT}"
row "USS Shell"           "$USS_PORT/tcp"      "telnet localhost ${USS_PORT}"
row "FTP"                 "$FTP_PORT/tcp"      "ftp localhost ${FTP_PORT}"
row "CBSA / DVCA API"     "$APP_PORT/tcp"      "http://localhost:${APP_PORT}"
row "FIBS Bank Web"       "$FIBS_PORT/tcp"     "http://localhost:${FIBS_PORT}"
row "Dashboard"           "$DASH_PORT/tcp"     "https://localhost:${DASH_PORT}"
row "Browser Terminal"    "$WEBTERM_PORT/tcp"  "http://localhost:${WEBTERM_PORT}"
row "DB2 DAS"             "$DB2_TCP_PORT/tcp"  "tcp localhost ${DB2_TCP_PORT}"
row "DB2 WebSocket"       "$DB2_WS_PORT/tcp"   "ws://localhost:${DB2_WS_PORT}"
line
echo ""

exec python -m gibson.cli "$@"
