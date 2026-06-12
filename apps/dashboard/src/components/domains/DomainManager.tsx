"use client";

import { FormEvent, useState } from "react";
import { createProjectDomain, deleteProjectDomain, Domain, refreshProjectDomain } from "@/lib/platform-api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";

const HOSTNAME_PATTERN = /^(?=.{1,253}$)(?!-)(?:[a-z0-9-]{1,63}\.)+[a-z]{2,63}$/i;

export function validateHostname(hostname: string): string {
  if (!hostname.trim()) {
    return "Domain is required.";
  }
  if (!HOSTNAME_PATTERN.test(hostname.trim())) {
    return "Enter a valid domain name.";
  }
  return "";
}

type DomainManagerProps = {
  projectId: string;
  domains: Domain[];
  canManageDomains: boolean;
};

export function DomainManager({ projectId, domains, canManageDomains }: DomainManagerProps) {
  const [items, setItems] = useState(domains);
  const [formError, setFormError] = useState("");
  const [actionError, setActionError] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onAddDomain(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");
    setActionError("");
    const hostname = String(new FormData(event.currentTarget).get("hostname") ?? "").trim().toLowerCase();
    const validationError = validateHostname(hostname);
    if (validationError) {
      setFormError(validationError);
      return;
    }
    setIsSubmitting(true);
    try {
      const created = await createProjectDomain(projectId, hostname);
      setItems((current) => [created, ...current]);
      event.currentTarget.reset();
    } catch {
      setFormError("Domain could not be added. Check ownership and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function onRefresh(domainId: string) {
    setActionError("");
    try {
      const refreshed = await refreshProjectDomain(projectId, domainId);
      setItems((current) => current.map((domain) => (domain.id === refreshed.id ? refreshed : domain)));
    } catch {
      setActionError("DNS status could not be refreshed.");
    }
  }

  async function onDelete(domainId: string) {
    setActionError("");
    try {
      await deleteProjectDomain(projectId, domainId);
      setItems((current) => current.filter((domain) => domain.id !== domainId));
      setPendingDeleteId(null);
    } catch {
      setActionError("Domain could not be removed.");
    }
  }

  return (
    <div className="grid gap-6">
      {canManageDomains ? (
        <Card>
          <CardHeader><CardTitle>Add custom domain</CardTitle></CardHeader>
          <CardContent>
            <form className="grid gap-4 sm:grid-cols-[1fr_auto]" onSubmit={onAddDomain} noValidate>
              <Input label="Domain" name="hostname" placeholder="app.example.com" error={formError} />
              <Button type="submit" className="self-end" disabled={isSubmitting}>{isSubmitting ? "Adding..." : "Add domain"}</Button>
            </form>
          </CardContent>
        </Card>
      ) : null}
      {!canManageDomains ? <Alert variant="info">Your role can view domains, but cannot manage custom domains.</Alert> : null}
      {actionError ? <Alert variant="danger">{actionError}</Alert> : null}
      <Card>
        <CardContent className="overflow-x-auto p-0">
          <Table>
            <TableHead><tr><Th>Domain</Th><Th>Verification</Th><Th>SSL</Th><Th>DNS instructions</Th><Th /></tr></TableHead>
            <TableBody>
              {items.map((domain) => (
                <tr key={domain.id}>
                  <Td className="align-top font-semibold">{domain.hostname}</Td>
                  <Td className="align-top"><StatusBadge status={domain.status} /></Td>
                  <Td className="align-top">{domain.certificate_status ? <StatusBadge status={domain.certificate_status} /> : "Not requested"}</Td>
                  <Td className="min-w-80 align-top">
                    <div className="grid gap-2 text-sm">
                      <p className="text-subdued">{domain.dns_instructions?.[0] ?? "Create the TXT record below to verify ownership."}</p>
                      {domain.verification_record_name && domain.verification_record_value ? (
                        <code className="block break-all rounded-md bg-muted p-3 text-xs">
                          TXT {domain.verification_record_name} = {domain.verification_record_value}
                        </code>
                      ) : null}
                    </div>
                  </Td>
                  <Td className="align-top">
                    {canManageDomains ? (
                      <div className="flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={() => onRefresh(domain.id)}>Refresh DNS</Button>
                        {pendingDeleteId === domain.id ? (
                          <>
                            <Button variant="danger" onClick={() => onDelete(domain.id)}>Confirm delete</Button>
                            <Button variant="ghost" onClick={() => setPendingDeleteId(null)}>Cancel</Button>
                          </>
                        ) : (
                          <Button variant="danger" onClick={() => setPendingDeleteId(domain.id)}>Delete</Button>
                        )}
                      </div>
                    ) : null}
                  </Td>
                </tr>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
