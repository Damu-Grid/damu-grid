"use client";

import { SyntheticBadge } from "@/components/status-chips";
import { DEMO_ACTORS, useRole } from "@/lib/session";

/** Screen heading (docs/DESIGN.md): eyebrow + synthetic pill, title, one-line purpose. */
export function PageHeader({
  title,
  children,
  actions,
}: {
  title: string;
  children?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const { role } = useRole();
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="grid max-w-3xl gap-2">
        <div className="eyebrow">
          Red cell network · Kenya
          <SyntheticBadge />
          {role && <span className="normal-case tracking-normal text-ink-2">{DEMO_ACTORS[role].title}</span>}
        </div>
        <h1 className="text-2xl leading-tight font-bold md:text-[2rem]">{title}</h1>
        {children && <div className="text-[0.95rem] text-ink-2">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </header>
  );
}
