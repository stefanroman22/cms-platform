"use client";

import { useState } from "react";
import { AlertCircle } from "lucide-react";
import {
    dashboardInputCn,
    dashboardFieldLabelCn,
    dashboardSectionCardCn,
    dashboardErrorBannerCn,
} from "@/lib/styles";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";

type Priority = "High" | "Medium" | "Low";

interface IssueFormProps {
    projectSlug: string;
    onSubmitted: () => void;
}

const prioritySelectedCn: Record<Priority, string> = {
    High: "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-400",
    Medium: "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-400",
    Low: "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-400",
};

const priorityUnselectedCn =
    "bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800";

export function IssueForm({ projectSlug, onSubmitted }: IssueFormProps) {
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [priority, setPriority] = useState<Priority>("Medium");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault();
        setError(null);
        setSubmitting(true);

        try {
            const res = await fetch(`/api/projects/${projectSlug}/issues`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, description, priority }),
            });

            if (!res.ok) {
                let message = `Request failed with status ${res.status}`;
                try {
                    const data = await res.json();
                    if (typeof data?.detail === "string") message = data.detail;
                    else if (typeof data?.message === "string") message = data.message;
                } catch {
                    // ignore parse error, use default message
                }
                setError(message);
                return;
            }

            // Success — reset form and notify parent
            setTitle("");
            setDescription("");
            setPriority("Medium");
            onSubmitted();
        } catch (err) {
            setError(err instanceof Error ? err.message : "An unexpected error occurred.");
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="mt-8">
            <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-4 flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                Report an Issue
            </h2>
            <div className={`${dashboardSectionCardCn} p-6 max-w-2xl`}>
                <form onSubmit={handleSubmit} className="space-y-5">
                    {/* Error banner */}
                    {error && <p className={dashboardErrorBannerCn}>{error}</p>}

                    {/* Title field */}
                    <div>
                        <label htmlFor="issue-title" className={dashboardFieldLabelCn}>
                            Title <span className="text-red-500">*</span>
                        </label>
                        <input
                            id="issue-title"
                            type="text"
                            required
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="Brief summary of the issue"
                            className={dashboardInputCn}
                        />
                    </div>

                    {/* Description field with InfoTooltip */}
                    <div>
                        <label
                            htmlFor="issue-description"
                            className={`${dashboardFieldLabelCn} flex items-center gap-1.5`}
                        >
                            Description <span className="text-red-500">*</span>
                            <InfoTooltip
                                hint={`Be as specific as possible — mention the page name, section, exact text, and what it should be instead. Example: 'On the About page, the job title says "Software Developer" but it should be "Senior Software Engineer"'`}
                                direction="down"
                                wide
                            />
                        </label>
                        <textarea
                            id="issue-description"
                            required
                            rows={6}
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Describe what is wrong in detail. Include: which page, which section, what exactly is incorrect, and what it should say/look like instead."
                            className={`${dashboardInputCn} resize-none`}
                        />
                    </div>

                    {/* Priority segmented control */}
                    <div>
                        <span className={dashboardFieldLabelCn}>Priority</span>
                        <div className="flex gap-0 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
                            {(["High", "Medium", "Low"] as Priority[]).map((p) => (
                                <button
                                    key={p}
                                    type="button"
                                    onClick={() => setPriority(p)}
                                    className={`flex-1 py-1.5 text-sm font-medium transition-colors ${
                                        priority === p
                                            ? prioritySelectedCn[p]
                                            : priorityUnselectedCn
                                    }`}
                                >
                                    {p}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Submit button */}
                    <button
                        type="submit"
                        disabled={submitting}
                        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors dark:bg-zinc-700 dark:hover:bg-zinc-600"
                    >
                        {submitting ? "Submitting…" : "Submit Issue"}
                    </button>
                </form>
            </div>
        </div>
    );
}
