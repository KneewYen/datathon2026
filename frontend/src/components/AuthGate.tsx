"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import { authConfigured, beginLogin, getAccessToken } from "@/lib/auth";

export function AuthGate({ children }: { children: ReactNode }) {
  const authenticated = useSyncExternalStore(
    () => () => undefined,
    () => !authConfigured() || Boolean(getAccessToken()),
    () => !authConfigured(),
  );

  if (authenticated) return children;
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <section className="max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-brand-600">Protected AWS demo</p>
        <h1 className="mt-3 text-2xl font-semibold text-navy">Sign in to PortfolioGuard AI</h1>
        <p className="mt-3 text-sm leading-relaxed text-slate-600">
          The AWS workflow is available only to invited demo users. Authentication uses Cognito and PKCE; no client secret is stored in this application.
        </p>
        <button
          className="mt-6 rounded-md bg-brand-500 px-5 py-3 text-sm font-bold text-white hover:bg-brand-600"
          onClick={() => void beginLogin()}
        >
          Sign in securely
        </button>
      </section>
    </main>
  );
}
