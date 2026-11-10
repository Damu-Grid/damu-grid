"use client";

import { useCallback, useSyncExternalStore } from "react";
import { RoleSchema, type Role } from "@/lib/api/schemas";

// Demo roles only (docs/API_SPEC.md "Auth"). Not production identity.
export const DEMO_ACTORS: Record<Role, { actorId: string; title: string; home: string }> = {
  coordinator: { actorId: "demo-coordinator", title: "Regional stock coordinator", home: "/queue" },
  sender: { actorId: "demo-sender", title: "Sending officer", home: "/dispatch" },
  receiver: { actorId: "demo-receiver", title: "Receiving officer", home: "/receive" },
  safety: { actorId: "demo-safety", title: "Safety / quarantine officer", home: "/queue" },
};

const KEY = "damu.role";
const listeners = new Set<() => void>();

function read(): Role | null {
  try {
    const parsed = RoleSchema.safeParse(localStorage.getItem(KEY));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function useRole() {
  const role = useSyncExternalStore(subscribe, read, () => null);
  const setRole = useCallback((next: Role | null) => {
    try {
      if (next) localStorage.setItem(KEY, next);
      else localStorage.removeItem(KEY);
    } catch {
      // Storage blocked: the role lasts for this page only.
    }
    listeners.forEach((l) => l());
  }, []);
  return { role, setRole };
}
