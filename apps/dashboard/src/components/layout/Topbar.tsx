import { Button } from "@/components/ui/Button";

export function Topbar() {
  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-white px-4 lg:px-6">
      <div>
        <p className="text-sm font-semibold text-ink">Acme Hosting</p>
        <p className="text-xs text-subdued">Production workspace</p>
      </div>
      <div className="flex items-center gap-3">
        <Button variant="secondary" className="hidden sm:inline-flex">
          New project
        </Button>
        <div className="grid h-9 w-9 place-items-center rounded-full bg-brand-50 text-sm font-bold text-brand-700" aria-label="Current user">
          A
        </div>
      </div>
    </header>
  );
}
