import type { InputHTMLAttributes, Ref } from "react";
import { cn } from "../../lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  //React 19 takes ref as a plain prop, no forwardRef needed
  ref?: Ref<HTMLInputElement>;
}

export function Input({ className, ref, ...rest }: InputProps) {
  return (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-control border border-border bg-surface px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none transition-colors duration-150 focus:border-accent-primary/60",
        className,
      )}
      {...rest}
    />
  );
}