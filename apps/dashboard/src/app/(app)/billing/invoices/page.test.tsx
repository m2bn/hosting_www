import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BillingInvoicesPage from "./page";
import { fetchBillingInvoices } from "@/lib/platform-api";
import { invoiceFixture } from "../billing-test-data";

vi.mock("@/lib/platform-api", () => ({
  fetchBillingInvoices: vi.fn(),
}));

describe("BillingInvoicesPage", () => {
  beforeEach(() => {
    vi.mocked(fetchBillingInvoices).mockReset();
  });

  it("shows invoice history", async () => {
    vi.mocked(fetchBillingInvoices).mockResolvedValue([invoiceFixture]);

    render(createElement(BillingInvoicesPage));

    expect(await screen.findByText("INV-001")).toBeInTheDocument();
    expect(screen.getByText("$29.00")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", invoiceFixture.hosted_invoice_url);
  });

  it("shows empty state when there are no invoices", async () => {
    vi.mocked(fetchBillingInvoices).mockResolvedValue([]);

    render(createElement(BillingInvoicesPage));

    expect(await screen.findByText("No invoices")).toBeInTheDocument();
  });
});
