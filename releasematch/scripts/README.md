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

## Linode VPS lifecycle (create / IP / delete)

脚本与配置同目录：`workflow/torrent_sources/`。文档：`docs/linode-vps-lifecycle.md`。

```bash
pip install -r workflow/torrent_sources/requirements-linode.txt
# Token：复制模板并填入（linode.local.json 已 gitignore，不上传 GitHub）
cp workflow/torrent_sources/linode.example.json \
   workflow/torrent_sources/linode.local.json
# 或临时：export LINODE_TOKEN=...

python workflow/torrent_sources/linode_vps.py create --region jp-osa --label demo
python workflow/torrent_sources/linode_vps.py create --json --region jp-osa
python workflow/torrent_sources/linode_vps.py params --kind region --region-filter jp
python workflow/torrent_sources/linode_vps.py params --kind type --json
python workflow/torrent_sources/linode_vps.py ip --label demo
python workflow/torrent_sources/linode_vps.py list
python workflow/torrent_sources/linode_vps.py delete --label demo --yes

# 一键：购买 + 装 Jackett（推荐）
bash scripts/install_jackett_oneclick.sh --provision-linode --with-indexers
bash scripts/install_jackett_oneclick.sh --destroy-linode
# label 默认来自 linode.local.json → defaults.label（linode_vps.py defaults）
```

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

### Batch speedtest Worker (cron)

```bash
# 5 concurrent workers, strategy A2 (256KB), write MySQL
python scripts/speedtest_batch_worker.py \
  --slots-json worklogs/2026-06-30/benchmark-slots.json \
  --write --workers 5 \
  --report worklogs/2026-07-02/speedtest-batch-benchmark.json
```

### Incremental publish Worker (cron)

Detect stale pages vs `generated_at`, bake dist, optional wrangler upload:

```bash
# detect only
python scripts/incremental_publish_worker.py --dry-run

# bake only (CF soft-launch)
python scripts/incremental_publish_worker.py --prepare-only \
  --report worklogs/$(date +%Y-%m-%d)/incremental-publish.json
```

See `docs/12-日常运营执行手册.md` §5.4 for crontab.
