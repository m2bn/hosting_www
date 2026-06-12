import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectDeploymentsPage from "./page";
import { fetchProject, fetchProjectDeployments } from "@/lib/platform-api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project_1" }),
}));

vi.mock("@/lib/platform-api", () => ({
  fetchProject: vi.fn(),
  fetchProjectDeployments: vi.fn(),
}));

describe("ProjectDeploymentsPage", () => {
  beforeEach(() => {
    vi.mocked(fetchProject).mockReset();
    vi.mocked(fetchProjectDeployments).mockReset();
    vi.mocked(fetchProjectDeployments).mockResolvedValue([
      { id: "dep_1", version: "v1", status: "active", created_at: "2026-06-12", actor: "Ada" },
    ]);
  });

  it("shows deploy action for developers", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "developer", status: "active" });

    render(createElement(ProjectDeploymentsPage));

    expect(await screen.findByRole("button", { name: "Deploy" })).toBeInTheDocument();
  });

  it("hides deploy action for billing users", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "billing", status: "active" });

    render(createElement(ProjectDeploymentsPage));

    expect(await screen.findByText("v1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deploy" })).not.toBeInTheDocument();
  });
});
