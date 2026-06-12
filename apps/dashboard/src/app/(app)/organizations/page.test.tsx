import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OrganizationsPage from "./page";
import { fetchOrganizations } from "@/lib/platform-api";

vi.mock("@/lib/platform-api", () => ({
  fetchOrganizations: vi.fn(),
}));

describe("OrganizationsPage", () => {
  beforeEach(() => {
    vi.mocked(fetchOrganizations).mockReset();
  });

  it("renders an empty state", async () => {
    vi.mocked(fetchOrganizations).mockResolvedValue([]);

    render(createElement(OrganizationsPage));

    expect(screen.getByText("Loading organizations...")).toBeInTheDocument();
    expect(await screen.findByText("No organizations")).toBeInTheDocument();
  });

  it("hides create action for viewer-only organization access", async () => {
    vi.mocked(fetchOrganizations).mockResolvedValue([
      { id: "org_1", name: "Viewer Org", role: "viewer", status: "active", projects_count: 1 },
    ]);

    render(createElement(OrganizationsPage));

    expect(await screen.findByText("Viewer Org")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New organization" })).not.toBeInTheDocument();
  });

  it("shows create action for organization admins", async () => {
    vi.mocked(fetchOrganizations).mockResolvedValue([
      { id: "org_1", name: "Admin Org", role: "admin", status: "active", projects_count: 3 },
    ]);

    render(createElement(OrganizationsPage));

    expect(await screen.findByRole("button", { name: "New organization" })).toBeInTheDocument();
  });
});
