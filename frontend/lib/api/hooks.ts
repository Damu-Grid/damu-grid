"use client";

import { useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { toast } from "sonner";
import { backend, type DecisionInput, type MoveActionInput } from "./backend";
import { ApiError, apiFetch, isUnreachable } from "./client";
import {
  enqueueOutbox,
  readCache,
  readOutbox,
  removeOutbox,
  writeCache,
} from "@/lib/offline/cache";
import { useOnline } from "@/lib/offline/use-online";
import {
  ForecastEvalSchema,
  SnapshotSchema,
  type Move,
  type MoveAction,
  type Policy,
  type Suggestion,
  type SuggestionAction,
} from "./schemas";

/**
 * Persist successful reads; when the network fails, serve the last good copy
 * and say so (OfflineBanner). Read-only offline: writes go to the outbox.
 */
function useCachedQuery<T>(key: string, query: UseQueryResult<T>) {
  const { data, error } = query;
  useEffect(() => {
    if (data !== undefined) writeCache(key, data);
  }, [data, key]);
  const cached = useMemo(
    () => (error && data === undefined ? readCache<T>(key) : null),
    [error, data, key],
  );
  return {
    ...query,
    data: data ?? cached?.data,
    cachedAt: cached?.at ?? null,
    isOfflineData: cached !== null,
  };
}

export function useSuggestions(policy: Policy) {
  return useCachedQuery(
    `suggestions:${policy}`,
    useQuery({
      queryKey: ["suggestions", policy],
      queryFn: () => backend.listSuggestions(policy),
    }),
  );
}

/** Accept / change / reject. One event_id per user decision. */
export function useSuggestionAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      suggestion,
      action,
      input,
    }: {
      suggestion: Suggestion;
      action: SuggestionAction;
      input: DecisionInput;
    }) => {
      try {
        return await backend.decide(action, suggestion, input);
      } catch (error) {
        if (!isUnreachable(error)) throw error;
        enqueueOutbox({
          event_id: input.event_id,
          kind: "suggestion",
          action,
          resource_id: suggestion.suggestion_id,
          unit_ids: suggestion.unit_ids,
          unit_version: suggestion.unit_version,
          to_facility_id: input.to_facility_id ?? suggestion.to_facility_id,
          input: { ...input },
          queued_at: new Date().toISOString(),
        });
        throw new ApiError(0, "Offline — action queued and will sync on reconnect.");
      }
    },
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
    mutationFn: async ({ move, action, input }: { move: Move; action: MoveAction; input: MoveActionInput }) => {
      try {
        return await backend.moveAction(action, move, input);
      } catch (error) {
        if (!isUnreachable(error)) throw error;
        enqueueOutbox({
          event_id: input.event_id,
          kind: "move",
          action,
          resource_id: move.move_id,
          input: { ...input },
          queued_at: new Date().toISOString(),
        });
        throw new ApiError(0, "Offline — action queued and will sync on reconnect.");
      }
    },
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
  return useCachedQuery(
    "snapshot",
    useQuery({
      queryKey: ["snapshot"],
      queryFn: () => apiFetch("/snapshot", SnapshotSchema),
    }),
  );
}



/**
 * Replays the offline outbox through the normal endpoints with the original
 * idempotency keys as soon as the browser is back online. Mount once globally.
 */
export function useOfflineSync() {
  const queryClient = useQueryClient();
  const online = useOnline();
  useEffect(() => {
    if (!online) return;
    const pending = readOutbox();
    if (pending.length === 0) return;
    let cancelled = false;
    (async () => {
      const settled: string[] = [];
      for (const item of pending) {
        try {
          if (item.kind === "suggestion") {
            await backend.decide(
              item.action as SuggestionAction,
              {
                suggestion_id: item.resource_id,
                unit_ids: item.unit_ids ?? [],
                unit_version: item.unit_version ?? 0,
                to_facility_id: item.to_facility_id ?? "",
              } as Suggestion,
              item.input as unknown as DecisionInput,
            );
          } else {
            await backend.moveAction(
              item.action as MoveAction,
              { move_id: item.resource_id } as Move,
              item.input as unknown as MoveActionInput,
            );
          }
          settled.push(item.event_id);
          toast.success(`Synced queued ${item.action} (${item.resource_id}).`);
        } catch (error) {
          if (isUnreachable(error)) return; // still offline: keep the rest queued
          settled.push(item.event_id);
          toast.warning(
            `Queued ${item.action} (${item.resource_id}) was rejected on reconnect.`,
          );
        }
      }
      if (cancelled) return;
      removeOutbox(settled);
      queryClient.invalidateQueries({ queryKey: ["suggestions"] });
      queryClient.invalidateQueries({ queryKey: ["moves"] });
    })();
    return () => {
      cancelled = true;
    };
  }, [online, queryClient]);
}
