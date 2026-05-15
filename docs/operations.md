# Operations

Deployment state, day-2 procedures, and recovery notes.

---

## Live deployments (as of 2026-04-21)

### Server 16 ? 192.168.0.16 ? HyperCube production
- Public URL: `http://192.168.0.16:3334/`
- Deploy folder: `/home/agics-ai/docker/hypercube`
- Image tag pinned in `.env`: currently `sha-a92ed89`
  (override to `latest` to track main automatically)
- Container names: `hc-nginx`, `hc-backend`, `hc-celery-worker`, `hc-celery-beat`, `hc-postgres`, `hc-redis`
- SPA mounts at root `/`. Django admin at `/django-admin/`.
- Port 7003 on the host is **owned by `agdevblog_frontend`** (unrelated project) ? do not touch.
- Former DCMTool stack at `/home/agics-ai/docker/DCMTool` is stopped via `docker compose down` (volumes preserved). Restart with `docker compose up -d` from that directory if you need to roll all the way back to the pre-HyperCube world.
- DCMTool self-hosted runner (`actions.runner.dev-agics-DCMTool.agicsai-desktop`) is **stopped + disabled** ? nothing auto-redeploys the old DCMTool image.

### Server 41 ? 192.168.0.41 ? production agent
- Container: `hypercube-agent-prod-agent-1` (running the fixed build `ac0daaf` with WS response queue)
- Config: `BACKEND_URL=ws://192.168.0.16:3334`, `AGENT_HOSTNAME=server_41_prod`
- SSH: `root@192.168.0.41:2022` (password auth)
- Also has a stray local-test agent `hypercube-agent-agent-1` that tries to reach `192.168.0.47:8000`. Ignore unless told otherwise.

### Server 63 ? agent presence (partial)
- Reports as registered; operational status to be confirmed when needed.

---

## Image + bundle pipeline

```
HyperCube (private)
    main push
       ?
       ??? build-push-images.yml   ? ghcr.io/qkr7287/hypercube-{backend,nginx} (public)
       ??? publish-deploy-bundle.yml ? qkr7287/hypercube-deploy (public)
       ??? sync-to-dcmtool.yml     ? legacy DCMTool/dev mirror (no longer acted on)

hypercube-deploy/main
    (stopping point for now ? future: hypercube-deploy push
     triggers self-hosted runner on server 16 to pull + up)
```

- Images: **public** (repo stays private). If images ever flip back to private, toggle via Profile ? Packages ? `hypercube-*` ? Package settings ? Visibility ? Public.
- Bundle sync currently needs secret `DEPLOY_BUNDLE_PAT` on `qkr7287/HyperCube`. Until that secret is set the bundle workflow is a no-op and you have to copy `deploy/docker-compose.yml` + `deploy/.env.example` manually.

---

## Day-2 procedures (server 16)

### Update to latest main
```bash
ssh -i ~/.ssh/dcmtool_sync -p 2022 root@192.168.0.16
cd /home/agics-ai/docker/hypercube
docker compose pull
docker compose up -d
docker compose logs -f backend   # optional ? watch the migrate + startup
```
Migrations run automatically on container start. No extra steps for ordinary releases.

### Pin to a specific commit (rollback or freeze)
```bash
cd /home/agics-ai/docker/hypercube
sed -i 's|^IMAGE_TAG=.*|IMAGE_TAG=sha-<7char>|' .env
docker compose pull
docker compose up -d
```

### Back up the database
```bash
cd /home/agics-ai/docker/hypercube
docker compose exec postgres pg_dump -U hypercube hypercube \
  > /home/agics-ai/docker/hypercube/backup-$(date +%F).sql
```

### Create another Django superuser
```bash
docker compose exec backend python manage.py createsuperuser
```

### Reset password of an existing user
```bash
docker compose exec backend python manage.py changepassword <username>
```

---

## Recovery

### Stop HyperCube, restart legacy DCMTool
```bash
ssh -i ~/.ssh/dcmtool_sync -p 2022 root@192.168.0.16

cd /home/agics-ai/docker/hypercube
docker compose down                    # stop prod stack, keep volumes
cd /home/agics-ai/docker/DCMTool
docker compose up -d                   # bring old stack back (data intact)
systemctl enable --now actions.runner.dev-agics-DCMTool.agicsai-desktop
```

