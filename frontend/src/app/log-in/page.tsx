"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { createSlideIn } from "@/lib/animations";
import { login } from "@/lib/auth";
import { useLoading } from "@/context/loading";
import { useAuth } from "@/context/auth";

const cardVariants = createSlideIn({ direction: "top", delay: 0.5 });

/** Named window target — reuses the same tab if already open */
const DASHBOARD_WINDOW_NAME = "cms-dashboard";

export default function LogInPage() {
    const { show, hide } = useLoading();
    const { isLoggedIn, setLoggedIn } = useAuth();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [rememberMe, setRememberMe] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    // Hide any loading screen lingering from a sign-out transition
    useEffect(() => {
        hide();
    }, [hide]);

    const isFormValid = email.trim() !== "" && password.trim() !== "";

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!isFormValid) return;

        show();
        setIsLoading(true);
        setError("");

        try {
            await login({ email, password, remember_me: rememberMe });
            // Update shared auth state — Header will react instantly
            setLoggedIn(true);
            // Name the current window so `window.open` never replaces it
            window.name = "cms-login";
            // Open dashboard in a named window (reuses the tab if already open)
            window.open("/dashboard", DASHBOARD_WINDOW_NAME);
        } catch (err) {
            setError(err instanceof Error ? err.message : "An unexpected error occurred.");
        } finally {
            hide();
            setIsLoading(false);
        }
    };

    const handleGoToDashboard = () => {
        window.open("/dashboard", DASHBOARD_WINDOW_NAME);
    };

    /* ── Success view ──────────────────────────────────────────────────────── */
    if (isLoggedIn) {
        return (
            <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-black px-4 py-12 sm:px-6 lg:px-8">
                <motion.div
                    variants={cardVariants}
                    initial="hidden"
                    animate="visible"
                    className="w-full max-w-md space-y-8 rounded-2xl border border-white/[0.08] bg-zinc-950 p-8 shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
                >
                    <div className="flex flex-col items-center text-center space-y-3">
                        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-950/60">
                            <CheckCircle className="h-7 w-7 text-emerald-400" />
                        </div>
                        <h2 className="text-2xl font-semibold tracking-tight text-white">
                            Successfully Logged In
                        </h2>
                        <p className="text-sm text-zinc-400">
                            You&apos;re all set. Head over to your dashboard to manage
                            your projects.
                        </p>
                    </div>

                    <div>
                        <Button
                            type="button"
                            variant="primary"
                            size="lg"
                            className="w-full text-base"
                            onClick={handleGoToDashboard}
                        >
                            Go to Dashboard
                        </Button>
                    </div>
                </motion.div>
            </div>
        );
    }

    /* ── Login form ────────────────────────────────────────────────────────── */
    return (
        <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-black px-4 py-12 sm:px-6 lg:px-8">
            <motion.div
                variants={cardVariants}
                initial="hidden"
                animate="visible"
                className="w-full max-w-md space-y-8 rounded-2xl border border-white/[0.08] bg-zinc-950 p-8 shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
            >
                <div>
                    <h2 className="mt-2 text-center text-3xl font-semibold tracking-tight text-white">
                        Access CMS
                    </h2>
                    <p className="mt-2 text-center text-sm text-zinc-400">
                        Please sign in to your administrative account.
                    </p>
                </div>

                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    {error && (
                        <div className="rounded-md bg-red-950/50 p-4 text-sm font-medium text-red-400">
                            {error}
                        </div>
                    )}

                    <div className="space-y-4 rounded-md shadow-sm">
                        <div>
                            <label
                                htmlFor="email"
                                className="block text-sm font-medium leading-6 text-zinc-300"
                            >
                                Email address or Username
                            </label>
                            <div className="mt-2 text-white">
                                <input
                                    id="email"
                                    name="email"
                                    type="text"
                                    autoComplete="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="block w-full rounded-md border-0 bg-transparent py-2.5 px-3 text-white shadow-sm ring-1 ring-inset ring-white/[0.12] placeholder:text-zinc-500 focus:ring-1 focus:ring-inset focus:ring-white/30 sm:text-sm sm:leading-6 transition-colors"
                                    placeholder="admin@example.com"
                                />
                            </div>
                        </div>

                        <div>
                            <label
                                htmlFor="password"
                                className="block text-sm font-medium leading-6 text-zinc-300"
                            >
                                Password
                            </label>
                            <div className="relative mt-2 text-white">
                                <input
                                    id="password"
                                    name="password"
                                    type={showPassword ? "text" : "password"}
                                    autoComplete="current-password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="block w-full rounded-md border-0 bg-transparent py-2.5 pl-3 pr-10 text-white shadow-sm ring-1 ring-inset ring-white/[0.12] placeholder:text-zinc-500 focus:ring-1 focus:ring-inset focus:ring-white/30 sm:text-sm sm:leading-6 transition-colors"
                                    placeholder="••••••••"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-zinc-400 hover:text-zinc-300 transition-colors"
                                    aria-label={showPassword ? "Hide password" : "Show password"}
                                >
                                    {showPassword ? (
                                        <EyeOff className="h-5 w-5" aria-hidden="true" />
                                    ) : (
                                        <Eye className="h-5 w-5" aria-hidden="true" />
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="flex w-full flex-row items-center justify-between gap-4">
                        <div className="flex shrink-0 items-center">
                            <input
                                id="remember-me"
                                name="remember-me"
                                type="checkbox"
                                checked={rememberMe}
                                onChange={(e) => setRememberMe(e.target.checked)}
                                className="h-4 w-4 shrink-0 cursor-pointer rounded border-white/[0.12] bg-zinc-950 accent-white focus:ring-1 focus:ring-white/30 focus:ring-offset-0 checked:border-white checked:bg-white transition-colors"
                            />
                            <label
                                htmlFor="remember-me"
                                className="ml-2 block cursor-pointer text-sm text-zinc-400"
                            >
                                Remember me
                            </label>
                        </div>

                        <div className="shrink-0 text-right text-sm">
                            <a
                                href="#"
                                className="font-medium text-white transition-colors hover:text-zinc-300"
                            >
                                Forgot your password?
                            </a>
                        </div>
                    </div>

                    <div>
                        <Button
                            type="submit"
                            variant="primary"
                            size="lg"
                            className="w-full text-base"
                            disabled={!isFormValid || isLoading}
                            isLoading={isLoading}
                        >
                            Sign in to dashboard
                        </Button>
                    </div>
                </form>
            </motion.div>
        </div>
    );
}
