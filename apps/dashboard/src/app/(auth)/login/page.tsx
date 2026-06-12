"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";
import { hasErrors, validateEmail, validatePassword } from "@/lib/auth-validation";
import { AuthCard } from "@/components/auth/AuthCard";
import { FormStatus } from "@/components/auth/FormStatus";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const nextErrors = {
      email: validateEmail(email),
      password: validatePassword(password),
    };
    setFieldErrors(nextErrors);
    if (hasErrors(nextErrors)) {
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await login(email, password);
      router.push(result.requires_two_factor ? "/two-factor" : "/dashboard");
    } catch {
      setError("Unable to sign in with those credentials.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Sign in"
      description="Use your platform account. Sessions are kept in httpOnly cookies and protected with CSRF."
      footer={
        <>
          No account?{" "}
          <Link href="/register" className="font-semibold text-brand-700">
            Create one
          </Link>
          <span className="mx-2 text-border">/</span>
          <Link href="/forgot-password" className="font-semibold text-brand-700">
            Forgot password?
          </Link>
        </>
      }
    >
      <form className="grid gap-4" onSubmit={onSubmit} noValidate>
        <FormStatus error={error} />
        <Input label="Email" name="email" type="email" autoComplete="email" error={fieldErrors.email} required />
        <Input label="Password" name="password" type="password" autoComplete="current-password" error={fieldErrors.password} required />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in"}
        </Button>
      </form>
    </AuthCard>
  );
}
