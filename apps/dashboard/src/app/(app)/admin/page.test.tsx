import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminPage from "./page";
import { blockOperatorOrganization, fetchOperatorDashboard, OperatorDashboard } from "@/lib/platform-api";

vi.mock("@/lib/platform-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/platform-api")>("@/lib/platform-api");
  return {
    ...actual,
    blockOperatorOrganization: vi.fn(),
    blockOperatorProject: vi.fn(),
    fetchOperatorDashboard: vi.fn(),
    unblockOperatorOrganization: vi.fn(),
  };
});

function dashboardFixture(overrides: Partial<OperatorDashboard> = {}): OperatorDashboard {
  return {
    access: {
      is_operator: true,
      two_factor_verified: true,
      user_role: "operator",
    },
    organizations: [
      {
        id: "org_1",
        name: "Acme Hosting",
        status: "active",
        plan: "Business",
        billing_status: "active",
        projects_count: 3,
      },
    ],
    projects: [
      {
        id: "project_1",
        name: "Marketing Site",
        organization_name: "Acme Hosting",
        status: "active",
        deployment_status: "active",
        billing_status: "active",
        domain_status: "verified",
        certificate_status: "active",
      },
    ],
    audit_logs: [
      {
        id: "audit_1",
        actor: "operator@example.com",
        action: "operator.login",
        target_type: "operator_session",
        target_id: "session_1",
        created_at: "2026-06-12T10:00:00Z",
      },
    ],
    ...overrides,
  };
}

describe("AdminPage", () => {
  beforeEach(() => {
    vi.mocked(fetchOperatorDashboard).mockReset();
    vi.mocked(blockOperatorOrganization).mockReset();
  });

  it("denies access for a regular user", async () => {
    vi.mocked(fetchOperatorDashboard).mockResolvedValue(
      dashboardFixture({ access: { is_operator: false, two_factor_verified: false, user_role: "user" } }),
    );

    render(createElement(AdminPage));

    expect(await screen.findByText("Operator access required. Organization owners and regular users cannot use this panel.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Block organization" })).not.toBeInTheDocument();
    expect(screen.queryByText("Marketing Site")).not.toBeInTheDocument();
  });

  it("denies access for an organization owner", async () => {
    vi.mocked(fetchOperatorDashboard).mockResolvedValue(
      dashboardFixture({ access: { is_operator: false, two_factor_verified: true, user_role: "owner" } }),
    );

    render(createElement(AdminPage));

    expect(await screen.findByText("Operator access required. Organization owners and regular users cannot use this panel.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Organizations" })).not.toBeInTheDocument();
  });

  it("denies access for an operator without 2FA", async () => {
    vi.mocked(fetchOperatorDashboard).mockResolvedValue(
      dashboardFixture({ access: { is_operator: true, two_factor_verified: false, user_role: "operator" } }),
    );

    render(createElement(AdminPage));

    expect(await screen.findByText("Two-factor verification required before accessing operator resources.")).toBeInTheDocument();
    expect(screen.queryByText("Marketing Site")).not.toBeInTheDocument();
  });

  it("shows operator resources for an operator with 2FA", async () => {
    vi.mocked(fetchOperatorDashboard).mockResolvedValue(dashboardFixture());

    render(createElement(AdminPage));

    expect(await screen.findByText("Acme Hosting")).toBeInTheDocument();
    expect(screen.getByText("Marketing Site")).toBeInTheDocument();
    expect(screen.getByText("operator.login")).toBeInTheDocument();
    expect(screen.getByLabelText("Search resources")).toBeInTheDocument();
    expect(screen.getByText("Customer secrets are not available in this operator panel. Customer impersonation is disabled in the first version.")).toBeInTheDocument();
  });

  it("requires a reason before blocking an organization", async () => {
    vi.mocked(fetchOperatorDashboard).mockResolvedValue(dashboardFixture());

    render(createElement(AdminPage));

    await userEvent.click(await screen.findByRole("button", { name: "Block organization" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm action" }));

    expect(screen.getByText("Reason is required for high-risk operator actions.")).toBeInTheDocument();
    expect(blockOperatorOrganization).not.toHaveBeenCalled();
  });

  it("records an AuditLog entry after an operator block action", async () => {
    vi.mocked(fetchOperatorDashboard).mockResolvedValue(dashboardFixture());
    vi.mocked(blockOperatorOrganization).mockResolvedValue({
      resource: {
        id: "org_1",
        name: "Acme Hosting",
        status: "blocked",
        plan: "Business",
        billing_status: "active",
        projects_count: 3,
      },
      audit_log: {
        id: "audit_2",
        actor: "operator@example.com",
        action: "operator.organization.block",
        target_type: "organization",
        target_id: "org_1",
        reason: "Security incident INC-123",
        created_at: "2026-06-12T10:10:00Z",
      },
    });

    render(createElement(AdminPage));

    await userEvent.click(await screen.findByRole("button", { name: "Block organization" }));
    await userEvent.type(screen.getByLabelText("Reason"), "Security incident INC-123");
    await userEvent.click(screen.getByRole("button", { name: "Confirm action" }));

    expect(blockOperatorOrganization).toHaveBeenCalledWith("org_1", "Security incident INC-123");
    expect(await screen.findByText("Operator action completed and recorded in AuditLog.")).toBeInTheDocument();
    expect(screen.getByText("operator.organization.block")).toBeInTheDocument();
    expect(screen.getByText("Security incident INC-123")).toBeInTheDocument();
  });
});
