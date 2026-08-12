"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutGrid, ClipboardCheck, Activity, Users, LogOut } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { usePendingReviewCount } from "@/lib/pendingReviewCountContext";

// Next.js does NOT auto-prefix plain <img> src paths with basePath the way it does
// next/link hrefs — see next.config.ts's basePath comment and the vendored
// node_modules/next/dist/docs/.../basePath.md ("Images" section). Same
// NEXT_PUBLIC_BASE_PATH build arg next.config.ts reads, so this can't drift out of sync
// with the actual basePath in effect.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

function NavItem({
  icon: Icon,
  label,
  href,
  active,
  badge,
}: {
  icon: LucideIcon;
  label: string;
  href: string;
  active: boolean;
  badge?: number;
}) {
  return (
    <Link
      href={href}
      className={`nav-item flex w-full items-center gap-[10px] rounded-[9px] px-[10px] py-2 text-[13.5px] ${
        active ? "bg-accent-bg font-semibold text-accent-ink" : "font-normal text-ink-soft"
      }`}
    >
      <Icon size={17} />
      <span className="flex-1">{label}</span>
      {!!badge && (
        <span className="flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-warn-dot px-[5px] text-[10.5px] font-semibold text-white">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { count: pendingCount } = usePendingReviewCount();

  const onLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <aside className="flex w-[218px] shrink-0 flex-col border-r-[0.5px] border-line bg-surface px-3 pt-[28px] pb-[18px]">
      <Link href="/projects" className="flex flex-col items-center gap-[10px] px-2 pb-[18px]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`${BASE_PATH}/intel-logo.svg`} alt="Intel" className="h-[44px] w-auto" />
        <div className="text-center text-[15px] leading-[1.15] font-semibold">Tender Bid Evaluator</div>
      </Link>
      <div className="mt-[10px] flex flex-col gap-[2px]">
        <NavItem icon={LayoutGrid} label="Projects" href="/projects" active={pathname.startsWith("/projects")} />
        <NavItem
          icon={ClipboardCheck}
          label="Review queue"
          href="/review"
          active={pathname === "/review"}
          badge={pendingCount}
        />
        <NavItem icon={Activity} label="Operations" href="/ops" active={pathname === "/ops"} />
        {user?.role === "ADMIN" && (
          <NavItem icon={Users} label="Employees" href="/employees" active={pathname === "/employees"} />
        )}
      </div>
      <div className="mt-auto border-t-[0.5px] border-line px-2 pt-[10px]">
        {user && (
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-[12.5px] font-medium text-ink">{user.name}</div>
              <div className="text-[10.5px] text-ink-faint">{user.role === "ADMIN" ? "Admin" : "Reviewer"}</div>
            </div>
            <button
              onClick={onLogout}
              className="btn cursor-pointer rounded-md border-none bg-transparent p-1 text-ink-faint transition-colors hover:bg-bad-bg hover:text-bad-fg"
              title="Log out"
            >
              <LogOut size={15} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
