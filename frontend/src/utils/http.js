import { API_URL, API_PREFIX } from "../config/api";
import {
    getAccessToken,
    getRefreshToken,
    getStoredUser,
    setSessionTokens,
    clearSession,
} from "./tokenStorage";

export const AUTH_CLEARED_EVENT = "hr:auth-cleared";

let authCleared = false;
let refreshPromise = null;

export function resetAuthClearedFlag() {
    authCleared = false;
}

function formatErrorDetail(detail, fallback) {
    if (detail == null || detail === "") return fallback;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        return detail
            .map((item) => {
                if (typeof item === "string") return item;
                if (item && typeof item === "object") {
                    return item.msg || item.message || JSON.stringify(item);
                }
                return String(item);
            })
            .filter(Boolean)
            .join("; ") || fallback;
    }
    if (typeof detail === "object") {
        return detail.msg || detail.message || JSON.stringify(detail);
    }
    return String(detail);
}

/** HH OAuth / upstream auth must not wipe the HR platform session. */
function isUpstreamAuthFailure(detail) {
    const msg = String(detail || "").toLowerCase();
    return (
        msg.includes("hh token")
        || msg.includes("hh.ru")
        || msg.includes("hh authorization")
        || msg.includes("hh api")
        || msg.includes("ошибка авторизации hh")
        || msg.includes("не сессия hr")
        || (msg.includes("авторизац") && msg.includes("hh"))
        || msg.includes("ai service auth")
    );
}

function handleUnauthorized() {
    if (authCleared) return;
    if (!getAccessToken() && !getRefreshToken()) return;
    authCleared = true;
    clearSession();
    try {
        window.dispatchEvent(new Event(AUTH_CLEARED_EVENT));
    } catch {
        /* ignore */
    }
    if (window.location.pathname !== "/") {
        window.location.replace("/");
    }
}

/**
 * Single-flight refresh: concurrent 401s share one /token/refresh call.
 * Survives multi-tab races: if another tab already rotated, treat local tokens as OK.
 * @returns {Promise<boolean>} true if tokens were renewed (or already renewed elsewhere)
 */
export async function refreshSession() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    if (!refreshPromise) {
        refreshPromise = (async () => {
            const startedWith = refreshToken;
            try {
                const url = `${API_URL}${API_PREFIX}/token/refresh`;
                const res = await fetch(url, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ refresh_token: startedWith }),
                    mode: "cors",
                    cache: "no-store",
                });
                const text = await res.text();
                let data = null;
                if (text) {
                    try {
                        data = JSON.parse(text);
                    } catch {
                        data = null;
                    }
                }
                if (res.ok && data?.access_token) {
                    setSessionTokens(data);
                    return true;
                }
            } catch {
                // Network / parse — fall through to cross-tab check
            }

            // Another tab may have rotated the same family and written new tokens.
            const latestRefresh = getRefreshToken();
            const latestAccess = getAccessToken();
            if (latestAccess && latestRefresh && latestRefresh !== startedWith) {
                return true;
            }
            return false;
        })().finally(() => {
            refreshPromise = null;
        });
    }

    try {
        return await refreshPromise;
    } catch {
        const latestRefresh = getRefreshToken();
        const latestAccess = getAccessToken();
        if (latestAccess && latestRefresh && latestRefresh !== refreshToken) {
            return true;
        }
        return false;
    }
}

async function parseResponseBody(res) {
    if (!res || typeof res.text !== "function") {
        throw new Error("Пустой ответ от API (сеть или прокси)");
    }
    const text = await res.text();
    let data = null;
    if (text) {
        try {
            data = JSON.parse(text);
        } catch {
            if (res.status === 401) {
                data = null;
            } else if (!res.ok) {
                throw new Error(text || res.statusText);
            } else {
                return { data: text, text };
            }
        }
    }
    return { data, text };
}

async function tryRefreshAndRetry(retryFn, detail) {
    if (isUpstreamAuthFailure(detail)) return { refreshed: false, shouldClear: false };
    if (!getRefreshToken()) return { refreshed: false, shouldClear: Boolean(getAccessToken()) };
    const refreshed = await refreshSession();
    if (refreshed) {
        return { refreshed: true, shouldClear: false, result: await retryFn() };
    }
    return { refreshed: false, shouldClear: true };
}

function actorHeaders() {
    const user = getStoredUser();
    if (!user || typeof user !== "object") return {};
    const id = user.erp_user_id ?? user.id;
    const name = user.full_name || user.name || user.username || user.login;
    const headers = {};
    if (id != null && String(id).trim()) headers["X-Actor-Id"] = String(id).trim();
    if (name && String(name).trim()) headers["X-Actor-Name"] = encodeURIComponent(String(name).trim());
    return headers;
}

