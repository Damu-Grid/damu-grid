"use client";

import { BarChart3, Bell, Droplet, ListChecks, LogOut, Map as MapIcon, PackageCheck, Truck } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { DEMO_ACTORS, useRole } from "@/lib/session";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/queue", label: "Review queue", Icon: ListChecks },
  { href: "/map", label: "Transfer map", Icon: MapIcon },
  { href: "/dispatch", label: "Dispatch", Icon: Truck },
  { href: "/receive", label: "Receive", Icon: PackageCheck },
  { href: "/evaluation", label: "Evaluation", Icon: BarChart3 },
  { href: "/alerts", label: "Alerts", Icon: Bell },
];

const initials = (title: string) =>
  title
    .split(/\s+/)
    .filter((w) => /^[A-Z]/i.test(w) && w !== "/")
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");

/** Left icon rail (docs/DESIGN.md): brand mark, screens, current role. */
export function AppRail() {
  const { role, setRole } = useRole();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <nav
      aria-label="Damu Grid"
      className="sticky top-0 z-10 flex h-auto flex-row flex-wrap items-center justify-center gap-3 border-b border-line bg-white/55 px-2 py-2 md:h-screen md:flex-col md:justify-start md:border-r md:border-b-0 md:py-4"
    >
      <Link
        href="/"
        aria-label="Damu Grid home"
        className="grid size-[42px] place-items-center rounded-full bg-navy text-white"
      >
        <Droplet className="size-5 fill-white" aria-hidden />
      </Link>
      <span className="hidden h-px w-7 bg-line md:block" aria-hidden />
      {NAV.map(({ href, label, Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            title={label}
            aria-label={label}
            aria-current={active ? "page" : undefined}
            className={cn(
              "grid size-11 place-items-center rounded-xl text-navy transition-colors hover:bg-soft",
              active && "bg-navy text-white hover:bg-navy",
            )}
          >
            <Icon className="size-5" aria-hidden />
          </Link>
        );
      })}
      {role && (
        <div className="flex items-center gap-2 md:mt-auto md:flex-col">
          <span
            title={`Signed in as ${DEMO_ACTORS[role].title}`}
            aria-label={`Signed in as ${DEMO_ACTORS[role].title}`}
            className="grid size-10 place-items-center rounded-full bg-gold-soft text-xs font-bold text-gold-ink"
          >
            {initials(DEMO_ACTORS[role].title)}
          </span>
          <button
            type="button"
            title="Switch role"
            aria-label="Switch role"
            onClick={() => {
              setRole(null);
              router.push("/login");
            }}
            className="grid size-11 place-items-center rounded-xl text-ink-2 hover:bg-soft"
          >
            <LogOut className="size-5" aria-hidden />
          </button>
        </div>
      )}
    </nav>
  );
}
