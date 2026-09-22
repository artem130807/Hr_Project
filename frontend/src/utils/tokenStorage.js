/**
 * Session token storage for HR panel (access + refresh).
 * Keys are centralized so AuthContext / http interceptors stay in sync.
 */
const ACCESS_TOKEN_KEY = "token";
const REFRESH_TOKEN_KEY = "refresh_token";
const ACCESS_EXPIRES_KEY = "token_expires";
const REFRESH_EXPIRES_KEY = "refresh_expires";
const USER_KEY = "user";

/** Seconds before real expiry when we treat access as stale and renew early. */
const ACCESS_SKEW_SECONDS = 60;

export function getAccessToken() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getAccessExpires() {
    return localStorage.getItem(ACCESS_EXPIRES_KEY);
}

export function getStoredUser() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function decodeJwtPayload(token) {
    if (!token || typeof token !== "string") return null;
    const parts = token.split(".");
    if (parts.length < 2) return null;
    try {
        const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
        const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
        return JSON.parse(atob(padded));
    } catch {
        return null;
    }
}

export function getAccessTokenPayload() {
    return decodeJwtPayload(getAccessToken());
}

/**
 * True when access is missing or at/near expiry (skew).
 * Uses stored `expires` first, then JWT `exp`.
 */
export function isAccessTokenExpired(skewSeconds = ACCESS_SKEW_SECONDS) {
    const access = getAccessToken();
    if (!access) return true;

    const expiresRaw = getAccessExpires();
    if (expiresRaw) {
        const ms = Date.parse(expiresRaw);
        if (!Number.isNaN(ms)) {
            return Date.now() >= ms - skewSeconds * 1000;
        }
    }

    const payload = decodeJwtPayload(access);
    if (payload && typeof payload.exp === "number") {
        return Date.now() >= payload.exp * 1000 - skewSeconds * 1000;
    }

    // Token present but unreadable expiry — keep using it until API 401.
    return false;
}

export function hasPersistedSession() {
    return Boolean(getStoredUser() && (getAccessToken() || getRefreshToken()));
}

/**
 * Persist tokens from AuthResponse ({ access_token, refresh_token?, expires?, refresh_expires? }).
 */
export function setSessionTokens(data) {
    if (!data?.access_token) return;
    localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
    if (data.expires) {
        localStorage.setItem(ACCESS_EXPIRES_KEY, data.expires);
    }
    if (data.refresh_token) {
        localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
    }
    if (data.refresh_expires) {
        localStorage.setItem(REFRESH_EXPIRES_KEY, data.refresh_expires);
    }
}

export function setStoredUser(user) {
    if (user == null) {
        localStorage.removeItem(USER_KEY);
        return;
    }
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(ACCESS_EXPIRES_KEY);
    localStorage.removeItem(REFRESH_EXPIRES_KEY);
    localStorage.removeItem(USER_KEY);
}

export const TOKEN_KEYS = {
    ACCESS_TOKEN_KEY,
    REFRESH_TOKEN_KEY,
    ACCESS_EXPIRES_KEY,
    REFRESH_EXPIRES_KEY,
    USER_KEY,
};
