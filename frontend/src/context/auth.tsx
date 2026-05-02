"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getMe } from "@/lib/auth";
import { useLoading } from "@/context/loading";

/** Channel name shared between all tabs for auth-state sync */
const AUTH_CHANNEL = "cms-auth";

interface AuthContextValue {
  isLoggedIn: boolean;
  /** Call after a successful login to update all consumers instantly */
  setLoggedIn: (v: boolean) => void;
}

const AuthContext = createContext<AuthContextValue>({
  isLoggedIn: false,
  setLoggedIn: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const { show, hide } = useLoading();

  // Check auth state once on mount
  useEffect(() => {
    getMe().then((user) => setIsLoggedIn(!!user));
  }, []);

  // Listen for auth events broadcast from other tabs (e.g. dashboard sign-out)
  useEffect(() => {
    const channel = new BroadcastChannel(AUTH_CHANNEL);
    channel.onmessage = (event) => {
      if (event.data?.type === "logout") {
        // Show loading screen while the UI re-renders
        show();
        setIsLoggedIn(false);
        // Give React a tick to re-render, then hide loading
        setTimeout(() => hide(), 600);
      }
    };
    return () => channel.close();
  }, [show, hide]);

  const setLoggedIn = useCallback((v: boolean) => setIsLoggedIn(v), []);

  return (
    <AuthContext.Provider value={{ isLoggedIn, setLoggedIn }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Broadcast a logout event to all other tabs */
export function broadcastLogout() {
  const channel = new BroadcastChannel(AUTH_CHANNEL);
  channel.postMessage({ type: "logout" });
  channel.close();
}
