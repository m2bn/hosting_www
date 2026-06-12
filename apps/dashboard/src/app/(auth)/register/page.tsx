"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export default function RegisterPage() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      await apiRequest("/auth/register/", {
        method: "POST",
        body: {
          email: form.get("email"),
          password: form.get("password"),
          full_name: form.get("full_name"),
        },
        csrf: true,
      });
      setMessage("Registration started. Check your email to verify the account.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-muted px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create account</CardTitle>
          <p className="mt-1 text-sm text-subdued">Dashboard access uses cookie-based sessions and CSRF protection.</p>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={onSubmit}>
            {message ? <Alert variant="success">{message}</Alert> : null}
            {error ? <Alert variant="danger">{error}</Alert> : null}
            <Input label="Full name" name="full_name" autoComplete="name" required />
            <Input label="Email" name="email" type="email" autoComplete="email" required />
            <Input label="Password" name="password" type="password" autoComplete="new-password" required />
            <Button type="submit">Create account</Button>
          </form>
          <p className="mt-4 text-sm text-subdued">
            Already registered?{" "}
            <Link href="/login" className="font-semibold text-brand-700">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
