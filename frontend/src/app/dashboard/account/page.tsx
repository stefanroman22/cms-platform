"use client";

import { useState } from "react";
import {
  User,
  Calendar,
  FolderOpen,
  Lock,
  CheckCircle,
  Pencil,
  X,
  Mail,
  Sun,
  Moon,
  Palette,
} from "lucide-react";
import { useUser } from "@/context/user";
import { useOptimistic } from "@/hooks/useOptimistic";
import { useTheme } from "@/context/theme";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { FormField } from "@/components/dashboard/FormField";
import { FormFeedback } from "@/components/dashboard/FormFeedback";
import { dashboardPrimaryBtnCn, dashboardInputCn, dashboardSectionCardCn } from "@/lib/styles";

export default function AccountSettingsPage() {
  const { user, loading, updateFullName } = useUser();
  const { theme, toggleTheme } = useTheme();

  // ── Full name edit (optimistic) ─────────────────────────────────────────
  const {
    value: displayName,
    update: optimisticUpdateName,
    isPending: nameLoading,
    error: nameOptimisticError,
  } = useOptimistic<string | null>(user?.full_name ?? null);

  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [nameError, setNameError] = useState("");
  const [nameSuccess, setNameSuccess] = useState(false);

  function openNameEdit() {
    setNameValue(user?.full_name ?? "");
    setNameError("");
    setNameSuccess(false);
    setEditingName(true);
  }

  function cancelNameEdit() {
    setEditingName(false);
    setNameError("");
    setNameSuccess(false);
  }

  const trimmedName = nameValue.trim();
  const nameUnchanged = trimmedName === (user?.full_name ?? "").trim();
  const nameSaveDisabled = nameLoading || !trimmedName || nameUnchanged;

  async function handleSaveName() {
    if (nameSaveDisabled) return;
    setNameError("");

    await optimisticUpdateName(trimmedName, async () => {
      const res = await fetch("/api/auth/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ full_name: trimmedName }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? "Failed to update name.");
      }
      updateFullName(trimmedName); // sync context (sidebar etc.)
    });

    // If no error after optimistic update, close the form
    if (!nameOptimisticError) {
      setNameSuccess(true);
      setEditingName(false);
    }
  }

  // ── Password change ─────────────────────────────────────────────────────
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwLoading, setPwLoading] = useState(false);
  const [pwError, setPwError] = useState("");
  const [pwSuccess, setPwSuccess] = useState(false);

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError("");
    setPwSuccess(false);

    if (newPw.length < 8) {
      setPwError("New password must be at least 8 characters.");
      return;
    }
    if (newPw !== confirmPw) {
      setPwError("Passwords do not match.");
      return;
    }

    setPwLoading(true);
    try {
      const res = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setPwError(data?.detail ?? "Failed to change password.");
      } else {
        setPwSuccess(true);
        setCurrentPw("");
        setNewPw("");
        setConfirmPw("");
      }
    } catch {
      setPwError("An unexpected error occurred.");
    } finally {
      setPwLoading(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="p-4 md:p-8">
        <div className="h-6 w-40 rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse mb-2" />
        <div className="h-4 w-64 rounded bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8">
      <div className="max-w-2xl">
        <PageHeader
          title="Account Settings"
          description="Manage your profile and security settings."
        />

        {/* Profile info */}
        <section className={`mb-8 ${dashboardSectionCardCn}`}>
          <div className="px-4 py-4 border-b border-zinc-100 dark:border-zinc-800 sm:px-6">
            <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Profile</h2>
          </div>
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
            <Row icon={<Mail className="h-4 w-4" />} label="Email" value={user?.email ?? "—"} />

            {/* Full name — editable row */}
            <div className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-start sm:gap-4 sm:px-6">
              <div className="flex items-center gap-3 sm:items-start sm:gap-4 sm:w-44 sm:shrink-0">
                <span className="text-zinc-400 dark:text-zinc-500 shrink-0 sm:mt-0.5">
                  <User className="h-4 w-4" />
                </span>
                <span className="text-sm text-zinc-500 dark:text-zinc-400 sm:mt-0.5">
                  Full name
                </span>
              </div>
              <div className="flex-1 min-w-0">
                {editingName ? (
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={nameValue}
                      onChange={(e) => {
                        setNameValue(e.target.value);
                        setNameError("");
                      }}
                      maxLength={100}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSaveName();
                        if (e.key === "Escape") cancelNameEdit();
                      }}
                      className={dashboardInputCn}
                      placeholder="Your full name"
                    />
                    {nameError && (
                      <p className="text-xs text-red-600 dark:text-red-400">{nameError}</p>
                    )}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleSaveName}
                        disabled={nameSaveDisabled}
                        className={dashboardPrimaryBtnCn}
                      >
                        <CheckCircle className="h-4 w-4" />
                        {nameLoading ? "Saving…" : "Save name"}
                      </button>
                      <button
                        onClick={cancelNameEdit}
                        disabled={nameLoading}
                        className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 dark:hover:text-zinc-300 transition-colors disabled:opacity-40 cursor-pointer"
                      >
                        <X className="h-4 w-4" />
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm ${displayName ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-400 dark:text-zinc-500 italic"}`}
                    >
                      {displayName ?? "Not set"}
                    </span>
                    {nameSuccess && (
                      <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                        <CheckCircle className="h-3 w-3" /> Saved
                      </span>
                    )}
                    <button
                      onClick={openNameEdit}
                      className="ml-1 flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:text-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-300 transition-colors cursor-pointer"
                      aria-label="Edit full name"
                    >
                      <Pencil className="h-3 w-3" />
                      Edit
                    </button>
                  </div>
                )}
              </div>
            </div>

            <Row
              icon={<Calendar className="h-4 w-4" />}
              label="Member since"
              value={
                user?.created_at
                  ? new Date(user.created_at).toLocaleDateString("en-GB", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })
                  : "—"
              }
            />
            <Row
              icon={<FolderOpen className="h-4 w-4" />}
              label="Active projects"
              value={String(user?.projects_count ?? 0)}
            />
          </div>
        </section>

        {/* Appearance */}
        <section className={`mb-8 ${dashboardSectionCardCn}`}>
          <div className="px-4 py-4 border-b border-zinc-100 dark:border-zinc-800 sm:px-6">
            <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Appearance</h2>
          </div>
          <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
            <div className="flex items-center gap-3 sm:gap-4 sm:w-44 sm:shrink-0">
              <span className="text-zinc-400 dark:text-zinc-500 shrink-0">
                <Palette className="h-4 w-4" />
              </span>
              <span className="text-sm text-zinc-500 dark:text-zinc-400">Theme</span>
            </div>
            <button
              role="switch"
              aria-checked={theme === "dark"}
              onClick={toggleTheme}
              className="self-start flex items-center gap-0.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 p-1 transition-colors cursor-pointer"
              aria-label="Toggle theme"
            >
              <span
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${theme === "light" ? "bg-white shadow-sm text-zinc-900" : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"}`}
              >
                <Sun className="h-3.5 w-3.5" />
                Light
              </span>
              <span
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${theme === "dark" ? "bg-zinc-700 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-700"}`}
              >
                <Moon className="h-3.5 w-3.5" />
                Dark
              </span>
            </button>
          </div>
        </section>

        {/* Change password */}
        <section className={dashboardSectionCardCn}>
          <div className="px-4 py-4 border-b border-zinc-100 dark:border-zinc-800 sm:px-6">
            <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Change Password
            </h2>
          </div>
          <form onSubmit={handleChangePassword} className="p-6 space-y-4">
            <FormFeedback
              success={pwSuccess ? "Password updated successfully." : undefined}
              error={pwError || undefined}
            />
            <FormField
              label="Current password"
              type="password"
              value={currentPw}
              onChange={setCurrentPw}
              placeholder="••••••••"
            />
            <FormField
              label="New password"
              type="password"
              value={newPw}
              onChange={setNewPw}
              placeholder="Min. 8 characters"
            />
            <FormField
              label="Confirm new password"
              type="password"
              value={confirmPw}
              onChange={setConfirmPw}
              placeholder="••••••••"
            />
            <div className="pt-1">
              <button
                type="submit"
                disabled={pwLoading || !currentPw || !newPw || !confirmPw}
                className={dashboardPrimaryBtnCn}
              >
                <Lock className="h-4 w-4" />
                {pwLoading ? "Updating…" : "Update password"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

function Row({
  icon,
  label,
  value,
  muted = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  muted?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 px-4 py-4 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
      <div className="flex items-center gap-3 sm:gap-4 sm:w-44 sm:shrink-0">
        <span className="text-zinc-400 dark:text-zinc-500 shrink-0">{icon}</span>
        <span className="text-sm text-zinc-500 dark:text-zinc-400">{label}</span>
      </div>
      <span
        className={`pl-7 text-sm break-all sm:pl-0 sm:min-w-0 sm:flex-1 ${
          muted ? "text-zinc-400 dark:text-zinc-500 italic" : "text-zinc-900 dark:text-zinc-100"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
