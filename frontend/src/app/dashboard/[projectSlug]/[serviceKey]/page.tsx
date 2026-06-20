"use client";

import { use, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArcSpinner } from "@/components/ui/ArcSpinner";

/**
 * Legacy route. Service editing now happens inline in the project page's CMS
 * section (`?view=cms&service=`), so this route only translates old links
 * and bookmarks into the new shape, preserving the locale.
 */
export default function LegacyServiceEditorRedirect({
  params,
}: {
  params: Promise<{ projectSlug: string; serviceKey: string }>;
}) {
  const { projectSlug, serviceKey } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const next = new URLSearchParams();
    next.set("view", "cms");
    next.set("service", serviceKey);
    const locale = searchParams.get("locale");
    if (locale) next.set("locale", locale);
    router.replace(`/dashboard/${projectSlug}?${next.toString()}`);
  }, [router, searchParams, projectSlug, serviceKey]);

  return (
    <div
      role="status"
      aria-label="Opening editor"
      className="flex min-h-[60vh] items-center justify-center"
    >
      <ArcSpinner size={22} />
    </div>
  );
}
