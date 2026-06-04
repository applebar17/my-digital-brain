import type { ReactNode } from "react";

export type WorkspaceId = "chat" | "graph" | "analytics";
export type AppTheme = "dark" | "light";

interface AppShellProps {
  workspace: WorkspaceId;
  onNavigate: (workspace: WorkspaceId) => void;
  theme: AppTheme;
  onToggleTheme: () => void;
  children: ReactNode;
}

type IconName = "chat" | "graph" | "analytics" | "sun" | "moon";

const navItems: Array<{ id: WorkspaceId; label: string; icon: IconName }> = [
  { id: "chat", label: "Chat", icon: "chat" },
  { id: "graph", label: "Memory Graph", icon: "graph" },
  { id: "analytics", label: "Analytics", icon: "analytics" }
];

export function AppShell({ workspace, onNavigate, theme, onToggleTheme, children }: AppShellProps) {
  return (
    <div className="app-shell" data-theme={theme}>
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
              <Icon name={item.icon} />
            </button>
          ))}
        </nav>
      </aside>
      <main className="app-main">
        <button
          className="theme-toggle"
          type="button"
          title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          aria-pressed={theme === "light"}
          onClick={onToggleTheme}
        >
          <Icon name={theme === "dark" ? "sun" : "moon"} />
        </button>
        {children}
      </main>
    </div>
  );
}

function Icon({ name }: { name: IconName }) {
  if (name === "chat") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M5 6.5A3.5 3.5 0 0 1 8.5 3h7A3.5 3.5 0 0 1 19 6.5v4.9a3.5 3.5 0 0 1-3.5 3.5H11l-4.4 4.2v-4.2A3.5 3.5 0 0 1 5 11.4V6.5Z" />
      </svg>
    );
  }
  if (name === "graph") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M7 8.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM17 21.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM17 8.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM8.9 7l6.2 10M9.8 5.5h4.4M9.8 18.5h4.4" />
      </svg>
    );
  }
  if (name === "analytics") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M5 20V9M12 20V4M19 20v-7M3.5 20h17" />
      </svg>
    );
  }
  if (name === "sun") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M12 5V2M12 22v-3M5 12H2M22 12h-3M6.4 6.4 4.2 4.2M19.8 19.8l-2.2-2.2M17.6 6.4l2.2-2.2M4.2 19.8l2.2-2.2M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
      </svg>
    );
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M20.5 14.2A7.7 7.7 0 0 1 9.8 3.5 8.6 8.6 0 1 0 20.5 14.2Z" />
    </svg>
  );
}
