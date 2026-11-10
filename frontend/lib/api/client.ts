import { z } from "zod";
import { ApiErrorBodySchema } from "./schemas";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// Status codes from docs/API_SPEC.md "Error model".
const STATUS_MESSAGES: Record<number, string> = {
  403: "Your role is not allowed to do this.",
  409: "Someone else changed this first (stale version or conflicting reservation). Reload and try again.",
  422: "This move failed the eligibility checks.",
  503: "The demand estimator is offline. Switch to the fallback rule.",
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** True when the API could not be reached at all (server down, offline, CORS). */
export function isUnreachable(error: unknown): boolean {
  return error instanceof ApiError && error.status === 0;
}

export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, `Cannot reach the Damu Grid API at ${API_BASE_URL}.`);
  }

  const body: unknown = await res.json().catch(() => null);

  if (!res.ok) {
    const parsed = ApiErrorBodySchema.safeParse(body);
    const err = parsed.success ? parsed.data : {};
    throw new ApiError(
      res.status,
      err.message ?? STATUS_MESSAGES[res.status] ?? `Request failed (${res.status}).`,
      err.code,
      err.detail,
    );
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError(
      res.status,
      "The API response does not match docs/API_SPEC.md.",
      "contract_mismatch",
      parsed.error.flatten(),
    );
  }
  return parsed.data;
}

/** Idempotency key for every write (docs/API_SPEC.md "Idempotency"). */
export function newEventId(): string {
  return crypto.randomUUID();
}