export async function request(path, { auth = true, method = "GET", headers = {}, body, signal, _retried = false, _netRetried = false } = {}) {
    const url = `${API_URL}${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;
    const token = getAccessToken();

    const finalHeaders = {
        ...(auth ? actorHeaders() : {}),
        ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
    };

    let finalBody = body;
    if (body && !(body instanceof FormData) && !(body instanceof URLSearchParams)) {
        finalHeaders["Content-Type"] = finalHeaders["Content-Type"] || "application/json";
        finalBody = JSON.stringify(body);
    }

    let res;
    try {
        res = await fetch(url, {
            method,
            headers: finalHeaders,
            body: finalBody,
            mode: "cors",
            cache: "no-store",
            ...(signal ? { signal } : {}),
        });
    } catch (err) {
        if (signal?.aborted || err?.name === "AbortError") {
            const abortErr = new Error("Aborted");
            abortErr.name = "AbortError";
            throw abortErr;
        }
        const msg = err?.message || String(err);
        if (/failed to fetch|networkerror|load failed/i.test(msg)) {
            // Aborted fetches are often reported as Failed to fetch in Chromium.
            if (signal?.aborted) {
                const abortErr = new Error("Aborted");
                abortErr.name = "AbortError";
                throw abortErr;
            }
            // One automatic retry for transient network blips
            if (!_netRetried && method === "GET") {
                await new Promise((r) => setTimeout(r, 500));
                if (signal?.aborted) {
                    const abortErr = new Error("Aborted");
                    abortErr.name = "AbortError";
                    throw abortErr;
                }
                return request(path, { auth, method, headers, body, signal, _retried, _netRetried: true });
            }
            const apiHint = API_URL || "тот же хост, путь /v1 (dev-прокси)";
            throw new Error(
                `Нет связи с API (${msg}). Если открыт прод (hr-web), запросы должны идти на тот же хост (/v1/...), ` +
                `не на hr-platform. Обновите фронт и сделайте Ctrl+Shift+R. Иначе проверьте VPN. API: ${apiHint}`
            );
        }
        throw err instanceof Error ? err : new Error(msg);
    }

    const { data, text } = await parseResponseBody(res);

    if (res.status === 401) {
        const detail = formatErrorDetail(data?.detail ?? data?.message, text || "Unauthorized");
        if (isUpstreamAuthFailure(detail)) {
            throw new Error(detail || "Unauthorized");
        }
        if (auth && !_retried) {
            const outcome = await tryRefreshAndRetry(
                () => request(path, { auth, method, headers, body, signal, _retried: true, _netRetried }),
                detail
            );
            if (outcome.refreshed) return outcome.result;
            if (outcome.shouldClear) handleUnauthorized();
        }
        // After a successful refresh, a second 401 is endpoint/business auth — do not wipe the HR session.
        throw new Error(detail || "Unauthorized");
    }

    if (!res.ok) {
        throw new Error(formatErrorDetail(data?.detail ?? data?.message, text || res.statusText));
    }
    return data;
}

export async function requestBlob(path, { auth = true, headers = {}, _retried = false } = {}) {
    const url = `${API_URL}${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;
    const token = getAccessToken();

    const finalHeaders = {
        ...(auth ? actorHeaders() : {}),
        ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
    };

    const res = await fetch(url, { method: "GET", headers: finalHeaders, mode: "cors", cache: "no-store" });

    if (res.status === 401) {
        if (auth && !_retried) {
            const outcome = await tryRefreshAndRetry(
                () => requestBlob(path, { auth, headers, _retried: true }),
                "Unauthorized"
            );
            if (outcome.refreshed) return outcome.result;
            if (outcome.shouldClear) handleUnauthorized();
        }
        throw new Error("Unauthorized");
    }

    if (!res.ok) {
        const text = await res.text();
        try {
            const data = text ? JSON.parse(text) : null;
            throw new Error(formatErrorDetail(data?.detail ?? data?.message, text || res.statusText));
        } catch (e) {
            if (e instanceof Error && e.message && !e.message.startsWith("{")) throw e;
            throw new Error(text || res.statusText);
        }
    }

    return res.blob();
}

export const http = {
    get: (path, opts = {}) => request(path, { ...opts, method: "GET" }),
    post: (path, body, opts = {}) => request(path, { ...opts, method: "POST", body }),
    put: (path, body, opts = {}) => request(path, { ...opts, method: "PUT", body }),
    patch: (path, body, opts = {}) => request(path, { ...opts, method: "PATCH", body }),
    del: (path, opts = {}) => request(path, { ...opts, method: "DELETE" }),
    getBlob: (path, opts = {}) => requestBlob(path, opts),
};
