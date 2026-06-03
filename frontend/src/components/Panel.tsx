import type { ReactNode } from "react";

interface PanelProps {
  title?: string;
  eyebrow?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export function Panel({ title, eyebrow, actions, children }: PanelProps) {
  return (
    <section className="panel">
      {(title || eyebrow || actions) && (
        <header className="panel-header">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h2>{title}</h2>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
