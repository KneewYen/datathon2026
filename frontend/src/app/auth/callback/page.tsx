"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { completeLogin } from "@/lib/auth";

function AuthCallbackContent() {
  const router = useRouter();
  const search = useSearchParams();
  const code = search.get("code");
  const state = search.get("state");
  const [error, setError] = useState<string | null>(
    !code || !state ? "The authentication response is incomplete." : null,
  );

  useEffect(() => {
    if (!code || !state) return;
    completeLogin(code, state)
      .then((returnTo) => router.replace(returnTo))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Authentication failed"));
  }, [code, router, state]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm" role="status">
        {error ? <p className="text-sm text-red-700">{error}</p> : <p className="text-sm text-slate-600">Completing secure sign-in…</p>}
      </div>
    </main>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<main className="flex min-h-screen items-center justify-center">Completing secure sign-in…</main>}>
      <AuthCallbackContent />
    </Suspense>
  );
}
