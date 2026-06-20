// SettingsTab.tsx  (read-only placeholder in Plan 1; toggle wired in Plan 2)
export function SettingsTab({ projectSlug }: { projectSlug: string }) {
  return (
    <p className="text-sm text-zinc-500">
      SEO settings for <span className="font-mono">{projectSlug}</span> appear here once the agent
      has run (blog route, locale scope, enable toggle).
    </p>
  );
}
