import { DeploymentStatus } from "@/lib/platform-api";

export const activeDeploymentStatuses = new Set<DeploymentStatus>(["queued", "building", "scanning", "deploying"]);

export function isDeploymentInProgress(status: DeploymentStatus): boolean {
  return activeDeploymentStatuses.has(status);
}
