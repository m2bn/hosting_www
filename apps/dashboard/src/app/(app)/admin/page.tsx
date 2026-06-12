"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Table, TableBody, Td, Th, TableHead } from "@/components/ui/Table";
import {
  blockOperatorOrganization,
  blockOperatorProject,
  fetchOperatorDashboard,
  OperatorActionResult,
  OperatorDashboard,
  OperatorOrganization,
  OperatorProject,
  unblockOperatorOrganization,
} from "@/lib/platform-api";

type OperatorAction =
  | { type: "block_organization"; id: string; label: string }
  | { type: "unblock_organization"; id: string; label: string }
  | { type: "block_project"; id: string; label: string };

function matchesQuery(values: Array<string | number | undefined>, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return values.some((value) => String(value ?? "").toLowerCase().includes(normalized));
}

function updateOrganization(data: OperatorDashboard, result: OperatorActionResult<OperatorOrganization>): OperatorDashboard {
  return {
    ...data,
    organizations: data.organizations.map((organization) => (organization.id === result.resource.id ? result.resource : organization)),
    audit_logs: [result.audit_log, ...data.audit_logs],
  };
}

function updateProject(data: OperatorDashboard, result: OperatorActionResult<OperatorProject>): OperatorDashboard {
  return {
    ...data,
    projects: data.projects.map((project) => (project.id === result.resource.id ? result.resource : project)),
    audit_logs: [result.audit_log, ...data.audit_logs],
  };
}

