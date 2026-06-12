import { apiRequest } from "@/lib/api";
import { Permission, Role } from "@/lib/rbac";

type ListResponse<T> = T[] | { results: T[] };

function normalizeList<T>(response: ListResponse<T>): T[] {
  return Array.isArray(response) ? response : response.results;
}

export type Organization = {
  id: string;
  name: string;
  slug?: string;
  role: Role;
  status: string;
  projects_count?: number;
  members_count?: number;
  permissions?: Permission[];
};

export type OrganizationMember = {
  id: string;
  name: string;
  email: string;
  role: Role;
  status: string;
};

export type Project = {
  id: string;
  organization_id: string;
  organization_name?: string;
  name: string;
  slug?: string;
  status: string;
  last_deployment_at?: string;
  deployments_count?: number;
  domains_count?: number;
  storage_gb?: number;
  role?: Role;
  permissions?: Permission[];
};

export type Deployment = {
  id: string;
  version: string;
  status: DeploymentStatus;
  created_at: string;
  actor?: string;
  type?: "static" | "container";
  commit_sha?: string;
  image_tag?: string;
  artifact_name?: string;
  can_rollback?: boolean;
};

export type DeploymentStatus = "queued" | "building" | "scanning" | "deploying" | "active" | "failed" | "rolled_back";

export type DeploymentLogLine = {
  id: string;
  timestamp: string;
  stream: "build" | "deploy" | "scan";
  message: string;
};

export type StaticDeploymentInput = {
  file: File;
};

export type ContainerDeploymentInput = {
  repository_url: string;
  branch: string;
  dockerfile_path: string;
};

export type Domain = {
  id: string;
  hostname: string;
  status: DomainStatus;
  certificate_status?: string;
  verification_record_name?: string;
  verification_record_value?: string;
  dns_instructions?: string[];
};

export type DomainStatus = "pending_verification" | "verified" | "active" | "failed" | "disabled";

export type ProjectSettings = {
  id: string;
  name: string;
  slug?: string;
  environment_count?: number;
  runtime?: string;
  permissions?: Permission[];
};

export type DashboardSummary = {
  organizations_count: number;
  projects_count: number;
  deployments_count: number;
  failed_deployments_count: number;
  recent_projects: Project[];
  organizations: Organization[];
  permissions?: Permission[];
};

export type PlanLimits = {
  projects: number;
  storage_gb: number;
  transfer_gb: number;
  cpu_limit?: string;
  memory_limit?: string;
  custom_domains: boolean;
  container_deployments: boolean;
};

export type BillingPlan = {
  id: string;
  name: string;
  code: string;
  price_label: string;
  description?: string;
  limits: PlanLimits;
  current?: boolean;
};

export type Subscription = {
  id: string;
  status: string;
  current_period_end?: string;
  payment_failed?: boolean;
  payment_failure_message?: string;
};

export type UsageMetric = {
  key: "projects" | "storage_gb" | "transfer_gb" | "cpu_hours" | "memory_gb_hours";
  label: string;
  used: number;
  limit: number;
  unit: string;
};

export type Invoice = {
  id: string;
  number: string;
  status: string;
  amount_due: string;
  issued_at: string;
  hosted_invoice_url?: string;
};

export type BillingOverview = {
  organization_id: string;
  organization_name: string;
  role: Role;
  permissions?: Permission[];
  current_plan: BillingPlan;
  subscription: Subscription;
  usage: UsageMetric[];
  recent_invoices: Invoice[];
};

export type CheckoutSession = {
  checkout_url: string;
};

export async function fetchDashboard(): Promise<DashboardSummary> {
  return apiRequest<DashboardSummary>("/dashboard/");
}

export async function fetchOrganizations(): Promise<Organization[]> {
  return normalizeList(await apiRequest<ListResponse<Organization>>("/organizations/"));
}

export async function fetchOrganization(id: string): Promise<Organization> {
  return apiRequest<Organization>(`/organizations/${id}/`);
}

