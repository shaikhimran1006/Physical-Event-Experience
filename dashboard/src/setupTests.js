import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

const mockCanvasContext = {
  fillRect: () => {},
  clearRect: () => {},
  getImageData: () => ({ data: [] }),
  putImageData: () => {},
  createImageData: () => ({ data: [] }),
  setTransform: () => {},
  drawImage: () => {},
  save: () => {},
  fillText: () => {},
  restore: () => {},
  beginPath: () => {},
  moveTo: () => {},
  lineTo: () => {},
  closePath: () => {},
  stroke: () => {},
  translate: () => {},
  scale: () => {},
  rotate: () => {},
  arc: () => {},
  fill: () => {},
  measureText: () => ({ width: 0 }),
  transform: () => {},
  rect: () => {},
  clip: () => {},
};

if (typeof HTMLCanvasElement !== "undefined") {
  Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
    configurable: true,
    writable: true,
    value: vi.fn(() => mockCanvasContext),
  });
}

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;

  constructor() {
    this.readyState = MockWebSocket.OPEN;
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
