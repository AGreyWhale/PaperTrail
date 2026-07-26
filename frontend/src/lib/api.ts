import { useAuth } from "@clerk/react";
import { useCallback } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/**
 * Returns a `request` function pre-wired with the current Clerk
 * session token, so feature code never has to think about auth
 * headers — it just calls `api.request("/papers")`.
 */
export function useApiClient() {
  const { getToken } = useAuth();

  const request = useCallback(
    async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...options.headers,
        },
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`API error ${response.status}: ${body}`);
      }

      // 204 No Content etc. have no body to parse
      if (response.status === 204) return undefined as T;
      return response.json() as Promise<T>;
    },
    [getToken],
  );

  return { request };
}
