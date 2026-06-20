// frontend/src/components/dashboard/seo/types.ts
export interface SeoOverview {
  enabled: boolean;
  blog_route: string | null;
  last_run_at: string | null;
  seo_score: number | null;
  geo_score: number | null;
  local_score: number | null;
  last_status: string | null;
  locales: string[];
}

export interface SeoPlanItem {
  id: string;
  track: "seo" | "geo" | "local";
  title: string;
  description: string;
  rationale: string;
  priority: number;
  effort: string;
  action_kind: "content" | "meta" | "schema" | "article" | "new_page" | "manual_human";
  target: string | null;
  status: "planned" | "in_progress" | "applied" | "published" | "dismissed";
}

export interface SeoRun {
  id: string;
  status: string;
  trigger: string;
  summary: string | null;
  scores: Record<string, number>;
  started_at: string;
  finished_at: string | null;
}

export interface SeoChange {
  id: string;
  kind: string;
  target: string | null;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  verified: Record<string, unknown>;
  reverted: boolean;
  applied_at: string;
  published_at: string | null;
}

export interface SeoHistory {
  runs: SeoRun[];
  changes: SeoChange[];
}

export interface SeoCompetitor {
  id: string;
  name: string;
  url: string | null;
  location: string | null;
  signals: Record<string, unknown>;
  analysis: string;
  captured_at: string;
}

export interface SeoArticle {
  id: string;
  slug: string;
  locale: string;
  title: string;
  excerpt: string;
  body: string;
  json_ld: Record<string, unknown>;
  hero_image_url: string | null;
  status: "draft" | "published";
  updated_by: string;
  created_at: string;
  updated_at: string;
}
