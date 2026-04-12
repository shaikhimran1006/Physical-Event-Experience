const runtimeConfig = window.__APP_CONFIG__ || {};

function normalizeBaseUrl(url, fallback) {
  return (url || fallback).replace(/\/+$/, "");
}

export const API_URL = normalizeBaseUrl(
  runtimeConfig.API_URL,
  import.meta.env.VITE_API_URL || "http://localhost:8000",
);

export const WS_URL = normalizeBaseUrl(
  runtimeConfig.WS_URL,
  import.meta.env.VITE_WS_URL || API_URL.replace(/^http/i, "ws"),
);

export const VENUE_ID =
  runtimeConfig.VENUE_ID || import.meta.env.VITE_VENUE_ID || "stadium_01";

export const AUTH_TOKEN =
  runtimeConfig.AUTH_TOKEN || import.meta.env.VITE_AUTH_TOKEN || "";

export const WRITE_API_KEY =
  runtimeConfig.WRITE_API_KEY || import.meta.env.VITE_WRITE_API_KEY || "";

export function buildAuthHeaders() {
  const headers = {};

  if (AUTH_TOKEN) {
    headers.Authorization = `Bearer ${AUTH_TOKEN}`;
  }

  if (WRITE_API_KEY) {
    headers["X-API-Key"] = WRITE_API_KEY;
  }

  return headers;
}

export function buildWebSocketProtocols() {
  if (AUTH_TOKEN) {
    return [`bearer.${AUTH_TOKEN}`];
  }

  if (WRITE_API_KEY) {
    return [`apikey.${WRITE_API_KEY}`];
  }

  return [];
}
