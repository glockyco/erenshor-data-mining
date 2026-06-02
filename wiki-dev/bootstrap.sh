#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

BASE_URL="${BASE_URL:-http://localhost:8088}"
WIKI_NAME="${WIKI_NAME:-Erenshor Dev Wiki}"
ADMIN_USER="${ADMIN_USER:-WikiSysop}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-DevWikiPassword-2026}"

mkdir -p images runtime

docker compose up -d --build

if [ -f runtime/LocalSettings.php ]; then
  docker compose cp runtime/LocalSettings.php mediawiki:/var/www/html/LocalSettings.php
fi

if ! docker compose exec -T mediawiki test -f /var/www/html/LocalSettings.php; then
  docker compose exec -T mediawiki php maintenance/run.php install \
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

  docker compose exec -T mediawiki sh -c 'printf "\n# Erenshor local development extensions.\nrequire_once __DIR__ . '\''/LocalSettings.extra.php'\'';\n" >> /var/www/html/LocalSettings.php'
  docker compose cp mediawiki:/var/www/html/LocalSettings.php runtime/LocalSettings.php
fi

docker compose exec -T mediawiki php maintenance/run.php update --quick
