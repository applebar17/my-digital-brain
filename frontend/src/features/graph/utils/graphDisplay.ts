import type { GraphViewNode, GraphViewRelationship } from "../../../types/graph";

export const graphNodeLabels = [
  "",
  "Person",
  "Event",
  "Place",
  "Organization",
  "Object",
  "Animal",
  "SocialCircle",
  "Topic",
  "Source",
  "Claim",
  "Perception",
  "RelationshipContext",
  "ProfileMemory"
];

export type GraphTone = "verified" | "inferred" | "disputed" | "private" | "neutral";

export function graphNodeTone(node: GraphViewNode): GraphTone {
  if (node.privacy_level === "sensitive" || node.privacy_level === "private") {
    return "private";
  }
  if (node.trust_level === "contradicted" || node.lifecycle_state === "disputed") {
    return "disputed";
  }
  if (node.trust_level === "llm_inferred" || node.trust_level === "inferred") {
    return "inferred";
  }
  if (node.trust_level === "user_confirmed" || node.trust_level === "source_stated") {
    return "verified";
  }
  return toneFromLabel(node.label);
}

export function graphRelationshipTone(relationship: GraphViewRelationship): GraphTone {
  if (relationship.lifecycle_state === "disputed") {
    return "disputed";
  }
  if (relationship.lifecycle_state === "inferred") {
    return "inferred";
  }
  return "neutral";
}

export function graphToneColor(tone: GraphTone): string {
  if (tone === "verified") {
    return "#14d8a2";
  }
  if (tone === "inferred") {
    return "#f6a524";
  }
  if (tone === "disputed") {
    return "#ff5d5d";
  }
  if (tone === "private") {
    return "#a78bfa";
  }
  return "#8fb5ff";
}

export function trimGraphLabel(value: string | null | undefined, maxLength = 28): string {
  if (!value) {
    return "Untitled";
  }
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
}

function toneFromLabel(label: string): GraphTone {
  if (label === "Person" || label === "Event" || label === "Place") {
    return "verified";
  }
  if (label === "Claim" || label === "Perception" || label === "RelationshipContext") {
    return "inferred";
  }
  if (label === "ProfileMemory") {
    return "private";
  }
  return "neutral";
}
