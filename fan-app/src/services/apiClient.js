import { API_URL, buildAuthHeaders } from "./runtimeConfig";

const API_TIMEOUT_MS = 5000;

function toApiUrl(path) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_URL}${path.startsWith("/") ? "" : "/"}${path}`;
}

export async function requestJson(path, options = {}) {
  const {
    method = "GET",
    body,
    headers = {},
    auth = false,
    timeoutMs = API_TIMEOUT_MS,
  } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const mergedHeaders = {
    ...(auth ? buildAuthHeaders() : {}),
    ...headers,
  };

  if (body !== undefined && !mergedHeaders["Content-Type"]) {
    mergedHeaders["Content-Type"] = "application/json";
  }

  try {
    const response = await fetch(toApiUrl(path), {
      method,
      headers: mergedHeaders,
      body: body !== undefined
        ? typeof body === "string"
          ? body
          : JSON.stringify(body)
        : undefined,
      signal: controller.signal,
    });

    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    return {
      ok: response.ok,
      status: response.status,
      data,
    };
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Request timed out");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
