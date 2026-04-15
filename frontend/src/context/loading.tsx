"use client";

import { createContext, useContext, useState, useCallback } from "react";
import { LoadingScreen } from "@/components/ui/LoadingScreen";

interface LoadingContextValue {
  show: () => void;
  hide: () => void;
}

const LoadingContext = createContext<LoadingContextValue>({
  show: () => {},
  hide: () => {},
});

export function LoadingProvider({ children }: { children: React.ReactNode }) {
  const [isVisible, setIsVisible] = useState(false);

  const show = useCallback(() => setIsVisible(true), []);
  const hide = useCallback(() => setIsVisible(false), []);

  return (
    <LoadingContext.Provider value={{ show, hide }}>
      <LoadingScreen isVisible={isVisible} />
      {children}
    </LoadingContext.Provider>
  );
}

export function useLoading() {
  return useContext(LoadingContext);
}
