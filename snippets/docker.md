---
name: docker
description: Docker and container development conventions
tags: [docker, containers, devops]
version: 1
---

## Docker Conventions

### Dockerfiles

- Use official, versioned base images — never `latest` in production Dockerfiles.
- Put the most-frequently-changing instructions last to maximise layer caching.
- Combine `RUN` commands with `&&` and `\` line continuations to reduce layers.
- Use `COPY` instead of `ADD` unless you specifically need URL or tar-extraction support.
- Drop to a non-root user before the final `CMD`/`ENTRYPOINT`.
- Pin OS package versions when the exact version matters to reproducibility.

### Images

- Prefer multi-stage builds: compile/build in one stage, copy only the artifact into a
  minimal runtime image in the next.
- `.dockerignore` must list `node_modules/`, `.git/`, `__pycache__/`, and any secrets file.
- Image tags in CI: use the full commit SHA, not a branch name.

### Compose

- Define explicit service names, not just the default.
- Use named volumes for persistent data; never rely on anonymous volumes.
- Pass secrets via environment variables sourced from `.env` (gitignored), not hard-coded.
- Always specify `restart: unless-stopped` for long-running services.

### General

- Health checks should test the application's actual readiness, not just that the process started.
- Log to stdout/stderr, not to files inside the container.
