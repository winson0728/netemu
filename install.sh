#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash install.sh"
  exit 1
fi

INSTALL_DIR="/opt/netemu"
SERVICE_FILE="/etc/systemd/system/netemu.service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  python3 python3-pip python3-venv \
  iproute2 iptables net-tools kmod curl

echo "==> Loading kernel modules..."
modprobe sch_netem 2>/dev/null || true
modprobe ifb 2>/dev/null || true
mkdir -p /etc/modules-load.d
printf "sch_netem\nifb\n" > /etc/modules-load.d/netemu.conf

echo "==> Deploying to ${INSTALL_DIR}..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/backend" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/frontend" "$INSTALL_DIR/"

echo "==> Setting up Python venv..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --no-cache-dir -q
"$INSTALL_DIR/venv/bin/pip" install --no-cache-dir -q -r "$INSTALL_DIR/backend/requirements.txt"

echo "==> Installing systemd service..."
cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=NetEmu - Network Emulator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/netemu/backend
ExecStart=/opt/netemu/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8080 --log-level info
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable netemu
systemctl restart netemu

echo ""
echo "==> NetEmu installed successfully!"
echo "    Status:  sudo systemctl status netemu"
echo "    Logs:    sudo journalctl -u netemu -f"
echo "    Web UI:  http://$(hostname -I | awk '{print $1}'):8080"
echo ""
systemctl status netemu --no-pager
