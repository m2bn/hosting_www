import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BillingPage from "./page";
import { fetchBillingOverview } from "@/lib/platform-api";
import { billingOverviewFixture } from "./billing-test-data";

vi.mock("@/lib/platform-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/platform-api")>("@/lib/platform-api");
  return {
    ...actual,
    fetchBillingOverview: vi.fn(),
  };
});

describe("BillingPage", () => {
  beforeEach(() => {
    vi.mocked(fetchBillingOverview).mockReset();
  });

  it("shows current plan, subscription status, limits, and usage", async () => {
    vi.mocked(fetchBillingOverview).mockResolvedValue(billingOverviewFixture("owner"));

    render(createElement(BillingPage));

    expect(await screen.findByText("Pro")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("100 GB")).toBeInTheDocument();
    expect(screen.getByText("42 / 100 GB")).toBeInTheDocument();
  });

  it("shows payment failed message", async () => {
    const overview = billingOverviewFixture("owner");
    overview.subscription = {
      id: "sub_1",
      status: "past_due",
      payment_failed: true,
      payment_failure_message: "Payment failed. Update billing details.",
    };
    vi.mocked(fetchBillingOverview).mockResolvedValue(overview);

    render(createElement(BillingPage));

    expect(await screen.findByText("Payment failed. Update billing details.")).toBeInTheDocument();
  });

  it("shows billing management for owner and billing roles only", async () => {
    vi.mocked(fetchBillingOverview).mockResolvedValue(billingOverviewFixture("owner"));
    const { unmount } = render(createElement(BillingPage));
    expect(await screen.findByRole("button", { name: "Manage billing" })).toBeInTheDocument();
    unmount();

    vi.mocked(fetchBillingOverview).mockResolvedValue(billingOverviewFixture("billing"));
    render(createElement(BillingPage));
    expect(await screen.findByRole("button", { name: "Manage billing" })).toBeInTheDocument();
  });

  it("hides billing management for viewer and developer roles", async () => {
    vi.mocked(fetchBillingOverview).mockResolvedValue(billingOverviewFixture("viewer"));
    const { unmount } = render(createElement(BillingPage));
    expect(await screen.findByText("Pro")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Manage billing" })).not.toBeInTheDocument();
    unmount();

    vi.mocked(fetchBillingOverview).mockResolvedValue(billingOverviewFixture("developer"));
    render(createElement(BillingPage));
    expect(await screen.findByText("Pro")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Manage billing" })).not.toBeInTheDocument();
  });
});
