import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BillingPlansPage from "./page";
import { fetchBillingOverview, fetchBillingPlans } from "@/lib/platform-api";
import { billingOverviewFixture, planFixture } from "../billing-test-data";

vi.mock("@/lib/platform-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/platform-api")>("@/lib/platform-api");
  return {
    ...actual,
    fetchBillingOverview: vi.fn(),
    fetchBillingPlans: vi.fn(),
  };
});

describe("BillingPlansPage", () => {
  beforeEach(() => {
    vi.mocked(fetchBillingOverview).mockReset();
    vi.mocked(fetchBillingPlans).mockReset();
  });

  it("shows checkout for non-current plans when billing can manage payments", async () => {
    vi.mocked(fetchBillingOverview).mockResolvedValue(billingOverviewFixture("billing"));
    vi.mocked(fetchBillingPlans).mockResolvedValue([
      planFixture,
      { ...planFixture, id: "plan_business", name: "Business", code: "business", current: false, price_label: "$99/month" },
    ]);

    render(createElement(BillingPlansPage));

    expect(await screen.findByRole("button", { name: "Choose Business" })).toBeInTheDocument();
  });

  it("hides checkout from developers", async () => {
    vi.mocked(fetchBillingOverview).mockResolvedValue(billingOverviewFixture("developer"));
    vi.mocked(fetchBillingPlans).mockResolvedValue([{ ...planFixture, id: "plan_business", name: "Business", code: "business", current: false }]);

    render(createElement(BillingPlansPage));

    expect(await screen.findByText("Business")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Choose Business" })).not.toBeInTheDocument();
  });
});
