import { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type AlertVariant = "info" | "success" | "warning" | "danger";

const variants: Record<AlertVariant, string> = {
  info: "border-brand-100 bg-brand-50 text-brand-700",
  success: "border-emerald-100 bg-emerald-50 text-success",
  warning: "border-amber-100 bg-amber-50 text-warning",
  danger: "border-orange-100 bg-orange-50 text-danger",
};

type AlertProps = HTMLAttributes<HTMLDivElement> & {
  variant?: AlertVariant;
};

export function Alert({ className, variant = "info", ...props }: AlertProps) {
  return <div className={cn("rounded-md border px-4 py-3 text-sm font-medium leading-6 break-words", variants[variant], className)} {...props} />;
}
