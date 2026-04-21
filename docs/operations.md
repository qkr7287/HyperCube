# Operations

Deployment state, day-2 procedures, and recovery notes.

---

## Live deployments (as of 2026-04-21)

### Server 16 — 192.168.0.16 — HyperCube production
- Public URL: `http://192.168.0.16:3334/`
- Deploy folder: `/home/agics-ai/docker/hypercube`
- Image tag pinned in `.env`: currently `sha-a92ed89`
  (override to `latest` to track main automatically)
- Container names: `hc-nginx`, `hc-backend`, `hc-celery-worker`, `hc-celery-beat`, `hc-postgres`, `hc-redis`
- SPA mounts at root `/`. Django admin at `/django-admin/`.
- Port 7003 on the host is **owned by `agdevblog_frontend`** (unrelated project) — do not touch.
- Former DCMTool stack at `/home/agics-ai/docker/DCMTool` is stopped via `docker compose down` (volumes preserved). Restart with `docker compose up -d` from that directory if you need to roll all the way back to the pre-HyperCube world.
- DCMTool self-hosted runner (`actions.runner.dev-agics-DCMTool.agicsai-desktop`) is **stopped + disabled** — nothing auto-redeploys the old DCMTool image.

### Server 41 — 192.168.0.41 — production agent
- Container: `hypercube-agent-prod-agent-1` (running the fixed build `ac0daaf` with WS response queue)
- Config: `BACKEND_URL=ws://192.168.0.16:3334`, `AGENT_HOSTNAME=server_41_prod`
- SSH: `root@192.168.0.41:2022` (password auth)
- Also has a stray local-test agent `hypercube-agent-agent-1` that tries to reach `192.168.0.47:8000`. Ignore unless told otherwise.

### Server 63 — agent presence (partial)
- Reports as registered; operational status to be confirmed when needed.

---

## Image + bundle pipeline

```
HyperCube (private)
    main push
       │
       ├── build-push-images.yml   → ghcr.io/qkr7287/hypercube-{backend,nginx} (public)
       ├── publish-deploy-bundle.yml → qkr7287/hypercube-deploy (public)
       └── sync-to-dcmtool.yml     → legacy DCMTool/dev mirror (no longer acted on)

hypercube-deploy/main
    (stopping point for now — future: hypercube-deploy push
     triggers self-hosted runner on server 16 to pull + up)
```

- Images: **public** (repo stays private). If images ever flip back to private, toggle via Profile → Packages → `hypercube-*` → Package settings → Visibility → Public.
- Bundle sync currently needs secret `DEPLOY_BUNDLE_PAT` on `qkr7287/HyperCube`. Until that secret is set the bundle workflow is a no-op and you have to copy `deploy/docker-compose.yml` + `deploy/.env.example` manually.

---

## Day-2 procedures (server 16)

### Update to latest main
```bash
ssh -i ~/.ssh/dcmtool_sync -p 2022 root@192.168.0.16
cd /home/agics-ai/docker/hypercube
docker compose pull
docker compose up -d
docker compose logs -f backend   # optional — watch the migrate + startup
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

### Full DB wipe (dev only — production lose data!)
```bash
docker compose down -v                 # -v deletes volumes
docker compose up -d                   # fresh DB, fresh migrations
```

---

## Dev on server 41 (remote Docker, local editing)

Run Docker on server 41 so your laptop stays light, but keep editing
the repo locally and watching the app at `localhost:...`. File sync
lives in a single Mutagen session; Docker commands run on the server
via SSH.

**Why this shape**
- Local Windows has the authoritative checkout (your editor, git,
  branches). Mutagen pushes writes up to the server within ms.
- Docker compose + containers live entirely on `192.168.0.41`. Nothing
  in your PC's RAM beyond the editor + terminal + browser.
- Source is visible on the server at `/home/stdt/ts/HyperCube/` for
  debugging — same bind mounts as local dev.

**Port plan on server 41**
| purpose | host port | notes |
|---|---|---|
| frontend (Vite) | `3090` | `3000` is already taken on 41 |
| backend (uvicorn) | `8000` | free |
| postgres | `15432` | dev default |
| redis | `16379` | dev default |

Configure these in `.env.dev` (see below).

### One-time setup (on your Windows PC)

1. Install Mutagen (CLI only — we're not using Mutagen Compose here):
   ```powershell
   winget install Mutagen.Mutagen
   ```

2. Generate an SSH key if you don't have one yet (or reuse `dcmtool_sync`),
   then copy its public half into server 41's `root` authorized keys.
   From a local terminal:
   ```bash
   type ~/.ssh/dcmtool_sync.pub
   ```
   Paste that line at the end of `/root/.ssh/authorized_keys` on 41. From
   that point on, key-based SSH works and you don't need the password.

3. Add an SSH alias so Mutagen and docker compose find the server
   easily. In `~/.ssh/config`:
   ```
   Host hc-dev-41
       HostName 192.168.0.41
       User root
       Port 2022
       IdentityFile ~/.ssh/dcmtool_sync
   ```

4. On the server, create the workspace folder (once):
   ```bash
   ssh hc-dev-41 "mkdir -p /home/stdt/ts/HyperCube"
   ```

5. Create `.env.dev` (local, git-ignored) with dev values. Minimum:
   ```dotenv
   DB_NAME=hypercube
   DB_USER=hypercube
   DB_PASSWORD=dev-local-pass
   DJANGO_ENV=dev
   DJANGO_SECRET_KEY=dev-insecure-key
   FE_PORT=3090
   # BE_PORT/DB_PORT/REDIS_PORT default to 8000/15432/16379
   ```
   Copy it up to the server too:
   ```bash
   scp .env.dev hc-dev-41:/home/stdt/ts/HyperCube/.env.dev
   ```
   (From here, the Mutagen session keeps it in sync automatically — but
   the server needs a copy for the first compose run.)

### Start the Mutagen sync session (once per machine)

```bash
mutagen sync create \
  --name=hypercube \
  --mode=two-way-resolved \
  --ignore-vcs \
  --ignore="node_modules,build,.svelte-kit,staticfiles,__pycache__,*.pyc,.pytest_cache,.claude,.playwright-mcp,.serena" \
  "C:\Users\agics\Desktop\workspace\01. git\HyperCube" \
  "hc-dev-41:/home/stdt/ts/HyperCube"
