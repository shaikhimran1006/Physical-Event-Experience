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

function queuePayload() {
  return {
    gate_A: {
      point_type: "gate",
      avgWaitMinutes: 6,
      currentQueueLength: 24,
      status: "orange",
    },
    gate_B: {
      point_type: "gate",
      avgWaitMinutes: 2,
      currentQueueLength: 8,
      status: "green",
    },
    conc_1: {
      point_type: "concession",
      avgWaitMinutes: 5,
      currentQueueLength: 20,
      status: "yellow",
    },
    rest_1: {
      point_type: "restroom",
      avgWaitMinutes: 3,
      currentQueueLength: 6,
      status: "green",
    },
  };
}

function mockPayload(url) {
  if (url.includes("/best-gate")) {
    return {
      best_gate: "gate_B",
      wait_minutes: 2,
      all_gates: {
        gate_A: { avgWaitMinutes: 6, currentQueueLength: 24 },
        gate_B: { avgWaitMinutes: 2, currentQueueLength: 8 },
      },
    };
  }
  if (url.includes("/best-concession")) {
    return {
      best_concession: "conc_1",
      wait_minutes: 5,
      all_concessions: {
        conc_1: { avgWaitMinutes: 5, currentQueueLength: 20 },
      },
    };
  }
  if (url.includes("/exit-guidance")) {
    return {
      best_exit: "gate_B",
      message: "Exit via Gate B — currently clear",
      all_exits: {
        gate_A: { congestionScore: 0.4, status: "yellow" },
        gate_B: { congestionScore: 0.2, status: "green" },
      },
    };
  }
  if (url.includes("/state/") && url.includes("/queues")) {
    return queuePayload();
  }
  if (url.includes("/simulation/status")) {
    return { phase: "pre_game", progress: 25 };
  }
  if (url.includes("/interventions/")) {
    return [];
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
