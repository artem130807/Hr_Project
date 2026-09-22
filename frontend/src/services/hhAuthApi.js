import { API_URL, API_PREFIX } from "../config/api";
import { http, refreshSession } from "../utils/http";
import { getAccessToken } from "../utils/tokenStorage";

/**
 * HH OAuth via database-service.
 * Prod edge returns 404 for `/hh/connect/*` (and `/auth`, `/oauth`) even when
 * OpenAPI lists them. `/hh-oauth/*` already works (tokens endpoint).
 */

export const checkHHAuth = () => http.get("/hh-oauth/status");

export const getHHAuthLink = async () => {
    const url = `${API_URL}${API_PREFIX}/hh-oauth/login-url`;

    const doFetch = async () => {
        const token = getAccessToken();
        return fetch(url, {
            method: "GET",
            mode: "cors",
            cache: "no-store",
            headers: {
                Accept: "text/plain, application/json, */*",
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
        });
    };

    let res = await doFetch();
    if (res.status === 401) {
        const refreshed = await refreshSession();
        if (refreshed) res = await doFetch();
    }
    if (!res.ok) {
        let detail = `HTTP error! status: ${res.status}`;
        try {
            const body = await res.json();
            if (body?.detail) {
                detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
            }
        } catch {
            if (res.status === 404) {
                detail = "Not Found — задеплойте database-service (маршрут /v1/hh-oauth/login-url).";
            }
        }
        throw new Error(detail);
    }
    return (await res.text()).trim().replace(/^["']|["']$/g, "");
};