### Full DB wipe (dev only ? production lose data!)
```bash
docker compose down -v                 # -v deletes volumes
docker compose up -d                   # fresh DB, fresh migrations
```

---

## Dev on server 63 (remote Docker, local editing)

Docker runs on `agics@192.168.0.63:2022`; the checkout lives on your
Windows PC; a Mutagen session keeps the two sides in lockstep. Your
editor, git, and browser stay local.

**Why this shape**
- Local Windows has the authoritative checkout (editor, branches).
  Mutagen pushes writes up to the server within ~100 ms.
- Docker compose + containers live entirely on `192.168.0.63`. Nothing
  in your PC's RAM beyond the editor + terminal + browser.
- Source is visible on the server at `/home/agics/ts/HyperCube/` ? the
  same bind mounts as pure-local dev.

**Port plan on server 63**
| purpose | host port | notes |
|---|---|---|
| frontend (Vite) | `3000` | free on 63 (collision-free) |
| backend (uvicorn) | `8000` | free |
| postgres | `15432` | dev default |
| redis | `16379` | dev default |

Override any of these via `.env.dev` (`FE_PORT`, `BE_PORT`, `DB_PORT`, `REDIS_PORT`).

### One-time setup (on your Windows PC)

1. Install Mutagen (CLI only ? not Mutagen Compose):
   ```powershell
   winget install Mutagen.Mutagen
   ```

2. Key-based SSH is already set up (`ssh-ed25519` from
   `~/.ssh/dcmtool_sync` is installed under `agics@192.168.0.63`).
   Verify:
   ```bash
   ssh -i ~/.ssh/dcmtool_sync -p 2022 agics@192.168.0.63 whoami
   ```
   Should print `agics` without asking for a password.

3. Add an SSH alias so Mutagen and compose find the host easily.
   In `~/.ssh/config`:
   ```
   Host hc-dev-63
       HostName 192.168.0.63
       User agics
       Port 2022
       IdentityFile ~/.ssh/dcmtool_sync
   ```

4. On the server, the workspace already exists at `/home/agics/ts`.
   Mutagen will populate `/home/agics/ts/HyperCube/` on first sync.

5. Create `.env.dev` (local, git-ignored) with dev values. Minimum:
   ```dotenv
   DB_NAME=hypercube
   DB_USER=hypercube
   DB_PASSWORD=dev-local-pass
   DJANGO_ENV=dev
   DJANGO_SECRET_KEY=dev-insecure-key
   # Defaults: FE_PORT=3000, BE_PORT=8000, DB_PORT=15432, REDIS_PORT=16379
   ```
   Copy it up so the first compose run has what it needs (Mutagen
   keeps it in sync afterwards):
   ```bash
   ssh hc-dev-63 "mkdir -p /home/agics/ts/HyperCube"
   scp .env.dev hc-dev-63:/home/agics/ts/HyperCube/.env.dev
   ```

### Start the Mutagen sync session (once per machine)

```bash
mutagen sync create \
  --name=hypercube \
  --mode=two-way-resolved \
  --ignore-vcs \
  --ignore="node_modules,build,.svelte-kit,staticfiles,__pycache__,*.pyc,.pytest_cache,.claude,.playwright-mcp,.serena" \
  "C:\Users\agics\Desktop\workspace\01. git\HyperCube" \
  "hc-dev-63:/home/agics/ts/HyperCube"
```

Check state anytime:
```bash
mutagen sync list
mutagen sync monitor hypercube    # live event stream
```

### Bring the stack up
```bash
ssh hc-dev-63 "
  cd /home/agics/ts/HyperCube &&
  docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d
"
```

Tail logs:
```bash
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose logs -f backend"
```

### Access from your PC

Either hit the server directly:
```
http://192.168.0.63:3000/
```

Or keep the `localhost:3000` feel with a persistent SSH tunnel:
```bash
ssh hc-dev-63 -L 3000:localhost:3000 -N &
# then browse http://localhost:3000/
```

### Day-to-day

- Save a file locally ? Mutagen pushes within ~100 ms ? Vite / uvicorn
  `--reload` picks it up and the browser refreshes.
- `git` stays on your PC. You commit as usual; the server never talks
  to GitHub for dev.
- Tear down: `ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose down"`.
  The Mutagen session can stay up (it idles when nothing changes).
