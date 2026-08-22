export type RoleGrant = {
  name: string;
  template_code: string;
  facility: string | null;
  department: string | null;
  department_code: string | null;
};

export type ApiSession = {
  access_token: string;
  access_expires_at: string;
  user: {
    id: string;
    username: string;
    full_name: string;
    first_name: string;
    last_name: string;
  };
  organisation: {
    id: string;
    name: string;
    default_currency: string;
  };
  facilities: Facility[];
  roles: RoleGrant[];
  capabilities: string[];
};

export type Facility = {
  id: string;
  name: string;
  code: string;
  mode: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export class ApiRequestError extends Error {
  readonly status: number;
  readonly data: unknown;
  readonly headers: Headers;

  constructor(status: number, data: unknown, headers: Headers) {
    const detail =
      data && typeof data === "object" && "detail" in data && typeof data.detail === "string"
        ? data.detail
        : "The request could not be completed.";
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
    this.data = data;
    this.headers = new Headers(headers);
  }
}

let accessToken: string | null = null;
let facilityId: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setFacilityId(id: string | null) {
  facilityId = id;
}

let restoreInFlight: Promise<ApiSession | null> | null = null;

export function restoreSession(): Promise<ApiSession | null> {
  if (!restoreInFlight) {
    restoreInFlight = (async () => {
      try {
        const response = await fetch(API_URL + "/api/v1/auth/refresh/", {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) {
          accessToken = null;
          facilityId = null;
          return null;
        }
        const data = (await response.json()) as ApiSession;
        accessToken = data.access_token;
        facilityId = data.facilities[0]?.id || null;
        return data;
      } finally {
        restoreInFlight = null;
      }
    })();
  }
  return restoreInFlight;
}

async function refreshAccessToken() {
  return Boolean(await restoreSession());
}
export async function login(username: string, password: string, organisationId?: string) {
  const response = await fetch(API_URL + "/api/v1/auth/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      username,
      password,
      ...(organisationId ? { organisation_id: organisationId } : {}),
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Could not sign in.");
  }
  accessToken = data.access_token;
  return data as ApiSession;
}

export async function logout() {
  if (accessToken) {
    await fetch(API_URL + "/api/v1/auth/logout/", {
      method: "POST",
      credentials: "include",
      headers: {
        Authorization: "Bearer " + accessToken,
        ...(facilityId ? { "X-Facility-Id": facilityId } : {}),
      },
    });
  }
  accessToken = null;
  facilityId = null;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) {
    headers.set("Authorization", "Bearer " + accessToken);
  }
  if (facilityId) {
    headers.set("X-Facility-Id", facilityId);
  }
  const response = await fetch(API_URL + path, {
    ...init,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry && (await refreshAccessToken())) {
    return apiRequest<T>(path, init, false);
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new ApiRequestError(response.status, data, response.headers);
  }
  return data as T;
}
