/**
 * Module-level SWR cache store.
 *
 * Lives outside React — survives re-renders and navigation within the same tab.
 * Call clearAll() on logout to ensure no data leaks to the next session.
 *
 * `PERSIST_KEYS` are mirrored to `sessionStorage` so that a hard reload
 * (or a navigation that drops the JS module instance) still serves the
 * dashboard skeleton instantly while the network revalidates. The
 * keys listed here MUST be safe to render briefly stale — anything
 * sensitive or fast-changing should stay in-memory only.
 */

interface CacheEntry<T = unknown> {
  data: T;
  fetchedAt: number; // Date.now() ms timestamp
  inflight: Promise<T> | null; // deduplicate concurrent fetches
}

const store = new Map<string, CacheEntry>();

// ── Pub/sub ─────────────────────────────────────────────────────────────────
//
// `useQuery` instances subscribe to their key so external mutations
// (e.g. `updateFullName` in `context/user.tsx` calling `cache.set`)
// propagate to React state without a refetch. Without this, the
// account-settings name change would update the sidebar's user
// context only on the next `useQuery` revalidation.
type Listener = () => void;
const listeners = new Map<string, Set<Listener>>();

export function subscribe(key: string, listener: Listener): () => void {
  let set = listeners.get(key);
  if (!set) {
    set = new Set();
    listeners.set(key, set);
  }
  set.add(listener);
  return () => {
    set!.delete(listener);
    if (set!.size === 0) listeners.delete(key);
  };
}

function notify(key: string) {
  const set = listeners.get(key);
  if (!set) return;
  for (const fn of set) fn();
}

const PERSIST_KEYS = new Set(["account", "projects"]);
const PERSIST_PREFIX = "cms-cache:";

function persistedRead<T>(key: string): { data: T; fetchedAt: number } | null {
  if (typeof window === "undefined") return null;
  if (!PERSIST_KEYS.has(key)) return null;
  try {
    const raw = window.sessionStorage.getItem(PERSIST_PREFIX + key);
    if (!raw) return null;
    return JSON.parse(raw) as { data: T; fetchedAt: number };
  } catch {
    return null;
  }
}

function persistedWrite(key: string, entry: { data: unknown; fetchedAt: number }) {
  if (typeof window === "undefined") return;
  if (!PERSIST_KEYS.has(key)) return;
  try {
    window.sessionStorage.setItem(PERSIST_PREFIX + key, JSON.stringify(entry));
  } catch {
    /* quota / disabled — fine, falls back to in-memory only */
  }
}

function persistedDelete(key: string) {
  if (typeof window === "undefined") return;
  if (!PERSIST_KEYS.has(key)) return;
  try {
    window.sessionStorage.removeItem(PERSIST_PREFIX + key);
  } catch {
    /* ignore */
  }
}

// ── Read ─────────────────────────────────────────────────────────────────────

export function get<T>(key: string): T | null {
  // In-memory only. sessionStorage promotion happens in `promotePersisted`
  // below, called from `useQuery`'s mount effect — never during render —
  // because returning persisted data here would diverge from the
  // server-rendered HTML and trigger a React 19 hydration mismatch.
  const entry = store.get(key);
  return entry ? (entry.data as T) : null;
}

export function isStale(key: string, ttlMs: number): boolean {
  const entry = store.get(key);
  if (!entry) return true;
  return Date.now() - entry.fetchedAt > ttlMs;
}

/**
 * Post-mount sessionStorage hydration.
 *
 * Promotes a persisted entry back into the in-memory cache so the
 * next `get()` call sees it. Safe to call from a `useEffect` —
 * NEVER from render, NEVER from a `useState` lazy initializer
 * (would cause hydration mismatch).
 *
 * Returns the promoted entry (or null) so callers can update local
 * state in the same effect without an extra `get()` round-trip.
 */
export function promotePersisted<T>(key: string): { data: T; fetchedAt: number } | null {
  if (!PERSIST_KEYS.has(key)) return null;
  if (store.has(key)) {
    const e = store.get(key)!;
    return { data: e.data as T, fetchedAt: e.fetchedAt };
  }
  const persisted = persistedRead<T>(key);
  if (!persisted) return null;
  store.set(key, { data: persisted.data, fetchedAt: persisted.fetchedAt, inflight: null });
  return persisted;
}

export function getInflight<T>(key: string): Promise<T> | null {
  const entry = store.get(key);
  return entry ? (entry.inflight as Promise<T> | null) : null;
}

// ── Write ────────────────────────────────────────────────────────────────────

export function set<T>(key: string, data: T): void {
  const fetchedAt = Date.now();
  store.set(key, {
    data,
    fetchedAt,
    inflight: null,
  });
  persistedWrite(key, { data, fetchedAt });
  notify(key);
}

export function setInflight<T>(key: string, promise: Promise<T>): void {
  const existing = store.get(key);
  store.set(key, {
    data: existing?.data ?? null,
    fetchedAt: existing?.fetchedAt ?? 0,
    inflight: promise as Promise<unknown>,
  });
  // When the promise resolves, cache the result and clear inflight
  promise
    .then((data) => set(key, data))
    .catch(() => {
      const e = store.get(key);
      if (e) store.set(key, { ...e, inflight: null });
    });
}

// ── Invalidate ───────────────────────────────────────────────────────────────

export function invalidate(key: string): void {
  store.delete(key);
  persistedDelete(key);
  notify(key);
}

/** Wipe everything — call on logout. */
export function clearAll(): void {
  store.clear();
  if (typeof window !== "undefined") {
    try {
      // Drop every persisted entry so the next sign-in doesn't show
      // the previous user's projects through the gap before
      // /api/account returns.
      for (const k of Array.from(PERSIST_KEYS)) {
        window.sessionStorage.removeItem(PERSIST_PREFIX + k);
      }
    } catch {
      /* ignore */
    }
  }
}

// ── Prefetch ─────────────────────────────────────────────────────────────────

/**
 * Fire a fetch and cache the result.
 * Safe to call multiple times — deduplicates via inflight promise.
 */
export function prefetch<T>(key: string, fetcher: () => Promise<T>): void {
  if (getInflight(key)) return; // already in-flight
  if (!isStale(key, 5 * 60 * 1000)) return; // fresh — no-op
  const promise = fetcher();
  setInflight(key, promise);
}

/**
 * Prefetch both account and projects data immediately after login.
 * By the time the dashboard window mounts, the cache will be warm.
 */
export function prefetchAll(): void {
  prefetch("account", () =>
    fetch("/api/account", { credentials: "include", cache: "no-store" }).then((r) => r.json())
  );
  prefetch("projects", () =>
    fetch("/api/projects", { credentials: "include", cache: "no-store" }).then((r) => r.json())
  );
}
