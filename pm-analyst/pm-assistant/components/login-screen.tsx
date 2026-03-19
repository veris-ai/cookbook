"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/components/providers/auth-provider";

export function LoginScreen() {
  const { login } = useAuth();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">PM Analyst</CardTitle>
          <CardDescription>
            Convert meeting transcripts into epics, features, and user stories.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={login} className="w-full" size="lg">
            Sign in with Microsoft
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
