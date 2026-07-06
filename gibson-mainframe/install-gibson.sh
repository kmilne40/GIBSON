#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
NONINTERACTIVE=0
CHOICE=""
usage() {
  cat <<'USAGE'
Usage: ./install-gibson.sh [--with-web-terminal|--no-web-terminal] [--non-interactive]

Installs/configures Gibson. The optional browser terminal uses Apache Guacamole
on port 8023 and requires Docker or Podman. Raw ncat/telnet on port 2023 does
not require the web terminal.
USAGE
}
while [ $# -gt 0 ]; do
  case "$1" in
    --with-web-terminal) CHOICE="yes" ;;
    --no-web-terminal) CHOICE="no" ;;
    --non-interactive) NONINTERACTIVE=1 ;;
    -h|--help|help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
  shift
done

echo "Gibson Mainframe Simulator v30.288-freeze installer"
echo "Project: $PROJECT_ROOT"
echo
if [ -z "$CHOICE" ]; then
  if [ $NONINTERACTIVE -eq 1 ] || [ ! -t 0 ]; then
    CHOICE="no"
    echo "Non-interactive mode: remote browser web terminal not enabled unless --with-web-terminal is specified."
  else
    cat <<'PROMPT'
Gibson can install an optional browser-based terminal on port 8023 using Apache Guacamole.
This requires Docker or Podman and will download container images.
Raw ncat/telnet access on port 2023 works without this option.
PROMPT
    read -r -p "Install and enable the remote browser web terminal? [Y/n]: " ans || ans=""
    case "${ans:-Y}" in n|N|no|NO) CHOICE="no" ;; *) CHOICE="yes" ;; esac
  fi
fi

case "$CHOICE" in
  no)
    echo "GIBSON_WEB_TERMINAL=0" > .gibson-install.conf
    ./gibsonctl.sh web-disable >/dev/null 2>&1 || true
    echo "Browser web terminal disabled. Raw ncat/telnet on 2023 remains available."
    ;;
  yes)
    echo "GIBSON_WEB_TERMINAL=1" > .gibson-install.conf
    ./gibsonctl.sh web-enable >/dev/null 2>&1 || true
    echo "Installing/checking Docker/Guacamole dependencies..."
    ./install-docker-for-gibson.sh || {
      echo "[!] Web terminal dependencies could not be fully installed. Raw Gibson remains usable on 2023."
      echo "Run ./gibsonctl.sh install-deps later after resolving package-manager/sudo issues."
      exit 0
    }
    ./gibsonctl.sh preflight || true
    ;;
  *) echo "Internal installer choice error: $CHOICE"; exit 2 ;;
esac
cat <<MSG

Install step complete.
Start Gibson with:
  ./gibsonctl.sh start

Show web status with:
  ./gibsonctl.sh web-status
  ./gibsonctl.sh web-status --show-credentials
MSG
