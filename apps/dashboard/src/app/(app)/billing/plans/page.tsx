"use client";

import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { BillingTabs } from "@/components/billing/BillingTabs";
import { CheckoutButton } from "@/components/billing/CheckoutButton";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { fetchBillingOverview, fetchBillingPlans } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function BillingPlansPage() {
  const overview = useApiResource(fetchBillingOverview, []);
  const plans = useApiResource(fetchBillingPlans, []);
  const canManageBilling = canAccess(overview.data ?? undefined, "billing:manage");

  return (
    <AppShell>
      <PageHeader title="Plans" description="Compare plan limits and start Stripe Checkout from a trusted backend-selected price." />
      <BillingTabs />
      {overview.isLoading || plans.isLoading ? <LoadingState label="Loading plans..." /> : null}
      {overview.error ? <ErrorState error={overview.error} /> : null}
      {plans.error ? <ErrorState error={plans.error} /> : null}
      {plans.data?.length === 0 ? <EmptyState title="No plans available" description="Plans will appear when billing configuration is published." /> : null}
      {plans.data && plans.data.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-3">
          {plans.data.map((plan) => (
            <Card key={plan.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <CardTitle>{plan.name}</CardTitle>
                  {plan.current ? <Badge variant="brand">Current</Badge> : null}
                </div>
                <p className="mt-2 text-sm text-subdued">{plan.price_label}</p>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm">
                <p className="text-subdued">{plan.description ?? "Managed SaaS hosting plan."}</p>
                <div className="flex justify-between gap-4"><span className="text-subdued">Projects</span><strong>{plan.limits.projects}</strong></div>
                <div className="flex justify-between gap-4"><span className="text-subdued">Storage</span><strong>{plan.limits.storage_gb} GB</strong></div>
                <div className="flex justify-between gap-4"><span className="text-subdued">Transfer</span><strong>{plan.limits.transfer_gb} GB</strong></div>
                {canManageBilling && !plan.current ? <CheckoutButton planCode={plan.code} label={`Choose ${plan.name}`} /> : null}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}
    </AppShell>
  );
}
