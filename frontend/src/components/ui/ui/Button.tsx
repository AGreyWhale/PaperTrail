//Button UI

import type { ButtonHTMLAttributes, ReactNode } from "react"
import { cn } from "../../../lib/cn";

type ButtonVariant = "primary" | "ai" | "secondary" | "ghost";
type ButtonSize = "sm" | "md"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    /**
     * primary: user's own actions (save, favorite, create collection)
     * ai: anything the assistant originates
     * secondary: bordered, neutral actions
     * ghost: lowest-emphasis actions (toolbar, dismiss)
     */
    variant?: ButtonVariant;
    size?: ButtonSize;
    children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
    primary: "bg-accent-primary text-white hover:bg-accent-primary/90 border border-transparent",
    ai:"bg-accent-ai-soft text-accent-ai hover:bg-accent-ai/15 border border-transparent",
    secondary: "bg-surface text-text-primary border border-border hover:border-border-strong",
    ghost:"bg-transparent text-text-secondary hover:bg-bg-secondary border border-transparent",
};

const sizeClasses: Record<ButtonSize, string> = {
    sm: "text-sm px-3 py-1.5 gap-1.5",
    md: "text-sm px-4 py-2.5 gap-2",
};

export function Button({
    variant = "secondary",
    size = "md",
    className,
    children,
    ...rest
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-control font-medium transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}