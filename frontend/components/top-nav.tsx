"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const items = [
  { href: "/", label: "Home" },
  { href: "/banks", label: "Experience Banks" },
  { href: "/tailor", label: "Tailor Resume" },
  { href: "/docs", label: "Docs" }
];

export function TopNav() {
  const pathname = usePathname();
  return (
    <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
        <Link href="/" className="text-sm font-semibold">
          Evidence-Grounded Resume Tailoring
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          {items.map((it) => (
            <Link
              key={it.href}
              href={it.href}
              className={cn(
                "rounded-md px-3 py-1.5 hover:bg-slate-100",
                pathname === it.href ? "bg-slate-100 font-medium" : "text-slate-700"
              )}
            >
              {it.label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}

