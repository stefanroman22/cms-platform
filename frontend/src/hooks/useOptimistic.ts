import { useState, useCallback, useRef } from "react";

interface UseOptimisticResult<T> {
  /** The value to render — optimistically updated, rolled back on failure */
  value: T;
  /** Apply an optimistic update. Calls serverFn, rolls back on error. */
  update: (next: T, serverFn: () => Promise<void>) => Promise<void>;
  /** True while the server call is in-flight */
  isPending: boolean;
  /** Set if the last server call failed (cleared on next update attempt) */
  error: string | null;
}

/**
 * Optimistic update hook.
 *
 * Usage:
 *   const { value, update, isPending, error } = useOptimistic(user.full_name);
 *
 *   // On user action:
 *   await update(newName, () => patchName(newName));
 *   // → UI shows newName immediately; rolls back if patchName() throws.
 */
export function useOptimistic<T>(initial: T): UseOptimisticResult<T> {
  const [value, setValue] = useState<T>(initial);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Keep a ref to the committed (server-confirmed) value for rollbacks
  const committed = useRef<T>(initial);

  // Sync committed ref when initial prop changes (e.g. parent refetch)
  // We only update if not mid-flight to avoid overwriting an optimistic value
  if (!isPending && initial !== committed.current) {
    committed.current = initial;
    setValue(initial);
  }

  const update = useCallback(async (next: T, serverFn: () => Promise<void>) => {
    setError(null);
    setIsPending(true);
    setValue(next); // optimistic apply
    try {
      await serverFn();
      committed.current = next; // commit on success
    } catch (err) {
      setValue(committed.current); // rollback
      setError(err instanceof Error ? err.message : "Update failed.");
    } finally {
      setIsPending(false);
    }
  }, []);

  return { value, update, isPending, error };
}
