import { Fragment } from "react";

interface InlineFormattedTextProps {
  text: string;
}

/** Render the small, intentionally supported subset of chat formatting. */
export function InlineFormattedText({ text }: InlineFormattedTextProps) {
  return (
    <>
      {text.split("\n").map((line, lineIndex) => (
        <Fragment key={`${lineIndex}-${line}`}>
          {lineIndex > 0 ? <br /> : null}
          {renderBold(line)}
        </Fragment>
      ))}
    </>
  );
}

function renderBold(text: string) {
  const parts = text.split("**");
  if (parts.length < 3 || parts.length % 2 === 0) {
    return text;
  }
  return parts.map((part, index) =>
    index % 2 === 1 ? <strong key={`${index}-${part}`}>{part}</strong> : part
  );
}
