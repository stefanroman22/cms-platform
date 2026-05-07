"use client";

interface ArcSpinnerProps {
  /** Outer diameter in pixels. Stroke scales with size. */
  size?: number;
  /** Stroke colour for the bright arc. Defaults to currentColor. */
  color?: string;
}

/**
 * Inline version of the post-login `LoadingScreen` comet spinner.
 *
 * SVG-based for two reasons:
 *   1. A `stroke-dasharray` arc renders crisply at 16-40 px where the
 *      original conic-gradient's 1 px masked ring looked nearly static.
 *   2. Tailwind's `animate-spin` (CSS keyframes) is hardware-accelerated
 *      and never gets paused by React re-renders — the framer
 *      `animate={{ rotate: 360 }}` approach was visibly stalling.
 *
 * Two layers — a dim full-circle track + a bright 110° arc — match
 * the comet feel of the full-screen loader without needing a conic
 * gradient + mask.
 *
 * Pure visual; no semantics. Wrap with `aria-busy` / `role="status"`
 * at the call site if screen readers should announce the wait.
 */
export function ArcSpinner({ size = 28, color = "currentColor" }: ArcSpinnerProps) {
  // Stroke ~7 % of size, clamped to whole pixels — a touch thicker than
  // the 2.2 % of the 68 px loader so smaller spinners stay legible.
  const stroke = Math.max(1.5, Math.round(size * 0.07));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  // Bright arc covers ~30 % of the circumference (≈ 108°).
  const arcLength = circumference * 0.3;
  const dashGap = circumference - arcLength;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="animate-spin"
      style={{ animationDuration: "1.1s" }}
      aria-hidden="true"
    >
      {/* Dim track ring — non-rotating context for the comet to move
          against. Same opacity as the loading-screen track. */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0.12}
        strokeWidth={stroke}
      />
      {/* Bright arc — the rotation comes from the parent <svg>'s
          animate-spin, so the arc's start position is irrelevant. */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeOpacity={0.92}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${arcLength} ${dashGap}`}
      />
    </svg>
  );
}
