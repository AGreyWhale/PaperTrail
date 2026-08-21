import { useAuth } from "@clerk/react";
import { useCallback } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/**
 * Returns request functions pre-wired with the current Clerk
 * session token, so feature code never has to think about auth
 * headers — it just calls `api.request("/papers")`.
 */
export function useApiClient() {
  const { getToken } = useAuth();

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [getToken]);

  const request = useCallback(
    async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
      // File uploads must let the browser set multipart/form-data along
      // with its boundary parameter; forcing application/json here would
      // make the request unparseable on the server.
      const isFormData = options.body instanceof FormData;

      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: {
          ...(isFormData ? {} : {"Content-Type": "application/json"}),
          ...(await authHeaders()),
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
    [authHeaders],
  );

  // For binary responses (the PDF). An <iframe src> can't carry an
  // Authorization header, so fetch the bytes here and hand back a
  // blob: URL for the viewer to point at instead.
  const requestBlobUrl = useCallback(
    async (path: string): Promise<string> => {
      const response = await fetch(`${API_BASE_URL}${path}`, { headers: await authHeaders() });
      if (!response.ok) {
        throw new Error(`API error ${response.status}`);
      }
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    },
    [authHeaders],
  );

  return { request, requestBlobUrl };
}
