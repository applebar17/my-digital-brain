import type { FormEvent } from "react";

interface ChatComposerProps {
  value: string;
  isSending: boolean;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function ChatComposer({ value, isSending, onChange, onSubmit }: ChatComposerProps) {
  return (
    <footer className="memory-chat-composer-shell">
      <form className="memory-chat-composer" onSubmit={onSubmit}>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ask a question or record a thought..."
          rows={2}
        />
        <button className="memory-chat-send" type="submit" disabled={isSending || !value.trim()}>
          {isSending ? "..." : "Send"}
        </button>
      </form>
      <p>AI assistant can make mistakes. Verify important information.</p>
    </footer>
  );
}