```

Check state anytime:
```bash
mutagen sync list
mutagen sync monitor hypercube    # tail live events
```

### Bring the stack up
```bash
ssh hc-dev-41 "
  cd /home/stdt/ts/HyperCube &&
  docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d
"
```

Watch logs:
```bash
ssh hc-dev-41 "cd /home/stdt/ts/HyperCube && docker compose logs -f backend"
```

### Access from your PC

Either use the server's address directly:
```
http://192.168.0.41:3090/
```

Or keep the `localhost:3090` feel with a persistent SSH tunnel:
```bash
ssh hc-dev-41 -L 3090:localhost:3090 -N &
# then browse http://localhost:3090/
```

### Day-to-day

- Save a file locally → Mutagen pushes within ~100 ms → Vite / uvicorn
  `--reload` picks it up and refreshes.
- `git` stays on the local PC. You commit as usual; the server never
  talks to GitHub for dev.
- To tear down: `ssh hc-dev-41 "cd /home/stdt/ts/HyperCube && docker compose down"`.
  Mutagen session can stay up; it pauses when idle.
- To stop the sync session: `mutagen sync terminate hypercube`.

### Gotchas to remember
- If Mutagen reports a conflict (`two-way-resolved` handles most, but
  not all), resolve it with `mutagen sync resolve hypercube`.
- Server 41 also hosts `hypercube-agent-prod-agent-1` which keeps a WS
  open to production (server 16). Running dev containers there does
  **not** interfere with that agent.
- Anything you mutate inside the running containers writes back to the
  bind-mounted filesystem (and then into your local checkout) — great
  for migrations, dangerous for accidental `python manage.py startapp`.
  Stay aware of it.

---

## Known quirks / limitations

| Area | Quirk | Impact |
|---|---|---|
| `/user/containers` time series | `7d` range actually returns the **last ~2 h** because `limit=240` is hard-capped. No downsampling yet. | Graphs for long ranges look truncated — visual only, no data loss. |
| Port validation | Neither frontend nor backend pre-checks whether the requested host port is free on the target agent. | Collisions surface as `failed` requests with the Docker error in `progress_message`. Fix needs agent-side netstat. |
| Agent WS response delivery | Prior to `ac0daaf` a disconnect mid-`compose_up` would strand the request in `deploying`. Fixed with an outbound queue + reconnect drain. Safety net on the server side (auto-heal stuck requests) is **not** implemented. | If you see `deploying` stuck >5 min, check agent logs; otherwise the queue fix handles it. |
| Legacy agent on 41 | `hypercube-agent-agent-1` keeps retrying an old `192.168.0.47:8000` backend. Harmless, but noisy in logs. | Skip, or remove if you want clean logs. |

---

## Port map on server 16 (snapshot)

| Host port | Service |
|---|---|
| 3334 | HyperCube production (nginx → backend) |
| 7003 | `agdevblog_frontend` (unrelated) |
| 5432 | `release-notes-db-1` Postgres (unrelated) |
| (others) | many third-party stacks — see `docker ps` |

Any new HyperCube dev stack on server 16 should pick non-conflicting ports (e.g. `3000`, `8000`, `15432`, `16379`).

---

## Contact points (external)

- HyperCube source: https://github.com/qkr7287/HyperCube (private)
- Deploy bundle:   https://github.com/qkr7287/hypercube-deploy (public)
- GHCR images:     https://github.com/qkr7287?tab=packages (public images, private profile)
- Agent repo: **separate repository**; operational contract lives in `docs/agent-mailbox.md` in this repo.
