"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { SnapshotSchema, SuggestionListSchema, type Policy } from "./schemas";

export function useSuggestions(policy: Policy) {
  return useQuery({
    queryKey: ["suggestions", policy],
    queryFn: () => apiFetch(`/suggestions?policy=${policy}`, SuggestionListSchema),
  });
}

export function useSnapshot() {
  return useQuery({
    queryKey: ["snapshot"],
    queryFn: () => apiFetch("/snapshot", SnapshotSchema),
  });
}
