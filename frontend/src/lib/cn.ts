/**
 * Joins class names, filtering out falsy values.
 * Lets components do: cn("base-classes", condition && "conditional-class")
 */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
