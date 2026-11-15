"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AssistantDrawer } from "@/components/dashboard/AssistantDrawer";
import { Header } from "@/components/dashboard/Header";
import { useLanguage } from "@/i18n";
import { PERSONAS } from "@/lib/personas";
import { useFeatureFlags } from "./flags";
import { usePersona } from "./persona";
import { PAGES, featureForPath } from "./registry";

function PersonaSwitcher() {
  const { personaId, setPersonaId } = usePersona();
  const { t } = useLanguage();
  return (
    <div className="flex items-center gap-2" role="group" aria-label={t("shell.investorGroup")}>
      <span className="hidden text-xs uppercase tracking-wide text-slate-500 sm:inline">{t("shell.investor")}</span>
      {PERSONAS.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => setPersonaId(p.id)}
          aria-pressed={personaId === p.id}
          className={`rounded-full px-3.5 py-1.5 text-sm font-medium ring-1 transition ${
            personaId === p.id
              ? "bg-brand-500 text-white ring-brand-500"
              : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"
          }`}
        >
          {p.name}
        </button>
      ))}
    </div>
  );
}

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-white p-8 text-center ring-1 ring-slate-200">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mt-2 text-sm text-slate-600">{children}</p>
    </div>
  );
}

/** Header, tab bar and investor switcher around every dashboard page. */
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { t } = useLanguage();
  const { loaded, isEnabled } = useFeatureFlags();
  const tabs = PAGES.filter((f) => isEnabled(f.id));
  const current = featureForPath(pathname);
  const label = (id: string) => t(`feature.${id}.label` as Parameters<typeof t>[0]);

  let content = children;
  if (!loaded) {
    content = <p className="py-16 text-center text-sm text-slate-500">{t("shell.loading")}</p>;
  } else if (current && !isEnabled(current.id)) {
    content = (
      <Notice title={t("shell.off.title", { label: label(current.id) })}>
        {t("shell.off.body")}{" "}
        {tabs[0] ? (
          <Link href={tabs[0].path} className="font-medium text-link hover:underline">
            {t("shell.off.goto", { label: label(tabs[0].id) })}
          </Link>
        ) : (
          <Link href="/admin" className="font-medium text-link hover:underline">
            {t("shell.off.openAdmin")}
          </Link>
        )}
      </Notice>
    );
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2">
          <nav aria-label={t("shell.pages")} className="-mb-2 flex gap-1 overflow-x-auto">
            {tabs.map((f) => {
              const active = current?.id === f.id;
              return (
                <Link
                  key={f.id}
                  href={f.path}
                  aria-current={active ? "page" : undefined}
                  className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition ${
                    active
                      ? "border-brand-500 text-navy"
                      : "border-transparent text-slate-500 hover:text-slate-800"
                  }`}
                >
                  {label(f.id)}
                </Link>
              );
            })}
          </nav>
          <PersonaSwitcher />
        </div>
      </div>
      <main className="mx-auto max-w-6xl px-4 py-6">{content}</main>
      <p className="pb-8 text-center text-xs text-slate-400">{t("app.footer")}</p>
      {loaded && isEnabled("assistant") && <AssistantDrawer />}
    </div>
  );
}
