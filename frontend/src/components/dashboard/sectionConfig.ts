import {
  LayoutDashboard,
  FileText,
  LocateFixed,
  Settings,
  Calendar,
  Search,
  type LucideIcon,
} from "lucide-react";

export type SectionKey = "dashboard" | "cms" | "autofix" | "bookings" | "seo" | "settings";

export interface SectionCaps {
  bookingEnabled: boolean;
  seoEnabled: boolean;
}

export interface SectionDef {
  key: SectionKey;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  /** Section is shown only when this capability is true (admins always see it). */
  requiresCap?: keyof SectionCaps;
}

export const PROJECT_SECTIONS: SectionDef[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "cms", label: "CMS", icon: FileText },
  { key: "autofix", label: "Auto-Fix", icon: LocateFixed },
  { key: "bookings", label: "Bookings", icon: Calendar, requiresCap: "bookingEnabled" },
  // Visible to everyone as a teaser; the functional content is admin-gated inside
  // SeoSection (clients see a "coming soon" message until we open the agent to them).
  { key: "seo", label: "SEO & GEO", icon: Search },
  { key: "settings", label: "Settings", icon: Settings, adminOnly: true },
];

export const DEFAULT_VIEW: SectionKey = "dashboard";

export function visibleSections(
  isAdmin: boolean,
  caps: SectionCaps = { bookingEnabled: false, seoEnabled: false }
): SectionDef[] {
  return PROJECT_SECTIONS.filter((s) => {
    if (s.adminOnly && !isAdmin) return false;
    if (s.requiresCap && !caps[s.requiresCap] && !isAdmin) return false;
    return true;
  });
}

export function isAccessibleView(
  view: string | null,
  isAdmin: boolean,
  caps?: SectionCaps
): view is SectionKey {
  return view !== null && visibleSections(isAdmin, caps).some((s) => s.key === view);
}
