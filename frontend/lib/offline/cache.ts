"use client";

// Offline cache + outbox. localStorage only, no new dependencies.
// Cached snapshots let the app open read-only while offline; the outbox holds
// review/move actions until reconnect, then replays them through the same
// backend functions with their original idempotency keys.
export type OutboxItem = {
  event_id: string;
  kind: "suggestion" | "move";
  action: string;
  resource_id: string;
  unit_ids?: string[];
  unit_version?: number;
  to_facility_id?: string;
  input: Record<string, unknown>;
  queued_at: string;
};

const CACHE_PREFIX = "dg.cache.v1:";
const OUTBOX_KEY = "dg.outbox.v1";

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or unavailable: stay online-only rather than crash.
  }
}

export function writeCache<T>(key: string, data: T): void {
  writeJson(CACHE_PREFIX + key, { at: new Date().toISOString(), data });
}

export function readCache<T>(key: string): { at: string; data: T } | null {
  return readJson(CACHE_PREFIX + key);
}

export function readOutbox(): OutboxItem[] {
  return readJson<OutboxItem[]>(OUTBOX_KEY) ?? [];
}

export function enqueueOutbox(item: OutboxItem): void {
  writeJson(OUTBOX_KEY, [...readOutbox(), item]);
  notifyOutbox();
}

export function removeOutbox(eventIds: string[]): void {
  const gone = new Set(eventIds);
  writeJson(
    OUTBOX_KEY,
    readOutbox().filter((item) => !gone.has(item.event_id)),
  );
  notifyOutbox();
}

function notifyOutbox(): void {
  window.dispatchEvent(new Event("dg:outbox"));
}

/** Africa/Nairobi timestamp for "last updated at" labels. */
export function formatNairobi(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Africa/Nairobi",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

import { useSyncExternalStore } from "react";

/** Number of actions waiting in the offline outbox (updates on change). */
export function useOutboxCount(): number {
  return useSyncExternalStore(subscribeOutbox, readOutboxLength, readOutboxLength);
}

function subscribeOutbox(callback: () => void): () => void {
  window.addEventListener("dg:outbox", callback);
  window.addEventListener("online", callback);
  return () => {
    window.removeEventListener("dg:outbox", callback);
    window.removeEventListener("online", callback);
  };
}

function readOutboxLength(): number {
  return readOutbox().length;
}
