import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../../lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    //Makes clickable cards look clickable
    interactive?: boolean;
    children: ReactNode;
}

/**
 * Base paper surface so it stays consistent
 */
export function Card({interactive, className, children, ...rest}: CardProps){
    return (
    <div
      className={cn(
        "bg-surface border border-border rounded-card shadow-[0_1px_2px_rgba(43,38,33,0.04)]",
        interactive &&
          "transition-all duration-150 hover:shadow-[0_4px_12px_rgba(43,38,33,0.08)] hover:border-border-strong cursor-pointer",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}