FROM python:3.12-slim

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependency layer — cached unless pyproject changes
COPY pyproject.toml ./
RUN uv venv && uv pip install -e ".[dev]"

# Source. Bind-mounted over in dev (see docker-compose.yml) so edits are live.
COPY . .

EXPOSE 8000

# serve.py binds X_ZOHO_CATALYST_LISTEN_PORT when present (Zoho Catalyst AppSail custom
# runtime), else 8000 — the same image works in compose and on Catalyst. Note Catalyst
# accepts OCI images built for linux/amd64 only. Dev reload is added by docker-compose.
CMD ["python", "serve.py"]
