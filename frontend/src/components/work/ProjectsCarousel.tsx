"use client";

import { useEffect, useRef, useState } from "react";
import { LazyMotion, domAnimation, m, AnimatePresence, MotionConfig } from "motion/react";
import { ChevronLeft, ChevronRight, ArrowUpRight } from "lucide-react";
import { projects } from "@/content/projects";
import { cn } from "@/lib/utils";

const EXPO = [0.16, 1, 0.3, 1] as const;

/** Directional slide for the image — `custom` carries the travel direction so
 *  the exiting frame leaves the way the new one enters. */
const slide = {
  enter: (dir: number) => ({ opacity: 0, x: dir * 64 }),
  center: { opacity: 1, x: 0 },
  exit: (dir: number) => ({ opacity: 0, x: dir * -64 }),
};

const arrowCn =
  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border text-text-secondary transition-colors hover:border-accent/50 hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer";

export function ProjectsCarousel() {
  // [index, direction] — direction drives the image slide on every change.
  const [[active, direction], setState] = useState<[number, number]>([0, 0]);
  const count = projects.length;
  const project = projects[active];
  const scrollRef = useRef<HTMLDivElement>(null);

  const select = (i: number) => {
    if (i !== active) setState([i, i > active ? 1 : -1]);
  };
  const step = (dir: number) => setState([(active + dir + count) % count, dir]);

  // Keep the selected name in view. The names sit flush (no gaps — spacing is
  // padding) so the row edge always slices through a name, leaving the next
  // one's first letters peeking to signal there are more projects.
  useEffect(() => {
    const el = scrollRef.current;
    (el?.children[active] as HTMLElement | undefined)?.scrollIntoView({
      behavior: "smooth",
      inline: "nearest",
      block: "nearest",
    });
  }, [active]);

  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <div>
          {/* One row of project names + arrows. The names scroll horizontally so
              more projects never wrap or stack; the next name's first letters
              peek past the edge to signal there are more — use the arrows. */}
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <div
              ref={scrollRef}
              data-lenis-prevent
              className="flex min-w-0 flex-1 items-center overflow-x-auto scroll-smooth [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              {projects.map((p, i) => {
                const isActive = i === active;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => select(i)}
                    aria-current={isActive}
                    className={cn(
                      "relative shrink-0 whitespace-nowrap px-2.5 py-1.5 text-sm font-medium transition-colors cursor-pointer first:pl-0",
                      isActive ? "text-accent" : "text-text-tertiary hover:text-text-secondary"
                    )}
                  >
                    {p.short}
                    {isActive && (
                      <span
                        aria-hidden="true"
                        className="absolute inset-x-2.5 bottom-0 h-0.5 rounded-full bg-accent"
                      />
                    )}
                  </button>
                );
              })}
            </div>
            <div className="flex shrink-0 items-center gap-1.5 pl-1">
              <button
                type="button"
                onClick={() => step(-1)}
                aria-label="Previous project"
                className={arrowCn}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => step(1)}
                aria-label="Next project"
                className={arrowCn}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Image stage — gold ambient shadow + inset ring matching the theme. */}
          <div className="relative mt-5 aspect-[16/10] w-full overflow-hidden rounded-2xl border border-border bg-surface/40 shadow-[0_28px_80px_-28px_rgba(201,169,97,0.45)]">
            <AnimatePresence initial={false} custom={direction}>
              <m.img
                key={project.id}
                src={project.image}
                alt={`${project.name} preview`}
                loading="lazy"
                draggable={false}
                custom={direction}
                variants={slide}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.5, ease: EXPO }}
                className="absolute inset-0 h-full w-full object-cover"
              />
            </AnimatePresence>

            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 z-10 rounded-2xl ring-1 ring-inset ring-accent/15"
            />

            {/* Open the live site in a new tab — top-right, with a hover lift. */}
            {project.url && (
              <a
                href={project.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${project.name} in a new tab`}
                className="group absolute right-3 top-3 z-20 flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-black/40 text-white backdrop-blur-sm transition-all duration-300 hover:scale-105 hover:border-accent hover:bg-accent hover:text-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-black active:scale-95 cursor-pointer"
              >
                <ArrowUpRight className="h-5 w-5 transition-transform duration-300 group-hover:rotate-45" />
              </a>
            )}
          </div>

          {/* One sentence (max two lines). */}
          <AnimatePresence mode="wait">
            <m.p
              key={project.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3, ease: EXPO }}
              className="mt-4 line-clamp-2 text-sm leading-relaxed text-text-secondary"
            >
              {project.tagline}
            </m.p>
          </AnimatePresence>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
