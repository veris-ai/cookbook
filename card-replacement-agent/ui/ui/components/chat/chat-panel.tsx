"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatMessage, type ChatMessageData } from "@/components/chat/chat-message";
import { ChatInput } from "@/components/chat/chat-input";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

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

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = useCallback(
    async (content: string) => {
      const userMsg: ChatMessageData = {
        id: crypto.randomUUID(),
        author: "user",
        content,
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const payload: Record<string, string> = { message: content };
        if (sessionId) payload.session_id = sessionId;

        const res = await fetch(`${API_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        setSessionId(data.session_id);

        const agentMsg: ChatMessageData = {
          id: crypto.randomUUID(),
          author: "agent",
          content: data.response,
        };
        setMessages((prev) => [...prev, agentMsg]);
      } catch (err) {
        const errorMsg: ChatMessageData = {
          id: crypto.randomUUID(),
          author: "agent",
          content: err instanceof Error ? err.message : "Something went wrong.",
          type: "error",
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <h1 className="text-lg font-semibold">Card Replacement Agent</h1>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-4 py-6">
          {isEmpty && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Welcome to Card Support
              </h2>
              <p className="max-w-md text-muted-foreground">
                I can help you with card replacements, status updates, and
                freezing lost or stolen cards.
              </p>
            </div>
          )}
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          {isLoading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
