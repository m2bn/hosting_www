"use client";

import { FormEvent, useState } from "react";
import { createContainerDeployment, createStaticDeployment, Deployment } from "@/lib/platform-api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

const MAX_ZIP_SIZE_BYTES = 100 * 1024 * 1024;

export function validateZipFile(file: File | null): string {
  if (!file) {
    return "Select a ZIP file.";
  }
  if (!file.name.toLowerCase().endsWith(".zip")) {
    return "Only .zip files are accepted for static deployments.";
  }
  if (file.size > MAX_ZIP_SIZE_BYTES) {
    return "ZIP file must be 100 MB or smaller.";
  }
  if (file.type && !["application/zip", "application/x-zip-compressed", "application/octet-stream"].includes(file.type)) {
    return "Selected file does not look like a ZIP archive.";
  }
  return "";
}

type DeploymentFormsProps = {
  projectId: string;
  onCreated: (deployment: Deployment) => void;
};

export function DeploymentForms({ projectId, onCreated }: DeploymentFormsProps) {
  const [staticError, setStaticError] = useState("");
  const [containerError, setContainerError] = useState("");
  const [isStaticSubmitting, setIsStaticSubmitting] = useState(false);
  const [isContainerSubmitting, setIsContainerSubmitting] = useState(false);

  async function onStaticSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStaticError("");
    const file = new FormData(event.currentTarget).get("artifact");
    const selectedFile = file instanceof File && file.size > 0 ? file : null;
    const validationError = validateZipFile(selectedFile);
    if (validationError) {
      setStaticError(validationError);
      return;
    }
    if (!selectedFile) {
      setStaticError("Select a ZIP file.");
      return;
    }
    setIsStaticSubmitting(true);
    try {
      onCreated(await createStaticDeployment(projectId, { file: selectedFile }));
      event.currentTarget.reset();
    } catch {
      setStaticError("Static deployment could not be started. Try again later.");
    } finally {
      setIsStaticSubmitting(false);
    }
  }

  async function onContainerSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setContainerError("");
    const form = new FormData(event.currentTarget);
    const repositoryUrl = String(form.get("repository_url") ?? "").trim();
    const branch = String(form.get("branch") ?? "").trim();
    const dockerfilePath = String(form.get("dockerfile_path") ?? "").trim();
    if (!repositoryUrl || !branch || !dockerfilePath) {
      setContainerError("Repository URL, branch, and Dockerfile path are required.");
      return;
    }
    setIsContainerSubmitting(true);
    try {
      onCreated(await createContainerDeployment(projectId, { repository_url: repositoryUrl, branch, dockerfile_path: dockerfilePath }));
      event.currentTarget.reset();
    } catch {
      setContainerError("Container deployment could not be started. Try again later.");
    } finally {
      setIsContainerSubmitting(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Static deployment</CardTitle></CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={onStaticSubmit} noValidate>
            {staticError ? <Alert variant="danger">{staticError}</Alert> : null}
            <Input label="ZIP artifact" name="artifact" type="file" accept=".zip,application/zip,application/x-zip-compressed" />
            <p className="text-sm leading-6 text-subdued">Frontend checks extension, MIME, and 100 MB limit. Backend still validates archive safety independently.</p>
            <Button type="submit" disabled={isStaticSubmitting}>{isStaticSubmitting ? "Uploading..." : "Upload ZIP"}</Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Container deployment</CardTitle></CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={onContainerSubmit} noValidate>
            {containerError ? <Alert variant="danger">{containerError}</Alert> : null}
            <Input label="Repository URL" name="repository_url" placeholder="https://github.com/acme/app" />
            <Input label="Branch" name="branch" placeholder="main" />
            <Input label="Dockerfile path" name="dockerfile_path" placeholder="Dockerfile" />
            <Button type="submit" disabled={isContainerSubmitting}>{isContainerSubmitting ? "Starting..." : "Start container deployment"}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
