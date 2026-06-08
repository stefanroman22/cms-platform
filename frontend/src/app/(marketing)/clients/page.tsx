import type { Metadata } from "next";
import { ProjectsGrid } from "@/components/work/ProjectsGrid";

export const metadata: Metadata = {
  title: "Clients — Roman Technologies",
  description:
    "A selection of websites, applications and AI workflows we've built and now keep running for clients across the EU.",
};

/**
 * Clients page: a short hero + the filterable projects grid. Project data lives
 * in `src/content/projects.ts`.
 */
export default function ClientsPage() {
  return (
    <div className="bg-black">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-10 pt-14 sm:pb-12 sm:pt-24">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[660px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
          style={{
            background: "radial-gradient(circle, rgba(201,169,97,0.12), rgba(201,169,97,0) 70%)",
          }}
        />
        <div className="animate-fade-down relative z-10 mx-auto max-w-2xl text-center">
          <p className="mb-5 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
            Our work
          </p>
          <h1 className="text-balance font-display text-[clamp(2.25rem,6vw,4rem)] font-bold leading-[1.04] tracking-[-0.02em] text-text-primary">
            Built for ambitious companies.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.15rem]">
            A selection of websites, applications and AI workflows we&apos;ve designed, built and
            now keep running for clients across the EU.
          </p>
        </div>
      </section>

      <ProjectsGrid />
    </div>
  );
}
