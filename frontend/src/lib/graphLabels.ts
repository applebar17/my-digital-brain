import type { NodeSearchResult } from "../types/graph";

export function nodeId(node: NodeSearchResult): string {
  const id = node.properties.id;
  return typeof id === "string" ? id : "";
}

export function nodeTitle(node: NodeSearchResult): string {
  return firstString(
    node.properties.display_name,
    node.properties.title,
    node.properties.name,
    node.properties.profile_key,
    node.properties.text,
    node.properties.id
  );
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
