import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectDomainsPage from "./page";
import { ApiError } from "@/lib/api";
import { fetchProject, fetchProjectDomains } from "@/lib/platform-api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project_1" }),
}));

vi.mock("@/lib/platform-api", () => ({
  fetchProject: vi.fn(),
  fetchProjectDomains: vi.fn(),
}));

describe("ProjectDomainsPage", () => {
  beforeEach(() => {
    vi.mocked(fetchProject).mockReset();
    vi.mocked(fetchProjectDomains).mockReset();
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
    expect(screen.queryByRole("button", { name: "Verify" })).not.toBeInTheDocument();
  });
});
