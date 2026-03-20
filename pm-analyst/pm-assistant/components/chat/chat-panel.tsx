"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/components/chat/chat-message";
import { ChatInput } from "@/components/chat/chat-input";
import { useWebSocket, type ConnectionStatus } from "@/hooks/use-websocket";
import { useAuth } from "@/components/providers/auth-provider";

function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const variant =
    status === "connected"
      ? "default"
      : status === "connecting"
        ? "secondary"
        : "destructive";

  const label =
    status === "connected"
      ? "Connected"
      : status === "connecting"
        ? "Connecting..."
        : status === "error"
          ? "Connection error"
          : "Disconnected";

  return (
    <Badge variant={variant} className="text-xs">
      <span
        className={`mr-1.5 inline-block h-2 w-2 rounded-full ${
          status === "connected"
            ? "bg-green-400"
            : status === "connecting"
              ? "bg-yellow-400 animate-pulse"
              : "bg-red-400"
        }`}
      />
      {label}
    </Badge>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 px-4">
      <div className="flex items-center gap-1 rounded-2xl bg-muted px-4 py-3">
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:300ms]" />
      </div>
    </div>
  );
}

export function ChatPanel({ token }: { token: string }) {
  const { logout } = useAuth();
  const { messages, sendMessage, connectionStatus, isAgentTyping } =
    useWebSocket(token);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAgentTyping]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b px-6 py-3">
        <h1 className="text-lg font-semibold">PM Analyst</h1>
        <div className="flex items-center gap-3">
          <ConnectionBadge status={connectionStatus} />
          <Button variant="ghost" size="sm" onClick={logout}>
            Sign out
          </Button>
        </div>
      </header>

      {/* Messages */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-4 py-6">
          {isEmpty && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Welcome to PM Analyst
              </h2>
              <p className="max-w-md text-muted-foreground">
                Start by uploading a meeting transcript or ask me to pull your
                recent Teams meetings.
              </p>
            </div>
          )}
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          {isAgentTyping && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <ChatInput
        onSend={sendMessage}
        disabled={connectionStatus !== "connected"}
      />
    </div>
  );
}
