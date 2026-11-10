export function PlaceholderBanner({ reason }: { reason: string }) {
  return (
    <div
      role="status"
      className="rounded-lg border-2 border-dashed border-warn-foreground bg-warn px-4 py-3 text-warn-foreground"
    >
      <p className="font-semibold uppercase tracking-wide">Not computed: layout placeholder</p>
      <p className="text-sm">
        {reason} The cards below are fake fixtures for layout only. They are not suggestions and
        must not appear in the demo.
      </p>
    </div>
  );
}
