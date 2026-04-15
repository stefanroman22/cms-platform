import Link from "next/link";
import { Layers } from "lucide-react";

interface LogoProps {
  /** "dark" (default) — white text for dark backgrounds.
   *  "light" — zinc-900 text for light/white backgrounds. */
  variant?: "dark" | "light";
  /** When false the logo renders as a static element (not clickable). Default true. */
  clickable?: boolean;
}

export function Logo({ variant = "dark", clickable = true }: LogoProps) {
  const isDark = variant === "dark";

  const content = (
    <>
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
          isDark ? "bg-white" : "bg-zinc-900"
        }`}
      >
        <Layers
          className={`h-4 w-4 ${isDark ? "text-black" : "text-white"}`}
          strokeWidth={1.5}
        />
      </span>
      <span
        className={`text-sm font-semibold tracking-tight ${
          isDark ? "text-white" : "text-zinc-900"
        }`}
      >
        Roman Technologies
      </span>
    </>
  );

  if (!clickable) {
    return (
      <div className="flex w-fit items-center gap-2.5">
        {content}
      </div>
    );
  }

  return (
    <Link
      href="/"
      className="flex w-fit items-center gap-2.5 transition-opacity duration-200 hover:opacity-75"
    >
      {content}
    </Link>
  );
}
