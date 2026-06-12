"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { requestPasswordReset } from "@/lib/auth";
import { hasErrors, validateEmail } from "@/lib/auth-validation";
import { AuthCard } from "@/components/auth/AuthCard";
import { FormStatus } from "@/components/auth/FormStatus";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

const RESET_MESSAGE = "If the address is eligible, reset instructions will be sent shortly.";

export default function ForgotPasswordPage() {
  const [message, setMessage] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const nextErrors = { email: validateEmail(email) };
    setFieldErrors(nextErrors);
    if (hasErrors(nextErrors)) {
      return;
    }
    setIsSubmitting(true);
    try {
      await requestPasswordReset(email);
    } catch {
      // Keep account enumeration resistance: the visible result is intentionally identical.
    } finally {
      setMessage(RESET_MESSAGE);
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Reset password"
      description="Enter your email address. We will show the same response whether an account exists or not."
      footer={
        <Link href="/login" className="font-semibold text-brand-700">
          Back to sign in
        </Link>
      }
    >
      <form className="grid gap-4" onSubmit={onSubmit} noValidate>
        <FormStatus success={message} />
        <Input label="Email" name="email" type="email" autoComplete="email" error={fieldErrors.email} required />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Sending..." : "Send reset instructions"}
        </Button>
      </form>
    </AuthCard>
  );
}
