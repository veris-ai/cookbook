"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface ChatMessage {
  id: string;
  content: string;
  author: "user" | "agent";
  type: "message" | "error";
  timestamp: Date;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws");
const RECONNECT_DELAY = 3000;

export function useWebSocket(token: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");
  const [isAgentTyping, setIsAgentTyping] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const connect = useCallback(() => {
    if (!token) return;

    setConnectionStatus("connecting");
    const ws = new WebSocket(
      `${WS_URL}/ws/conversations?token=${encodeURIComponent(token)}`
    );

    ws.onopen = () => {
      setConnectionStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setIsAgentTyping(false);
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            content: data.content,
            author: "agent",
            type: data.type === "error" ? "error" : "message",
            timestamp: new Date(),
          },
        ]);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnectionStatus("disconnected");
      wsRef.current = null;
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => {
      setConnectionStatus("error");
    };

    wsRef.current = ws;
  }, [token]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      const msg: ChatMessage = {
        id: crypto.randomUUID(),
        content,
        author: "user",
        type: "message",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, msg]);
      setIsAgentTyping(true);
      wsRef.current.send(JSON.stringify({ content }));
    },
    []
  );

  return { messages, sendMessage, connectionStatus, isAgentTyping };
}