- Stop the sync session: `mutagen sync terminate hypercube`.

### Gotchas to remember
- If Mutagen reports a conflict (`two-way-resolved` covers most, but
  not all), resolve with `mutagen sync resolve hypercube`.
- `agics` is in the `docker` group on 63, so `docker compose` runs
  without `sudo`.
- Anything you mutate inside the running containers writes back to the
  bind-mounted filesystem (and then up into your local checkout) ?
  great for migrations, dangerous for accidental `python manage.py startapp`.
  Stay aware of it.

---

## Agent network mode (run on host network)

**Policy ? production + dev on Linux hosts**: the HyperCube agent must
be launched with `network_mode: host` in its docker-compose. This is
not a Docker quirk ? it's a deliberate choice aligned with standard
host-monitoring agents (Datadog, Prometheus node_exporter, cAdvisor).

### Why
The agent's job is to report its host's CPU, memory, disk, Docker, and
TCP state. When it runs in an isolated bridge network, two things go
wrong:

1. **Wrong IP**. `os.networkInterfaces()` inside the container returns
   the container's bridge IP (`172.x` or `192.168.192.x`), never the
   host's LAN IP. The agent therefore cannot report a useful
   `ip_address`, and the backend's `_client_ip()` observation only
   recovers the real host IP when the agent connects **across hosts**
   (the SNAT hop gives the backend the host IP). For same-host setups
   (backend + agent both on the same Linux box) every TCP peer the
   backend sees is a docker-bridge internal IP, so `agents.ip_address`
   ends up as e.g. `172.24.0.1`. The sidebar IP field mirrors this.
2. **Blind host monitoring**. Metrics like `ss -tan`, `/proc/net/tcp`,
   open-file counts, and login sessions live in the host's network
   namespace. A bridged container can't see them faithfully.

`network_mode: host` fixes both problems by putting the agent in the
host's network namespace.

### Required `docker-compose` shape

```yaml
services:
  agent:
    image: ghcr.io/qkr7287/hypercube-agent:<tag>
    network_mode: host            # <-- mandatory on Linux
    environment:
      BACKEND_URL: ws://192.168.0.16:3334
      AGENT_HOSTNAME: server_63_prod
      # AGENT_ADVERTISE_IP: 192.168.0.63   # see fallback below
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped
```

Things to remove when migrating to host mode:
- any `networks:` blocks
- any `ports:` mapping (meaningless once the container shares the host
  stack)

### Fallback for Docker Desktop (Windows / macOS)
`network_mode: host` is unreliable on Docker Desktop ? the "host" is
the Linux VM, not the developer's Mac/Windows machine. Developer
workstations running the agent should skip host mode and instead set
an explicit env override:

```yaml
services:
  agent:
    environment:
      BACKEND_URL: ws://host.docker.internal:3334
      AGENT_ADVERTISE_IP: 10.0.10.123   # your LAN IP, manually
```

Agent implementations should honor `AGENT_ADVERTISE_IP` when present and
forward it through whatever channel the backend expects (currently:
noop, since backend trusts observed IP). For Docker Desktop use, the
operator either accepts "IP shown = backend's observation" or wires the
advertised value through. This is a rare case ? Linux servers are the
norm.

### Backend side (no change required)
`backend/apps/agents/viewsets.py` already derives `ip_address` from the
forwarded client IP (`_client_ip()` prefers nginx's overwritten
`X-Real-IP`, then `REMOTE_ADDR`, with `X-Forwarded-For` only as a final
fallback). `AgentViewSet.create()` uses that in both the idempotent
re-registration path and the fresh registration path. The registration
payload shape is unchanged; agents continue to omit `ip_address`
intentionally.

### nginx requirement
`nginx/nginx.conf` must forward the client IP. The backend treats
`X-Real-IP` as the authoritative reverse-proxy observation because nginx
overwrites it with `$remote_addr`. `X-Forwarded-For` is useful for
diagnostics but may include client-supplied values when
`$proxy_add_x_forwarded_for` is used, so it is only a fallback.

The current config already sets these on every proxied location:
```
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```
If `X-Real-IP` ever regresses, every agent registration will fall back
to `REMOTE_ADDR`, which on a bridge network is the upstream docker proxy
rather than the real client.

### Acceptance tests

When an agent migrates to `network_mode: host`, verify all three:

