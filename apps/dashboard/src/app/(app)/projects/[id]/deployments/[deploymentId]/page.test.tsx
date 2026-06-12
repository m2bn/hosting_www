import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeploymentDetailPage from "./page";
import { fetchProject, fetchProjectDeployment, fetchProjectDeploymentLogs, rollbackDeployment } from "@/lib/platform-api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project_1", deploymentId: "dep_1" }),
}));

vi.mock("@/lib/platform-api", () => ({
  fetchProject: vi.fn(),
  fetchProjectDeployment: vi.fn(),
  fetchProjectDeploymentLogs: vi.fn(),
  rollbackDeployment: vi.fn(),
}));

describe("DeploymentDetailPage", () => {
  beforeEach(() => {
    vi.mocked(fetchProject).mockReset();
    vi.mocked(fetchProjectDeployment).mockReset();
    vi.mocked(fetchProjectDeploymentLogs).mockReset();
    vi.mocked(rollbackDeployment).mockReset();
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "developer", status: "active" });
    vi.mocked(fetchProjectDeployment).mockResolvedValue({
      id: "dep_1",
      version: "v1",
      status: "failed",
      created_at: "2026-06-12",
      type: "container",
      image_tag: "org/project/dep",
      can_rollback: true,
    });
    vi.mocked(fetchProjectDeploymentLogs).mockResolvedValue([
      { id: "log_1", timestamp: "2026-06-12T10:00:00Z", stream: "build", message: "Build started" },
    ]);
  });

  it("shows deployment details and logs", async () => {
    render(createElement(DeploymentDetailPage));

    expect(await screen.findByText("v1")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText(/\[2026-06-12T10:00:00Z\] build: Build started/)).toBeInTheDocument();
  });

  it("allows rollback for deploy-capable roles", async () => {
    vi.mocked(rollbackDeployment).mockResolvedValue({
      id: "dep_2",
      version: "rollback-v1",
      status: "queued",
      created_at: "2026-06-12",
      can_rollback: false,
    });
    render(createElement(DeploymentDetailPage));

    await userEvent.click(await screen.findByRole("button", { name: "Rollback" }));

    expect(rollbackDeployment).toHaveBeenCalledWith("project_1", "dep_1");
    expect(await screen.findByText("rollback-v1")).toBeInTheDocument();
  });

  it("hides rollback for viewers", async () => {
    vi.mocked(fetchProject).mockResolvedValue({ id: "project_1", organization_id: "org_1", name: "App", role: "viewer", status: "active" });
    render(createElement(DeploymentDetailPage));

    expect(await screen.findByText("v1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rollback" })).not.toBeInTheDocument();
  });
});
