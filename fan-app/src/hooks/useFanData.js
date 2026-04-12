import { useCallback, useEffect, useRef, useState } from "react";

import { requestJson } from "../services/apiClient";
import { VENUE_ID, WS_URL, buildWebSocketProtocols } from "../services/runtimeConfig";
import { useBackoffPolling } from "./useBackoffPolling";

const IS_TEST_ENV = import.meta.env.MODE === "test";

export function useFanData() {
  const [bestGate, setBestGate] = useState(null);
  const [bestConc, setBestConc] = useState(null);
  const [exitGuide, setExitGuide] = useState(null);
  const [queues, setQueues] = useState({});
  const [simStatus, setSimStatus] = useState({ running: false, phase: "idle", progress: 0 });
  const [notifications, setNotifications] = useState([]);
  const [connected, setConnected] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [lastError, setLastError] = useState("");

  const wsRef = useRef(null);
  const reconnectDelayRef = useRef(1000);
  const reconnectTimerRef = useRef(null);

  const hydrateFromWsPayload = useCallback((payload) => {
    if (payload?.queues) setQueues(payload.queues);
    if (payload?.best_gate) setBestGate(payload.best_gate);
    if (payload?.best_concession) setBestConc(payload.best_concession);
    if (payload?.simulation) setSimStatus(payload.simulation);
  }, []);

  const fetchSnapshot = useCallback(async () => {
    if (document.hidden) {
      return true;
    }

    try {
      const [gateRes, concRes, exitRes, queueRes, simRes, alertRes] = await Promise.all([
        requestJson(`/fan/${VENUE_ID}/best-gate`),
        requestJson(`/fan/${VENUE_ID}/best-concession`),
        requestJson(`/fan/${VENUE_ID}/exit-guidance`),
        requestJson(`/state/${VENUE_ID}/queues`),
        requestJson("/simulation/status"),
        requestJson(`/interventions/${VENUE_ID}?limit=20`),
      ]);

      if (gateRes.ok) setBestGate(gateRes.data);
      if (concRes.ok) setBestConc(concRes.data);
      if (exitRes.ok) setExitGuide(exitRes.data);
      if (queueRes.ok) setQueues(queueRes.data || {});
      if (simRes.ok) setSimStatus(simRes.data || {});
      if (alertRes.ok) setNotifications(alertRes.data || []);

      const anyOk = gateRes.ok || concRes.ok || exitRes.ok || queueRes.ok || simRes.ok;
      setConnected(anyOk);
      setLoading(false);
      setLastError(anyOk ? "" : "Backend is not responding");
      return anyOk;
    } catch (error) {
      setConnected(false);
      setLoading(false);
      setLastError(error?.message || "Failed to load fan app data");
      return false;
    }
  }, []);

  const connectWs = useCallback(() => {
    const protocols = buildWebSocketProtocols();
    const ws = protocols.length
      ? new WebSocket(`${WS_URL}/ws/fan/${VENUE_ID}`, protocols)
      : new WebSocket(`${WS_URL}/ws/fan/${VENUE_ID}`);

    wsRef.current = ws;

    ws.onopen = () => {
      reconnectDelayRef.current = 1000;
      setWsConnected(true);
      setConnected(true);
      setLoading(false);
      setLastError("");
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "fan_update") {
          hydrateFromWsPayload(payload);
          setConnected(true);
          setLoading(false);
          setLastError("");
        }
      } catch {
        // Ignore malformed payloads and continue processing next messages.
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onclose = () => {
      setWsConnected(false);
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }

      const nextDelay = Math.min(30000, reconnectDelayRef.current * 2);
      reconnectDelayRef.current = nextDelay;
      reconnectTimerRef.current = setTimeout(() => {
        connectWs();
      }, nextDelay);
    };
  }, [hydrateFromWsPayload]);

  useEffect(() => {
    if (IS_TEST_ENV) {
      fetchSnapshot();
      return undefined;
    }

    connectWs();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWs, fetchSnapshot]);

  useBackoffPolling({
    enabled: !wsConnected && !IS_TEST_ENV,
    onTick: fetchSnapshot,
    initialDelayMs: 3000,
    maxDelayMs: 30000,
    factor: 2,
    jitterRatio: 0.2,
  });

  return {
    bestGate,
    bestConc,
    exitGuide,
    queues,
    simStatus,
    notifications,
    connected,
    wsConnected,
    loading,
    lastError,
    refreshData: fetchSnapshot,
  };
}
