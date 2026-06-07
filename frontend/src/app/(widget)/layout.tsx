/**
 * Widget route group layout — intentionally bare: no Header, no Footer,
 * no marketing providers. The /w/[slug] page is served inside an iframe
 * on third-party sites.
 */
export default function WidgetLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
