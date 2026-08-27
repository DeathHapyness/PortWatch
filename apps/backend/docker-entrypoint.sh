#!/bin/sh
# Wrapper so a plain `docker run`/`docker compose up` with no configuration
# beyond the image itself still starts, instead of forcing every new user to
# go generate a token before they can see the dashboard once.
#
# PORTWATCH_BIND_HOST is always 0.0.0.0 inside this image (needed for Docker
# networking regardless of whether anything outside the container can reach
# it) — so the app's own startup check (core/config.py) always demands a
# non-empty PORTWATCH_API_TOKEN, by design, and this container would
# otherwise refuse to start with no explanation more specific than that
# check's error message. If the operator didn't provide one, generate a
# random one here instead of crash-looping.
#
# Not persisted anywhere on purpose (see CLAUDE.md: no persistence in the
# MVP) — it changes on every restart unless PORTWATCH_API_TOKEN is set
# explicitly. Fine for "just try it," not a substitute for a real token in
# an actual deployment (ver docs/security/operator-guide.md).
set -e

if [ -z "$PORTWATCH_API_TOKEN" ]; then
    PORTWATCH_API_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
    export PORTWATCH_API_TOKEN
    echo "===============================================================" >&2
    echo "PORTWATCH_API_TOKEN not set - generated one for this container run:" >&2
    echo "PORTWATCH_API_TOKEN=${PORTWATCH_API_TOKEN}" >&2
    echo "" >&2
    echo "Paste it into the dashboard (key icon in the header). It changes" >&2
    echo "on every restart - set PORTWATCH_API_TOKEN yourself to keep it" >&2
    echo "stable, see docs/reference/configuration.md." >&2
    echo "===============================================================" >&2
fi

exec uvicorn "$@"
