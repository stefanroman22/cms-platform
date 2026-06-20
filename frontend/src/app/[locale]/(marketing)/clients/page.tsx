import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { buildAlternates } from "@/i18n/alternates";
import type { Locale } from "@/lib/locale";
import { ProjectsGrid } from "@/components/work/ProjectsGrid";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "clientsPage" });
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    alternates: buildAlternates("/clients", locale),
  };
}

/**
 * Clients page: a short hero + the filterable projects grid. Hero copy lives
 * under the `clientsPage` namespace; project data lives in
 * `src/content/projects.ts`.
 */
export default async function ClientsPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("clientsPage");
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
            {t("eyebrow")}
          </p>
          <h1 className="text-balance font-display text-[clamp(2.25rem,6vw,4rem)] font-bold leading-[1.04] tracking-[-0.02em] text-text-primary">
            {t("title")}
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.15rem]">
            {t("subheading")}
          </p>
        </div>
      </section>

      <ProjectsGrid />
    </div>
  );
}
