#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-wiki-dev}"
WIKI_HOST_PORT="${WIKI_HOST_PORT:-8088}"
BASE_URL="${BASE_URL:-http://localhost:${WIKI_HOST_PORT}}"
WIKI_NAME="${WIKI_NAME:-Erenshor Dev Wiki}"
ADMIN_USER="${ADMIN_USER:-WikiSysop}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-DevWikiPassword-2026}"
BOT_USER="${BOT_USER:-ErenshorBot}"
BOT_PASSWORD="${BOT_PASSWORD:-BotDevPassword-2026}"

compose() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" "$@"
}

if [[ "${WIKI_DB_MOUNT_TYPE:-bind}" == "bind" ]]; then
  mkdir -p "${WIKI_DB_MOUNT_SOURCE:-./db}"
fi
if [[ "${WIKI_IMAGES_MOUNT_TYPE:-bind}" == "bind" ]]; then
  mkdir -p "${WIKI_IMAGES_MOUNT_SOURCE:-./images}"
fi
if [[ "${WIKI_RUNTIME_MOUNT_TYPE:-bind}" == "bind" ]]; then
  mkdir -p "${WIKI_RUNTIME_MOUNT_SOURCE:-./runtime}"
fi

compose up -d --build

if compose exec -T mediawiki test -f /workspace/wiki-dev-runtime/LocalSettings.php; then
  compose exec -T mediawiki cp \
    /workspace/wiki-dev-runtime/LocalSettings.php \
    /var/www/html/LocalSettings.php
fi

if ! compose exec -T mediawiki test -f /var/www/html/LocalSettings.php; then
  compose exec -T mediawiki php maintenance/run.php install \
    --server="$BASE_URL" \
    --scriptpath='' \
    --dbtype=mysql \
    --dbserver=db \
    --dbname=mediawiki \
    --dbuser=wiki \
    --dbpass=wiki \
    --pass="$ADMIN_PASSWORD" \
    "$WIKI_NAME" \
    "$ADMIN_USER"

  compose exec -T mediawiki sh -c 'printf "\n# Erenshor local development extensions.\nrequire_once __DIR__ . '\''/LocalSettings.extra.php'\'';\n" >> /var/www/html/LocalSettings.php'
  compose exec -T mediawiki cp \
    /var/www/html/LocalSettings.php \
    /workspace/wiki-dev-runtime/LocalSettings.php
fi

compose exec -T mediawiki php maintenance/run.php update --quick

# Provision the deploy bot the wiki deploy pipeline and integration tests use.
# --bot grants the bot right so assert=bot edits succeed; --force keeps the
# password in sync on every bootstrap. The account is local-only.
compose exec -T mediawiki php maintenance/run.php createAndPromote --bot --force "$BOT_USER" "$BOT_PASSWORD"

API_WAIT_TIMEOUT="${API_WAIT_TIMEOUT:-120}"
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to verify MediaWiki API readiness" >&2
  exit 1
fi
if ! [[ "$API_WAIT_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
  echo "API_WAIT_TIMEOUT must be a positive integer" >&2
  exit 1
fi
API_URL="${BASE_URL%/}/api.php?action=query&meta=siteinfo&format=json"
API_DEADLINE=$((SECONDS + API_WAIT_TIMEOUT))
until curl --fail --silent --show-error --max-time 5 "$API_URL" >/dev/null; do
  if (( SECONDS >= API_DEADLINE )); then
    echo "Timed out waiting for the MediaWiki API at ${BASE_URL}" >&2
    exit 1
  fi
  sleep 2
done
