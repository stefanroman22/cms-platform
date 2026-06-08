"use client";

import { useMemo, useState } from "react";
import { LazyMotion, domAnimation, m, AnimatePresence, MotionConfig } from "motion/react";
import { ArrowUpRight, Search } from "lucide-react";
import { projects } from "@/content/projects";
import { REVEAL_EASE } from "@/components/motion/Reveal";

/**
 * Clients page grid: detailed project cards (image, name, tagline, key info,
 * live link) with a name filter. Reads the same `content/projects.ts` as the
 * home carousel. Cards animate in and re-flow as the filter narrows results.
 */
export function ProjectsGrid() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) => p.name.toLowerCase().includes(q) || p.short.toLowerCase().includes(q)
    );
  }, [query]);

  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="px-6 pb-24 sm:pb-32">
          <div className="mx-auto max-w-6xl">
            {/* Search */}
            <div className="mx-auto mb-10 max-w-md">
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary"
                  aria-hidden="true"
                />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search projects…"
                  aria-label="Search projects by name"
                  className="w-full rounded-xl border border-border bg-surface/40 py-3 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors focus:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
                />
              </div>
            </div>

            {filtered.length === 0 ? (
              <p className="text-center text-sm text-text-secondary">
                No projects match &ldquo;{query}&rdquo;.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                <AnimatePresence>
                  {filtered.map((p, i) => (
                    <m.article
                      key={p.id}
                      layout
                      initial={{ opacity: 0, y: 24 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -12 }}
                      whileHover={{ y: -6 }}
                      transition={{ duration: 0.4, ease: REVEAL_EASE, delay: i * 0.05 }}
                      className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-surface/30 transition-colors hover:border-accent/40"
                    >
                      <div className="relative aspect-[16/10] w-full overflow-hidden">
                        <img
                          src={p.image}
                          alt={`${p.name} preview`}
                          loading="lazy"
                          draggable={false}
                          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        />
                        {p.url && (
                          <a
                            href={p.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`Open ${p.name} in a new tab`}
                            className="group/btn absolute right-3 top-3 flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-black/40 text-white backdrop-blur-sm transition-all duration-300 hover:scale-105 hover:border-accent hover:bg-accent hover:text-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer"
                          >
                            <ArrowUpRight className="h-5 w-5 transition-transform duration-300 group-hover/btn:rotate-45" />
                          </a>
                        )}
                      </div>
                      <div className="flex flex-1 flex-col p-6">
                        <h3 className="font-display text-lg font-semibold text-text-primary">
                          {p.name}
                        </h3>
                        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                          {p.tagline}
                        </p>
                        <dl className="mt-5 space-y-2 border-t border-border pt-4">
                          {p.keyInfo.map((info) => (
                            <div key={info.label} className="flex items-baseline gap-3 text-sm">
                              <dt className="w-16 shrink-0 text-text-tertiary">{info.label}</dt>
                              <dd className="text-text-secondary">{info.value}</dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    </m.article>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
