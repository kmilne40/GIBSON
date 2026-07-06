#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SIM_ROOT="${GIBSON_SIM_ROOT:-$HOME/mfsim}"
SIM_ROOT="$DEFAULT_SIM_ROOT"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MODE="venv"
VENV_DIR="${GIBSON_VENV_DIR:-$ROOT/.venv}"
UPGRADE_PIP=1
INSTALL_DEPS=1

BLUE='\033[1;94m'
GREEN='\033[1;32m'
RED='\033[1;31m'
WHITE='\033[1;37m'
RESET='\033[0m'

say()  { printf '%b\n' "$*"; }
step() { say "${BLUE}==>${RESET} ${WHITE}$*${RESET}"; }
ok()   { say "${GREEN}[OK]${RESET} $*"; }
warn() { say "${RED}[!]${RESET} $*"; }

usage() {
  cat <<USAGE
Usage: ./install_gibson.sh [options]

Options:
  --venv              Install into $ROOT/.venv (default)
  --system            Install into the active/system Python instead of a venv
  --python PATH       Use a specific Python interpreter
  --sim-root PATH     Simulator root to seed (default: $DEFAULT_SIM_ROOT)
  --no-upgrade-pip    Skip pip/setuptools/wheel upgrades
  --skip-deps         Install Gibson without resolving Python dependencies
  -h, --help          Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) MODE="venv" ;;
    --system) MODE="system" ;;
    --python) shift; PYTHON_BIN="$1" ;;
    --sim-root) shift; SIM_ROOT="$1" ;;
    --no-upgrade-pip) UPGRADE_PIP=0 ;;
    --skip-deps) INSTALL_DEPS=0 ;;
    -h|--help) usage; exit 0 ;;
    *) warn "Unknown option: $1"; usage; exit 2 ;;
  esac
  shift
done

show_banner() {
  say "${BLUE}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
  say "${BLUE}║${RESET} ${WHITE}Gibson Complete Dynamic Edition Installer${RESET}                     ${BLUE}║${RESET}"
  say "${BLUE}║${RESET} ${GREEN}z/OS-style training simulator bootstrap${RESET}                         ${BLUE}║${RESET}"
  say "${BLUE}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
}

require_python() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    warn "Python interpreter not found: $PYTHON_BIN"
    exit 1
  fi
  step "Checking Python"
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10 or newer is required")
print(f"Python {sys.version.split()[0]}")
PY
  ok "Python ready"
}


python_minor_version() {
  "$PYTHON_BIN" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
}

venv_works() {
  "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import venv, ensurepip
PY
}

install_venv_package_if_possible() {
  [[ "$MODE" == "venv" ]] || return 0
  venv_works && return 0
  if [[ "$INSTALL_DEPS" == "0" ]]; then
    warn "Python venv support is missing, but --skip-deps/offline mode was requested."
    warn "Install the matching venv package manually before using --venv."
    return 1
  fi
  local pyver pkg_specific pkg_generic runner=""
  pyver="$(python_minor_version)"
  pkg_specific="python${pyver}-venv"
  pkg_generic="python3-venv"
  step "Python venv support is missing; detected Python $pyver"
  if command -v apt-get >/dev/null 2>&1; then
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
      runner=""
    elif command -v sudo >/dev/null 2>&1; then
      runner="sudo"
    else
      warn "Cannot install venv package automatically because sudo/root is unavailable."
      warn "Run: sudo apt-get update && sudo apt-get install -y $pkg_specific"
      warn "If unavailable, run: sudo apt-get install -y $pkg_generic"
      return 1
    fi
    step "Installing $pkg_specific or $pkg_generic using apt-get"
    $runner apt-get update
    if ! $runner apt-get install -y "$pkg_specific"; then
      $runner apt-get install -y "$pkg_generic"
    fi
    venv_works && { ok "Python venv support installed"; return 0; }
    warn "venv still unavailable after package installation."
    return 1
  fi
  if command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1 || command -v zypper >/dev/null 2>&1 || command -v apk >/dev/null 2>&1; then
    warn "Python venv support is missing. Install the Python venv/ensurepip package for this distribution."
    warn "Detected Python $pyver. Common package names include python3-venv, python${pyver}-venv, python3-pip, or py3-virtualenv."
    return 1
  fi
  warn "Python venv support is missing and no supported package manager was detected."
  warn "Install $pkg_specific or $pkg_generic, then rerun ./install_gibson.sh."
  return 1
}

