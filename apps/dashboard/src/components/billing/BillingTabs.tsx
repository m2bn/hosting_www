import { PageTabs } from "@/components/data/PageTabs";

export function BillingTabs() {
  return (
    <PageTabs
      tabs={[
        { href: "/billing", label: "Overview" },
        { href: "/billing/plans", label: "Plans" },
        { href: "/billing/invoices", label: "Invoices" },
        { href: "/billing/usage", label: "Usage" },
      ]}
    />
  );
}
