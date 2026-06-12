"use client";

import { useState } from "react";
import { startStripeCheckout } from "@/lib/platform-api";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

type CheckoutButtonProps = {
  planCode?: string;
  label?: string;
};

export function CheckoutButton({ planCode, label = "Manage billing" }: CheckoutButtonProps) {
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onClick() {
    setError("");
    setIsSubmitting(true);
    try {
      const session = await startStripeCheckout(planCode);
      window.location.assign(session.checkout_url);
    } catch {
      setError("Could not start billing checkout. Try again later.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="grid gap-3">
      {error ? <Alert variant="danger">{error}</Alert> : null}
      <Button onClick={onClick} disabled={isSubmitting}>
        {isSubmitting ? "Opening checkout..." : label}
      </Button>
    </div>
  );
}
