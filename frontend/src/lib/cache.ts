/**
 * Module-level SWR cache store.
 *
 * Lives outside React — survives re-renders and navigation within the same tab.
 * Call clearAll() on logout to ensure no data leaks to the next session.
 */

interface CacheEntry<T = unknown> {
    data: T;
    fetchedAt: number;          // Date.now() ms timestamp
    inflight: Promise<T> | null; // deduplicate concurrent fetches
}

const store = new Map<string, CacheEntry>();

// ── Read ─────────────────────────────────────────────────────────────────────

export function get<T>(key: string): T | null {
    const entry = store.get(key);
    return entry ? (entry.data as T) : null;
}

export function isStale(key: string, ttlMs: number): boolean {
    const entry = store.get(key);
    if (!entry) return true;
    return Date.now() - entry.fetchedAt > ttlMs;
}

export function getInflight<T>(key: string): Promise<T> | null {
    const entry = store.get(key);
    return entry ? (entry.inflight as Promise<T> | null) : null;
}

// ── Write ────────────────────────────────────────────────────────────────────

export function set<T>(key: string, data: T): void {
    store.set(key, {
        data,
        fetchedAt: Date.now(),
        inflight: null,
    });
}

export function setInflight<T>(key: string, promise: Promise<T>): void {
    const existing = store.get(key);
    store.set(key, {
        data: existing?.data ?? null,
        fetchedAt: existing?.fetchedAt ?? 0,
        inflight: promise as Promise<unknown>,
    });
    // When the promise resolves, cache the result and clear inflight
    promise.then((data) => set(key, data)).catch(() => {
        const e = store.get(key);
        if (e) store.set(key, { ...e, inflight: null });
    });
}

// ── Invalidate ───────────────────────────────────────────────────────────────

export function invalidate(key: string): void {
    store.delete(key);
}

/** Wipe everything — call on logout. */
export function clearAll(): void {
    store.clear();
}

// ── Prefetch ─────────────────────────────────────────────────────────────────

/**
 * Fire a fetch and cache the result.
 * Safe to call multiple times — deduplicates via inflight promise.
 */
export function prefetch<T>(key: string, fetcher: () => Promise<T>): void {
    if (getInflight(key)) return;             // already in-flight
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
