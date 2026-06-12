import { HTMLAttributes, TableHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export function Table({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full border-collapse text-left text-sm", className)} {...props} />;
}

export function TableHead({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("border-b border-border bg-muted text-xs uppercase text-subdued", className)} {...props} />;
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("divide-y divide-border bg-white", className)} {...props} />;
}

export function Th({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("px-4 py-3 font-semibold", className)} {...props} />;
}

export function Td({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-4 py-3 text-ink", className)} {...props} />;
}
