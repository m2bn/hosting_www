export type ApiErrorPayload = {
  detail?: string;
  code?: string;
};

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code = "api_error") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export function getCookie(name: string): string {
  if (typeof document === "undefined") {
    return "";
  }
  const value = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1];
  return value ? decodeURIComponent(value) : "";
}

export async function ensureCsrfToken(): Promise<string> {
  let token = getCookie("csrftoken");
  if (token) {
    return token;
  }
  await fetch(`${API_BASE_URL}/auth/csrf/`, {
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });
  token = getCookie("csrftoken");
  return token;
}

type ApiRequestOptions = Omit<RequestInit, "body" | "credentials"> & {
  body?: unknown;
  csrf?: boolean;
};

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  if (options.csrf || !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
    const csrfToken = await ensureCsrfToken();
    if (csrfToken) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method,
    headers,
    body,
    credentials: "include",
  });

  if (!response.ok) {
    let payload: ApiErrorPayload = {};
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = {};
    }
    throw new ApiError(payload.detail ?? "Request failed.", response.status, payload.code);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
