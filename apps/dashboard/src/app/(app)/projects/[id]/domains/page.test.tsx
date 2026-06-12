import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectDomainsPage from "./page";
import { ApiError } from "@/lib/api";
import { createProjectDomain, deleteProjectDomain, fetchProject, fetchProjectDomains, refreshProjectDomain } from "@/lib/platform-api";
import { validateHostname } from "@/components/domains/DomainManager";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project_1" }),
}));

vi.mock("@/lib/platform-api", () => ({
  createProjectDomain: vi.fn(),
  deleteProjectDomain: vi.fn(),
  fetchProject: vi.fn(),
  fetchProjectDomains: vi.fn(),
  refreshProjectDomain: vi.fn(),
}));

describe("ProjectDomainsPage", () => {
  beforeEach(() => {
    vi.mocked(fetchProject).mockReset();
    vi.mocked(fetchProjectDomains).mockReset();
    vi.mocked(createProjectDomain).mockReset();
    vi.mocked(deleteProjectDomain).mockReset();
    vi.mocked(refreshProjectDomain).mockReset();
  });

  it("does not reveal forbidden resource details for 403 responses", async () => {
    vi.mocked(fetchProject).mockRejectedValue(new ApiError("Project belongs to another organization", 403));
    vi.mocked(fetchProjectDomains).mockRejectedValue(new ApiError("Project belongs to another organization", 403));

    render(createElement(ProjectDomainsPage));

    expect(await screen.findAllByText("Resource not found or you do not have access.")).toHaveLength(2);
    expect(screen.queryByText(/another organization/i)).not.toBeInTheDocument();
  });

  it("hides domain actions when permission is missing", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "viewer", status: "active" });
    vi.mocked(fetchProjectDomains).mockResolvedValue([{ id: "dom_1", hostname: "app.example.com", status: "verified", certificate_status: "active" }]);

    render(createElement(ProjectDomainsPage));

    expect(await screen.findByText("app.example.com")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add domain" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh DNS" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("shows DNS instructions and TXT verification record", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "admin", status: "active" });
    vi.mocked(fetchProjectDomains).mockResolvedValue([
      {
        id: "dom_1",
        hostname: "app.example.com",
        status: "pending_verification",
        certificate_status: "pending",
        verification_record_name: "_hosting.app.example.com",
        verification_record_value: "verify-token",
        dns_instructions: ["Add this TXT record at your DNS provider."],
      },
    ]);

    render(createElement(ProjectDomainsPage));

    expect(await screen.findByText("pending verification")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("Add this TXT record at your DNS provider.")).toBeInTheDocument();
    expect(screen.getByText("TXT _hosting.app.example.com = verify-token")).toBeInTheDocument();
  });

  it("validates hostnames before creating domains", async () => {
    expect(validateHostname("not a domain")).toBe("Enter a valid domain name.");
    expect(validateHostname("app.example.com")).toBe("");
  });

  it("adds a domain for users with domain management permission", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "admin", status: "active" });
    vi.mocked(fetchProjectDomains).mockResolvedValue([{ id: "dom_1", hostname: "app.example.com", status: "verified", certificate_status: "active" }]);
    vi.mocked(createProjectDomain).mockResolvedValue({ id: "dom_2", hostname: "docs.example.com", status: "pending_verification" });

    render(createElement(ProjectDomainsPage));

    await userEvent.type(await screen.findByLabelText("Domain"), "docs.example.com");
    await userEvent.click(screen.getByRole("button", { name: "Add domain" }));

    expect(createProjectDomain).toHaveBeenCalledWith("project_1", "docs.example.com");
    expect(await screen.findByText("docs.example.com")).toBeInTheDocument();
  });

  it("refreshes DNS status", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "admin", status: "active" });
    vi.mocked(fetchProjectDomains).mockResolvedValue([{ id: "dom_1", hostname: "app.example.com", status: "pending_verification", certificate_status: "pending" }]);
    vi.mocked(refreshProjectDomain).mockResolvedValue({ id: "dom_1", hostname: "app.example.com", status: "verified", certificate_status: "issuing" });

    render(createElement(ProjectDomainsPage));

    await userEvent.click(await screen.findByRole("button", { name: "Refresh DNS" }));

    expect(refreshProjectDomain).toHaveBeenCalledWith("project_1", "dom_1");
    expect(await screen.findByText("verified")).toBeInTheDocument();
  });

  it("requires explicit confirmation before deleting a domain", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "admin", status: "active" });
    vi.mocked(fetchProjectDomains).mockResolvedValue([{ id: "dom_1", hostname: "app.example.com", status: "verified", certificate_status: "active" }]);
    vi.mocked(deleteProjectDomain).mockResolvedValue();

    render(createElement(ProjectDomainsPage));

    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(deleteProjectDomain).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));

    expect(deleteProjectDomain).toHaveBeenCalledWith("project_1", "dom_1");
    expect(screen.queryByText("app.example.com")).not.toBeInTheDocument();
  });
});
