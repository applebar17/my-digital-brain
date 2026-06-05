import { useEffect, useMemo, useState } from "react";
import { AppShell, type AppTheme, type WorkspaceId } from "./components/AppShell";
import { AnalyticsView } from "./views/AnalyticsView";
import { AITraceDebugView } from "./views/AITraceDebugView";
import { ChatView } from "./views/ChatView";
import { GraphView } from "./views/GraphView";
import { aiTraceDebugEnabled } from "./config";

const workspaces: WorkspaceId[] = aiTraceDebugEnabled
  ? ["chat", "graph", "analytics", "debug"]
  : ["chat", "graph", "analytics"];
const themeStorageKey = "my-digital-brain.theme";

export default function App() {
  const [workspace, setWorkspace] = useState<WorkspaceId>(() => parseHashWorkspace());
  const [theme, setTheme] = useState<AppTheme>(() => initialTheme());

  useEffect(() => {
    const onHashChange = () => setWorkspace(parseHashWorkspace());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem(themeStorageKey, theme);
  }, [theme]);

  const content = useMemo(() => {
    if (workspace === "graph") {
      return <GraphView />;
    }
    if (workspace === "analytics") {
      return <AnalyticsView />;
    }
    if (workspace === "debug" && aiTraceDebugEnabled) {
      return <AITraceDebugView sessionId={parseHashSessionId()} />;
    }
    return <ChatView />;
  }, [workspace]);

  return (
    <AppShell
      workspace={workspace}
      theme={theme}
      onToggleTheme={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
      debugEnabled={aiTraceDebugEnabled}
      onNavigate={(nextWorkspace) => {
        window.location.hash = nextWorkspace;
        setWorkspace(nextWorkspace);
      }}
    >
      {content}
    </AppShell>
  );
}

function parseHashWorkspace(): WorkspaceId {
  const hash = window.location.hash.replace("#", "").split("/")[0] as WorkspaceId;
  return workspaces.includes(hash) ? hash : "chat";
}

function parseHashSessionId(): string | undefined {
  const [, sessionId] = window.location.hash.replace("#", "").split("/");
  return sessionId || undefined;
}

function initialTheme(): AppTheme {
  const stored = localStorage.getItem(themeStorageKey);
  return stored === "light" ? "light" : "dark";
}
