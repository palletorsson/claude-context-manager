"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, MessageSquare, FileText, Zap, GitBranch, Network } from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tree", label: "Working Tree", icon: Network },
  { href: "/sessions", label: "Sessions", icon: MessageSquare },
  { href: "/memory", label: "Memory", icon: FileText },
  { href: "/context", label: "Context", icon: Zap },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-[var(--color-sidebar-bg)] border-r border-[var(--color-border)] flex flex-col">
      <div className="p-4 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-[var(--color-done)]" />
          <span className="font-semibold text-[var(--color-fg-default)] text-sm">Context Manager</span>
        </div>
        <p className="text-[11px] text-[var(--color-fg-subtle)] mt-1">Claude Code Session Memory</p>
      </div>

      <nav className="flex-1 p-2 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-[#ddf4ff] text-[var(--color-accent)]  font-medium"
                  : "text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-fg-default)]"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-[var(--color-border)] text-[11px] text-[var(--color-fg-subtle)]">
        API: localhost:8000
      </div>
    </aside>
  );
}
