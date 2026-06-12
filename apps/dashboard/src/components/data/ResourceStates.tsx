import { ApiError } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Card, CardContent } from "@/components/ui/Card";

export function LoadingState({ label = "Loading data..." }: { label?: string }) {
  return (
    <Card>
      <CardContent className="grid gap-3">
        <div className="h-4 w-40 animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-64 animate-pulse rounded bg-slate-200" />
        <p className="text-sm text-subdued">{label}</p>
      </CardContent>
    </Card>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Card>
      <CardContent className="py-10 text-center">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-subdued">{description}</p>
      </CardContent>
    </Card>
  );
}

export function ErrorState({ error }: { error: Error }) {
  const status = error instanceof ApiError ? error.status : 0;
  const message =
    status === 403 || status === 404
      ? "Resource not found or you do not have access."
      : "We could not load this data. Try again later.";

  return <Alert variant="danger">{message}</Alert>;
}
