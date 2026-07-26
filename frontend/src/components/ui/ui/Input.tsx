import type { InputHTMLAttributes } from "react";
import { cn } from "../../../lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export function Input({ className, ...rest }: InputProps) {
  return (
    <input
      className={cn(
        "w-full rounded-control border border-border bg-surface px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none transition-colors duration-150 focus:border-accent-primary/60",
        className,
      )}
      {...rest}
    />
  );
}