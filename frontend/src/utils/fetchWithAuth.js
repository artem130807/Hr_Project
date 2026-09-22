import { getAccessToken } from "./tokenStorage";
import { refreshSession } from "./http";

/**
 * fetch with Bearer access token + one silent refresh retry on 401.
 * Used by APIs that call HH/AI hosts directly (bypass http.request).
 */
export async function fetchWithAuth(url, options = {}, { retried = false } = {}) {
    const token = getAccessToken();
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    const res = await fetch(url, {
        ...options,
        headers,
        mode: options.mode || "cors",
        cache: options.cache || "no-store",
    });

    if (res.status === 401 && !retried) {
        const refreshed = await refreshSession();
        if (refreshed) {
            return fetchWithAuth(url, options, { retried: true });
        }
    }

    return res;
}
