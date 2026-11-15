"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { translate } from "@/i18n";
import { api, type Account } from "@/lib/api";

type AccountsContext = {
  accounts: Account[];
  selected: Account | null;
  error: string | null;
  select: (account: Account | null) => void;
  refresh: () => Promise<void>;
  remove: (id: string) => Promise<void>;
};

const Context = createContext<AccountsContext | null>(null);

export function AccountsProvider({ children }: { children: React.ReactNode }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selected, setSelected] = useState<Account | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setAccounts(await api.accounts());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate("accounts.err.load"));
    }
  }, []);

  useEffect(() => {
    api
      .accounts()
      .then((list) => setAccounts(list))
      .catch((reason) => setError(reason instanceof Error ? reason.message : translate("accounts.err.load")));
  }, []);

  const remove = useCallback(async (id: string) => {
    try {
      await api.deleteAccount(id);
      setAccounts((list) => list.filter((a) => a.id !== id));
      setSelected((current) => (current?.id === id ? null : current));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate("accounts.err.remove"));
    }
  }, []);

  const value = useMemo<AccountsContext>(
    () => ({ accounts, selected, error, select: setSelected, refresh, remove }),
    [accounts, selected, error, refresh, remove]
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAccounts() {
  const value = useContext(Context);
  if (!value) throw new Error("useAccounts must be used inside AccountsProvider");
  return value;
}
