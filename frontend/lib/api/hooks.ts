"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { backend, type DecisionInput, type MoveActionInput } from "./backend";
import { ApiError, apiFetch } from "./client";
import {
  ForecastEvalSchema,
  SnapshotSchema,
  type Move,
  type MoveAction,
  type Policy,
  type Suggestion,
  type SuggestionAction,
} from "./schemas";

export function useSuggestions(policy: Policy) {
  return useQuery({
    queryKey: ["suggestions", policy],
    queryFn: () => backend.listSuggestions(policy),
  });
}

/** Accept / change / reject. One event_id per user decision. */
export function useSuggestionAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      suggestion,
      action,
      input,
    }: {
      suggestion: Suggestion;
      action: SuggestionAction;
      input: DecisionInput;
    }) => backend.decide(action, suggestion, input),
    onSettled: (_data, error) => {
      // Success changes the queue; a 409 means our copy is stale. Either way, reload.
      if (!error || (error instanceof ApiError && error.status === 409)) {
        queryClient.invalidateQueries({ queryKey: ["suggestions"] });
        queryClient.invalidateQueries({ queryKey: ["moves"] });
      }
    },
  });
}

/** Moves in one or more states (screen names: reserved, in_transit, …). */
export function useMoves(states: string[]) {
  return useQuery({
    queryKey: ["moves", states],
    queryFn: () => backend.listMoves(states),
    refetchInterval: 30_000,
  });
}

export function useMove(moveId: string) {
  return useQuery({
    queryKey: ["move", moveId],
    queryFn: () => backend.getMove(moveId),
  });
}

/** Dispatch (sender) or receive (receiver). */
export function useMoveAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ move, action, input }: { move: Move; action: MoveAction; input: MoveActionInput }) =>
      backend.moveAction(action, move, input),
    onSettled: (_data, _error, { move }) => {
      queryClient.invalidateQueries({ queryKey: ["moves"] });
      queryClient.invalidateQueries({ queryKey: ["move", move.move_id] });
    },
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
