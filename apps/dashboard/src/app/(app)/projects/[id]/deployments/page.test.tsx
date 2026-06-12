import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectDeploymentsPage from "./page";
import { createContainerDeployment, createStaticDeployment, fetchProject, fetchProjectDeployments } from "@/lib/platform-api";
import { validateZipFile } from "@/components/deployments/DeploymentForms";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project_1" }),
}));

vi.mock("@/lib/platform-api", () => ({
  createContainerDeployment: vi.fn(),
  createStaticDeployment: vi.fn(),
  fetchProject: vi.fn(),
  fetchProjectDeployments: vi.fn(),
}));

describe("ProjectDeploymentsPage", () => {
  beforeEach(() => {
    vi.mocked(fetchProject).mockReset();
    vi.mocked(fetchProjectDeployments).mockReset();
    vi.mocked(createContainerDeployment).mockReset();
    vi.mocked(createStaticDeployment).mockReset();
    vi.mocked(fetchProjectDeployments).mockResolvedValue([
      { id: "dep_1", version: "v1", status: "active", created_at: "2026-06-12", actor: "Ada" },
    ]);
  });

  it("shows deployment forms for developers", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "developer", status: "active" });

    render(createElement(ProjectDeploymentsPage));

    expect(await screen.findByRole("button", { name: "Upload ZIP" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start container deployment" })).toBeInTheDocument();
  });

  it("hides deployment forms for billing users", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "billing", status: "active" });

    render(createElement(ProjectDeploymentsPage));

    expect(await screen.findByText("v1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload ZIP" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start container deployment" })).not.toBeInTheDocument();
    expect(screen.getByText("Your role can view deployments, but cannot start new deployments.")).toBeInTheDocument();
  });

  it("validates ZIP files before static upload", async () => {
    expect(validateZipFile(new File(["not a zip"], "site.txt", { type: "text/plain" }))).toBe("Only .zip files are accepted for static deployments.");
    expect(validateZipFile(new File(["zip"], "site.zip", { type: "application/zip" }))).toBe("");
  });

  it("requires a file before static upload", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "developer", status: "active" });
    render(createElement(ProjectDeploymentsPage));

    await screen.findByRole("button", { name: "Upload ZIP" });
    await userEvent.click(screen.getByRole("button", { name: "Upload ZIP" }));

    expect(await screen.findByText("Select a ZIP file.")).toBeInTheDocument();
    expect(createStaticDeployment).not.toHaveBeenCalled();
  });

  it("validates container deployment required fields", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "developer", status: "active" });
    render(createElement(ProjectDeploymentsPage));

    await screen.findByRole("button", { name: "Start container deployment" });
    await userEvent.click(screen.getByRole("button", { name: "Start container deployment" }));

    expect(await screen.findByText("Repository URL, branch, and Dockerfile path are required.")).toBeInTheDocument();
    expect(createContainerDeployment).not.toHaveBeenCalled();
  });
});
