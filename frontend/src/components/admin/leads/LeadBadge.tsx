"use client";

interface LeadBadgeProps {
  label: string;
  className: string;
  width?: string; // tailwind width class (e.g. "w-24"); default "w-24"
}

export function LeadBadge({ label, className, width = "w-24" }: LeadBadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        width,
        className,
      ].join(" ")}
    >
      {label}
    </span>
  );
}
