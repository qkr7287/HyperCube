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
