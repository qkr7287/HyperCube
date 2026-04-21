# HyperCube — Appliance Deploy

Pull-and-run deployment. The target host only needs Docker — no git, no
Node, no Python, no build tools. All images live on
[GHCR](https://ghcr.io) (`ghcr.io/qkr7287/hypercube-*`) and are built by
GitHub Actions on every push to `main`.

## What you need on the target host

- Docker Engine 24+
- Docker Compose v2 (bundled with Docker Desktop or `docker-compose-plugin` package)
- Outbound access to `ghcr.io`

That's it. No repo clone.

## 1. Drop the deploy files onto the host

Any two files are enough:

- `docker-compose.yml` (this folder)
- `.env` (create from `.env.example`)

Grab them straight from GitHub, for example:

```bash
mkdir -p /opt/hypercube && cd /opt/hypercube

curl -fLO https://raw.githubusercontent.com/qkr7287/HyperCube/main/deploy/docker-compose.yml
curl -fL  https://raw.githubusercontent.com/qkr7287/HyperCube/main/deploy/.env.example -o .env
```

Edit `.env` and set at minimum:

- `DJANGO_SECRET_KEY` — any long random string
- `DB_PASSWORD`       — strong random password
- `DJANGO_ALLOWED_HOSTS` — the hostnames/IPs you'll access the service from

Optional:

- `IMAGE_TAG` — pin to `sha-abc1234` to freeze a specific build. Default `latest`.
- `HC_PORT`   — host port for the web tier. Default `7003`.

## 2. Pull + run

```bash
docker compose pull        # fetches backend + nginx images from GHCR
docker compose up -d       # starts all six services

docker compose logs -f backend   # watch the first boot migrate + start
```

Open `http://<host>:7003/hypercube`.

## 3. Updating

```bash
docker compose pull
docker compose up -d
```

Django migrations run automatically on backend container start, so a
fresh `pull + up` is enough for most releases. For major schema work,
dump Postgres first:

```bash
docker compose exec postgres pg_dump -U hypercube hypercube > backup.sql
```

## 4. Creating the first admin

```bash
docker compose exec backend python manage.py createsuperuser
```

## Services included

| Container        | Image                                           | Role                             |
|------------------|-------------------------------------------------|----------------------------------|
| `hc-nginx`       | `ghcr.io/qkr7287/hypercube-nginx:<tag>`         | static SPA + reverse proxy       |
| `hc-backend`     | `ghcr.io/qkr7287/hypercube-backend:<tag>`       | Django (uvicorn, ASGI)           |
| `hc-celery-worker` | same image, different command                 | background task worker           |
| `hc-celery-beat` | same image, different command                   | periodic task scheduler          |
| `hc-postgres`    | `pgvector/pgvector:pg16`                        | relational DB (with pgvector)    |
| `hc-redis`       | `redis:7-alpine`                                | channels + cache + celery broker |

## Tear down

```bash
docker compose down         # stop, keep Postgres data
docker compose down -v      # stop AND wipe Postgres data (careful)
```

## Troubleshooting

- **`pull` fails with 403 `denied`** — the image is private and you
  haven't authenticated. Run once:
  ```bash
  echo <PAT> | docker login ghcr.io -u <github-username> --password-stdin
  ```
  where `<PAT>` is a GitHub Personal Access Token with `read:packages`
  scope. `~/.docker/config.json` caches it for future pulls.
- **Backend crash loops on first boot** — usually `DB_PASSWORD` or
  `DJANGO_SECRET_KEY` is missing from `.env`. `docker compose logs backend`
  will say so.
