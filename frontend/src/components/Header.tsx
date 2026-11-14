import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-[1760px] items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-brand-500 font-bold text-white">P</div>
          <div>
            <div className="font-semibold leading-tight">PortfolioGuard AI</div>
            <div className="text-xs text-slate-500">Team 62 · Datathon 2026</div>
          </div>
        </Link>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-300 sm:inline">
            Simulation
          </span>
          <Link
            href="/profile"
            aria-label="Profile"
            title="Profile"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white font-semibold text-slate-700 ring-1 ring-slate-700 transition hover:bg-slate-50"
          >
            D
          </Link>
        </div>
      </div>
    </header>
  );
}
