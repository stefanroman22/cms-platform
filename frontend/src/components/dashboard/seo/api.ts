// frontend/src/components/dashboard/seo/api.ts
import type { SeoArticle, SeoCompetitor, SeoHistory, SeoOverview, SeoPlanItem } from "./types";

async function throwOnError(r: Response): Promise<void> {
  if (!r.ok) {
    const body = (await r.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Request failed (${r.status})`);
  }
}

export async function getOverview(slug: string): Promise<SeoOverview> {
  const r = await fetch(`/api/projects/${slug}/seo/overview`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getPlan(slug: string): Promise<SeoPlanItem[]> {
  const r = await fetch(`/api/projects/${slug}/seo/plan`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getHistory(slug: string): Promise<SeoHistory> {
  const r = await fetch(`/api/projects/${slug}/seo/history`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getCompetitors(slug: string): Promise<SeoCompetitor[]> {
  const r = await fetch(`/api/projects/${slug}/seo/competitors`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getArticles(slug: string): Promise<SeoArticle[]> {
  const r = await fetch(`/api/projects/${slug}/seo/articles`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function deleteArticle(slug: string, id: string): Promise<void> {
  const r = await fetch(`/api/projects/${slug}/seo/articles/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  await throwOnError(r);
}

export async function enqueueRun(slug: string, kind = "run_full"): Promise<{ id: string }> {
  const r = await fetch(`/api/projects/${slug}/seo/jobs`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind }),
  });
  await throwOnError(r);
  return r.json();
}
