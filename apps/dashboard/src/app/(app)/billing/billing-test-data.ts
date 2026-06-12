import { BillingOverview, BillingPlan, Invoice, UsageMetric } from "@/lib/platform-api";

export const usageFixture: UsageMetric[] = [
  { key: "projects", label: "Projects", used: 2, limit: 5, unit: "projects" },
  { key: "storage_gb", label: "Storage", used: 42, limit: 100, unit: "GB" },
];

export const planFixture: BillingPlan = {
  id: "plan_pro",
  name: "Pro",
  code: "pro",
  price_label: "$29/month",
  description: "Custom domains and container deployments.",
  current: true,
  limits: {
    projects: 5,
    storage_gb: 100,
    transfer_gb: 1000,
    custom_domains: true,
    container_deployments: true,
  },
};

export function billingOverviewFixture(role: BillingOverview["role"]): BillingOverview {
  return {
    organization_id: "org_1",
    organization_name: "Acme",
    role,
    current_plan: planFixture,
    subscription: {
      id: "sub_1",
      status: "active",
      current_period_end: "2026-07-12",
    },
    usage: usageFixture,
    recent_invoices: [],
  };
}

export const invoiceFixture: Invoice = {
  id: "inv_1",
  number: "INV-001",
  status: "paid",
  amount_due: "$29.00",
  issued_at: "2026-06-12",
  hosted_invoice_url: "https://billing.stripe.test/invoices/inv_1",
};
