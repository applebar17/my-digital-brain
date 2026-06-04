export type ChatIconName = "panel" | "new" | "search" | "more";

interface ChatIconProps {
  name: ChatIconName;
}

export function ChatIcon({ name }: ChatIconProps) {
  if (name === "new") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M4 20h16M5.5 14.5 15.8 4.2a2 2 0 0 1 2.8 2.8L8.3 17.3 4 18.5l1.5-4Z" />
      </svg>
    );
  }
  if (name === "search") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="m20 20-4.4-4.4M10.5 17a6.5 6.5 0 1 1 0-13 6.5 6.5 0 0 1 0 13Z" />
      </svg>
    );
  }
  if (name === "more") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M5 12h.01M12 12h.01M19 12h.01" />
      </svg>
    );
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-13ZM9 4v16" />
    </svg>
  );
}
