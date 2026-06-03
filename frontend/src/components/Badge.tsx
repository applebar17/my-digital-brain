import type { ReactNode } from "react";

interface BadgeProps {
  tone?: "neutral" | "trust" | "warning" | "privacy" | "danger" | "info";
  children: ReactNode;
}

export function Badge({ tone = "neutral", children }: BadgeProps) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
