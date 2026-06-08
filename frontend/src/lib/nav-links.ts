/**
 * Primary site navigation. Shared by `Header` (Server Component, desktop
 * nav bar) and `HeaderRightCluster` (client island, mobile drawer).
 * Single source of truth so a future nav change touches one file.
 */
export const NAV_LINKS = [
  { label: "About", href: "/about" },
  { label: "Clients", href: "/clients" },
  { label: "Team", href: "/team" },
  { label: "Contact", href: "/contact" },
] as const;
