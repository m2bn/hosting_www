import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BillingUsagePage from "./page";
import { fetchBillingUsage } from "@/lib/platform-api";
import { usageFixture } from "../billing-test-data";

vi.mock("@/lib/platform-api", () => ({
  fetchBillingUsage: vi.fn(),
}));

describe("BillingUsagePage", () => {
  beforeEach(() => {
    vi.mocked(fetchBillingUsage).mockReset();
  });

  it("shows current usage against limits", async () => {
    vi.mocked(fetchBillingUsage).mockResolvedValue(usageFixture);

    render(createElement(BillingUsagePage));

    expect(await screen.findByText("2 / 5 projects")).toBeInTheDocument();
    expect(screen.getByText("42 / 100 GB")).toBeInTheDocument();
  });

  it("shows empty state when no usage exists", async () => {
    vi.mocked(fetchBillingUsage).mockResolvedValue([]);

    render(createElement(BillingUsagePage));

    expect(await screen.findByText("No usage reported")).toBeInTheDocument();
  });
});
