import { cn } from "@/lib/utils";

type ChipProps = { className?: string; children: React.ReactNode; title?: string };

function Chip({ className, children, title }: ChipProps) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function SyntheticBadge() {
  return (
    <Chip
      className="rounded-full bg-gold-soft px-2.5 text-[11px] font-semibold tracking-[0.12em] text-warn-foreground uppercase"
      title="Official synthetic starter dataset. Not facts about real Kenyan facilities."
    >
      <i className="size-1.5 rounded-full bg-gold" aria-hidden />
      Synthetic data
    </Chip>
  );
}

export function FallbackChip() {
  return <Chip className="bg-fallback text-fallback-foreground">Fallback rule · model off</Chip>;
}

export function PolicyChip({ policy }: { policy: string }) {
  const label =
    policy === "expiry_aware" ? "Expiry-aware" : policy === "nearest" ? "Nearest site" : policy;
  return <Chip className="bg-secondary text-secondary-foreground">Policy: {label}</Chip>;
}

/** Days from the as-of time to expiry; text carries the meaning, colour only reinforces it. */
export function ExpiryChip({ expiryDate, asOf }: { expiryDate: string; asOf: string }) {
  const days = Math.floor(
    (Date.parse(`${expiryDate}T23:59:59+03:00`) - Date.parse(asOf)) / 86_400_000,
  );
  // Gold = expiring (reference look); red only when it is close to unusable.
  // An expiry that does not parse is a warning, never a calm "fine".
  const tone = !Number.isFinite(days)
    ? "bg-warn text-warn-foreground"
    : days <= 3
      ? "bg-expiry text-expiry-foreground"
      : days <= 10
        ? "bg-warn text-warn-foreground"
        : "bg-soft text-ink-2";
  return (
    <Chip className={tone}>
      Expires {expiryDate}
      {Number.isFinite(days) && ` · ${days} day${days === 1 ? "" : "s"} after as-of`}
    </Chip>
  );
}

export function DataAgeChip({ asOf, ageHours }: { asOf: string; ageHours: number | null }) {
  const when = new Date(asOf).toLocaleString("en-GB", {
    timeZone: "Africa/Nairobi",
    dateStyle: "medium",
    timeStyle: "short",
  });
  return (
    <Chip className="bg-muted text-muted-foreground" title="Stock snapshot time (EAT)">
      Stock as of {when} EAT
      {ageHours !== null && ` · data age ${ageHours} h`}
    </Chip>
  );
}

export function WarningChip({ children }: { children: React.ReactNode }) {
  return <Chip className="bg-warn text-warn-foreground">⚠ {children}</Chip>;
}
