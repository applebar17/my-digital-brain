import type { ReactNode } from "react";

export type WorkspaceId = "chat" | "graph" | "analytics";

interface AppShellProps {
  workspace: WorkspaceId;
  onNavigate: (workspace: WorkspaceId) => void;
  children: ReactNode;
}

const navItems: Array<{ id: WorkspaceId; label: string; hint: string }> = [
  { id: "chat", label: "Chat", hint: "Capture and query memories" },
  { id: "graph", label: "Memory Graph", hint: "Search and inspect graph context" },
  { id: "analytics", label: "Analytics", hint: "Graph health and coverage" }
];

export function AppShell({ workspace, onNavigate, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-nav" aria-label="Primary navigation">
        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true">
            MB
          </span>
          <div>
            <p className="eyebrow">Private Workspace</p>
            <h1>My Digital Brain</h1>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              className={`nav-item ${workspace === item.id ? "is-active" : ""}`}
              type="button"
              key={item.id}
              onClick={() => onNavigate(item.id)}
            >
              <span>{item.label}</span>
              <small>{item.hint}</small>
            </button>
          ))}
        </nav>
      </aside>
      <main className="app-main">{children}</main>
    </div>
  );
}
