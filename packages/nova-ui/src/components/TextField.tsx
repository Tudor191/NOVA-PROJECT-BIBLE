import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";

import { cn } from "../cn";

export type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  /** Validation or submission failure. Rendered, never swallowed. */
  error?: string | null;
  /** Hide the visual label but keep it for assistive technology. */
  hideLabel?: boolean;
};

/**
 * `forwardRef` is required, not stylistic: React Hook Form registers inputs
 * by ref, and the login form and composer both use it (doc 04 §5).
 */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, error, hideLabel = false, className, id, ...rest },
  ref,
) {
  const inputId = id ?? `nova-field-${label.replace(/\s+/g, "-").toLowerCase()}`;
  const errorId = `${inputId}-error`;
  return (
    <div className={cn("nova-field", className)}>
      <label
        className={cn("nova-field-label", hideLabel && "nova-visually-hidden")}
        htmlFor={inputId}
      >
        {label}
      </label>
      <input
        {...rest}
        id={inputId}
        ref={ref}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className="nova-field-input"
      />
      {error ? (
        <p className="nova-field-error" id={errorId} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
});