export async function fetchOrganizationMembers(id: string): Promise<OrganizationMember[]> {
  return normalizeList(await apiRequest<ListResponse<OrganizationMember>>(`/organizations/${id}/members/`));
}

export async function fetchOrganizationProjects(id: string): Promise<Project[]> {
  return normalizeList(await apiRequest<ListResponse<Project>>(`/organizations/${id}/projects/`));
}

export async function fetchProject(id: string): Promise<Project> {
  return apiRequest<Project>(`/projects/${id}/`);
}

export async function fetchProjectDeployments(id: string): Promise<Deployment[]> {
  return normalizeList(await apiRequest<ListResponse<Deployment>>(`/projects/${id}/deployments/`));
}

export async function fetchProjectDeployment(projectId: string, deploymentId: string): Promise<Deployment> {
  return apiRequest<Deployment>(`/projects/${projectId}/deployments/${deploymentId}/`);
}

export async function fetchProjectDeploymentLogs(projectId: string, deploymentId: string): Promise<DeploymentLogLine[]> {
  return normalizeList(await apiRequest<ListResponse<DeploymentLogLine>>(`/projects/${projectId}/deployments/${deploymentId}/logs/`));
}

export async function createStaticDeployment(projectId: string, input: StaticDeploymentInput): Promise<Deployment> {
  const formData = new FormData();
  formData.set("file", input.file);
  return apiRequest<Deployment>(`/projects/${projectId}/deployments/static/`, {
    method: "POST",
    body: formData,
    csrf: true,
  });
}

export async function createContainerDeployment(projectId: string, input: ContainerDeploymentInput): Promise<Deployment> {
  return apiRequest<Deployment>(`/projects/${projectId}/deployments/container/`, {
    method: "POST",
    body: input,
    csrf: true,
  });
}

export async function rollbackDeployment(projectId: string, deploymentId: string): Promise<Deployment> {
  return apiRequest<Deployment>(`/projects/${projectId}/deployments/${deploymentId}/rollback/`, {
    method: "POST",
    body: {},
    csrf: true,
  });
}

export async function fetchProjectDomains(id: string): Promise<Domain[]> {
  return normalizeList(await apiRequest<ListResponse<Domain>>(`/projects/${id}/domains/`));
}

export async function createProjectDomain(projectId: string, hostname: string): Promise<Domain> {
  return apiRequest<Domain>(`/projects/${projectId}/domains/`, {
    method: "POST",
    body: { hostname },
    csrf: true,
  });
}

export async function refreshProjectDomain(projectId: string, domainId: string): Promise<Domain> {
  return apiRequest<Domain>(`/projects/${projectId}/domains/${domainId}/refresh/`, {
    method: "POST",
    body: {},
    csrf: true,
  });
}

export async function deleteProjectDomain(projectId: string, domainId: string): Promise<void> {
  await apiRequest<void>(`/projects/${projectId}/domains/${domainId}/`, {
    method: "DELETE",
    csrf: true,
  });
}

export async function fetchProjectSettings(id: string): Promise<ProjectSettings> {
  return apiRequest<ProjectSettings>(`/projects/${id}/settings/`);
}

export async function fetchBillingOverview(): Promise<BillingOverview> {
  return apiRequest<BillingOverview>("/billing/");
}

export async function fetchBillingPlans(): Promise<BillingPlan[]> {
  return normalizeList(await apiRequest<ListResponse<BillingPlan>>("/billing/plans/"));
}

export async function fetchBillingInvoices(): Promise<Invoice[]> {
  return normalizeList(await apiRequest<ListResponse<Invoice>>("/billing/invoices/"));
}

export async function fetchBillingUsage(): Promise<UsageMetric[]> {
  return normalizeList(await apiRequest<ListResponse<UsageMetric>>("/billing/usage/"));
}

export async function startStripeCheckout(planCode?: string): Promise<CheckoutSession> {
  return apiRequest<CheckoutSession>("/billing/checkout/", {
    method: "POST",
    body: planCode ? { plan_code: planCode } : {},
    csrf: true,
  });
}
