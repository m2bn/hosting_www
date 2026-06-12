import { DeploymentLogLine } from "@/lib/platform-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";

export function DeploymentLogs({ logs }: { logs: DeploymentLogLine[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>Build and deployment logs</CardTitle></CardHeader>
      <CardContent>
        {logs.length === 0 ? (
          <p className="text-sm text-subdued">No logs have been emitted yet.</p>
        ) : (
          <pre className="max-h-96 overflow-auto rounded-md bg-slate-950 p-4 text-xs leading-6 text-slate-100">
            {logs.map((line) => `[${line.timestamp}] ${line.stream}: ${line.message}`).join("\n")}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
