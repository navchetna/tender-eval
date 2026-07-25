"use client";

import { Search } from "lucide-react";

export function Header() {
  return (
    <header className="flex h-[49px] shrink-0 items-center justify-between border-b-[0.5px] border-line bg-surface px-5">
      <div className="flex items-center gap-[6px] text-[12.5px] text-ink-faint">
        <span>Reconcile</span>
      </div>
      <div className="flex items-center gap-2 rounded-lg border-[0.5px] border-line bg-surface2 px-[10px] py-[5px] text-[12.5px] text-ink-faint">
        <Search size={14} />
        <span>Search clauses, bidders…</span>
      </div>
    </header>
  );
}
