import { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type BadgeVariant = "neutral" | "success" | "warning" | "danger" | "brand";

const variants: Record<BadgeVariant, string> = {
  neutral: "bg-muted text-subdued",
  success: "bg-emerald-50 text-success",
  warning: "bg-amber-50 text-warning",
  danger: "bg-orange-50 text-danger",
  brand: "bg-brand-50 text-brand-700",
};

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

export function Badge({ className, variant = "neutral", ...props }: BadgeProps) {
  return <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-semibold", variants[variant], className)} {...props} />;
}
