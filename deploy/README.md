# Deploy bundle — source of truth

This folder hosts the **source** of the appliance-deploy bundle:

- `docker-compose.yml` — six-service stack (no `build:` blocks; GHCR images only)
- `.env.example`       — required + optional variables

On every push to `main`, the workflow `.github/workflows/publish-deploy-bundle.yml`
copies these two files into the public distribution repo
[`qkr7287/hypercube-deploy`](https://github.com/qkr7287/hypercube-deploy)
and cuts a `sha-xxxxxxx` release there.

Operators install HyperCube from that public repo — they do **not**
clone this (private) source tree.

## Operator install guide

See the Korean guide in the public bundle:
<https://github.com/qkr7287/hypercube-deploy#readme>

## Editing

- Change a compose value or add/rename an env var **here**, not in the
  public repo. The sync workflow overwrites the public copies on next
  main push. (The public repo's `README.md` is maintained over there;
  the workflow never touches it.)
- After a merge into `main`, check the workflow run and confirm the new
  release appears at
  <https://github.com/qkr7287/hypercube-deploy/releases>.
