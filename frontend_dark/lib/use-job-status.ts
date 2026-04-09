"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed" | "unknown";
  current_step: string;
  progress: number;
  error_message?: string;
  updated_at?: string;
  // Terminal result fields (sent on complete/failed)
  contract_id?: string;
  package_id?: string;
  generated_code?: string;
  [key: string]: unknown;
}

type Transport = "websocket" | "polling" | "connecting";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getWsUrl(jobId: string): string {
  // Derive WS URL from API URL
  const base = API_URL.replace(/\/api\/v1\/?$/, "");
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}/ws/status/${jobId}`;
}

export function useJobStatus(jobId: string | null) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [transport, setTransport] = useState<Transport>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const isTerminalRef = useRef(false);

  const cleanup = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      if (wsRef.current.readyState <= WebSocket.OPEN) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  // Polling fallback
  const startPolling = useCallback(() => {
    if (!jobId || !isMountedRef.current || isTerminalRef.current) return;
    setTransport("polling");

    const poll = async () => {
      if (!isMountedRef.current || isTerminalRef.current) return;
      try {
        const resp = await fetch(`${API_URL}/status/${jobId}`);
        if (!resp.ok) return;
        const data: JobStatus = await resp.json();
        if (!isMountedRef.current) return;
        setStatus(data);

        if (data.status === "complete" || data.status === "failed") {
          isTerminalRef.current = true;
          return;
        }
      } catch {
        // Retry on error
      }

      if (isMountedRef.current && !isTerminalRef.current) {
        pollTimerRef.current = setTimeout(poll, 2000);
      }
    };

    poll();
  }, [jobId]);

  // WebSocket with polling fallback
  const connect = useCallback(() => {
    if (!jobId || !isMountedRef.current || isTerminalRef.current) return;

    setTransport("connecting");
    const wsUrl = getWsUrl(jobId);
    let ws: WebSocket;

    try {
      ws = new WebSocket(wsUrl);
    } catch {
      // WebSocket not supported or blocked — fall back to polling
      startPolling();
      return;
    }

    let opened = false;
    let pingInterval: ReturnType<typeof setInterval> | null = null;

    ws.onopen = () => {
      if (!isMountedRef.current) {
        ws.close();
        return;
      }
      opened = true;
      setTransport("websocket");

      // Keep alive every 25s
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      const text = event.data;

      // Ignore heartbeat and pong
      if (text === "pong") return;
      try {
        const data = JSON.parse(text);
        if (data.type === "heartbeat") return;

        setStatus(data as JobStatus);

        if (data.status === "complete" || data.status === "failed") {
          isTerminalRef.current = true;
          // Server will close, but clean up our side too
          if (pingInterval) clearInterval(pingInterval);
        }
      } catch {
        // Ignore unparseable messages
      }
    };

    ws.onerror = () => {
      // Will trigger onclose
    };

    ws.onclose = () => {
      if (pingInterval) clearInterval(pingInterval);
      wsRef.current = null;

      if (!isMountedRef.current || isTerminalRef.current) return;

      if (!opened) {
        // WS never connected — fall back to polling
        startPolling();
      } else {
        // WS dropped mid-stream — try reconnect after short delay, then fall back
        setTimeout(() => {
          if (isMountedRef.current && !isTerminalRef.current) {
            startPolling();
          }
        }, 1000);
      }
    };

    wsRef.current = ws;
  }, [jobId, startPolling]);

  useEffect(() => {
    isMountedRef.current = true;
    isTerminalRef.current = false;
    setStatus(null);
    setTransport("connecting");

    if (jobId) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, [jobId, connect, cleanup]);

  return { status, transport };
}
