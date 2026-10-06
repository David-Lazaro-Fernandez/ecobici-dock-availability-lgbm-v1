#!/usr/bin/env bash
# Install the collector on Amazon Linux 2023 (arm64 or x86_64). Run as root from a
# checkout of this repo: sudo ./deploy/ec2/setup.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_DIR=/opt/ecobici

id ecobici &>/dev/null || useradd --system --home-dir "$APP_DIR" --shell /sbin/nologin ecobici
timedatectl set-timezone UTC
command -v rsync &>/dev/null || dnf install -y rsync

mkdir -p "$APP_DIR"
rsync -a --delete --exclude .venv --exclude .git "$REPO_DIR"/ "$APP_DIR"/

if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
fi
cd "$APP_DIR"
UV_PYTHON_INSTALL_DIR=/opt/uv-python uv sync --frozen --extra collector --no-dev
chown -R ecobici:ecobici "$APP_DIR"

mkdir -p /etc/ecobici
[ -f /etc/ecobici/capture.env ] || cp deploy/ec2/capture.env.example /etc/ecobici/capture.env

cp deploy/ec2/systemd/* /etc/systemd/system/
systemctl daemon-reload

if grep -q YOUR-BUCKET /etc/ecobici/capture.env; then
  echo "Set ECOBICI_SINK in /etc/ecobici/capture.env, then re-run this script." >&2
  exit 1
fi
for feed in station_status station_information system_information; do
  systemctl enable --now "ecobici-capture@${feed}.timer"
done

echo "Installed. Check: systemctl list-timers 'ecobici*'"
