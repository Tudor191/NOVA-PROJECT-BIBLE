/**
 * `@nova/ui` -- the design-system package doc 04 §6 names.
 *
 * Phase 4A builds the minimum the shell and the Conversation panel require
 * and nothing else; a finished design system is an explicit 4A non-goal
 * (TDD 4A §13). What is here is the part that carries a *rule* rather than
 * a look: how a missing confidence is displayed, how a degraded upstream is
 * disclosed, and when an indicator is allowed to animate.
 *
 * Named exports only. The generated contracts package learned in R-3 what
 * `export *` costs when two modules happen to export the same name.
 */
export { cn } from "./cn";
export { Button } from "./components/Button";
export type { ButtonProps } from "./components/Button";
export { ConfidenceBadge, ConfidenceTierBadge } from "./components/ConfidenceBadge";
export type {
  ConfidenceBadgeProps,
  ConfidenceTierBadgeProps,
} from "./components/ConfidenceBadge";
export { CorrelationTag } from "./components/CorrelationTag";
export type { CorrelationTagProps } from "./components/CorrelationTag";
export { DegradationNotice } from "./components/DegradationNotice";
export type { DegradationNoticeProps } from "./components/DegradationNotice";
export { Panel } from "./components/Panel";
export type { PanelProps } from "./components/Panel";
export { StatusDot } from "./components/StatusDot";
export type { StatusDotProps, StatusTone } from "./components/StatusDot";
export { TextField } from "./components/TextField";
export type { TextFieldProps } from "./components/TextField";
