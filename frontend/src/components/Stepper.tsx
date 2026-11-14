const STEPS = ["Choose investor", "Ask a question", "Review analysis"];

export function Stepper({ current }: { current: number }) {
  return (
    <ol className="flex gap-2 text-sm">
      {STEPS.map((label, i) => (
        <li
          key={label}
          className={`flex items-center gap-2 rounded-full px-3 py-1 ${
            i === current
              ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
              : i < current
              ? "bg-neutral-200 dark:bg-neutral-800"
              : "text-neutral-400"
          }`}
        >
          <span className="font-mono">{i + 1}</span>
          <span className="hidden sm:inline">{label}</span>
        </li>
      ))}
    </ol>
  );
}
