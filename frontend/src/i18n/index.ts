import { useCallback, useEffect, useSyncExternalStore } from "react";
import { en, type MessageKey } from "./en";
import { fr } from "./fr";

export type Lang = "en" | "fr";
export type { MessageKey };

type Params = Record<string, string | number>;

const MESSAGES: Record<Lang, Record<string, string>> = { en, fr };
const STORAGE_KEY = "portfolioguard.lang";

/**
 * The current language lives in this module so plain helpers (number formatting, API errors) and
 * React components agree on it. Components subscribe through `useLanguage()` and re-render on change.
 */
let current: Lang = "en";
let initialised = false;
const listeners = new Set<() => void>();

function detect(): Lang {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "fr") return saved;
  } catch {
    /* storage can be blocked; fall through to the browser language */
  }
  return window.navigator.language?.toLowerCase().startsWith("fr") ? "fr" : "en";
}

function ensureInitialised() {
  if (initialised || typeof window === "undefined") return;
  initialised = true;
  current = detect();
}

export function getLang(): Lang {
  ensureInitialised();
  return current;
}

export function setLang(lang: Lang) {
  ensureInitialised();
  if (lang === current) return;
  current = lang;
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* the choice just won't survive a reload */
  }
  document.documentElement.lang = lang;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function format(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in params ? String(params[name]) : match));
}

/** Translate a key in the current language. Use this outside components. */
export function translate(key: MessageKey, params?: Params): string {
  return format(MESSAGES[getLang()][key] ?? en[key], params);
}

/** Look up a key built at run time (for example from a backend id). Returns the fallback if absent. */
export function translateOr(key: string, fallback: string, params?: Params): string {
  const message = MESSAGES[getLang()][key];
  return message === undefined ? fallback : format(message, params);
}

/** Subscribe a component to the language and get `t` for it. */
export function useLanguage() {
  const lang = useSyncExternalStore(subscribe, getLang, () => "en" as Lang);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const t = useCallback(
    (key: MessageKey, params?: Params) => format(MESSAGES[lang][key] ?? en[key], params),
    [lang]
  );
  const tOr = useCallback(
    (key: string, fallback: string, params?: Params) => {
      const message = MESSAGES[lang][key];
      return message === undefined ? fallback : format(message, params);
    },
    [lang]
  );
  return { lang, setLang, t, tOr };
}
