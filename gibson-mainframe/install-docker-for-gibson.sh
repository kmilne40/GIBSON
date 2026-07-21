#!/usr/bin/env bash
set -euo pipefail

REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
DRY_RUN="${GIBSON_INSTALL_DRY_RUN:-0}"
YES="${GIBSON_INSTALL_YES:-0}"

say(){ printf '%s\n' "$*"; }
run(){ if [[ "$DRY_RUN" == "1" ]]; then say "DRY-RUN: $*"; else "$@"; fi; }
have(){ command -v "$1" >/dev/null 2>&1; }
need_sudo(){ [[ "$(id -u)" -eq 0 ]] && "$@" || sudo "$@"; }

source_os(){
  if [[ -r /etc/os-release ]]; then . /etc/os-release; echo "${ID:-unknown}:${VERSION_CODENAME:-${VERSION_ID:-}}:${ID_LIKE:-}"; else echo "unknown::"; fi
}

fix_kali_bad_docker_repo(){
  local os; os="$(source_os)"
  [[ "$os" == kali:* ]] || return 0
  say "[*] Checking for invalid Docker upstream repositories on Kali..."
  need_sudo mkdir -p /root/gibson-docker-repo-backup
  shopt -s nullglob
  for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
    [[ -e "$f" ]] || continue
    if grep -q "download.docker.com" "$f" 2>/dev/null; then
      say "[*] Disabling unsupported Docker upstream repo in $f (Kali should use docker.io)"
      need_sudo cp "$f" "/root/gibson-docker-repo-backup/$(basename "$f").$(date +%Y%m%d-%H%M%S)"
      need_sudo sed -i 's|^\([^#].*download\.docker\.com.*\)$|# DISABLED BY GIBSON: \1|' "$f"
    fi
  done
}

install_apt(){
  fix_kali_bad_docker_repo
  say "[*] Installing Docker/Compose from distro packages with apt..."
  need_sudo apt update
  if ! need_sudo apt install -y docker.io docker-compose; then
    say "[!] docker-compose package unavailable; trying docker.io only."
    need_sudo apt install -y docker.io
  fi
}

install_dnf(){
  say "[*] Installing Docker/Podman dependencies with dnf/yum path..."
  if have dnf; then need_sudo dnf install -y docker docker-compose-plugin podman podman-compose || need_sudo dnf install -y podman podman-compose; else need_sudo yum install -y docker docker-compose-plugin || true; fi
}
install_pacman(){ say "[*] Installing Docker with pacman..."; need_sudo pacman -Sy --noconfirm docker docker-compose; }
install_zypper(){ say "[*] Installing Docker with zypper..."; need_sudo zypper --non-interactive install docker docker-compose; }

start_docker(){
  say "[*] Enabling/starting Docker daemon where available..."
  if have systemctl; then
    need_sudo systemctl enable docker || true
    need_sudo systemctl start docker || true
  elif have service; then
    need_sudo service docker start || true
  fi
}

configure_group(){
  say "[*] Ensuring docker group and adding $REAL_USER..."
  need_sudo groupadd -f docker || true
  need_sudo usermod -aG docker "$REAL_USER" || true
  if [[ -S /var/run/docker.sock ]]; then
    need_sudo chown root:docker /var/run/docker.sock || true
    need_sudo chmod 660 /var/run/docker.sock || true
  fi
}

pull_images(){
  local arch guac_version guac guacd nginx
  arch="$(uname -m)"; guac_version="${GIBSON_GUAC_VERSION:-1.6.0}"
  guac="${GIBSON_GUACAMOLE_IMAGE:-guacamole/guacamole:$guac_version}"
  guacd="${GIBSON_GUACD_IMAGE:-guacamole/guacd:$guac_version}"
  nginx="${GIBSON_WEB_WRAPPER_IMAGE:-nginx:1.25-alpine}"
  say "[*] Pulling Gibson web-terminal images for $arch..."
  need_sudo docker pull "$guac"
  need_sudo docker pull "$guacd"
  need_sudo docker pull "$nginx"
}

main(){
  say "Gibson Docker/Podman dependency installer"
  say "  user: $REAL_USER"
  say "  OS: $(source_os)"
  say "  architecture: $(uname -m)"
  if have apt; then install_apt; elif have dnf || have yum; then install_dnf; elif have pacman; then install_pacman; elif have zypper; then install_zypper; else say "[!] Unsupported package manager. Install Docker or Podman manually; raw Gibson still works."; exit 1; fi
  start_docker
  configure_group
  say "[*] Verifying Docker with elevated privileges..."
  need_sudo docker ps >/dev/null
  say "[+] Docker daemon is reachable with sudo/root."
  if have docker-compose; then docker-compose --version || true; elif docker compose version >/dev/null 2>&1; then docker compose version || true; else say "[!] Compose not found; install docker-compose or docker compose plugin."; fi
  pull_images
  say "[+] Docker/Compose/Guacamole dependencies installed."
  say "IMPORTANT: run 'newgrp docker' or log out/in before non-sudo docker use."
  say "Then run: ./gibsonctl.sh preflight && ./gibsonctl.sh start"
}
main "$@"
