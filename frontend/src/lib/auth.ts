export interface LoginPayload {
  email: string;
  password: string;
  remember_me: boolean;
}

export interface UserOut {
  id: string;
  email: string;
  full_name?: string;
}

export async function login(payload: LoginPayload): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail ?? "Invalid email or password");
  }

  // Warm the cache immediately after login so the dashboard opens with 0ms wait.
  // Import is dynamic to avoid loading cache.ts on the public login page bundle
  // before the user has authenticated.
  const { prefetchAll } = await import("@/lib/cache");
  prefetchAll();
}

export async function logout(): Promise<void> {
  // Clear cache before the API call so data is gone even if the call fails
  const { clearAll } = await import("@/lib/cache");
  clearAll();

  await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include",
  });
}

export async function getMe(): Promise<UserOut | null> {
  const res = await fetch("/api/auth/me", {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export async function refreshToken(): Promise<boolean> {
  const res = await fetch("/api/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
  return res.ok;
}
