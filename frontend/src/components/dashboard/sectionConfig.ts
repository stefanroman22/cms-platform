import { LayoutDashboard, FileText, Sparkles, Settings, type LucideIcon } from "lucide-react";

export type SectionKey = "dashboard" | "cms" | "autofix" | "settings";

export interface SectionDef {
  key: SectionKey;
  label: string;
  icon: LucideIcon;
  /** Renders in the rail only for admins. */
  adminOnly?: boolean;
}

export const PROJECT_SECTIONS: SectionDef[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "cms", label: "CMS", icon: FileText },
  { key: "autofix", label: "Auto-Fix", icon: Sparkles },
  { key: "settings", label: "Settings", icon: Settings, adminOnly: true },
];

export const DEFAULT_VIEW: SectionKey = "dashboard";

export function visibleSections(isAdmin: boolean): SectionDef[] {
  return PROJECT_SECTIONS.filter((s) => !s.adminOnly || isAdmin);
}

export function isAccessibleView(view: string | null, isAdmin: boolean): view is SectionKey {
  return view !== null && visibleSections(isAdmin).some((s) => s.key === view);
}
