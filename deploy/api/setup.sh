#!/usr/bin/env bash
# Install the API on Oracle Linux 9 (aarch64 or x86_64). Run as root from a checkout of this
# repo: sudo ./deploy/api/setup.sh
# Copy the model files to /opt/ecobici/artifacts/ before the first start (see README.md).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_DIR=/opt/ecobici
ENV_FILE=/etc/ecobici/api.env
REQUIRED_ARTIFACTS=(serving empty lgbm_15.txt isotonic_15.json platt_sub_15.json)

# The sudo secure_path on Oracle Linux does not include /usr/local/bin, where uv installs.
export PATH="$PATH:/usr/local/bin"

id ecobici &>/dev/null || useradd --system --home-dir "$APP_DIR" --shell /sbin/nologin ecobici
command -v rsync &>/dev/null || dnf install -y rsync

mkdir -p "$APP_DIR"
# Excluded paths are not deleted, so the copied model files stay.
rsync -a --delete --exclude .venv --exclude .git --exclude artifacts --exclude data \
  --exclude raw --exclude web --exclude .env --exclude /api.env "$REPO_DIR"/ "$APP_DIR"/

if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
fi
cd "$APP_DIR"
# The API imports the model code (polars, duckdb, lightgbm), so it needs both extras.
UV_PYTHON_INSTALL_DIR=/opt/uv-python uv sync --frozen --extra api --extra model --no-dev
mkdir -p artifacts
chown -R ecobici:ecobici "$APP_DIR"

mkdir -p /etc/ecobici
[ -f "$ENV_FILE" ] || install -m 600 deploy/api/api.env.example "$ENV_FILE"
chown ecobici:ecobici "$ENV_FILE"

cp deploy/api/ecobici-api.service deploy/api/ecobici-autodeploy.service \
  deploy/api/ecobici-autodeploy.timer /etc/systemd/system/
printf 'REPO_DIR=%s\n' "$REPO_DIR" > /etc/ecobici/autodeploy.env
systemctl daemon-reload

if grep -q YOUR- "$ENV_FILE"; then
  echo "Set every value in $ENV_FILE, then re-run this script." >&2
  exit 1
fi
for artifact in "${REQUIRED_ARTIFACTS[@]}"; do
  if [ ! -e "$APP_DIR/artifacts/$artifact" ]; then
    echo "Missing $APP_DIR/artifacts/$artifact. Copy the model files (README.md), then re-run." >&2
    exit 1
  fi
done
chown -R ecobici:ecobici "$APP_DIR/artifacts"

systemctl enable ecobici-api
systemctl restart ecobici-api
systemctl enable --now ecobici-autodeploy.timer
echo "Installed. Check: curl http://127.0.0.1:8000/docs"
