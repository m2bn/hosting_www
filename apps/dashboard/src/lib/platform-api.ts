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
  status: string;
  created_at: string;
  actor?: string;
};

export type Domain = {
  id: string;
  hostname: string;
  status: string;
  certificate_status?: string;
};

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

export async function fetchProjectDomains(id: string): Promise<Domain[]> {
  return normalizeList(await apiRequest<ListResponse<Domain>>(`/projects/${id}/domains/`));
}

export async function fetchProjectSettings(id: string): Promise<ProjectSettings> {
  return apiRequest<ProjectSettings>(`/projects/${id}/settings/`);
}
