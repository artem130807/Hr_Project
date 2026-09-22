import {
    mockCreateChannelSettings,
    mockFetchMessages,
    mockFetchUnreadCount,
    mockFetchUserChannels,
    mockFetchUserSettings,
    mockMarkMessagesAsRead,
    mockMarkMessageAsRead,
    mockUpdateChannelSettings,
    pushMockNotification,
    subscribeMockNotifications,
} from "./notificationsMock";
import { getAccessToken } from "../utils/tokenStorage";
import { createMessageServiceSocket } from "./messageServiceWs";
import { parseMarkReadPayload, parseUnreadCountPayload } from "../utils/notificationLogic";

const MODE = (
    process.env.REACT_APP_NOTIFICATIONS_MODE
    || (process.env.NODE_ENV === "test" ? "mock" : "message-service")
).toLowerCase();
const isDev = process.env.NODE_ENV === "development";
const WS_ENABLED = String(process.env.REACT_APP_MESSAGE_SERVICE_WS_ENABLED || "true").toLowerCase() !== "false";

export const NOTIFICATIONS_MODE = MODE;

export function messageServiceBaseURL() {
    if (isDev) return "/message-service";
    const raw = (process.env.REACT_APP_MESSAGE_SERVICE_URL || "").replace(/\/$/, "");
    return raw || "/message-service";
}

function messageServiceWsBaseCandidates() {
    const explicit = (process.env.REACT_APP_MESSAGE_SERVICE_WS_URL || "").trim();
    if (explicit) return [explicit];
    const base = messageServiceBaseURL();
    // Fallback to same-host `/api/ws` for envs where `/message-service` isn't
    // websocket-proxied but REST `/message-service/api` still works.
    if (base === "/message-service") {
        return [base, "/"];
    }
    return [base];
}

function buildMessageServiceUrl(path, params = {}) {
    const base = messageServiceBaseURL();
    const prefix = path.startsWith("/") ? path : `/${path}`;
    const url = new URL(`${base}/api${prefix}`, window.location.origin);
    Object.entries(params || {}).forEach(([key, value]) => {
        if (value == null || value === "") return;
        url.searchParams.set(key, String(value));
    });
    return url.toString();
}

async function msRequest(path, { method = "GET", params = {}, body, signal } = {}) {
    const token = getAccessToken();
    if (!token) throw new Error("Не найден access token для message-service");
    const res = await fetch(buildMessageServiceUrl(path, params), {
        method,
        headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
        },
        body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
        mode: "cors",
        cache: "no-store",
        signal,
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
    if (!res.ok) {
        const detail = data?.detail || data?.message || text || res.statusText;
        throw new Error(String(detail));
    }
    return data;
}

export async function fetchUnreadCount({ signal } = {}) {
    if (MODE === "mock") {
        return parseUnreadCountPayload(await mockFetchUnreadCount());
    }
    return parseUnreadCountPayload(await msRequest("/messages/unread-count", { signal }));
}

export async function fetchMessages(params = {}, { signal } = {}) {
    if (MODE === "mock") {
        return mockFetchMessages(params);
    }
    const data = await msRequest("/messages", { params, signal });
    return Array.isArray(data) ? data : [];
}

export async function markMessagesAsRead(params = {}, { signal } = {}) {
    if (MODE === "mock") {
        return parseMarkReadPayload(await mockMarkMessagesAsRead(params));
    }
    const data = await msRequest("/messages/read", { method: "POST", params, signal });
    return parseMarkReadPayload(data);
}

export async function markMessageAsRead(messageId, { signal } = {}) {
    const id = Number(messageId);
    if (!Number.isFinite(id) || id <= 0) throw new Error("Некорректный идентификатор уведомления");
    if (MODE === "mock") return mockMarkMessageAsRead(id);
    return msRequest(`/messages/${id}`, { method: "PUT", body: { is_read: true }, signal });
}

export async function fetchVapidPublicKey({ signal } = {}) {
    if (MODE === "mock") return { enabled: false, public_key: "" };
    return msRequest("/push/vapid-public-key", { signal });
}

export async function savePushSubscription(body, { signal } = {}) {
    if (MODE === "mock") return null;
    return msRequest("/push/subscriptions", { method: "POST", body, signal });
}

export async function deletePushSubscription(body, { signal } = {}) {
    if (MODE === "mock") return null;
    return msRequest("/push/subscriptions", { method: "DELETE", body, signal });
}

/**
 * Temporary no-op in message-service mode:
 * this frontend iteration supports personal notifications only.
 */
export async function fetchUserChannels(params = {}, { signal } = {}) {
    if (MODE === "mock") {
        return mockFetchUserChannels();
    }
    const data = await msRequest("/channels/push", { params, signal });
    return Array.isArray(data) ? data : [];
}

/**
 * Temporary no-op in message-service mode:
 * this frontend iteration supports personal notifications only.
 */
export async function fetchUserSettings({ signal } = {}) {
    if (MODE === "mock") {
        return mockFetchUserSettings();
    }
    const data = await msRequest("/settings/user", { signal });
    return Array.isArray(data) ? data : [];
}

export async function createChannelSettings(body, { signal } = {}) {
    if (MODE === "mock") {
        return mockCreateChannelSettings(body);
    }
    return msRequest("/settings", { method: "POST", body, signal });
}

export async function updateChannelSettings(id, body, { signal } = {}) {
    if (MODE === "mock") {
        return mockUpdateChannelSettings(id, body);
    }
    return msRequest(`/settings/${Number(id)}`, { method: "PUT", body, signal });
}

const listeners = new Set();
const socket = createMessageServiceSocket({
    getToken: () => getAccessToken() || "",
    getBaseURL: () => messageServiceBaseURL(),
    getBaseCandidates: () => messageServiceWsBaseCandidates(),
    onNotification: (payload) => {
        listeners.forEach((cb) => {
            try {
                cb(payload);
            } catch {
                // ignore listener errors
            }
        });
    },
});

/**
 * Realtime subscription.
 * `message-service` mode: WS `/message-service/api/ws?token=...`
 * `mock` mode: in-memory pub/sub.
 */
export function subscribeNotifications(onNotification) {
    if (typeof onNotification !== "function") return () => {};
    if (MODE === "mock") {
        return subscribeMockNotifications(onNotification);
    }
    if (!WS_ENABLED) {
        return () => {};
    }
    listeners.add(onNotification);
    if (listeners.size === 1) socket.connect();
    return () => {
        listeners.delete(onNotification);
        if (listeners.size === 0) socket.disconnect();
    };
}

/** Dev/demo helper — enabled only in mock mode. */
export function emitDemoNotification(partial) {
    if (MODE !== "mock") return null;
    return pushMockNotification(partial);
}
