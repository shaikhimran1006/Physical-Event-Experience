#!/bin/sh
set -eu

cat > /usr/share/nginx/html/config.js <<EOF
window.__APP_CONFIG__ = {
  API_URL: "${API_URL:-http://localhost:8000}",
  WS_URL: "${WS_URL:-}",
  AUTH_TOKEN: "${AUTH_TOKEN:-}",
  WRITE_API_KEY: "${WRITE_API_KEY:-}",
  VENUE_ID: "${VENUE_ID:-stadium_01}",
};
EOF
