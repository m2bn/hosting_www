"use client";

import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { BillingTabs } from "@/components/billing/BillingTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { fetchBillingInvoices } from "@/lib/platform-api";
import { useApiResource } from "@/hooks/useApiResource";

export default function BillingInvoicesPage() {
  const { data, error, isLoading } = useApiResource(fetchBillingInvoices, []);

  return (
    <AppShell>
      <PageHeader title="Invoices" description="Billing history and Stripe-hosted invoice links." />
      <BillingTabs />
      {isLoading ? <LoadingState label="Loading invoices..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data?.length === 0 ? <EmptyState title="No invoices" description="Invoices will appear after the first billing period." /> : null}
      {data && data.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Invoice</Th><Th>Status</Th><Th>Amount</Th><Th>Issued</Th><Th /></tr></TableHead>
              <TableBody>
                {data.map((invoice) => (
                  <tr key={invoice.id}>
                    <Td className="font-semibold">{invoice.number}</Td>
                    <Td><StatusBadge status={invoice.status} /></Td>
                    <Td>{invoice.amount_due}</Td>
                    <Td>{invoice.issued_at}</Td>
                    <Td>{invoice.hosted_invoice_url ? <a className="font-semibold text-brand-700" href={invoice.hosted_invoice_url}>Open</a> : null}</Td>
                  </tr>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </AppShell>
  );
}
