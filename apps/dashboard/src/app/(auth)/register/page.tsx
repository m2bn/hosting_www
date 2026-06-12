"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { register } from "@/lib/auth";
import { hasErrors, validateEmail, validatePassword, validatePasswordConfirmation, validateRequired } from "@/lib/auth-validation";
import { AuthCard } from "@/components/auth/AuthCard";
import { FormStatus } from "@/components/auth/FormStatus";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function RegisterPage() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const form = new FormData(event.currentTarget);
    const fullName = String(form.get("full_name") ?? "");
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const passwordConfirmation = String(form.get("password_confirmation") ?? "");
    const nextErrors = {
      full_name: validateRequired(fullName, "Full name"),
      email: validateEmail(email),
      password: validatePassword(password),
      password_confirmation: validatePasswordConfirmation(password, passwordConfirmation),
    };
    setFieldErrors(nextErrors);
    if (hasErrors(nextErrors)) {
      return;
    }
    setIsSubmitting(true);
    try {
      await register({ email, password, full_name: fullName });
      setMessage("Registration started. Check your email to verify the account.");
    } catch {
      setError("Registration could not be completed. Check the form and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Create account"
      description="Dashboard access uses cookie-based sessions and CSRF protection."
      footer={
        <>
          Already registered?{" "}
          <Link href="/login" className="font-semibold text-brand-700">
            Sign in
          </Link>
        </>
      }
    >
      <form className="grid gap-4" onSubmit={onSubmit} noValidate>
        <FormStatus error={error} success={message} />
        <Input label="Full name" name="full_name" autoComplete="name" error={fieldErrors.full_name} required />
        <Input label="Email" name="email" type="email" autoComplete="email" error={fieldErrors.email} required />
        <Input label="Password" name="password" type="password" autoComplete="new-password" error={fieldErrors.password} required />
        <Input
          label="Confirm password"
          name="password_confirmation"
          type="password"
          autoComplete="new-password"
          error={fieldErrors.password_confirmation}
          required
        />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating..." : "Create account"}
        </Button>
      </form>
    </AuthCard>
  );
}
