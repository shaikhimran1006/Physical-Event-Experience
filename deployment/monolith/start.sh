#!/bin/sh
set -eu

if [ -n "${API_URL:-}" ]; then
  API_URL_JS="\"${API_URL}\""
else
  API_URL_JS="window.location.origin"
fi

if [ -n "${WS_URL:-}" ]; then
  WS_URL_JS="\"${WS_URL}\""
else
  WS_URL_JS="window.location.origin.replace(/^http/i, 'ws')"
fi

cat > /usr/share/nginx/html/config.js <<EOF
window.__APP_CONFIG__ = {
  API_URL: ${API_URL_JS},
  WS_URL: ${WS_URL_JS},
};
EOF

uvicorn main:app --host 0.0.0.0 --port 8000 &

nginx -g "daemon off;"
