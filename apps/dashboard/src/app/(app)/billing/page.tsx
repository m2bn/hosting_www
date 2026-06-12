"use client";

import { Alert } from "@/components/ui/Alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { BillingTabs } from "@/components/billing/BillingTabs";
import { CheckoutButton } from "@/components/billing/CheckoutButton";
import { UsageList } from "@/components/billing/UsageList";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { fetchBillingOverview } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function BillingPage() {
  const { data, error, isLoading } = useApiResource(fetchBillingOverview, []);
  const canManageBilling = canAccess(data ?? undefined, "billing:manage");

  return (
    <AppShell>
      <PageHeader
        title="Billing"
        description="Subscription status, invoices, usage limits, and Stripe Checkout entry points."
        actions={canManageBilling ? <CheckoutButton label="Manage billing" /> : null}
      />
      <BillingTabs />
      {isLoading ? <LoadingState label="Loading billing data..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="grid gap-6">
          {data.subscription.payment_failed ? (
            <Alert variant="danger">{data.subscription.payment_failure_message ?? "Payment failed. Update billing details to keep services active."}</Alert>
          ) : null}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Current plan</CardTitle></CardHeader>
              <CardContent className="grid gap-3">
                <p className="text-3xl font-bold">{data.current_plan.name}</p>
                <p className="text-sm text-subdued">{data.current_plan.description ?? data.current_plan.price_label}</p>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-subdued">Subscription</span>
                  <StatusBadge status={data.subscription.status} />
                </div>
                {data.subscription.current_period_end ? (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-subdued">Renews</span>
                    <strong>{data.subscription.current_period_end}</strong>
                  </div>
                ) : null}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Plan limits</CardTitle></CardHeader>
              <CardContent className="grid gap-3 text-sm">
                <div className="flex justify-between gap-4"><span className="text-subdued">Projects</span><strong>{data.current_plan.limits.projects}</strong></div>
                <div className="flex justify-between gap-4"><span className="text-subdued">Storage</span><strong>{data.current_plan.limits.storage_gb} GB</strong></div>
                <div className="flex justify-between gap-4"><span className="text-subdued">Transfer</span><strong>{data.current_plan.limits.transfer_gb} GB</strong></div>
                <div className="flex justify-between gap-4"><span className="text-subdued">Custom domains</span><strong>{data.current_plan.limits.custom_domains ? "Enabled" : "Disabled"}</strong></div>
                <div className="flex justify-between gap-4"><span className="text-subdued">Container deployments</span><strong>{data.current_plan.limits.container_deployments ? "Enabled" : "Disabled"}</strong></div>
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader><CardTitle>Current usage</CardTitle></CardHeader>
            <CardContent>{data.usage.length > 0 ? <UsageList usage={data.usage} /> : <EmptyState title="No usage yet" description="Usage will appear after projects start consuming resources." />}</CardContent>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
