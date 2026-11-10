"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "./client";
import {
  ActionResultSchema,
  ForecastEvalSchema,
  MoveListSchema,
  MoveSchema,
  SnapshotSchema,
  SuggestionListSchema,
  type ActionBody,
  type MoveAction,
  type MoveActionBody,
  type Policy,
  type SuggestionAction,
} from "./schemas";

/**
 * Moves in one or more states. GET /moves?state= is proposed to the backend
 * (only GET /moves/{id} is in docs/API_SPEC.md so far); change it here if needed.
 */
export function useMoves(states: string[]) {
  return useQuery({
    queryKey: ["moves", states],
    queryFn: () =>
      apiFetch(`/moves?${states.map((s) => `state=${encodeURIComponent(s)}`).join("&")}`, MoveListSchema),
    refetchInterval: 30_000,
  });
}

export function useMove(moveId: string) {
  return useQuery({
    queryKey: ["move", moveId],
    queryFn: () => apiFetch(`/moves/${encodeURIComponent(moveId)}`, MoveSchema),
  });
}

/** POST /moves/{id}/dispatch (sender) or /receive (receiver). */
export function useMoveAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ moveId, action, body }: { moveId: string; action: MoveAction; body: MoveActionBody }) =>
      apiFetch(`/moves/${encodeURIComponent(moveId)}/${action}`, MoveSchema, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSettled: (_data, _error, { moveId }) => {
      queryClient.invalidateQueries({ queryKey: ["moves"] });
      queryClient.invalidateQueries({ queryKey: ["move", moveId] });
    },
  });
}

export function useSuggestions(policy: Policy) {
  return useQuery({
    queryKey: ["suggestions", policy],
    queryFn: () => apiFetch(`/suggestions?policy=${policy}`, SuggestionListSchema),
  });
}

export function useForecastEval() {
  return useQuery({
    queryKey: ["evaluation", "forecast"],
    queryFn: () => apiFetch("/evaluation/forecast", ForecastEvalSchema),
    staleTime: 5 * 60_000, // frozen results; rarely change
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
