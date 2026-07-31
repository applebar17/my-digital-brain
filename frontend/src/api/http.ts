import { apiBaseUrl } from "../config";

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
  bearerToken?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && isRecord(error.detail)) {
    const message = typeof error.detail.message === "string" ? error.detail.message : undefined;
    const code = typeof error.detail.code === "string" ? error.detail.code : undefined;
    if (message && code) {
      return `${message} (${code})`;
    }
    if (message) {
      return message;
    }
  }
  return error instanceof Error ? error.message : fallback;
}

export async function apiRequest<T>(
  path: string,
  { method = "GET", query, body, bearerToken }: ApiRequestOptions = {}
): Promise<T> {
  const url = new URL(path, apiBaseUrl);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });

  const headers = new Headers();
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (bearerToken) {
    headers.set("Authorization", `Bearer ${bearerToken}`);
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  });

  const payload = await readPayload(response);
  if (!response.ok) {
    const detail = isRecord(payload) && "detail" in payload ? payload.detail : payload;
    throw new ApiError(response.status, detail);
  }
  return payload as T;
}

async function readPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
