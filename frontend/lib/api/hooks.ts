"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "./client";
import {
  ActionResultSchema,
  SnapshotSchema,
  SuggestionListSchema,
  type ActionBody,
  type Policy,
  type SuggestionAction,
} from "./schemas";

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

/** POST /suggestions/{id}/accept|change|reject. One event_id per user action. */
export function useSuggestionAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      suggestionId,
      action,
      body,
    }: {
      suggestionId: string;
      action: SuggestionAction;
      body: ActionBody;
    }) =>
      apiFetch(
        `/suggestions/${encodeURIComponent(suggestionId)}/${action}`,
        ActionResultSchema,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSettled: (_data, error) => {
      // Success changes the queue; a 409 means our copy is stale. Either way, reload.
      if (!error || (error instanceof ApiError && error.status === 409)) {
        queryClient.invalidateQueries({ queryKey: ["suggestions"] });
      }
    },
  });
}
