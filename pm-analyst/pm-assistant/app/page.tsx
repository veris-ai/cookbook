"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { LoginScreen } from "@/components/login-screen";
import { ChatPanel } from "@/components/chat/chat-panel";

export default function Home() {
  const { isAuthenticated, token, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated || !token) {
    return <LoginScreen />;
  }

  return <ChatPanel token={token} />;
}
