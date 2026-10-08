#!/usr/bin/env bash
# Pull new commits of the checked-out branch and re-install the API. The
# ecobici-autodeploy timer runs it as root. A push to that branch is a deploy to prod.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OWNER="$(stat -c %U "$REPO_DIR")"
OWNER_HOME="$(getent passwd "$OWNER" | cut -d: -f6)"

# Run git as the checkout owner: root gets "dubious ownership" and would leave root-owned files.
as_owner() {
  runuser -u "$OWNER" -- env HOME="$OWNER_HOME" git -C "$REPO_DIR" "$@"
}

as_owner fetch --quiet
# Compare with the commit that setup.sh installed, not with the checkout. After a failed deploy the checkout is
# already up to date, and the next run must try again.
if [ "$(cat /opt/ecobici/DEPLOYED 2>/dev/null)" = "$(as_owner rev-parse '@{u}')" ]; then
  exit 0
fi
as_owner merge --ff-only --quiet '@{u}'
echo "Deploying $(as_owner log -1 --format='%h %s')"
"$REPO_DIR/deploy/api/setup.sh"
