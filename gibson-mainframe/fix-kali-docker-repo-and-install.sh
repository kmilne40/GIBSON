#!/usr/bin/env bash
set -euo pipefail

USER_NAME="${SUDO_USER:-${USER}}"

echo "[*] Removing invalid Docker upstream repo entries for kali-rolling..."

sudo mkdir -p /root/gibson-docker-repo-backup

# Back up and disable Docker upstream repo files that reference download.docker.com
for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
  [ -e "$f" ] || continue
  if sudo grep -q "download.docker.com" "$f"; then
    base="$(basename "$f")"
    sudo cp "$f" "/root/gibson-docker-repo-backup/$base.$(date +%Y%m%d-%H%M%S)"
    echo "[*] Disabling Docker repo in $f"
    sudo sed -i 's|^\([^#].*download\.docker\.com.*\)$|# DISABLED BY GIBSON: \1|' "$f"
  fi
done

echo "[*] Updating apt using Kali repositories..."
sudo apt update

echo "[*] Installing Docker from Kali packages..."
sudo apt install -y docker.io docker-compose

echo "[*] Ensuring docker group exists..."
sudo groupadd -f docker

echo "[*] Adding $USER_NAME to docker group..."
sudo usermod -aG docker "$USER_NAME"

echo "[*] Starting Docker service..."
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable docker || true
  sudo systemctl start docker || true
else
  sudo service docker start || true
fi

echo "[*] Checking Docker with sudo..."
sudo docker ps >/dev/null
echo "[+] Docker daemon works with sudo."

echo "[*] Fixing docker.sock permissions..."
if [ -S /var/run/docker.sock ]; then
  sudo chown root:docker /var/run/docker.sock || true
  sudo chmod 660 /var/run/docker.sock || true
  ls -l /var/run/docker.sock
fi

echo "[*] Checking Compose..."
if docker-compose --version >/dev/null 2>&1; then
  docker-compose --version
elif sudo docker compose version >/dev/null 2>&1; then
  sudo docker compose version
else
  echo "[!] Compose not found after install."
fi

echo "[*] Pulling Gibson Guacamole images..."
sudo docker pull guacamole/guacamole:1.6.0
sudo docker pull guacamole/guacd:1.6.0
sudo docker pull nginx:1.25-alpine

echo
echo "[+] Docker, Compose, and Gibson web-terminal images are installed."
echo
echo "IMPORTANT:"
echo "Your current shell may not yet have docker group access."
echo "Run:"
echo
echo "  newgrp docker"
echo
echo "Then test:"
echo
echo "  docker ps"
echo
echo "If that works, start Gibson:"
echo
echo "  cd /home/kali/gibson-mainframe-v30.286-freeze"
echo "  ./gibsonctl.sh preflight"
echo "  ./gibsonctl.sh start"
echo
echo "If docker still requires sudo in this shell, use:"
echo
echo "  sudo ./gibsonctl.sh start"
