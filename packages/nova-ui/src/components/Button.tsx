import type { ButtonHTMLAttributes } from "react";

import { cn } from "../cn";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
  /**
   * Disables the control and announces work in progress. Distinct from
   * `disabled`: a busy button is temporarily unavailable, a disabled one is
   * unavailable for a reason the user has to resolve.
   */
  busy?: boolean;
};

export function Button({
  variant = "primary",
  busy = false,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cn(
        "nova-button",
        variant === "primary" ? "nova-button-primary" : "nova-button-ghost",
        className,
      )}
    >
      {children}
    </button>
  );
}
