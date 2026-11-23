# Throwaway probe image for ticket 18. No secrets, no personal details.
FROM python:3.14-slim

ARG SOLVER_COMMIT=ec65f5e2b2be34441cb4b2a9efafea1ec0fe3b79
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /opt
RUN git clone https://github.com/solioanalytics/open-fpl-solver.git \
 && cd open-fpl-solver && git checkout "$SOLVER_COMMIT" \
 && UV_PYTHON_DOWNLOADS=never uv sync --frozen --no-dev --python /usr/local/bin/python3.14 \
 && .venv/bin/python -m compileall -q . > /dev/null || true

COPY probe.py /app/probe.py
ENV PYTHONUNBUFFERED=1 SOLVER_DIR=/opt/open-fpl-solver
CMD ["python", "/app/probe.py"]
