import type { ReactNode } from "react";

export type WorkspaceId = "chat" | "graph" | "analytics";

interface AppShellProps {
  workspace: WorkspaceId;
  onNavigate: (workspace: WorkspaceId) => void;
  children: ReactNode;
}

const navItems: Array<{ id: WorkspaceId; label: string; icon: string }> = [
  { id: "chat", label: "Chat", icon: "C" },
  { id: "graph", label: "Memory Graph", icon: "G" },
  { id: "analytics", label: "Analytics", icon: "A" }
];

export function AppShell({ workspace, onNavigate, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-nav" aria-label="Primary navigation">
        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true">
            MDB
          </span>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              className={`nav-item ${workspace === item.id ? "is-active" : ""}`}
              type="button"
              key={item.id}
              title={item.label}
              aria-label={item.label}
              onClick={() => onNavigate(item.id)}
            >
              <span aria-hidden="true">{item.icon}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="app-main">{children}</main>
    </div>
  );
}
