"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutGrid, ClipboardCheck, Activity, GitBranch, Users, LogOut } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";

function NavItem({
  icon: Icon,
  label,
  href,
  active,
}: {
  icon: LucideIcon;
  label: string;
  href: string;
  active: boolean;
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
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const onLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <aside className="flex w-[218px] shrink-0 flex-col border-r-[0.5px] border-line bg-surface px-3 py-[18px]">
      <div className="flex items-center gap-[9px] px-2 pb-[18px]">
        <div className="flex h-[27px] w-[27px] items-center justify-center rounded-lg bg-accent shadow-[0_2px_6px_-2px_rgba(47,93,138,.6)]">
          <GitBranch size={15} className="text-white" />
        </div>
        <div>
          <div className="text-[13.5px] leading-[1.1] font-semibold">Reconcile</div>
          <div className="text-[10.5px] text-ink-faint">tender ↔ bid</div>
        </div>
      </div>
      <div className="flex flex-col gap-[2px]">
        <NavItem icon={LayoutGrid} label="Projects" href="/projects" active={pathname.startsWith("/projects")} />
        <NavItem icon={ClipboardCheck} label="Review queue" href="/review" active={pathname === "/review"} />
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
            <button onClick={onLogout} className="btn cursor-pointer rounded-md border-none bg-transparent p-1 text-ink-faint" title="Log out">
              <LogOut size={15} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
