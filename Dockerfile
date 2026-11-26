# The bot's one image (ADR 0003, ADR 0004). Railway builds it from main after CI passes; CI builds
# the same file on every pull request and scans it with Trivy.
#
#   docker build --build-arg GIT_SHA="$(git rev-parse HEAD)" -t fplbot .
#
# Railway service settings: pre-deploy command `fplbot migrate` (alembic upgrade head, in a
# short-lived container from this image), start command left empty (CMD below).
# Base images are pinned by digest; Dependabot (docker ecosystem) proposes updates weekly.

FROM ghcr.io/astral-sh/uv:0.12.1@sha256:cf4eedcaa81655197f625739489effcbe71b61ceb1506f332c3facae5deceded AS uv

FROM python:3.14-slim-trixie@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.14 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1
WORKDIR /src
# Dependencies first (from the hashed lockfile only), so code changes reuse this layer.
COPY core/pyproject.toml core/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
# Then the bot itself, installed as a regular (non-editable) package: no tests or fixtures.
COPY core/README.md ./
COPY core/src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14-slim-trixie@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b
# The bot never installs anything at runtime: drop the base image's pip (and the copies of
# urllib3, msgpack and setuptools it vendors, which Trivy would otherwise flag).
RUN python -m pip uninstall --yes --quiet pip \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin fplbot
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER 10001:10001
# The commit this image was built from, for local builds: the `ready sha=<commit>` startup line and
# /status. Left empty by default, so on Railway the bot falls back to RAILWAY_GIT_COMMIT_SHA, which
# Railway sets at runtime for deploys from GitHub. Last, so a new commit rebuilds only this layer.
ARG GIT_SHA=
ENV GIT_SHA=$GIT_SHA
CMD ["fplbot"]