1. **Same-host (Linux)** ? deploy the agent on the same host that runs
   the backend (e.g. both on server 63). Restart the agent container;
   inspect the DB:
   ```bash
   docker compose exec -T backend python manage.py shell -c \
     "from apps.agents.models import Agent; \
      a = Agent.objects.get(hostname='server_63_dev'); \
      print(a.ip_address)"
   ```
   ? expect `192.168.0.63`, not `172.x.x.x`.

2. **Cross-host (no regression)** ? agent on server 41, backend on
   server 16. After re-register:
   ```bash
   # on the backend host
   docker compose exec -T backend python manage.py shell -c \
     "from apps.agents.models import Agent; \
      a = Agent.objects.get(hostname='server_41_prod'); \
      print(a.ip_address)"
   ```
   ? expect `192.168.0.41` (regression check ? host-mode must not
   break cross-host registration).

3. **Frontend sidebar** ? log into the UI, select each server in turn,
   confirm the `IP` row shows the correct LAN IP (`192.168.0.x`) and
   never a Docker bridge range (`172.x`, `192.168.192.x`).

If any of the three fails, revert host-mode for that deployment and
re-investigate before rolling forward.

---

## Known quirks / limitations

### ML workspace template seed

Migration `containers.0007_seed_ml_workspace_templates` seeds four air-gapped
ML templates when normal migrations run outside Django test mode:

- `PyTorch Jupyter GPU Workspace`
- `TensorFlow Jupyter GPU Workspace`
- `vLLM OpenAI API Workspace`
- `CUDA code-server Workspace`

After deployment on server 63, verify:

```bash
python manage.py shell -c "from apps.containers.models import ContainerTemplate; print(list(ContainerTemplate.objects.filter(category='ml').values_list('name', 'requires_gpu', 'workspace_enabled')))"
```

The request modal depends on at least one `category='ml'`,
`requires_gpu=True`, `workspace_enabled=True` template before a real GPU
workspace request can be submitted.

### GPU workspace proxy reachability gate

For normal workspaces, the backend proxy can use the agent-reported host port:

```bash
agent.ip_address:workspace_host_port
```

For `networkPolicy=internal_only` ML workspaces, the agent must not publish the
workspace port on the host. The backend container must join the same external
Docker internal network as the workspace container and use Docker DNS:

```bash
hc-ml-internal
<workspace-container-name>:<workspace_internal_port>
```

Before calling Jupyter workspace access production-ready on server 63 or any
GPU agent, run a smoke test from the backend container:

```bash
docker network inspect hc-ml-internal --format 'internal={{.Internal}}'
docker exec hc-backend python -c "import socket; socket.create_connection(('<workspace-container-name>', 8888), 5).close(); print('BACKEND_TO_WORKSPACE_OK')"
```

`docker-compose.dev.yml`, `docker-compose.prod.yml`, and
`deploy/docker-compose.yml` attach `hc-backend` to the external
`hc-ml-internal` network. That network must already exist before backend
recreate/startup.

Plaintext Jupyter tokens are stored only in Redis with
`WORKSPACE_TOKEN_TTL_SECONDS`; Postgres stores only `workspace_token_ref` and
expiry metadata.

### LVM thin workspace host gate

Container resource limits and quota-aware KPI display are implemented in
HyperCube core, but per-container `/workspace` LVM thin isolation requires a
host/agent runtime gate before it can be called complete on server 63.

Use `docs/runbooks/lvm-thin-workspace-host-setup.md` before enabling LVM mode.
At minimum, the host and chosen agent permission path must expose `lvcreate`,
`lvs`, `mkfs.ext4`, `mount`, `umount`, and `lvremove`; `lvs --units g` must show
the configured thin pool; `/mnt/datasets` and `/mnt/models` must exist or the
shared-mount policy must be explicitly changed.

As of the 2026-05-15 audit, `server_63_dev` and `hypercube-agent-dev-63` both
lack `lvcreate/lvs`, `/mnt/datasets` and `/mnt/models` are missing, and backend
Agent rows still have `lvm_pool_size_gb=None`. In that state the backend
correctly stays in legacy mode and omits `params.workspace`.

### Model asset local storage

Track 4a stores uploaded model files on the HyperCube backend host under
`HC_MODEL_STORAGE_DIR` and imports operator-provided offline files only from
`HC_MODEL_IMPORT_DIR`.

