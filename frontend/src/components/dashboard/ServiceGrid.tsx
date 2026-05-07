"use client";

import { useMemo } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { BoxSelect, Mail } from "lucide-react";
import { PageTabs } from "@/components/dashboard/PageTabs";
import { ServiceCard, type ServiceCardService } from "@/components/dashboard/ServiceCard";

const EMAIL_TYPES = new Set(["email_config"]);

// Pages always rendered in this order; everything else is alphabetical before "General"
const PAGE_ORDER = ["General"];

function sortPages(pages: string[]): string[] {
  const pinned = PAGE_ORDER.filter((p) => pages.includes(p));
  const others = pages.filter((p) => !PAGE_ORDER.includes(p)).sort();
  // Put non-General pages first, General last
  return [...others, ...pinned];
}

interface ServiceGridProps {
  services: ServiceCardService[];
  projectSlug: string;
  isAdmin: boolean;
  removingKey: string | null;
  onRemove: (serviceKey: string) => void;
}

export function ServiceGrid({
  services,
  projectSlug,
  isAdmin,
  removingKey,
  onRemove,
}: ServiceGridProps) {
  // Separate email services — they get their own section regardless of page
  const emailServices = services.filter((s) => EMAIL_TYPES.has(s.service_type_slug));
  const contentServices = services.filter((s) => !EMAIL_TYPES.has(s.service_type_slug));

  // Derive sorted page list from content services
  const pages = useMemo(() => {
    const pageSet = new Set(contentServices.map((s) => s.page_name || "General"));
    return sortPages(Array.from(pageSet));
  }, [contentServices]);

  // Active page is URL-derived so browser back from a service editor lands
  // on the same tab the user was on. URL: ?tab=<page-name>. Falls back to
  // the first available page when the param is missing or invalid.
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const effectivePage =
    requestedTab && pages.includes(requestedTab) ? requestedTab : (pages[0] ?? "General");

  function setActivePage(page: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", page);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  const visibleServices = contentServices.filter(
    (s) => (s.page_name || "General") === effectivePage
  );

  if (services.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white py-16 text-center dark:border-zinc-700 dark:bg-zinc-900">
        <BoxSelect className="h-8 w-8 text-zinc-300 mb-3 dark:text-zinc-600" />
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          No services configured yet.
        </p>
        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
          {isAdmin
            ? 'Click "Add Service" to get started.'
            : "An admin can add services to this project."}
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* ── Content services by page ───────────────────────────────────── */}
      {contentServices.length > 0 && (
        <>
          <PageTabs pages={pages} activePage={effectivePage} onSelect={setActivePage} />

          {/* AnimatePresence + key=page swaps the grid with a tiny
              fade + lift on tab change. `mode="wait"` makes the new
              tab wait for the old one to leave so cards never
              overlap mid-transition. Duration kept short (~180ms)
              to feel responsive, not theatrical. */}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={effectivePage}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: [0.32, 0.72, 0, 1] }}
            >
              {visibleServices.length === 0 ? (
                <p className="text-sm text-zinc-400 dark:text-zinc-500 py-8 text-center">
                  No services on this page yet.
                </p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {visibleServices.map((svc) => (
                    <ServiceCard
                      key={svc.id}
                      service={svc}
                      projectSlug={projectSlug}
                      isAdmin={isAdmin}
                      removing={removingKey === svc.service_key}
                      onRemove={onRemove}
                      variant="content"
                    />
                  ))}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </>
      )}

      {/* ── Email / integrations section ───────────────────────────────── */}
      {emailServices.length > 0 && (
        <div className={contentServices.length > 0 ? "mt-10" : ""}>
          <div className="flex items-center gap-2 mb-4">
            <Mail className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Email &amp; Integrations
            </h3>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {emailServices.map((svc) => (
              <ServiceCard
                key={svc.id}
                service={svc}
                projectSlug={projectSlug}
                isAdmin={isAdmin}
                removing={removingKey === svc.service_key}
                onRemove={onRemove}
                variant="email"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
