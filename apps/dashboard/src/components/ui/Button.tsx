import { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

const variants: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700",
  secondary: "border border-border bg-white text-ink hover:bg-muted",
  danger: "bg-danger text-white hover:bg-orange-700",
  ghost: "text-subdued hover:bg-muted hover:text-ink",
};

export function Button({ className, variant = "primary", type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
