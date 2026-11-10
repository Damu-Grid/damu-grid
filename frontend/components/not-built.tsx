export function NotBuilt({ title, issue, detail }: { title: string; issue: string; detail: string }) {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="rounded-lg border border-dashed p-4 text-muted-foreground">
        Not built yet ({issue}). {detail}
      </p>
    </div>
  );
}
