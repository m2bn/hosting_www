import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OrganizationMembersPage from "./page";
import { fetchOrganization, fetchOrganizationMembers } from "@/lib/platform-api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "org_1" }),
}));

vi.mock("@/lib/platform-api", () => ({
  fetchOrganization: vi.fn(),
  fetchOrganizationMembers: vi.fn(),
}));

describe("OrganizationMembersPage", () => {
  beforeEach(() => {
    vi.mocked(fetchOrganization).mockReset();
    vi.mocked(fetchOrganizationMembers).mockReset();
    vi.mocked(fetchOrganizationMembers).mockResolvedValue([
      { id: "mem_1", name: "Ada Admin", email: "ada@example.com", role: "admin", status: "active" },
    ]);
  });

  it("shows member management actions for admins", async () => {
    vi.mocked(fetchOrganization).mockResolvedValue({ id: "org_1", name: "Acme", role: "admin", status: "active" });

    render(createElement(OrganizationMembersPage));

    expect(await screen.findByRole("button", { name: "Invite member" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Change role" })).toBeInTheDocument();
  });

  it("hides member management actions for viewers", async () => {
    vi.mocked(fetchOrganization).mockResolvedValue({ id: "org_1", name: "Acme", role: "viewer", status: "active" });

    render(createElement(OrganizationMembersPage));

    expect(await screen.findByText("Ada Admin")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Invite member" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Change role" })).not.toBeInTheDocument();
  });
});
