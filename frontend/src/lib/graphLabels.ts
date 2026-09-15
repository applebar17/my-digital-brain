import type { NodeSearchResult } from "../types/graph";

export function nodeId(node: NodeSearchResult): string {
  const id = node.properties.id;
  return typeof id === "string" ? id : "";
}

export function nodeTitle(node: NodeSearchResult): string {
  return firstString(
    node.properties.display_name,
    node.properties.name,
    node.properties.title,
    node.properties.log_text,
    node.properties.label_text,
    node.properties.profile_key,
    node.properties.value,
    node.properties.caption,
    node.properties.text,
    firstAlias(node.properties.aliases),
    node.properties.description,
    node.properties.emotional_summary,
    node.properties.original_user_words,
    unnamedNodeLabel(node.label)
  );
}

function firstAlias(value: unknown): string | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.find(
    (alias): alias is string => typeof alias === "string" && alias.trim().length > 0
  );
}

function unnamedNodeLabel(label: string): string {
  const readableLabel = label.replaceAll(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  return `Unnamed ${readableLabel}`;
}

export function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }
  return "Untitled";
}

export function compactId(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  if (value.length <= 12) {
    return value;
  }
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

export function formatUnknown(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Unknown";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
