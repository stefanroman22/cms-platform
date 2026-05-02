"use client";

import { createContext, useContext, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@/hooks/useQuery";
import * as cache from "@/lib/cache";

export interface UserData {
  id: string;
  email: string;
  full_name: string | null;
  is_admin: boolean;
  created_at: string;
  projects_count: number;
}

interface UserContextValue {
  user: UserData | null;
  loading: boolean;
  updateFullName: (name: string) => void;
}

const UserContext = createContext<UserContextValue>({
  user: null,
  loading: true,
  updateFullName: () => {},
});

const ACCOUNT_TTL = 5 * 60 * 1000; // 5 minutes
const ACCOUNT_INTERVAL = 5 * 60 * 1000;

function fetchAccount(): Promise<UserData> {
  return fetch("/api/account", { credentials: "include", cache: "no-store" }).then((r) => {
    if (!r.ok) throw new Error("unauthorized");
    return r.json();
  });
}

export function UserProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: user, loading } = useQuery<UserData>("account", fetchAccount, {
    ttl: ACCOUNT_TTL,
    refetchInterval: ACCOUNT_INTERVAL,
  });

  // Redirect to login on 401
  useEffect(() => {
    if (!loading && user === null) {
      router.replace("/log-in");
    }
  }, [loading, user, router]);

  function updateFullName(name: string) {
    if (!user) return;
    const updated = { ...user, full_name: name };
    cache.set("account", updated); // keep cache in sync with optimistic update
  }

  return (
    <UserContext.Provider value={{ user, loading, updateFullName }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