Runtime model downloads are not allowed. Do not point model import at
`http://`, `https://`, S3, Git, Hugging Face, or any other external source.
Incomplete uploads use a `_tmp` directory below `HC_MODEL_STORAGE_DIR` and are
removed on failure.

### Model prepare and agent cache

Track 4b adds backend-owned prepare state:

- `ModelVersionCache` records per-agent cache status.
- `ModelPrepareJob` records one active transfer for an `(agent, model version)`
  and fans progress out to all waiting container requests.
- Celery beat runs `cleanup_stale_model_prepare_jobs_task` every 60 seconds.

The backend content endpoint is internal only:

```text
GET /api/model-versions/<version-id>/content/
Authorization: Bearer agent_...
```

The agent token is checked against an active prepare job. Operators should keep
this path reachable only on the HyperCube internal network. Runtime workspaces
still must not download models, packages, images, or source code from the public
internet.

### Workspace policy and shared GPU guardrail

Track 5 adds backend policy settings:

```dotenv
HC_GPU_SHARED_MODE_ENABLED=false
HC_MAX_ACTIVE_WORKSPACES_PER_USER=2
HC_MAX_ACTIVE_GPU_SLICES_PER_USER=1
HC_MAX_WORKSPACE_RUNTIME_HOURS=72
```

`HC_GPU_SHARED_MODE_ENABLED=false` is the required default. A GPU slice may
report `allow_shared=true`, and the request modal can explicitly submit
`gpu_share_ok=true`, but the backend still rejects shared GPU requests unless
the global setting is enabled. Do not enable shared mode in production until GPU
memory accounting and enforcement behavior are verified.

Workspace runtime policy is enforced when a request is created and when runtime
is extended. Active workspace and GPU slice quotas are enforced at approval time
before GPU reservation.

### WebSocket token log hygiene

Browser WebSocket clients pass JWTs through the `hypercube.jwt` subprotocol
instead of the URL query string. The backend still accepts `?token=` as a
backward-compatible fallback for older clients and agent builds.

Backend uvicorn is started with `--no-access-log`, and nginx disables access
logs for `/ws/` and `/workspace/`, so fallback query tokens and workspace
tickets do not land in routine access logs.

Longer term, move agent WebSocket authentication off query strings too and
rotate existing agent tokens after that migration.

| Area | Quirk | Impact |
|---|---|---|
| `/user/containers` time series | `7d` range actually returns the **last ~2 h** because `limit=240` is hard-capped. No downsampling yet. | Graphs for long ranges look truncated ? visual only, no data loss. |
| Port validation | Neither frontend nor backend pre-checks whether the requested host port is free on the target agent. | Collisions surface as `failed` requests with the Docker error in `progress_message`. Fix needs agent-side netstat. |
| Agent WS response delivery | Prior to `ac0daaf` a disconnect mid-`compose_up` would strand the request in `deploying`. Fixed with an outbound queue + reconnect drain. Safety net on the server side (auto-heal stuck requests) is **not** implemented. | If you see `deploying` stuck >5 min, check agent logs; otherwise the queue fix handles it. |
| Legacy agent on 41 | `hypercube-agent-agent-1` keeps retrying an old `192.168.0.47:8000` backend. Harmless, but noisy in logs. | Skip, or remove if you want clean logs. |

---

## Port map on server 16 (snapshot)

| Host port | Service |
|---|---|
| 3334 | HyperCube production (nginx ? backend) |
| 7003 | `agdevblog_frontend` (unrelated) |
| 5432 | `release-notes-db-1` Postgres (unrelated) |
| (others) | many third-party stacks ? see `docker ps` |

Any new HyperCube dev stack on server 16 should pick non-conflicting ports (e.g. `3000`, `8000`, `15432`, `16379`).

---

## Contact points (external)

- HyperCube source: https://github.com/qkr7287/HyperCube (private)
- Deploy bundle:   https://github.com/qkr7287/hypercube-deploy (public)
- GHCR images:     https://github.com/qkr7287?tab=packages (public images, private profile)
- Agent repo: **separate repository** (`qkr7287/hypercube-agent`). Cross-repo work is tracked via **GitHub Issues** on the agent repo. The mailbox doc was retired in favor of issue-based tracking.
