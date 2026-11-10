"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { SyntheticBadge } from "@/components/status-chips";
import { DEMO_ACTORS, useRole } from "@/lib/session";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/queue", label: "Review queue" },
  { href: "/dispatch", label: "Dispatch" },
  { href: "/receive", label: "Receive" },
  { href: "/evaluation", label: "Evaluation" },
];

export function AppHeader() {
  const { role, setRole } = useRole();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-semibold text-brand">
          Damu Grid
        </Link>
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm hover:bg-accent",
                pathname.startsWith(item.href) && "bg-accent font-medium",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <SyntheticBadge />
          {role && (
            <>
              <span className="text-sm">
                Signed in as <strong>{DEMO_ACTORS[role].title}</strong>
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setRole(null);
                  router.push("/login");
                }}
              >
                Switch role
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
