import { Check } from "lucide-react";

export function TrustBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-text-tertiary">
      <Check className="h-3.5 w-3.5 shrink-0 text-accent/70" strokeWidth={2.5} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}
