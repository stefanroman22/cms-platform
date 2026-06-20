import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Locale } from "@/lib/locale";
import { LoginForm } from "./LoginForm";

/**
 * Server Component. Static card heading/subtitle ship as HTML before
 * any JS arrives. Interactive form is the <LoginForm /> client island.
 */
export default async function LogInPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("login");
  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-black px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md">
        <div className="mb-8">
          <h2 className="mt-2 text-center text-3xl font-semibold tracking-tight text-white">
            {t("heading")}
          </h2>
          <p className="mt-2 text-center text-sm text-zinc-400">{t("subheading")}</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
