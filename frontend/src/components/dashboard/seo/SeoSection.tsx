// SeoSection.tsx
// Static placeholder: the SEO/GEO feature is being rebuilt from scratch, so this section has
// no backend calls and no agent behind it. Everyone (admins and clients) sees the same panel.
import { Search, Sparkles } from "lucide-react";

export function SeoSection() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-300 bg-white/50 px-6 py-16 text-center dark:border-zinc-700 dark:bg-zinc-900/40">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
        <Search className="h-6 w-6" aria-hidden />
      </div>
      <span className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
        <Sparkles className="h-3 w-3" aria-hidden /> Coming soon
      </span>
      <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
        SEO &amp; GEO — work in progress
      </h3>
      <p className="mt-2 max-w-md text-sm text-zinc-500 dark:text-zinc-400">
        We&apos;re building an AI assistant that boosts your visibility on Google and on AI search
        engines like ChatGPT, Perplexity and Gemini. You&apos;ll be able to run it on your own site
        here soon — we&apos;ll let you know the moment it&apos;s ready.
      </p>
    </div>
  );
}
