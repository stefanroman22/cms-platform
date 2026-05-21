"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface Ctx {
  editingId: string | null;
  /** Returns true if this section now holds the edit slot. */
  requestEdit: (id: string) => boolean;
  /** Releases the slot if this section currently holds it. */
  release: (id: string) => void;
}

const EditingSectionContext = createContext<Ctx | null>(null);

export function EditingSectionProvider({ children }: { children: ReactNode }) {
  const [editingId, setEditingId] = useState<string | null>(null);

  const requestEdit = useCallback((id: string) => {
    setEditingId(id);
    return true;
  }, []);

  const release = useCallback((id: string) => {
    setEditingId((curr) => (curr === id ? null : curr));
  }, []);

  return (
    <EditingSectionContext.Provider value={{ editingId, requestEdit, release }}>
      {children}
    </EditingSectionContext.Provider>
  );
}

export function useEditingSection(id: string) {
  const ctx = useContext(EditingSectionContext);
  if (!ctx) throw new Error("useEditingSection must be used inside EditingSectionProvider");
  return {
    isEditing: ctx.editingId === id,
    isAnyEditing: ctx.editingId !== null,
    requestEdit: () => ctx.requestEdit(id),
    release: () => ctx.release(id),
  };
}
