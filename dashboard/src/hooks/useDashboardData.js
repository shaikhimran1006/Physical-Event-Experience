import { useCallback, useEffect, useRef, useState } from "react";

import { requestJson } from "../services/apiClient";
import { VENUE_ID, WS_URL, buildWebSocketProtocols } from "../services/runtimeConfig";
import { useBackoffPolling } from "./useBackoffPolling";

const IS_TEST_ENV = import.meta.env.MODE === "test";

export function useDashboardData() {
  const [zones, setZones] = useState({});
  const [queues, setQueues] = useState({});
  const [interventions, setInterventions] = useState([]);
  const [kpis, setKpis] = useState({});
  const [simStatus, setSimStatus] = useState({ running: false, phase: "idle", progress: 0 });
  const [connected, setConnected] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [lastError, setLastError] = useState("");

  const wsRef = useRef(null);
  const reconnectDelayRef = useRef(1000);
  const reconnectTimerRef = useRef(null);

  const hydrateState = useCallback((payload) => {
    if (payload?.zones) setZones(payload.zones);
    if (payload?.queues) setQueues(payload.queues);
    if (payload?.interventions) setInterventions(payload.interventions);
    if (payload?.kpis) setKpis(payload.kpis);
    if (payload?.simulation) setSimStatus(payload.simulation);
  }, []);

  const fetchSnapshot = useCallback(async () => {
    if (document.hidden) {
      return true;
    }

    try {
      const [zRes, qRes, iRes, kRes, sRes] = await Promise.all([
        requestJson(`/state/${VENUE_ID}/zones`),
        requestJson(`/state/${VENUE_ID}/queues`),
        requestJson(`/interventions/${VENUE_ID}?limit=50`),
        requestJson(`/kpis/${VENUE_ID}`),
        requestJson("/simulation/status"),
      ]);

      if (zRes.ok) setZones(zRes.data || {});
      if (qRes.ok) setQueues(qRes.data || {});
      if (iRes.ok) setInterventions(iRes.data || []);
      if (kRes.ok) setKpis(kRes.data || {});
      if (sRes.ok) setSimStatus(sRes.data || {});

      const anyOk = zRes.ok || qRes.ok || iRes.ok || kRes.ok || sRes.ok;
      setConnected(anyOk);
      setLoading(false);
      setLastError(anyOk ? "" : "Backend is not responding");
      return anyOk;
    } catch (error) {
      setConnected(false);
      setLoading(false);
      setLastError(error?.message || "Failed to load dashboard data");
      return false;
    }
  }, []);

  const connectWs = useCallback(() => {
    const protocols = buildWebSocketProtocols();
    const ws = protocols.length
      ? new WebSocket(`${WS_URL}/ws/dashboard/${VENUE_ID}`, protocols)
      : new WebSocket(`${WS_URL}/ws/dashboard/${VENUE_ID}`);

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
        if (payload.type === "state_update") {
          hydrateState(payload);
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
  }, [hydrateState]);

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
    initialDelayMs: 2000,
    maxDelayMs: 30000,
    factor: 2,
    jitterRatio: 0.2,
  });

  return {
    zones,
    queues,
    interventions,
    kpis,
    simStatus,
    connected,
    wsConnected,
    loading,
    lastError,
    refreshData: fetchSnapshot,
  };
}
