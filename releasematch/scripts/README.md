# ReleaseMatch scripts (cross-platform Python)

PoC and setup scripts run on **Windows / Linux / macOS** with Python 3.10+.

## Quick commands

```bash
cd releasematch
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements.txt

python scripts/setup_block_a.py          # Block A env check
python scripts/poc_phase0.py             # 4 source channels
python scripts/poc_jackett_indexers.py # each Jackett indexer

# Remote Jackett (e.g. Linode)
python scripts/poc_phase0.py --jackett-base-url http://YOUR_VPS:9117
```

## Legacy PowerShell wrappers

`*.ps1` files delegate to the Python scripts above for backward compatibility.

## Jackett on overseas VPS

See `docs/jackett-remote-linode.md`.

### One-click remote install (from your machine)

```bash
# Uses workflow/torrent_sources/servers.local.json for host/user/password
bash scripts/deploy_jackett_vps.sh

# Or explicit host + SSHPASS
SSHPASS='...' bash scripts/deploy_jackett_vps.sh --host YOUR_VPS_IP

# Force recreate Docker containers on VPS
FORCE_RECREATE=1 bash scripts/deploy_jackett_vps.sh
```

Remote-only script (run on VPS as root): `scripts/remote/install_jackett_stack.sh`

Local Nyaa fallback (SSH SOCKS, not on VPS): `scripts/start_ssh_socks_tunnel.sh`
