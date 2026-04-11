import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;

  constructor() {
    this.readyState = MockWebSocket.OPEN;
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
  }

  send() {}

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose();
  }
}

function mockPayload(url) {
  if (url.includes("/simulation/status")) {
    return { running: false, phase: "idle", progress: 0 };
  }
  if (url.includes("/state/") && url.includes("/zones")) {
    return {};
  }
  if (url.includes("/state/") && url.includes("/queues")) {
    return {};
  }
  if (url.includes("/interventions/")) {
    return [];
  }
  if (url.includes("/kpis/")) {
    return {};
  }
  return {};
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input) => {
      const url = String(input);
      return {
        ok: true,
        json: async () => mockPayload(url),
      };
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
