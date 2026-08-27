# syntax=docker/dockerfile:1

FROM python:3.12-alpine@sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31 AS builder

ARG UV_VERSION=0.12.5

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --locked --no-dev --no-editable --no-cache


FROM python:3.12-alpine@sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31 AS runtime

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORTWATCH_BIND_HOST=0.0.0.0

RUN addgroup -S -g 10001 portwatch \
    && adduser -S -D -H -u 10001 -G portwatch portwatch

WORKDIR /app

COPY --from=builder --chown=portwatch:portwatch /app/.venv /app/.venv
COPY --chown=portwatch:portwatch docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["portwatch_backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
