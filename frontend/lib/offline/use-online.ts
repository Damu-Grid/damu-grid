"use client";

import { useSyncExternalStore } from "react";

function subscribe(callback: () => void): () => void {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

function snapshot(): boolean {
  return navigator.onLine;
}

/** True while the browser reports a network connection. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, snapshot, () => true);
}
