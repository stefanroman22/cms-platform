"use client";

import Link from "next/link";
import { Pencil, Trash2 } from "lucide-react";
import { ServiceIcon } from "@/components/dashboard/ServiceIcon";
import { dashboardSectionCardCn } from "@/lib/styles";

export interface ServiceCardService {
  id: string;
  service_key: string;
  label: string | null;
  service_type_slug: string;
  service_type_name: string;
  service_type_icon: string;
  display_order: number;
  page_name: string;
  last_updated: string | null;
}

interface ServiceCardProps {
  service: ServiceCardService;
  projectSlug: string;
  isAdmin: boolean;
  removing: boolean;
  onRemove: (serviceKey: string) => void;
  /** Visual variant: "content" (default) or "email" (dimmed, action-oriented) */
  variant?: "content" | "email";
}

export function ServiceCard({
  service: svc,
  projectSlug,
  isAdmin,
  removing,
  onRemove,
  variant = "content",
}: ServiceCardProps) {
  const isEmail = variant === "email";

  return (
    <div
      className={`${dashboardSectionCardCn} p-5 flex flex-col gap-4 ${
        isEmail ? "opacity-80 border-dashed" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3 min-w-0">
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
              isEmail ? "bg-amber-50 dark:bg-amber-950" : "bg-zinc-100 dark:bg-zinc-800"
            }`}
          >
            <ServiceIcon
              name={svc.service_type_icon}
              className={`h-4 w-4 ${
                isEmail ? "text-amber-600 dark:text-amber-400" : "text-zinc-600 dark:text-zinc-300"
              }`}
            />
          </span>
          <div className="min-w-0">
            <p className="font-medium text-zinc-900 leading-snug truncate dark:text-zinc-100">
              {svc.label ?? svc.service_key}
            </p>
            <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5">
              {svc.service_type_name}
            </p>
          </div>
        </div>

        {isAdmin && (
          <button
            onClick={() => onRemove(svc.service_key)}
            disabled={removing}
            className="shrink-0 flex items-center justify-center h-7 w-7 rounded-md text-zinc-300 hover:text-red-500 hover:bg-red-50 dark:text-zinc-600 dark:hover:text-red-400 dark:hover:bg-red-950 transition-colors disabled:opacity-40 cursor-pointer"
            aria-label="Remove service"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <div className="flex items-center justify-between mt-auto">
        <span className="text-xs text-zinc-400 dark:text-zinc-500">
          {svc.last_updated
            ? `Updated ${new Date(svc.last_updated).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
              })}`
            : "No content yet"}
        </span>
        <Link
          href={`/dashboard/${projectSlug}/${svc.service_key}`}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            isEmail
              ? "bg-amber-600 text-white hover:bg-amber-700 dark:bg-amber-700 dark:hover:bg-amber-600"
              : "bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
          }`}
        >
          <Pencil className="h-3 w-3" />
          {isEmail ? "Configure" : "Edit"}
        </Link>
      </div>
    </div>
  );
}
