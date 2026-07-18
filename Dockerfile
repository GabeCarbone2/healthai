FROM node:22-alpine AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM caddy:2.10-alpine AS web

COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /build/dist /srv


FROM python:3.12-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
RUN python -m pip install --no-cache-dir .

COPY alembic.ini ./
COPY backend/ backend/
COPY migrations/ migrations/
COPY reports/model_comparison.json reports/model_comparison.json
COPY models/pima_selected.joblib models/pima_selected.joblib
COPY models/nhanes_selected.joblib models/nhanes_selected.joblib

RUN groupadd --system healthai \
    && useradd --system --gid healthai --home-dir /app healthai \
    && mkdir -p /app/data \
    && chown -R healthai:healthai /app

USER healthai

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*", "--no-access-log"]
