import { LoginForm } from "./LoginForm";

/**
 * Server Component. Static card heading/subtitle ship as HTML before
 * any JS arrives. Interactive form is the <LoginForm /> client island.
 */
export default function LogInPage() {
  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-black px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md">
        <div className="mb-8">
          <h2 className="mt-2 text-center text-3xl font-semibold tracking-tight text-white">
            Access CMS
          </h2>
          <p className="mt-2 text-center text-sm text-zinc-400">
            Please sign in to your administrative account.
          </p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
