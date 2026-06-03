interface StatusLineProps {
  status?: "idle" | "loading" | "error" | "success";
  message?: string;
}

export function StatusLine({ status = "idle", message }: StatusLineProps) {
  if (!message) {
    return null;
  }
  return <p className={`status-line status-${status}`}>{message}</p>;
}
