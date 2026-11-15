"use client";
import { Suspense } from "react";
import { AccountsProvider } from "@/features/accounts";
import { AnalysisProvider } from "@/features/analysis";
import { ChatProvider } from "@/features/chat";
import { DashboardShell } from "@/features/DashboardShell";
import { PersonaProvider } from "@/features/persona";

/** Shared state for every dashboard page. Each page reads only the pieces it needs. */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <PersonaProvider>
        <AccountsProvider>
          <ChatProvider>
            <AnalysisProvider>
              <DashboardShell>{children}</DashboardShell>
            </AnalysisProvider>
          </ChatProvider>
        </AccountsProvider>
      </PersonaProvider>
    </Suspense>
  );
}
