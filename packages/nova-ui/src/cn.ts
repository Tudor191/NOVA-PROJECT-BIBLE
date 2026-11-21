/**
 * Conditional class-name join.
 *
 * Deliberately tiny: `clsx` and `tailwind-merge` are the usual reach, and
 * neither earns a dependency for the handful of components 4A builds. The
 * one behaviour that matters is that `false`, `null` and `undefined` drop
 * out, so a component can write `cn("base", active && "ring-2")` without
 * emitting the string "false" into `class`.
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter((part): part is string => Boolean(part)).join(" ");
}
