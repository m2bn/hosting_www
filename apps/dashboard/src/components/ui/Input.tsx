import { InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ className, label, error, id, ...props }, ref) {
  const inputId = id ?? props.name;
  return (
    <label className="grid gap-2 text-sm font-medium text-ink" htmlFor={inputId}>
      {label ? <span>{label}</span> : null}
      <input
        id={inputId}
        ref={ref}
        className={cn(
          "h-10 rounded-md border border-border bg-white px-3 text-sm text-ink shadow-sm transition placeholder:text-subdued focus:border-brand-500",
          error && "border-danger",
          className,
        )}
        {...props}
      />
      {error ? <span className="text-xs font-medium text-danger">{error}</span> : null}
    </label>
  );
});