export default function AdminPage() {
  const [data, setData] = useState<OperatorDashboard | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [action, setAction] = useState<OperatorAction | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchOperatorDashboard()
      .then((dashboard) => {
        if (active) {
          setData(dashboard);
          setError(null);
        }
      })
      .catch((loadError: Error) => {
        if (active) {
          setError(loadError);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const organizations = useMemo(() => {
    return (data?.organizations ?? []).filter((organization) =>
      matchesQuery([organization.name, organization.status, organization.plan, organization.billing_status], query),
    );
  }, [data?.organizations, query]);

  const projects = useMemo(() => {
    return (data?.projects ?? []).filter((project) =>
      matchesQuery(
        [project.name, project.organization_name, project.status, project.deployment_status, project.domain_status, project.certificate_status],
        query,
      ),
    );
  }, [data?.projects, query]);

  async function submitOperatorAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action) {
      return;
    }

    const trimmedReason = reason.trim();
    if (!trimmedReason) {
      setReasonError("Reason is required for high-risk operator actions.");
      return;
    }

    setSubmitting(true);
    setReasonError("");
    setActionError("");
    setActionSuccess("");

    try {
      if (action.type === "block_organization") {
        const result = await blockOperatorOrganization(action.id, trimmedReason);
        setData((current) => (current ? updateOrganization(current, result) : current));
      }
      if (action.type === "unblock_organization") {
        const result = await unblockOperatorOrganization(action.id, trimmedReason);
        setData((current) => (current ? updateOrganization(current, result) : current));
      }
      if (action.type === "block_project") {
        const result = await blockOperatorProject(action.id, trimmedReason);
        setData((current) => (current ? updateProject(current, result) : current));
      }
      setActionSuccess("Operator action completed and recorded in AuditLog.");
      setAction(null);
      setReason("");
    } catch {
      setActionError("Operator action failed. The backend keeps the authoritative audit and authorization decision.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppShell>
      <PageHeader title="Admin" description="Operator panel for tenant oversight, incident triage, and audited risk actions." />

      <div className="grid gap-6">
        <Alert variant="warning">
          UI visibility is not authorization. Backend operator permissions, 2FA checks, tenant isolation, and AuditLog are required for every action.
        </Alert>

        {loading ? <LoadingState label="Loading operator panel..." /> : null}
        {error ? <ErrorState error={error} /> : null}

        {data && !data.access.is_operator ? (
          <Alert variant="danger">Operator access required. Organization owners and regular users cannot use this panel.</Alert>
        ) : null}

        {data?.access.is_operator && !data.access.two_factor_verified ? (
          <Alert variant="danger">Two-factor verification required before accessing operator resources.</Alert>
        ) : null}

        {actionSuccess ? <Alert variant="success">{actionSuccess}</Alert> : null}
        {actionError ? <Alert variant="danger">{actionError}</Alert> : null}

        {data?.access.is_operator && data.access.two_factor_verified ? (
          <>
            <Alert variant="info">
              Customer secrets are not available in this operator panel. Customer impersonation is disabled in the first version.
            </Alert>

            <Card>
              <CardHeader>
                <CardTitle>Search and filters</CardTitle>
              </CardHeader>
              <CardContent>
                <Input
                  label="Search resources"
                  name="operator-search"
                  placeholder="Organization, project, status, billing, domain, certificate"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Organizations</CardTitle>
              </CardHeader>
              <CardContent>
                {organizations.length ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHead>
                        <tr>
                          <Th>Name</Th>
                          <Th>Status</Th>
                          <Th>Billing</Th>
                          <Th>Projects</Th>
                          <Th>Actions</Th>
                        </tr>
                      </TableHead>
                      <TableBody>
                        {organizations.map((organization) => (
                          <tr key={organization.id}>
                            <Td>
                              <div className="font-semibold">{organization.name}</div>
                              <div className="text-xs text-subdued">{organization.plan ?? "No plan"}</div>
                            </Td>
                            <Td>
                              <StatusBadge status={organization.status} />
                            </Td>
                            <Td>
                              <StatusBadge status={organization.billing_status ?? "unknown"} />
                            </Td>
                            <Td>{organization.projects_count ?? 0}</Td>
                            <Td>
                              {organization.status === "blocked" ? (
                                <Button
                                  variant="secondary"
                                  onClick={() => setAction({ type: "unblock_organization", id: organization.id, label: organization.name })}
                                >
                                  Unblock organization
                                </Button>
                              ) : (
                                <Button
                                  variant="danger"
                                  onClick={() => setAction({ type: "block_organization", id: organization.id, label: organization.name })}
                                >
                                  Block organization
                                </Button>
                              )}
                            </Td>
                          </tr>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <EmptyState title="No organizations found" description="Adjust the search filter or check whether the API returned operator resources." />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Projects</CardTitle>
              </CardHeader>
              <CardContent>
                {projects.length ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHead>
                        <tr>
                          <Th>Project</Th>
                          <Th>Deployment</Th>
                          <Th>Billing</Th>
                          <Th>Domain</Th>
                          <Th>Certificate</Th>
                          <Th>Actions</Th>
                        </tr>
                      </TableHead>
                      <TableBody>
                        {projects.map((project) => (
                          <tr key={project.id}>
                            <Td>
                              <div className="font-semibold">{project.name}</div>
                              <div className="text-xs text-subdued">{project.organization_name}</div>
                            </Td>
                            <Td>
                              <StatusBadge status={project.deployment_status ?? project.status} />
                            </Td>
                            <Td>
                              <StatusBadge status={project.billing_status ?? "unknown"} />
                            </Td>
                            <Td>
                              <StatusBadge status={project.domain_status ?? "unknown"} />
                            </Td>
                            <Td>
                              <StatusBadge status={project.certificate_status ?? "unknown"} />
                            </Td>
                            <Td>
                              <Button variant="danger" onClick={() => setAction({ type: "block_project", id: project.id, label: project.name })}>
                                Block project
                              </Button>
                            </Td>
                          </tr>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <EmptyState title="No projects found" description="No project matched the current operator filter." />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Audit log preview</CardTitle>
              </CardHeader>
              <CardContent>
                {data.audit_logs.length ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHead>
                        <tr>
                          <Th>Time</Th>
                          <Th>Actor</Th>
                          <Th>Action</Th>
                          <Th>Target</Th>
                          <Th>Reason</Th>
                        </tr>
                      </TableHead>
                      <TableBody>
                        {data.audit_logs.map((log) => (
                          <tr key={log.id}>
                            <Td>{new Date(log.created_at).toLocaleString()}</Td>
                            <Td>{log.actor}</Td>
                            <Td>{log.action}</Td>
                            <Td>
                              {log.target_type} {log.target_id}
                            </Td>
                            <Td>{log.reason ?? "Not provided"}</Td>
                          </tr>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <EmptyState title="No audit logs" description="Operator actions and critical platform events will appear here." />
                )}
              </CardContent>
            </Card>
          </>
        ) : null}
      </div>

      <Modal
        open={Boolean(action)}
        title="Confirm operator action"
        onClose={() => {
          setAction(null);
          setReason("");
          setReasonError("");
        }}
      >
        <form className="grid gap-4" onSubmit={submitOperatorAction}>
          <p className="text-sm leading-6 text-subdued">
            This high-risk action targets <span className="font-semibold text-ink">{action?.label}</span> and will be written to AuditLog.
          </p>
          <Input
            label="Reason"
            name="operator-action-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            error={reasonError}
            placeholder="Incident ticket, abuse case, billing hold, or security reason"
          />
          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              onClick={() => {
                setAction(null);
                setReason("");
                setReasonError("");
              }}
            >
              Cancel
            </Button>
            <Button variant="danger" type="submit" disabled={submitting}>
              Confirm action
            </Button>
          </div>
        </form>
      </Modal>
    </AppShell>
  );
}
