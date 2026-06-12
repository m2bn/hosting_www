"use client";

import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { BillingTabs } from "@/components/billing/BillingTabs";
import { UsageList } from "@/components/billing/UsageList";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { fetchBillingUsage } from "@/lib/platform-api";
import { useApiResource } from "@/hooks/useApiResource";

export default function BillingUsagePage() {
  const { data, error, isLoading } = useApiResource(fetchBillingUsage, []);

  return (
    <AppShell>
      <PageHeader title="Usage" description="Current consumption against plan limits." />
      <BillingTabs />
      {isLoading ? <LoadingState label="Loading usage..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data?.length === 0 ? <EmptyState title="No usage reported" description="Usage is reported after projects consume storage, transfer, or runtime resources." /> : null}
      {data && data.length > 0 ? (
        <Card>
          <CardHeader><CardTitle>Usage this period</CardTitle></CardHeader>
          <CardContent><UsageList usage={data} /></CardContent>
        </Card>
      ) : null}
    </AppShell>
  );
}
