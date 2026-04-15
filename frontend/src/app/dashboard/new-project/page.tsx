"use client";

import { useState } from "react";
import { Send, CheckCircle } from "lucide-react";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { FormFeedback } from "@/components/dashboard/FormFeedback";
import {
    dashboardPrimaryBtnCn,
    dashboardInputLgCn,
    dashboardFieldLabelCn,
} from "@/lib/styles";


const PROJECT_TYPES = [
    { value: "website", label: "Website" },
    { value: "web_app", label: "Web Application" },
    { value: "mobile_app", label: "Mobile App" },
    { value: "other", label: "Other" },
];

const BUDGET_OPTIONS = [
    { value: "", label: "Prefer not to say" },
    { value: "under_1k", label: "Under €1,000" },
    { value: "1k_5k", label: "€1,000 – €5,000" },
    { value: "5k_20k", label: "€5,000 – €20,000" },
    { value: "20k_plus", label: "€20,000+" },
];

const TIMELINE_OPTIONS = [
    { value: "", label: "No preference" },
    { value: "asap", label: "As soon as possible" },
    { value: "1_month", label: "Within 1 month" },
    { value: "3_months", label: "Within 3 months" },
    { value: "6_months", label: "Within 6 months" },
    { value: "flexible", label: "Flexible" },
];

export default function CreateNewProjectPage() {
    const [name, setName] = useState("");
    const [type, setType] = useState("website");
    const [description, setDescription] = useState("");
    const [budget, setBudget] = useState("");
    const [timeline, setTimeline] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [submitted, setSubmitted] = useState(false);

    const isValid = name.trim() !== "" && description.trim() !== "";

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!isValid) return;

        setLoading(true);
        setError("");

        try {
            const res = await fetch("/api/project-requests", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    name: name.trim(),
                    type,
                    description: description.trim(),
                    budget_range: budget || null,
                    timeline: timeline || null,
                }),
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                setError(data?.detail ?? "Failed to submit. Please try again.");
            } else {
                setSubmitted(true);
            }
        } catch {
            setError("An unexpected error occurred.");
        } finally {
            setLoading(false);
        }
    }

    if (submitted) {
        return (
            <div className="p-8">
              <div className="max-w-xl">
                <div className="flex flex-col items-center justify-center rounded-2xl border border-emerald-200 bg-emerald-50 py-16 text-center px-8 dark:border-emerald-900 dark:bg-emerald-950">
                    <CheckCircle className="h-10 w-10 text-emerald-500 dark:text-emerald-400 mb-4" />
                    <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Request submitted</h2>
                    <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
                        We've received your project idea. We'll review it and get back to you shortly.
                    </p>
                    <button
                        onClick={() => {
                            setSubmitted(false);
                            setName(""); setType("website"); setDescription("");
                            setBudget(""); setTimeline("");
                        }}
                        className="mt-6 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 cursor-pointer"
                    >
                        Submit another request
                    </button>
                </div>
              </div>
            </div>
        );
    }

    return (
        <div className="p-8">
          <div className="max-w-xl">
            <PageHeader
                title="Create New Project"
                description="Tell us about your idea and we'll get back to you with a proposal."
            />

            <form onSubmit={handleSubmit} className="space-y-5">
                <FormFeedback error={error || undefined} />

                <div>
                    <label className={dashboardFieldLabelCn}>
                        Project name <span className="text-red-400">*</span>
                    </label>
                    <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Company website redesign"
                        className={dashboardInputLgCn}
                    />
                </div>

                <div>
                    <label className={dashboardFieldLabelCn}>
                        Project type <span className="text-red-400">*</span>
                    </label>
                    <select
                        value={type}
                        onChange={(e) => setType(e.target.value)}
                        className={dashboardInputLgCn}
                    >
                        {PROJECT_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className={dashboardFieldLabelCn}>
                        Description <span className="text-red-400">*</span>
                    </label>
                    <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Describe what you'd like to build, its goals, and any specific requirements…"
                        rows={5}
                        className={`${dashboardInputLgCn} resize-none`}
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className={dashboardFieldLabelCn}>Budget range</label>
                        <select
                            value={budget}
                            onChange={(e) => setBudget(e.target.value)}
                            className={dashboardInputLgCn}
                        >
                            {BUDGET_OPTIONS.map((o) => (
                                <option key={o.value} value={o.value}>{o.label}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className={dashboardFieldLabelCn}>Timeline</label>
                        <select
                            value={timeline}
                            onChange={(e) => setTimeline(e.target.value)}
                            className={dashboardInputLgCn}
                        >
                            {TIMELINE_OPTIONS.map((o) => (
                                <option key={o.value} value={o.value}>{o.label}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="pt-2">
                    <button
                        type="submit"
                        disabled={!isValid || loading}
                        className={`${dashboardPrimaryBtnCn} px-5 py-2.5`}
                    >
                        <Send className="h-4 w-4" />
                        {loading ? "Submitting…" : "Submit request"}
                    </button>
                </div>
            </form>
          </div>
        </div>
    );
}
