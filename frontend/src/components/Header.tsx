import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-sky-100 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500 font-bold text-white">P</div>
          <div>
            <div className="font-semibold leading-tight">PortfolioGuard AI</div>
            <div className="text-xs text-slate-500">Team 62 · Datathon 2026</div>
          </div>
        </Link>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100 sm:inline">
            Simulation
          </span>
          <Link
            href="/profile"
            aria-label="Profile"
            title="Profile"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-100 font-semibold text-sky-700 ring-2 ring-white transition hover:ring-sky-300"
          >
            D
          </Link>
        </div>
      </div>
    </header>
  );
}
