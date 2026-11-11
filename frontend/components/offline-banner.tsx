"use client";

import { useOfflineSync, useSnapshot } from "@/lib/api/hooks";
import { formatNairobi, readCache } from "@/lib/offline/cache";
import { useOutboxCount } from "@/lib/offline/cache";
import { useOnline } from "@/lib/offline/use-online";

/**
 * Global connectivity banner. Mounted once under the app header: shows while
 * offline (or while serving the cached snapshot), the last-updated time, and
 * how many review actions are queued for sync.
 */
export function OfflineBanner() {
  const online = useOnline();
  const pending = useOutboxCount();
  useOfflineSync();
  const snapshot = useSnapshot() as ReturnType<typeof useSnapshot> & {
    cachedAt?: string | null;
    isOfflineData?: boolean;
  };
  const cached = snapshot.isOfflineData ?? false;
  const updatedAt =
    snapshot.cachedAt ?? readCache<unknown>("snapshot")?.at ?? snapshot.data?.as_of ?? null;
  const hasData = snapshot.data !== undefined;

  if (online && !cached && pending === 0) return null;
  return (
    <div role="status" className="border-b bg-warn px-4 py-2 text-sm text-warn-foreground">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1">
        {!online ? (
          <strong>Offline — showing saved data.</strong>
        ) : (
          <strong>Connection issue — showing saved data.</strong>
        )}
        {!hasData && <span>No saved snapshot on this device yet.</span>}
        {hasData && updatedAt && <span>Last updated {formatNairobi(updatedAt)} EAT.</span>}
        {pending > 0 && (
          <span>
            {pending} action{pending === 1 ? "" : "s"} queued — will sync on reconnect.
          </span>
        )}
      </div>
    </div>
  );
}
