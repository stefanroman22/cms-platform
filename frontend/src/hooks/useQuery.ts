import { useState, useEffect, useCallback, useRef } from "react";
import * as cache from "@/lib/cache";

interface UseQueryOptions {
    /** How long cached data is considered fresh, in ms. Default: 2 minutes. */
    ttl?: number;
    /** If set, silently refetch on this interval (ms) while the component is mounted. */
    refetchInterval?: number;
    /** Set to false to skip fetching (e.g. while waiting for a dependency). Default: true. */
    enabled?: boolean;
}

interface UseQueryResult<T> {
    data: T | null;
    /** True only on the very first load when there is nothing in cache yet. */
    loading: boolean;
    error: string | null;
    /** Force an immediate refetch regardless of staleness. */
    refresh: () => void;
}

export function useQuery<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: UseQueryOptions = {}
): UseQueryResult<T> {
    const { ttl = 2 * 60 * 1000, refetchInterval, enabled = true } = options;

    const [data, setData] = useState<T | null>(() => cache.get<T>(key));
    const [loading, setLoading] = useState<boolean>(() => cache.get(key) === null);
    const [error, setError] = useState<string | null>(null);
    const isMounted = useRef(true);

    useEffect(() => {
        isMounted.current = true;
        return () => { isMounted.current = false; };
    }, []);

    const doFetch = useCallback(
        async (background: boolean) => {
            if (!background) setLoading(true);
            setError(null);
            try {
                // Deduplicate: reuse an in-flight promise if one exists
                let promise = cache.getInflight<T>(key);
                if (!promise) {
                    promise = fetcher();
                    cache.setInflight(key, promise);
                }
                const result = await promise;
                if (isMounted.current) {
                    setData(result);
                    setLoading(false);
                }
            } catch (err) {
                if (isMounted.current) {
                    setError(err instanceof Error ? err.message : "Failed to load.");
                    setLoading(false);
                }
            }
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [key]
    );

    // Mount effect: serve cache or fetch
    useEffect(() => {
        if (!enabled) return;

        const cached = cache.get<T>(key);

        if (cached !== null) {
            // Serve immediately from cache
            setData(cached);
            setLoading(false);
            // If stale, revalidate silently in the background
            if (cache.isStale(key, ttl)) {
                doFetch(true);
            }
        } else {
            // Nothing cached — must fetch (shows loading)
            doFetch(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key, enabled]);

    // Periodic background refetch
    useEffect(() => {
        if (!enabled || !refetchInterval) return;
        const id = setInterval(() => {
            if (cache.isStale(key, ttl)) {
                doFetch(true); // silent — no loading spinner
            }
        }, refetchInterval);
        return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key, enabled, refetchInterval, ttl]);

    const refresh = useCallback(() => {
        cache.invalidate(key);
        doFetch(false);
    }, [key, doFetch]);

    return { data, loading, error, refresh };
}
