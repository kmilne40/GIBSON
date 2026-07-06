#!/usr/bin/env bash
#
# grant-port-capabilities.sh
#
# Gibson now listens on the real privileged ports - TN3270/line-mode on 23 and
# FTP on 21 (DB2 stays on 50000, TN3270E on 3270, etc.). Linux forbids binding
# ports below 1024 to a non-root process. Rather than run the whole simulator as
# root, grant the CAP_NET_BIND_SERVICE capability to the Python interpreter that
# runs Gibson. This lets that interpreter - and only that interpreter - bind low
# ports while still running under your normal user account.
#
# Run this ONCE (it needs sudo). After that, start Gibson normally as your user.
#
#   sudo ./scripts/grant-port-capabilities.sh
#   python3 -m gibson            # binds 23 and 21 without sudo
#
# To undo:
#   sudo setcap -r "$(readlink -f "$(command -v python3)")"
#
# Notes / caveats:
#   * The capability is attached to the resolved interpreter binary. If you use a
#     virtualenv, point this at that venv's python (pass it as $1).
#   * Granting the capability to a shared system python means anything run with
#     that interpreter may bind low ports. For an isolated lab box that is fine;
#     on a shared host, prefer a dedicated venv interpreter (see $1 below) or a
#     systemd unit with AmbientCapabilities=CAP_NET_BIND_SERVICE.
#   * setcap requires a real file (not a symlink) on a filesystem that supports
#     extended attributes. readlink -f resolves the symlink for you.

set -euo pipefail

# Allow an explicit interpreter path as the first argument (e.g. a venv python),
# otherwise use whatever python3 is on PATH.
PYBIN="${1:-$(command -v python3 || true)}"

if [[ -z "${PYBIN}" ]]; then
    echo "ERROR: could not find a python3 interpreter. Pass one explicitly:" >&2
    echo "  sudo $0 /path/to/venv/bin/python3" >&2
    exit 1
fi

# Resolve symlinks - setcap must target the real binary.
REAL_PY="$(readlink -f "${PYBIN}")"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: this must be run with sudo/root (setcap is privileged)." >&2
    echo "  sudo $0 ${PYBIN}" >&2
    exit 1
fi

if ! command -v setcap >/dev/null 2>&1; then
    echo "ERROR: 'setcap' not found. Install it first:" >&2
    echo "  Debian/Kali/Ubuntu : apt-get install -y libcap2-bin" >&2
    echo "  RHEL/Fedora        : dnf install -y libcap" >&2
    exit 1
fi

echo "Granting CAP_NET_BIND_SERVICE to: ${REAL_PY}"
setcap 'cap_net_bind_service=+ep' "${REAL_PY}"

echo "Verifying:"
getcap "${REAL_PY}"

cat <<EOF

Done. ${REAL_PY} may now bind ports below 1024 (23, 21) without root.

Start Gibson as your normal user, e.g.:
  python3 -m gibson

If you still get 'Permission denied' on bind:
  * confirm nothing else holds the port:  sudo ss -ltnp | grep -E ':21 |:23 '
  * confirm you started the SAME interpreter this script was pointed at
  * on a venv, re-run:  sudo $0 /path/to/venv/bin/python3
EOF
