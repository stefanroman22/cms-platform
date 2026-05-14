"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, CheckCircle, Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { login } from "@/lib/auth";
import { useLoading } from "@/context/loading";
import { useAuth } from "@/context/auth";

/**
 * Client island for the log-in page. Static card chrome (heading,
 * subtitle, labels, layout) is rendered by the Server Component
 * parent and shipped as HTML; only the interactive form + success
 * view live here.
 *
 * Entrance animation: pure CSS `.animate-fade-down` (defined in
 * globals.css). The form HTML paints immediately; the fade plays on
 * top, so perceived appearance is instant. Dropping framer-motion
 * from this island removes the form from the framer dependency graph;
 * the chunk itself is still pulled in on /log-in by HeaderRightCluster
 * (mobile drawer) until that island is rewritten too.
 */
const DASHBOARD_WINDOW_NAME = "cms-dashboard";

export function LoginForm() {
  const { show, hide } = useLoading();
  const { isLoggedIn, setLoggedIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const isFormValid = email.trim() !== "" && password.trim() !== "";

  // Warm the /dashboard chunk so the post-login window.open is instant.
  // `router` is a stable Next.js App Router object — this effect runs
  // once on mount in practice. Listed as a dep to satisfy
  // `react-hooks/exhaustive-deps` without disabling the rule.
  useEffect(() => {
    router.prefetch("/dashboard");
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid) return;

    show();
    setIsLoading(true);
    setError("");

    try {
      await login({ email, password, remember_me: rememberMe });
      setLoggedIn(true);
      window.name = "cms-login";
      window.open("/dashboard", DASHBOARD_WINDOW_NAME);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      hide();
      setIsLoading(false);
    }
  };

  if (isLoggedIn) {
    return (
      <div className="animate-fade-down w-full max-w-md space-y-8 rounded-2xl border border-white/[0.08] bg-zinc-950 p-8 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-950/60">
            <CheckCircle className="h-7 w-7 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-white">
            Successfully Logged In
          </h2>
          <p className="text-sm text-zinc-400">
            You&apos;re all set. Head over to your dashboard to manage your projects.
          </p>
        </div>

        <div>
          <Button
            type="button"
            variant="primary"
            size="lg"
            className="w-full text-base"
            onClick={() => window.open("/dashboard", DASHBOARD_WINDOW_NAME)}
          >
            Go to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-down w-full max-w-md space-y-8 rounded-2xl border border-white/[0.08] bg-zinc-950 p-8 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
      <form className="space-y-6" onSubmit={handleSubmit}>
        {error && (
          <div className="rounded-md bg-red-950/50 p-4 text-sm font-medium text-red-400">
            {error}
          </div>
        )}

        <div className="space-y-4 rounded-md shadow-sm">
          <div>
            <label htmlFor="email" className="block text-sm font-medium leading-6 text-zinc-300">
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
            <label htmlFor="password" className="block text-sm font-medium leading-6 text-zinc-300">
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

        <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <input
              id="remember-me"
              name="remember-me"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="sr-only"
            />
            <button
              type="button"
              role="checkbox"
              aria-checked={rememberMe}
              aria-labelledby="remember-me-label"
              onClick={() => setRememberMe((v) => !v)}
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors focus:outline-none focus:ring-1 focus:ring-white/30 ${
                rememberMe
                  ? "border-white bg-white"
                  : "border-white/30 bg-zinc-950 hover:border-white/50"
              }`}
            >
              {rememberMe && <Check className="h-3 w-3 text-black" strokeWidth={3} />}
            </button>
            <label
              id="remember-me-label"
              onClick={() => setRememberMe((v) => !v)}
              className="cursor-pointer text-sm text-zinc-400 select-none"
            >
              Remember me
            </label>
          </div>

          <div className="text-sm">
            <a href="#" className="font-medium text-white transition-colors hover:text-zinc-300">
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
    </div>
  );
}
