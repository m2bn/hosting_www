"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiRequest("/auth/login/", {
        method: "POST",
        body: {
          email: form.get("email"),
          password: form.get("password"),
        },
        csrf: true,
      });
      window.location.assign("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-muted px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <p className="mt-1 text-sm text-subdued">Use your platform account. Sessions are stored in secure cookies.</p>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={onSubmit}>
            {error ? <Alert variant="danger">{error}</Alert> : null}
            <Input label="Email" name="email" type="email" autoComplete="email" required />
            <Input label="Password" name="password" type="password" autoComplete="current-password" required />
            <Button type="submit">Sign in</Button>
          </form>
          <p className="mt-4 text-sm text-subdued">
            No account?{" "}
            <Link href="/register" className="font-semibold text-brand-700">
              Create one
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
