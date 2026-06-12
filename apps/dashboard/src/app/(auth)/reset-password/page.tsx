"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { resetPassword } from "@/lib/auth";
import { hasErrors, validatePassword, validatePasswordConfirmation, validateRequired } from "@/lib/auth-validation";
import { AuthCard } from "@/components/auth/AuthCard";
import { FormStatus } from "@/components/auth/FormStatus";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function ResetPasswordPage() {
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
    const form = new FormData(event.currentTarget);
    const formToken = String(form.get("token") ?? "");
    const password = String(form.get("password") ?? "");
    const confirmation = String(form.get("password_confirmation") ?? "");
    const nextErrors = {
      token: validateRequired(formToken, "Reset token"),
      password: validatePassword(password),
      password_confirmation: validatePasswordConfirmation(password, confirmation),
    };
    setFieldErrors(nextErrors);
    if (hasErrors(nextErrors)) {
      return;
    }
    setIsSubmitting(true);
    try {
      await resetPassword(formToken, password);
      setMessage("Password updated. You can sign in with the new password.");
    } catch {
      setError("The reset link could not be used. Request a new password reset and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Choose a new password"
      description="Reset links are single-use and should only be opened in this browser session."
      footer={
        <Link href="/login" className="font-semibold text-brand-700">
          Back to sign in
        </Link>
      }
    >
      <form className="grid gap-4" onSubmit={onSubmit} noValidate>
        <FormStatus error={error} success={message} />
        <Input label="Reset token" name="token" value={token} onChange={(event) => setToken(event.target.value)} error={fieldErrors.token} required />
        <Input label="New password" name="password" type="password" autoComplete="new-password" error={fieldErrors.password} required />
        <Input
          label="Confirm new password"
          name="password_confirmation"
          type="password"
          autoComplete="new-password"
          error={fieldErrors.password_confirmation}
          required
        />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Updating..." : "Update password"}
        </Button>
      </form>
    </AuthCard>
  );
}
