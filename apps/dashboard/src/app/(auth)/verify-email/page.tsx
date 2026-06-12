"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { verifyEmail } from "@/lib/auth";
import { hasErrors, validateRequired } from "@/lib/auth-validation";
import { AuthCard } from "@/components/auth/AuthCard";
import { FormStatus } from "@/components/auth/FormStatus";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function VerifyEmailPage() {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const nextErrors = { token: validateRequired(token, "Verification token") };
    setFieldErrors(nextErrors);
    if (hasErrors(nextErrors)) {
      return;
    }
    setIsSubmitting(true);
    try {
      await verifyEmail(token);
      setMessage("Email verified. You can now sign in.");
    } catch {
      setError("Email verification could not be completed. Request a new verification email and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Verify email"
      description="Confirm your email address before accessing organization dashboards."
      footer={
        <Link href="/login" className="font-semibold text-brand-700">
          Back to sign in
        </Link>
      }
    >
      <form className="grid gap-4" onSubmit={onSubmit} noValidate>
        <FormStatus error={error} success={message} />
        <Input label="Verification token" name="token" value={token} onChange={(event) => setToken(event.target.value)} error={fieldErrors.token} required />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Verifying..." : "Verify email"}
        </Button>
      </form>
    </AuthCard>
  );
}
