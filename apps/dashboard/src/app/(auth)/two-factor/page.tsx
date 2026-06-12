"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { completeTwoFactor } from "@/lib/auth";
import { hasErrors, validateTwoFactorCode } from "@/lib/auth-validation";
import { AuthCard } from "@/components/auth/AuthCard";
import { FormStatus } from "@/components/auth/FormStatus";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function TwoFactorPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const code = String(form.get("code") ?? "");
    const recoveryCode = String(form.get("recovery_code") ?? "");
    const nextErrors = { code: validateTwoFactorCode(code, recoveryCode) };
    setFieldErrors(nextErrors);
    if (hasErrors(nextErrors)) {
      return;
    }
    setIsSubmitting(true);
    try {
      await completeTwoFactor(code, recoveryCode);
      router.push("/dashboard");
    } catch {
      setError("The two-factor challenge could not be verified.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Two-factor authentication"
      description="Enter your authenticator code. Recovery codes are accepted when your authenticator is unavailable."
      footer={
        <Link href="/login" className="font-semibold text-brand-700">
          Use a different account
        </Link>
      }
    >
      <form className="grid gap-4" onSubmit={onSubmit} noValidate>
        <FormStatus error={error} />
        <Input label="Authenticator code" name="code" inputMode="numeric" autoComplete="one-time-code" error={fieldErrors.code} />
        <Input label="Recovery code" name="recovery_code" autoComplete="off" />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Verifying..." : "Verify and continue"}
        </Button>
      </form>
    </AuthCard>
  );
}
