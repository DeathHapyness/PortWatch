# syntax=docker/dockerfile:1

FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS builder

WORKDIR /app

RUN corepack enable

# Lockfile + manifest first so dependency install is cached independently of
# source changes.
COPY package.json pnpm-lock.yaml ./
RUN corepack use pnpm@11.24.0
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build


FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0 AS runtime

# PORTWATCH_BACKEND_URL is substituted into the nginx config at container
# startup (nginx's built-in envsubst-on-templates entrypoint hook) — it is
# never baked into the built JS bundle. Point it at wherever the backend is
# actually reachable from this container (e.g. http://backend:8000 on a
# shared Docker network). Defaults to localhost, which only works if the
# backend is reachable there too (host networking) — set it explicitly in
# any real deployment.
ENV PORTWATCH_BACKEND_URL=http://127.0.0.1:8000

COPY --chown=nginx:nginx nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/"]
