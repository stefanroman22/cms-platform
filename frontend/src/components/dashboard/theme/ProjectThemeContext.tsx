"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useQuery } from "@/hooks/useQuery";
import { readTheme, type CmsTheme } from "@/lib/cms-rich-text";
import { FontLoader } from "./FontLoader";

/** Cache key of a project's theme; invalidating it refetches the context. */
export const themeKey = (projectSlug: string) => `theme:${projectSlug}`;

interface ThemeResponse {
  theme: unknown;
  service_key: string | null;
}

interface ProjectThemeValue {
  theme: CmsTheme | null;
  serviceKey: string | null;
  refresh(): void;
}

const ProjectThemeContext = createContext<ProjectThemeValue>({
  theme: null,
  serviceKey: null,
  refresh: () => {},
});

function fetchTheme(projectSlug: string): Promise<ThemeResponse> {
  return fetch(`/api/projects/${projectSlug}/theme`, {
    credentials: "include",
    cache: "no-store",
  }).then((r) => {
    if (!r.ok) throw new Error("Failed to load theme.");
    return r.json();
  });
}

/** The project's draft theme (ADR-0011) for every dashboard view of the
 *  project; also loads its fonts so previews render in them. */
export function ProjectThemeProvider({
  projectSlug,
  children,
}: {
  projectSlug: string;
  children: ReactNode;
}) {
  const { data, refresh } = useQuery<ThemeResponse>(
    themeKey(projectSlug),
    () => fetchTheme(projectSlug),
    { ttl: 5 * 60 * 1000 }
  );
  const theme = useMemo(() => readTheme(data?.theme), [data]);
  const serviceKey = data?.service_key ?? null;
  const value = useMemo(() => ({ theme, serviceKey, refresh }), [theme, serviceKey, refresh]);

  return (
    <ProjectThemeContext.Provider value={value}>
      <FontLoader theme={theme} />
      {children}
    </ProjectThemeContext.Provider>
  );
}

export function useProjectTheme(): ProjectThemeValue {
  return useContext(ProjectThemeContext);
}
