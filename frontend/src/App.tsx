import { useEffect, useMemo, useState } from "react";
import { AppShell, type WorkspaceId } from "./components/AppShell";
import { AnalyticsView } from "./views/AnalyticsView";
import { ChatView } from "./views/ChatView";
import { GraphView } from "./views/GraphView";

const workspaces: WorkspaceId[] = ["chat", "graph", "analytics"];

export default function App() {
  const [workspace, setWorkspace] = useState<WorkspaceId>(() => parseHashWorkspace());

  useEffect(() => {
    const onHashChange = () => setWorkspace(parseHashWorkspace());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const content = useMemo(() => {
    if (workspace === "graph") {
      return <GraphView />;
    }
    if (workspace === "analytics") {
      return <AnalyticsView />;
    }
    return <ChatView />;
  }, [workspace]);

  return (
    <AppShell
      workspace={workspace}
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
