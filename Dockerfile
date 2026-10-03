# syntax=docker/dockerfile:1
FROM node:26-bookworm-slim@sha256:662933cf47f013bc8e4beb31a6116448427a82057ba7c42c97e4c5ba766504c2 AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_DEPLOYMENT_MODE=hosted
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 AS uv
FROM python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed AS simulator
RUN apt-get update && apt-get install --no-install-recommends -y build-essential bison flex curl ca-certificates
COPY deploy/build_ngspice.sh /build_ngspice.sh
RUN bash /build_ngspice.sh /usr/local
FROM python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed AS runtime
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && \
    mkdir -p /run/circuit-lab /var/log/circuit-lab && \
    chown 10001:10001 /run/circuit-lab /var/log/circuit-lab
COPY backend/ backend/
COPY harness/ harness/
COPY circuits/ circuits/
ENV PATH="/app/.venv/bin:$PATH"
ARG CIRCUIT_BUILD_ID=local
ENV CIRCUIT_BUILD_ID=$CIRCUIT_BUILD_ID
LABEL org.opencontainers.image.source="https://github.com/johnfire/circuit-lab"
LABEL org.opencontainers.image.revision=$CIRCUIT_BUILD_ID

FROM runtime AS worker
COPY --from=simulator /usr/local/bin/ngspice /usr/local/bin/ngspice
COPY --from=simulator /usr/local/lib/ngspice /usr/local/lib/ngspice
COPY --from=simulator /usr/local/share/ngspice /usr/local/share/ngspice
USER 10001:10001
CMD ["python", "-m", "backend.worker_service"]

FROM runtime AS api
COPY --from=frontend /build/frontend/dist/ frontend/dist/
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "backend.application:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "32", "--no-access-log"]
