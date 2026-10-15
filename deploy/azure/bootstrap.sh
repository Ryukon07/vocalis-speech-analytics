#!/usr/bin/env bash
# Run on the selected Ubuntu VM; never on the user's Windows machine.
set -euo pipefail
[[ $# == 2 ]] || { echo "Usage: bootstrap.sh AZURE_PUBLIC_DNS SEED_TAR_GZ" >&2; exit 2; }
cloud_host="$1"
seed_archive="$(realpath "$2")"
[[ "$cloud_host" =~ ^[a-z0-9.-]+\.cloudapp\.azure\.com$ ]] || { echo "Expected Azure public DNS hostname" >&2; exit 2; }
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -f "$seed_archive" ]] || { echo "Missing public seed archive" >&2; exit 2; }
command -v docker >/dev/null || { echo "Install Docker Engine and the Compose plugin first." >&2; exit 2; }
sudo mkdir -p /srv/vocalis/state /srv/vocalis/models
if [[ ! -f /srv/vocalis/state/state.sqlite ]]; then
    # The exporter only emits these reviewed paths; reject archive traversal.
    python3 - "$seed_archive" <<'PY'
import sys,tarfile
from pathlib import PurePosixPath
with tarfile.open(sys.argv[1]) as archive:
    for item in archive.getmembers():
        path=PurePosixPath(item.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert not item.issym() and not item.islnk()
        assert item.name in ('state.sqlite','seed-manifest.json') or item.name.startswith('storage/')
PY
    sudo tar --extract --gzip --file "$seed_archive" --directory /srv/vocalis/state --no-same-owner
fi
sudo chown -R 10001:10001 /srv/vocalis/state /srv/vocalis/models
printf 'VOCALIS_HOST=%s\n' "$cloud_host" > "$project_root/deploy/azure/.env"
cd "$project_root"
sudo docker compose --env-file deploy/azure/.env -f deploy/azure/compose.yaml build
# Warm actual recognition and alignment in the persistent model volume before
# accepting judging jobs. The task is a fresh process; the API loads on demand.
sudo docker compose --env-file deploy/azure/.env -f deploy/azure/compose.yaml run --rm --no-deps app python /app/scripts/warm_models.py
sudo docker compose --env-file deploy/azure/.env -f deploy/azure/compose.yaml up -d
echo "Full cloud workspace started: https://$cloud_host"