ensure_pip() {
  if "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  step "Bootstrapping pip"
  if ! "$PYTHON_BIN" -m ensurepip --upgrade; then
    warn "pip is not available for $PYTHON_BIN."
    warn "Install python3-venv/python3-pip for your distribution, or rerun with --system using a Python that has pip."
    exit 1
  fi
}

activate_env() {
  if [[ "$MODE" == "venv" ]]; then
    step "Preparing virtual environment"
    install_venv_package_if_possible
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
      if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        warn "Could not create virtual environment at $VENV_DIR."
        pyver="$(python_minor_version 2>/dev/null || echo 3)"
        warn "On Debian/Kali/Ubuntu install the matching venv package, for example: sudo apt install python${pyver}-venv or sudo apt install python3-venv"
        exit 1
      fi
    fi
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    PYTHON_BIN="$VENV_DIR/bin/python"
    ensure_pip
    ok "Using virtual environment: $VENV_DIR"
  else
    warn "Installing into the active/system Python environment"
    ensure_pip
  fi
}

install_python_bits() {
  step "Installing Gibson and Python dependencies"
  if [[ "$UPGRADE_PIP" == "1" ]]; then
    "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
  fi
  local pip_args=()
  if [[ "$INSTALL_DEPS" == "0" ]]; then
    pip_args+=(--no-deps)
  fi
  "$PYTHON_BIN" -m pip install "${pip_args[@]}" -e "$ROOT"
  "$PYTHON_BIN" - <<'PY'
from importlib.metadata import version, PackageNotFoundError
mods = ["flask", "passlib", "psutil", "requests", "websockets"]
missing = []
for name in mods:
    try:
        version(name)
    except PackageNotFoundError:
        missing.append(name)
if missing:
    raise SystemExit("Missing required package(s): " + ", ".join(missing))
print("Verified Python packages: " + ", ".join(f"{m} {version(m)}" for m in mods))
PY
  ok "Python packages installed"
}

seed_assets() {
  step "Seeding simulator files"
  mkdir -p "$SIM_ROOT/f/commands" "$SIM_ROOT/f" "$SIM_ROOT/logs"
  if [[ ! -f "$SIM_ROOT/GACF.DB" && -f "$ROOT/gibson/assets/GACF.DB" ]]; then
    cp "$ROOT/gibson/assets/GACF.DB" "$SIM_ROOT/GACF.DB"
  fi
  for f in "$ROOT"/gibson/assets/*; do
    [[ -f "$f" ]] || continue
    b="$(basename "$f")"
    case "$b" in
      GACF.DB) continue ;;
    esac
    cp -n "$f" "$SIM_ROOT/$b" 2>/dev/null || true
    cp -n "$f" "$SIM_ROOT/f/commands/$b" 2>/dev/null || true
    case "$b" in
      LISTCAT|SEARCH*|DISPLAY*|DPROGAPF|SETROPTS|*.TXT|*.txt)
        cp -n "$f" "$SIM_ROOT/f/commands/$b" 2>/dev/null || true
        ;;
    esac
  done
  chmod +x "$ROOT/run_gibson.sh" "$ROOT/gibsonctl.sh" "$ROOT/install_gibson.sh" 2>/dev/null || true
  ok "Simulator root prepared"
}

finish() {
  say
  say "${GREEN}Installation complete.${RESET}"
  say "${WHITE}Next steps${RESET}"
  say "  1. cd $ROOT"
  if [[ "$MODE" == "venv" ]]; then
    say "  2. source .venv/bin/activate"
    say "  3. ./gibsonctl.sh start"
  else
    say "  2. ./gibsonctl.sh start"
  fi
  say "${BLUE}Ports:${RESET} 2022 USS  2023 TSO/VTAM  3270 TN3270  2111 FTP  8443 Dashboard"
}

show_banner
require_python
activate_env
install_python_bits
seed_assets
finish
