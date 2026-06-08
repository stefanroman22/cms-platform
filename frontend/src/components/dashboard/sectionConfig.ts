import {
  LayoutDashboard,
  FileText,
  LocateFixed,
  Settings,
  Calendar,
  type LucideIcon,
} from "lucide-react";

export type SectionKey = "dashboard" | "cms" | "autofix" | "bookings" | "settings";

export interface SectionCaps {
  bookingEnabled: boolean;
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
  { key: "settings", label: "Settings", icon: Settings, adminOnly: true },
];

export const DEFAULT_VIEW: SectionKey = "dashboard";

export function visibleSections(
  isAdmin: boolean,
  caps: SectionCaps = { bookingEnabled: false }
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
