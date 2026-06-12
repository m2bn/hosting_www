import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";

export default function BillingPage() {
  return (
    <AppShell>
      <PageHeader title="Billing" description="Subscription status, invoices, usage limits, and Stripe Checkout entry points." actions={<Button>Change plan</Button>} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Current plan</CardTitle></CardHeader><CardContent><p className="text-3xl font-bold">Pro</p><p className="mt-2 text-sm text-subdued">Custom domains and container deployments enabled.</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Usage</CardTitle></CardHeader><CardContent><Alert variant="info">Storage is at 42% of the monthly limit.</Alert></CardContent></Card>
      </div>
    </AppShell>
  );
}
