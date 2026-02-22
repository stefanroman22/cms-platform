import Link from "next/link";
import { Layers } from "lucide-react";

/**
 * Brand logo — used in both Header and Footer.
 * White icon mark + wordmark on a dark background.
 */
export function Logo() {
  return (
    <Link
      href="/"
      className="flex w-fit items-center gap-2.5 transition-opacity duration-200 hover:opacity-75"
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
        <Layers className="h-4 w-4 text-black" strokeWidth={1.5} />
      </span>
      <span className="text-sm font-semibold tracking-tight text-white">
        Roman Technologies
      </span>
    </Link>
  );
}
