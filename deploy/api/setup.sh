#!/usr/bin/env bash
# Install the API on Oracle Linux 9 (aarch64 or x86_64). Run as root from a checkout of this
# repo: sudo ./deploy/api/setup.sh
# Copy the model files to /opt/ecobici/artifacts/ before the first start (see README.md).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REPO_OWNER="$(stat -c %U "$REPO_DIR")"
APP_DIR=/opt/ecobici
# The commit that runs in APP_DIR. autodeploy.sh compares it with the branch, so a failed deploy runs again.
DEPLOYED_FILE="$APP_DIR/DEPLOYED"
ENV_FILE=/etc/ecobici/api.env
REQUIRED_ARTIFACTS=(serving empty lgbm_15.txt isotonic_15.json platt_sub_15.json)

# The sudo secure_path on Oracle Linux does not include /usr/local/bin, where uv installs.
export PATH="$PATH:/usr/local/bin"

id ecobici &>/dev/null || useradd --system --home-dir "$APP_DIR" --shell /sbin/nologin ecobici
command -v rsync &>/dev/null || dnf install -y rsync

git_as_owner() {
  runuser -u "$REPO_OWNER" -- env HOME="$(getent passwd "$REPO_OWNER" | cut -d: -f6)" git -C "$REPO_DIR" "$@"
}

mkdir -p "$APP_DIR"
# SELinux: from a systemd unit, rsync runs as rsync_t, which cannot read /home or a unit's /tmp. A stage dir in
# /opt gets usr_t, which rsync_t can read. git archive also leaves out untracked files.
STAGE_DIR="$(mktemp -d -p /opt ecobici-stage.XXXXXX)"
trap 'rm -rf "$STAGE_DIR"' EXIT
git_as_owner archive HEAD | tar -x -C "$STAGE_DIR"
# Excluded paths are not deleted, so the copied model files stay.
rsync -a --delete --exclude .venv --exclude artifacts --exclude data --exclude raw --exclude web \
  --exclude .env --exclude /api.env --exclude /DEPLOYED "$STAGE_DIR"/ "$APP_DIR"/

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
git_as_owner rev-parse HEAD > "$DEPLOYED_FILE"
echo "Installed $(cat "$DEPLOYED_FILE"). Check: curl http://127.0.0.1:8000/docs"
