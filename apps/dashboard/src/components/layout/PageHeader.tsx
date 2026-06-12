import { ReactNode } from "react";

type PageHeaderProps = {
  title: string;
  description: string;
  actions?: ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-normal text-ink">{title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-subdued">{description}</p>
      </div>
      {actions ? <div className="flex gap-2">{actions}</div> : null}
    </div>
  );
}
