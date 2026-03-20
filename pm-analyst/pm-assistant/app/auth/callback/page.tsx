"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { setToken } from "@/lib/auth";

function CallbackHandler() {
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("session_token");
    if (token) {
      setToken(token);
      window.location.href = "/";
    }
  }, [searchParams]);

  return <p className="text-muted-foreground">Completing sign in...</p>;
}

export default function AuthCallbackPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Suspense
        fallback={
          <p className="text-muted-foreground">Completing sign in...</p>
        }
      >
        <CallbackHandler />
      </Suspense>
    </div>
  );
}
