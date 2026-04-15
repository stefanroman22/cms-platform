"use client";

import { useState } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { Mail } from "lucide-react";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";

export function EmailConfigEditor({ initialContent, onChange }: EditorProps) {
    const [email, setEmail] = useState(String(initialContent.destination_email ?? ""));
    const [touched, setTouched] = useState(false);

    const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    const showError = touched && email.length > 0 && !isValid;

    function handleChange(value: string) {
        setEmail(value);
        onChange({ destination_email: value });
    }

    return (
        <div className={dashboardSectionCardCn}>
            <div className="p-5">
                <span className="flex items-center gap-1.5 mb-1.5">
                    <label className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>Destination email address</label>
                    <InfoTooltip hint="All contact form submissions from the website will be sent to this address. It is never publicly visible." />
                </span>
                <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-3">
                    Form submissions from the website will be sent to this address.
                </p>
                <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400 dark:text-zinc-500 pointer-events-none" />
                    <input
                        type="email"
                        value={email}
                        onChange={(e) => handleChange(e.target.value)}
                        onBlur={() => setTouched(true)}
                        placeholder="contact@example.com"
                        className={`${dashboardInputCn} pl-9 ${showError ? "border-red-400 focus:border-red-400 dark:border-red-600" : ""}`}
                    />
                </div>
                {showError && (
                    <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">
                        Enter a valid email address.
                    </p>
                )}
            </div>
        </div>
    );
}
