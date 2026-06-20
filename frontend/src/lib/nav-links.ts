/**
 * Primary site navigation. Shared by `Header` (Server Component, desktop
 * nav bar) and `HeaderRightCluster` (client island, mobile drawer).
 * Single source of truth so a future nav change touches one file.
 *
 * `key` is the i18n key within the `nav` message namespace (see messages/en.json).
 * Consumers call `t(link.key)` to render the translated label.
 */
export const NAV_LINKS = [
  { key: "about", href: "/about" },
  { key: "clients", href: "/clients" },
  { key: "team", href: "/team" },
  { key: "contact", href: "/contact" },
] as const;
