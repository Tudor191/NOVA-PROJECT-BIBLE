import type { ReactNode } from "react";

import { cn } from "../cn";

/**
 * The panel frame every workspace surface sits in.
 *
 * Doc 04 §2 describes the client as a panelled workspace rather than a page
 * hierarchy, so the frame is a component and not a route decoration. 4A
 * builds one panel; 4B onwards add theirs into the same frame.
 */

export type PanelProps = {
  title: string;
  /** Rendered in the panel header, right-aligned -- status, confidence, actions. */
  accessory?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function Panel({ title, accessory, children, className }: PanelProps) {
  return (
    <section className={cn("nova-panel", className)} aria-label={title}>
      <header className="nova-panel-header">
        <h2 className="nova-panel-title">{title}</h2>
        {accessory ? <div className="nova-panel-accessory">{accessory}</div> : null}
      </header>
      <div className="nova-panel-body">{children}</div>
    </section>
  );
}
